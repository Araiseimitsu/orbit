"""
ORBIT MVP - FastAPI Application Entry Point
"""

import asyncio
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# ========== 環境変数読み込み（最優先） ==========
from dotenv import load_dotenv

# プロジェクトルートの.envを読み込み
BASE_DIR_ENV = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR_ENV / ".env")
# ===============================================

from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# アクション登録（インポート時に自動登録）
from . import actions  # noqa: F401
from .core.backup import BackupManager
from .core.executor import Executor
from .core.loader import WorkflowLoader
from .core.models import RunLog, Workflow
from .core.registry import get_registry
from .core.run_logger import RunLogger
from .core.run_manager import RunManager
from .core.scheduler import WorkflowScheduler
from .ai_flow import generate_ai_flow

# ログ設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ディレクトリ設定
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKFLOWS_DIR = BASE_DIR / "workflows"
RUNS_DIR = BASE_DIR / "runs"
BACKUPS_DIR = BASE_DIR / "backups"
TEMPLATES_DIR = Path(__file__).resolve().parent / "ui" / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "ui" / "static"

# Jinja2 テンプレート設定
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
STATIC_VERSION = str(int(time.time()))


def static_mtime(path: str) -> str:
    """静的ファイルの更新時刻をキャッシュバスターに利用"""
    try:
        return str(int((STATIC_DIR / path).stat().st_mtime))
    except FileNotFoundError:
        return STATIC_VERSION


def tojson_utf8(value, indent: int = 2) -> str:
    """日本語をエスケープせずにJSON表示するテンプレートフィルタ"""
    return json.dumps(value, ensure_ascii=False, indent=indent)


templates.env.filters["tojson_utf8"] = tojson_utf8
templates.env.globals["static_version"] = STATIC_VERSION
templates.env.globals["static_mtime"] = static_mtime

# コンポーネント初期化
loader = WorkflowLoader(WORKFLOWS_DIR)
executor = Executor(BASE_DIR)
run_logger = RunLogger(RUNS_DIR)
run_manager = RunManager()
backup_manager = BackupManager(BACKUPS_DIR, max_backups=10)
workflow_scheduler = WorkflowScheduler(loader, executor, run_logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: スケジューラーの起動/停止を管理"""
    # 起動時: スケジューラー開始
    logger.info("Starting ORBIT application...")

    # ログローテーション実行
    cleanup_result = run_logger.cleanup(retention_days=3)
    logger.info(f"Log cleanup: {cleanup_result['deleted_count']} old files removed")

    workflow_scheduler.start()
    registered = workflow_scheduler.register_workflows()
    logger.info(f"Scheduler ready: {registered} workflows registered")
    try:
        workflow_scheduler.scheduler.add_job(
            run_logger.cleanup,
            trigger=CronTrigger.from_crontab(
                "0 3 * * *", timezone=ZoneInfo("Asia/Tokyo")
            ),
            kwargs={"retention_days": 3},
            id="log_cleanup",
            name="Log Cleanup",
            replace_existing=True,
        )
        logger.info("Scheduled daily log cleanup (03:00 JST)")
    except Exception as e:
        logger.warning(f"Failed to schedule log cleanup: {e}")

    yield

    # 停止時: スケジューラー停止
    logger.info("Shutting down ORBIT application...")
    workflow_scheduler.stop()


# FastAPI アプリケーション（lifespanを設定）
app = FastAPI(
    title="ORBIT",
    description="n8nライクなワークフロー実行アプリ（MVP）",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_flow_editor_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in ("/static/flow-editor.js", "/static/flow-editor.css"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def build_editor_data(workflow: Workflow | None) -> dict:
    """ビジュアルエディタ向けのデータを構築"""
    if not workflow:
        return {
            "name": "",
            "description": "",
            "folder": "",
            "enabled": True,
            "trigger": {"type": "manual"},
            "steps": [],
        }

    steps = []
    for index, step in enumerate(workflow.steps):
        meta = step.meta or {}
        steps.append(
            {
                "id": step.id,
                "type": step.type,
                "params": step.params,
                "when": step.when.model_dump(exclude_defaults=True)
                if step.when
                else None,
                "position": {
                    "x": int(meta.get("x", 80)),
                    "y": int(meta.get("y", 80 + index * 120)),
                },
            }
        )

    trigger_data: dict[str, str] = {"type": workflow.trigger.type}
    if workflow.trigger.type == "schedule":
        trigger_data["cron"] = workflow.trigger.cron

    return {
        "name": workflow.name,
        "description": workflow.description or "",
        "folder": workflow.folder or "",
        "enabled": workflow.enabled,
        "trigger": trigger_data,
        "steps": steps,
    }


def build_error_run(workflow_name: str, message: str) -> RunLog:
    """エラー用の簡易RunLogを生成"""
    now = datetime.now().isoformat()
    return RunLog(
        workflow=workflow_name,
        run_id=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[-4:]}",
        status="failed",
        started_at=now,
        ended_at=now,
        error=message,
        steps=[],
    )


@app.get("/health")
async def health_check():
    """
    ヘルスチェックエンドポイント

    Returns:
        スケジューラ状態、登録ジョブ数、直近実行状況
    """
    # スケジューラ状態
    scheduler_running = workflow_scheduler.scheduler.running

    # 登録ジョブ数
    scheduled_jobs = workflow_scheduler.get_scheduled_jobs()
    workflow_jobs = [
        job for job in scheduled_jobs if job.get("id", "").startswith("workflow_")
    ]
    job_count = len(workflow_jobs)

    # 直近実行状況（最新5件）
    recent_runs = run_logger.get_all_runs(limit=5)
    recent_status = [
        {
            "workflow": run.workflow,
            "status": run.status,
            "started_at": run.started_at,
        }
        for run in recent_runs
    ]

    # ワークフロー統計
    workflows = loader.list_workflows()
    valid_count = sum(1 for wf in workflows if wf.is_valid)
    error_count = sum(1 for wf in workflows if not wf.is_valid)

    return {
        "status": "healthy" if scheduler_running else "degraded",
        "timestamp": datetime.now().isoformat(),
        "scheduler": {
            "running": scheduler_running,
            "job_count": job_count,
            "jobs": workflow_jobs,
        },
        "workflows": {
            "total": len(workflows),
            "valid": valid_count,
            "error": error_count,
        },
        "recent_runs": recent_status,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, q: str | None = None):
    """ダッシュボード - ワークフロー一覧"""
    start_time = time.perf_counter()
    workflows = loader.list_workflows()
    list_elapsed = time.perf_counter() - start_time
    query = (q or "").strip()

    # 最新実行ステータスを反映
    valid_names = {wf.name for wf in workflows if wf.is_valid and wf.name}
    latest_map = run_logger.get_latest_runs_map(valid_names)
    status_map = {"success": "成功", "failed": "失敗", "running": "実行中", "stopped": "停止"}
    for wf in workflows:
        if not wf.is_valid or not wf.name:
            continue
        latest = latest_map.get(wf.name)
        if latest:
            wf.status = status_map.get(latest.status, latest.status)
            wf.last_run = latest.started_at
    status_elapsed = time.perf_counter() - start_time
    logger.info("Dashboard load: workflows=%d valid=%d list=%.3fs status=%.3fs", len(workflows), len(valid_names), list_elapsed, status_elapsed)

    if query:
        lowered = query.lower()
        workflows = [
            wf
            for wf in workflows
            if (wf.name or "").lower().find(lowered) != -1
            or (wf.folder or "").lower().find(lowered) != -1
        ]

    def normalize_folder(value: str | None) -> str:
        label = (value or "").strip()
        return label if label else "未分類"

    grouped = {}
    for wf in workflows:
        label = normalize_folder(wf.folder)
        grouped.setdefault(label, []).append(wf)

    ordered_labels = sorted(
        grouped.keys(), key=lambda label: (label != "未分類", label.lower())
    )
    workflow_groups = [
        {
            "name": label,
            "workflows": grouped[label],
            "count": len(grouped[label]),
        }
        for label in ordered_labels
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "workflows": workflows,
            "workflow_groups": workflow_groups,
            "search_query": query,
        },
    )


@app.get("/workflows/{name}", response_class=HTMLResponse)
async def workflow_detail(request: Request, name: str, page: int = 1):
    """ワークフロー詳細画面"""
    workflow, error = loader.load_workflow(name)
    yaml_content = loader.get_yaml_content(name)

    # ページネーションパラメータ
    per_page = 50
    offset = (page - 1) * per_page

    # 実行履歴を取得
    runs = run_logger.get_runs_for_workflow(name, limit=per_page, offset=offset)
    total_runs = run_logger.count_runs_for_workflow(name)
    total_pages = (total_runs + per_page - 1) // per_page  # 切り上げ

    # 次回実行予定を取得
    next_run = None
    if workflow and workflow.trigger.type == "schedule":
        jobs = workflow_scheduler.get_scheduled_jobs()
        for job in jobs:
            if job["id"] == f"workflow_{name}":
                next_run = job.get("next_run")
                break

    return templates.TemplateResponse(
        "workflow_detail.html",
        {
            "request": request,
            "name": name,
            "yaml_content": yaml_content,
            "workflow": workflow,
            "error": error,
            "runs": runs,
            "next_run": next_run,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_runs,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
            },
        },
    )


@app.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, workflow: str | None = None, page: int = 1):
    """実行履歴一覧"""
    # ページネーションパラメータ
    per_page = 50
    offset = (page - 1) * per_page

    # 空文字列の場合はNoneに変換
    if workflow is not None and workflow.strip() == "":
        workflow = None

    workflows = loader.list_workflows()
    workflow_options = sorted({wf.name for wf in workflows if wf.name})
    if workflow and workflow not in workflow_options:
        workflow_options = [workflow, *workflow_options]
    def normalize_folder(value: str | None) -> str:
        label = (value or "").strip()
        return label if label else "未分類"
    workflow_folders = {
        wf.name: normalize_folder(wf.folder)
        for wf in workflows
        if wf.name
    }
    runs = run_logger.get_all_runs(
        limit=per_page, offset=offset, workflow_filter=workflow
    )
    total_runs = run_logger.count_all_runs(workflow_filter=workflow)
    total_pages = (total_runs + per_page - 1) // per_page  # 切り上げ

    return templates.TemplateResponse(
        "runs.html",
        {
            "request": request,
            "runs": runs,
            "workflow_filter": workflow,
            "workflow_options": workflow_options,
            "workflow_folders": workflow_folders,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_runs,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
            },
        },
    )


@app.get("/workflows/new", response_class=HTMLResponse)
async def workflow_new(request: Request):
    """ワークフロー新規作成（テンプレート選択）"""
    # テンプレート一覧を取得
    templates = []
    templates_dir = WORKFLOWS_DIR / "templates"
    if templates_dir.exists():
        for yaml_file in templates_dir.glob("*.yaml"):
            workflow, error = loader.load_workflow(yaml_file.stem, templates_dir=True)
            if workflow:
                templates.append(
                    {
                        "name": yaml_file.stem,
                        "title": workflow.name,
                        "description": workflow.description or "",
                        "filename": yaml_file.name,
                    }
                )

    return templates.TemplateResponse(
        "new_workflow.html",
        {"request": request, "templates": templates},
    )


@app.get("/workflows/new/visual", response_class=HTMLResponse)
async def workflow_new_visual(request: Request):
    """ビジュアルエディタ（新規作成）"""
    actions = sorted(get_registry().list_actions())
    editor_data = build_editor_data(None)
    config_json = json.dumps(
        {
            "workflow": editor_data,
            "actions": actions,
            "mode": "new",
            "saveUrl": "/api/workflows/save",
            "aiUrl": "/api/ai/flow",
        },
        ensure_ascii=False,
    )
    return templates.TemplateResponse(
        "flow_editor.html",
        {
            "request": request,
            "config_json": config_json,
            "error": None,
            "page_title": "ビジュアルエディタ（新規作成）",
            "static_version": str(int(__import__("time").time())),
        },
    )


@app.get("/workflows/{name}/edit", response_class=HTMLResponse)
async def workflow_edit(request: Request, name: str):
    """ビジュアルエディタ（編集）"""
    workflow, error = loader.load_workflow(name)
    actions = sorted(get_registry().list_actions())
    editor_data = build_editor_data(workflow)
    if not workflow:
        editor_data["name"] = name
    config_json = json.dumps(
        {
            "workflow": editor_data,
            "actions": actions,
            "mode": "edit",
            "saveUrl": "/api/workflows/save",
            "aiUrl": "/api/ai/flow",
        },
        ensure_ascii=False,
    )
    return templates.TemplateResponse(
        "flow_editor.html",
        {
            "request": request,
            "config_json": config_json,
            "error": error,
            "page_title": f"ビジュアルエディタ - {name}",
            "static_version": str(int(__import__("time").time())),
        },
    )


@app.get("/workflows/new/from-template/{template_name}")
async def workflow_from_template(request: Request, template_name: str):
    """テンプレートからワークフローを作成"""
    workflow, error = loader.load_workflow(template_name, templates_dir=True)
    if error or not workflow:
        raise HTTPException(
            status_code=400, detail=f"テンプレートの読み込みに失敗: {error}"
        )

    actions = sorted(get_registry().list_actions())
    editor_data = build_editor_data(workflow)
    config_json = json.dumps(
        {
            "workflow": editor_data,
            "actions": actions,
            "mode": "new",
            "saveUrl": "/api/workflows/save",
            "aiUrl": "/api/ai/flow",
        },
        ensure_ascii=False,
    )
    return templates.TemplateResponse(
        "flow_editor.html",
        {
            "request": request,
            "config_json": config_json,
            "error": None,
            "page_title": f"テンプレートから作成 - {workflow.name}",
            "static_version": str(int(__import__("time").time())),
        },
    )


@app.post("/api/workflows/{name}/run", response_class=HTMLResponse)
async def run_workflow(request: Request, name: str):
    """
    ワークフローを手動実行（HTMX用）

    成功時: トースト通知用のHTMLを返す
    失敗時: エラー表示用のHTMLを返す
    """
    safe_name = (name or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="ワークフロー名が必要です")
    if any(token in safe_name for token in ["/", "\\", ".."]):
        raise HTTPException(
            status_code=400, detail="ワークフロー名に使用できない文字があります"
        )

    if await run_manager.is_running(safe_name):
        error_run = build_error_run(
            safe_name,
            "すでに実行中です。停止ボタンで中断できます。",
        )
        return templates.TemplateResponse(
            "partials/run_result.html",
            {"request": request, "run": error_run, "workflow_name": safe_name},
        )

    try:
        payload = {}
        try:
            payload = await request.json()
        except Exception:
            if request.headers.get("content-type", "").startswith(
                "application/x-www-form-urlencoded"
            ):
                form = await request.form()
                payload = dict(form)

        prompt = (payload.get("prompt") or "").strip()

        workflow, error = loader.load_workflow(safe_name)

        if error or not workflow:
            error_run = build_error_run(
                safe_name,
                error or "Workflow not found",
            )
            return templates.TemplateResponse(
                "partials/run_result.html",
                {"request": request, "run": error_run, "workflow_name": safe_name},
            )

        if prompt and workflow.steps:
            first_step = workflow.steps[0]
            if first_step.type == "ai_generate":
                first_step.params = dict(first_step.params or {})
                first_step.params["prompt"] = prompt

        task = asyncio.create_task(executor.run(workflow))
        registered = await run_manager.register(safe_name, task)
        if not registered:
            task.cancel()
            error_run = build_error_run(
                safe_name,
                "すでに実行中です。停止ボタンで中断できます。",
            )
            return templates.TemplateResponse(
                "partials/run_result.html",
                {"request": request, "run": error_run, "workflow_name": safe_name},
            )

        try:
            run_log = await task
        finally:
            await run_manager.unregister(safe_name)

        run_logger.save(run_log)

        logger.info(
            f"Returning run_log: run_id={run_log.run_id}, status={run_log.status}, workflow={run_log.workflow}"
        )

        return templates.TemplateResponse(
            "partials/run_result.html",
            {"request": request, "run": run_log, "workflow_name": safe_name},
        )

    except Exception as e:
        logger.exception(f"Unexpected error running workflow {safe_name}")
        error_run = build_error_run(
            safe_name,
            f"{type(e).__name__}: {str(e)}",
        )
        return templates.TemplateResponse(
            "partials/run_result.html",
            {"request": request, "run": error_run, "workflow_name": safe_name},
        )


@app.post("/api/workflows/{name}/stop")
async def stop_workflow(name: str):
    """実行中ワークフローを停止"""
    safe_name = (name or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="ワークフロー名が必要です")
    if any(token in safe_name for token in ["/", "\\", ".."]):
        raise HTTPException(
            status_code=400, detail="ワークフロー名に使用できない文字があります"
        )

    cancelled = await run_manager.cancel(safe_name)
    if not cancelled:
        # run直後にstopした場合の競合を避けるため、短時間だけ再試行
        for _ in range(10):
            await asyncio.sleep(0.1)
            cancelled = await run_manager.cancel(safe_name)
            if cancelled:
                break
    if not cancelled:
        raise HTTPException(status_code=404, detail="実行中のワークフローがありません")

    logger.info(f"Stop requested for workflow: {safe_name}")
    return {"ok": True, "name": safe_name, "status": "stopping"}


@app.get("/api/actions")
async def list_actions():
    """登録済みアクション一覧（UI用）"""
    registry = get_registry()
    actions = sorted(registry.list_actions())

    # メタデータも含めて返す
    metadata = {}
    for action_type in actions:
        meta = registry.get_metadata(action_type)
        if meta:
            metadata[action_type] = meta.dict()

    return {"actions": actions, "metadata": metadata}


@app.get("/api/workflows")
async def list_workflows_api():
    """ワークフロー一覧取得（UI用、subworkflowドロップダウン用）"""
    workflows = loader.list_workflows()
    # 有効なワークフローのみ返す
    workflow_names = [wf.name for wf in workflows if wf.is_valid]
    return {"workflows": workflow_names}


@app.post("/api/ai/flow")
async def build_flow_with_ai(request: Request):
    """AI でワークフロー案を生成"""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="無効なリクエスト形式です")

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt が必要です")

    current_workflow = payload.get("current_workflow")
    if current_workflow is not None and not isinstance(current_workflow, dict):
        current_workflow = None
    use_search = payload.get("use_search")
    if not isinstance(use_search, bool):
        use_search = True

    try:
        result = generate_ai_flow(
            prompt,
            get_registry(),
            BASE_DIR,
            current_workflow,
            use_search=use_search,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("AI flow generation failed")
        raise HTTPException(
            status_code=500, detail="AI フロー生成に失敗しました"
        ) from exc

    return result


@app.post("/api/ai/expression")
async def build_expression_with_ai(request: Request):
    """AIでJinja2テンプレート式を生成"""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="無効なリクエスト形式です")

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt が必要です")

    param_key = (payload.get("param_key") or "").strip()
    step_type = (payload.get("step_type") or "").strip()
    raw_context = payload.get("context")
    context = raw_context if isinstance(raw_context, dict) else {}

    default_available_vars = [
        "run_id",
        "now",
        "today",
        "yesterday",
        "tomorrow",
        "today_ymd",
        "now_ymd_hms",
        "workflow",
        "base_dir",
    ]
    available_vars_raw = context.get("available_vars")
    available_vars: list[str] = []
    if isinstance(available_vars_raw, list):
        for item in available_vars_raw:
            if isinstance(item, str) and item.strip():
                available_vars.append(item.strip())
    if not available_vars:
        available_vars = default_available_vars

    previous_steps_raw = context.get("previous_steps")
    previous_steps: list[dict[str, Any]] = []
    if isinstance(previous_steps_raw, list):
        for item in previous_steps_raw:
            if not isinstance(item, dict):
                continue
            step_id = str(item.get("id") or "").strip()
            step_type_name = str(item.get("type") or "").strip()
            outputs_raw = item.get("outputs")
            outputs: list[str] = []
            if isinstance(outputs_raw, list):
                for output_key in outputs_raw:
                    if isinstance(output_key, str) and output_key.strip():
                        outputs.append(output_key.strip())
            if step_id:
                previous_steps.append(
                    {"id": step_id, "type": step_type_name, "outputs": outputs}
                )

    available_filters = [
        "int",
        "float",
        "string",
        "default",
        "replace",
        "lower",
        "upper",
        "title",
        "trim",
        "length",
        "join",
        "first",
        "last",
        "round",
        "abs",
        "tojson_utf8",
        "fromjson",
    ]

    prev_lines = []
    for prev in previous_steps:
        outputs = prev.get("outputs") or []
        outputs_text = ", ".join(outputs) if outputs else "(出力キー不明)"
        prev_lines.append(f"- {prev['id']} ({prev.get('type') or 'unknown'}): {outputs_text}")
    previous_steps_text = "\n".join(prev_lines) if prev_lines else "- なし"

    system_prompt = (
        "あなたは ORBIT 専用のJinja2式生成アシスタントです。\n"
        "このプロジェクトで実際に使える構文のみ提案してください。\n"
        "回答は必ず {{ ... }} 形式の式1つのみ。説明文・前置き・コードフェンスは禁止。\n\n"
        "## 現在のコンテキスト\n"
        f"- 対象ステップタイプ: {step_type or '(不明)'}\n"
        f"- 対象パラメータ: {param_key or '(不明)'}\n\n"
        "## 利用可能な共通変数\n"
        + "\n".join(f"- {var}" for var in available_vars)
        + "\n\n"
        "## 前ステップ参照（利用可能な場合）\n"
        f"{previous_steps_text}\n"
        "参照形式は {{ step_id.output_key }}。\n\n"
        "## 利用可能フィルター（主要）\n"
        + "\n".join(f"- {flt}" for flt in available_filters)
        + "\n\n"
        "## 厳守ルール\n"
        "- 未定義の関数・フィルター・変数を使わない。\n"
        "- Pythonコードやimport、関数定義を書かない。\n"
        "- 1つの式のみ返す。\n"
    )

    user_prompt_text = (
        f"ユーザー要望: {prompt}\n"
        f"対象パラメータ: {param_key or '(不明)'}\n"
        "上記要望を満たす、実行可能な式を1つだけ返してください。"
    )

    def extract_first_expression_candidate(raw_text: str) -> str | None:
        cleaned = (raw_text or "").strip()
        if not cleaned:
            return None

        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:jinja|jinja2|text|json)?", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        matches = re.findall(r"\{\{[\s\S]*?\}\}", cleaned)
        if matches:
            return matches[0].strip()

        # 式本体のみ（{{ }} なし）で返された場合に備えて、簡易候補を抽出
        for line in cleaned.splitlines():
            candidate = line.strip().strip("`").strip()
            if not candidate:
                continue
            if candidate.startswith("- "):
                candidate = candidate[2:].strip()
            if candidate.startswith("{{") and candidate.endswith("}}"):
                return candidate
            if re.search(r"(run_id|now|today|yesterday|tomorrow|today_ymd|now_ymd_hms|workflow|base_dir|\w+\.\w+)", candidate):
                return f"{{{{ {candidate} }}}}"
        return None

    def validate_expression(expression: str) -> tuple[bool, str | None]:
        text = (expression or "").strip()
        if not text:
            return False, "式が空です"
        if not (text.startswith("{{") and text.endswith("}}")):
            return False, "{{ ... }} 形式ではありません"

        expr = text[2:-2].strip()
        if not expr:
            return False, "式本体が空です"

        allowed_roots = set(available_vars)
        allowed_roots.update(prev["id"] for prev in previous_steps if prev.get("id"))
        allowed_filters_set = set(available_filters)
        keywords = {
            "true",
            "false",
            "none",
            "and",
            "or",
            "not",
            "in",
            "is",
            "if",
            "else",
        }
        root_tokens = re.findall(r"(?<!\.)\b([A-Za-z_][A-Za-z0-9_]*)\b", expr)
        for token in root_tokens:
            token_lower = token.lower()
            if token_lower in keywords:
                continue
            if token in allowed_roots:
                continue
            if token in allowed_filters_set:
                continue
            return False, f"未サポートの識別子: {token}"

        if re.search(r"(?<![\.\|])\b[A-Za-z_][A-Za-z0-9_]*\s*\(", expr):
            return False, "関数呼び出し形式はサポート外です"

        try:
            from .core.templating import _env

            _env.compile_expression(expr)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def fallback_expression(user_prompt: str) -> str:
        prompt_lower = (user_prompt or "").lower()
        prompt_text = (user_prompt or "")

        if (
            "日部分" in prompt_text
            or "日だけ" in prompt_text
            or "day" in prompt_lower
            or "先頭0なし" in prompt_text
        ):
            return "{{ today_ymd[-2:] | int }}"
        if "yyyymmdd" in prompt_lower:
            return "{{ today_ymd }}"
        if "現在時刻" in prompt_text or "timestamp" in prompt_lower or "時刻" in prompt_text:
            return "{{ now_ymd_hms }}"
        if "昨日" in prompt_text:
            return "{{ yesterday }}"
        if "明日" in prompt_text:
            return "{{ tomorrow }}"
        if "今日" in prompt_text or "日付" in prompt_text or "date" in prompt_lower:
            return "{{ today }}"

        for prev in reversed(previous_steps):
            outputs = prev.get("outputs") or []
            if outputs:
                return f"{{{{ {prev['id']}.{outputs[0]} }}}}"

        return "{{ today }}"

    try:
        from .actions.ai import (
            DEFAULT_GEMINI_KEY_FILE,
            DEFAULT_GEMINI_KEY_ENV,
            _load_api_key,
        )
        from .ai_flow import (
            DEFAULT_MODEL,
            DEFAULT_MAX_TOKENS,
            DEFAULT_TEMPERATURE,
            _call_gemini_rest,
        )

        api_key = _load_api_key(
            DEFAULT_GEMINI_KEY_FILE, BASE_DIR, DEFAULT_GEMINI_KEY_ENV
        )
        result = _call_gemini_rest(
            prompt=user_prompt_text,
            model=DEFAULT_MODEL,
            api_key=api_key,
            system=system_prompt,
            max_tokens=200,
            temperature=0.3,
            use_search=False,
        )

        raw_text = result.get("text", "")
        expression = extract_first_expression_candidate(raw_text) or ""
        valid, reason = validate_expression(expression)

        if not valid:
            fallback = fallback_expression(prompt)
            logger.warning(
                "AI expression invalid, fallback used: reason=%s raw=%s fallback=%s",
                reason,
                (raw_text or "")[:300],
                fallback,
            )
            expression = fallback

        return {"expression": expression}

    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("AI expression generation failed")
        raise HTTPException(status_code=500, detail="式の生成に失敗しました") from exc


@app.post("/api/ai/params")
async def build_params_with_ai(request: Request):
    """AIでステップパラメータ全体を生成"""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="無効なリクエスト形式です")

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt が必要です")

    step_type = (payload.get("step_type") or "").strip()
    if not step_type:
        raise HTTPException(status_code=400, detail="step_type が必要です")

    previous_steps = payload.get("previous_steps")

    try:
        from .ai_flow import generate_ai_params

        result = generate_ai_params(
            prompt,
            step_type,
            get_registry(),
            BASE_DIR,
            previous_steps,
        )
        return result

    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("AI params generation failed")
        raise HTTPException(
            status_code=500, detail="パラメータの生成に失敗しました"
        ) from exc


@app.post("/api/workflows/save")
async def save_workflow(request: Request):
    """ビジュアルエディタからワークフローを保存"""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="無効なリクエスト形式です")

    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="ワークフロー名が必要です")
    if any(token in name for token in ["/", "\\", ".."]):
        raise HTTPException(
            status_code=400, detail="ワークフロー名に使用できない文字があります"
        )

    trigger = payload.get("trigger") or {"type": "manual"}
    if not isinstance(trigger, dict) or not trigger.get("type"):
        raise HTTPException(status_code=400, detail="トリガー設定が不正です")
    if trigger.get("type") == "manual":
        trigger = {"type": "manual"}
    elif trigger.get("type") == "schedule":
        cron = (trigger.get("cron") or "").strip()
        if not cron:
            raise HTTPException(status_code=400, detail="schedule の cron が必要です")
        try:
            CronTrigger.from_crontab(cron, timezone=ZoneInfo("Asia/Tokyo"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"cron が不正です: {e}") from e
        trigger = {"type": "schedule", "cron": cron}
    else:
        raise HTTPException(status_code=400, detail="未対応のトリガーです")
    steps = payload.get("steps") or []
    description = payload.get("description") or None
    folder_raw = payload.get("folder")
    folder = None
    if folder_raw is not None:
        if not isinstance(folder_raw, str):
            raise HTTPException(
                status_code=400, detail="folder は文字列で指定してください"
            )
        folder = folder_raw.strip() or None
    enabled = payload.get("enabled", True)
    if not isinstance(enabled, bool):
        raise HTTPException(
            status_code=400, detail="enabled は true/false で指定してください"
        )

    if not isinstance(steps, list) or len(steps) == 0:
        raise HTTPException(status_code=400, detail="少なくとも1つのステップが必要です")

    normalized_steps = []
    step_ids = set()
    for step in steps:
        if not isinstance(step, dict):
            raise HTTPException(
                status_code=400, detail="ステップ形式が正しくありません"
            )
        step_id = (step.get("id") or "").strip()
        step_type = (step.get("type") or "").strip()
        if not step_id or not step_type:
            raise HTTPException(status_code=400, detail="ステップIDとタイプは必須です")
        if step_id in step_ids:
            raise HTTPException(status_code=400, detail="ステップIDが重複しています")
        step_ids.add(step_id)

        params = step.get("params") or {}
        when = step.get("when")
        normalized_when = None
        if when is not None:
            if not isinstance(when, dict):
                raise HTTPException(
                    status_code=400, detail="条件の形式が正しくありません"
                )
            when_step = (when.get("step") or "").strip()
            if not when_step:
                raise HTTPException(status_code=400, detail="条件の step が必要です")
            field = (when.get("field") or "text").strip()
            if not field:
                field = "text"
            if "equals" not in when:
                raise HTTPException(status_code=400, detail="条件の equals が必要です")
            equals = when.get("equals")
            if isinstance(equals, str) and equals.strip() == "":
                raise HTTPException(status_code=400, detail="条件の equals が必要です")
            normalized_when = {
                "step": when_step,
                "field": field,
                "equals": equals,
            }
            match = when.get("match")
            if match is not None:
                if not isinstance(match, str):
                    raise HTTPException(
                        status_code=400,
                        detail="条件の match は文字列で指定してください",
                    )
                match_value = match.strip().lower()
                if match_value not in ("equals", "contains"):
                    raise HTTPException(
                        status_code=400,
                        detail="条件の match は equals / contains のみ対応です",
                    )
                normalized_when["match"] = match_value
            if isinstance(when.get("trim"), bool):
                normalized_when["trim"] = when["trim"]
            if isinstance(when.get("case_insensitive"), bool):
                normalized_when["case_insensitive"] = when["case_insensitive"]
        position = step.get("position") or {}
        meta = {
            "x": int(position.get("x", 0)),
            "y": int(position.get("y", 0)),
        }
        step_data = {
            "id": step_id,
            "type": step_type,
            "params": params,
            "meta": meta,
        }
        if normalized_when is not None:
            step_data["when"] = normalized_when
        normalized_steps.append(step_data)

    workflow_data = {
        "name": name,
        "description": description,
        "folder": folder,
        "enabled": enabled,
        "trigger": trigger,
        "steps": normalized_steps,
    }

    try:
        workflow = Workflow.model_validate(workflow_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"バリデーションエラー: {e}") from e

    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = WORKFLOWS_DIR / f"{workflow.name}.yaml"

    import yaml

    # 既存のワークフローがあればバックアップ
    if yaml_path.exists():
        existing_content = yaml_path.read_text(encoding="utf-8")
        backup_manager.backup_workflow(workflow.name, existing_content)

    yaml_content = yaml.safe_dump(
        workflow.model_dump(exclude_none=True), sort_keys=False, allow_unicode=True
    )
    yaml_path.write_text(yaml_content, encoding="utf-8")
    workflow_scheduler.reload_workflows()

    return {"ok": True, "name": workflow.name, "path": str(yaml_path)}


@app.post("/api/workflows/{name}/toggle")
async def toggle_workflow(name: str, request: Request):
    """ワークフローの有効/無効を切り替え"""
    safe_name = (name or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="ワークフロー名が必要です")
    if any(token in safe_name for token in ["/", "\\", ".."]):
        raise HTTPException(
            status_code=400, detail="ワークフロー名に使用できない文字があります"
        )

    payload = await request.json()
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(
            status_code=400, detail="enabled は true/false で指定してください"
        )

    yaml_path = WORKFLOWS_DIR / f"{safe_name}.yaml"
    yml_path = WORKFLOWS_DIR / f"{safe_name}.yml"
    target = (
        yaml_path if yaml_path.exists() else yml_path if yml_path.exists() else None
    )
    if not target or not target.exists():
        raise HTTPException(status_code=404, detail="ワークフローが見つかりません")

    import yaml

    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="ワークフロー定義が不正です")
    data["enabled"] = enabled

    try:
        _ = Workflow.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"バリデーションエラー: {e}") from e

    yaml_content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    target.write_text(yaml_content, encoding="utf-8")
    workflow_scheduler.reload_workflows()
    return {"ok": True, "name": safe_name, "enabled": enabled}


@app.post("/api/workflows/{name}/delete")
async def delete_workflow(name: str):
    """ワークフローを削除"""
    safe_name = (name or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="ワークフロー名が必要です")
    if any(token in safe_name for token in ["/", "\\", ".."]):
        raise HTTPException(
            status_code=400, detail="ワークフロー名に使用できない文字があります"
        )

    yaml_path = WORKFLOWS_DIR / f"{safe_name}.yaml"
    yml_path = WORKFLOWS_DIR / f"{safe_name}.yml"
    target = (
        yaml_path if yaml_path.exists() else yml_path if yml_path.exists() else None
    )
    if not target or not target.exists():
        raise HTTPException(status_code=404, detail="ワークフローが見つかりません")

    target.unlink()
    workflow_scheduler.reload_workflows()
    return {"ok": True, "name": safe_name}


@app.get("/api/scheduler/jobs")
async def get_scheduled_jobs():
    """登録済みスケジュールジョブ一覧（デバッグ用）"""
    return {"jobs": workflow_scheduler.get_scheduled_jobs()}


@app.post("/api/scheduler/reload")
async def reload_scheduler():
    """スケジューラーのワークフロー再読み込み"""
    count = workflow_scheduler.reload_workflows()
    return {"message": f"Reloaded {count} scheduled workflows"}


@app.post("/api/scheduler/preview")
async def preview_cron(request: Request):
    """cronの次回実行時刻をプレビュー"""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="無効なリクエスト形式です")
    cron = (payload.get("cron") or "").strip()
    if not cron:
        raise HTTPException(status_code=400, detail="cron が必要です")

    try:
        trigger = CronTrigger.from_crontab(cron, timezone=ZoneInfo("Asia/Tokyo"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"cron が不正です: {e}") from e

    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    next_runs = []
    prev = None
    current = now
    for _ in range(5):
        next_time = trigger.get_next_fire_time(prev, current)
        if not next_time:
            break
        next_runs.append(next_time.isoformat())
        prev = next_time
        current = next_time

    return {"ok": True, "next_runs": next_runs}


@app.post("/api/logs/cleanup")
async def cleanup_logs(request: Request):
    """ログファイルの手動クリーンアップ"""
    payload = await request.json()
    retention_days = payload.get("retention_days", 30)

    if not isinstance(retention_days, int) or retention_days < 1:
        raise HTTPException(
            status_code=400, detail="retention_days は1以上の整数で指定してください"
        )

    result = run_logger.cleanup(retention_days=retention_days)
    return {"ok": True, **result}


@app.get("/api/workflows/{name}/export")
async def export_workflow(name: str):
    """ワークフローをYAMLファイルとしてエクスポート"""
    safe_name = (name or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="ワークフロー名が必要です")
    if any(token in safe_name for token in ["/", "\\", ".."]):
        raise HTTPException(
            status_code=400, detail="ワークフロー名に使用できない文字があります"
        )

    yaml_content = loader.get_yaml_content(safe_name)
    if not yaml_content:
        raise HTTPException(status_code=404, detail="ワークフローが見つかりません")

    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.yaml"'},
    )


@app.post("/api/workflows/import")
async def import_workflow(file: UploadFile = File(...)):
    """YAMLファイルからワークフローをインポート"""
    if not file.filename or not file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(
            status_code=400, detail="YAMLファイルをアップロードしてください"
        )

    try:
        content = await file.read()
        yaml_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="UTF-8でエンコードされたファイルをアップロードしてください",
        )

    import yaml as yaml_lib

    try:
        data = yaml_lib.safe_load(yaml_content)
    except yaml_lib.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"YAML構文エラー: {e}")

    if not isinstance(data, dict) or "name" not in data:
        raise HTTPException(status_code=400, detail="ワークフロー定義にnameが必要です")

    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="ワークフロー名が空です")
    if any(token in name for token in ["/", "\\", ".."]):
        raise HTTPException(
            status_code=400, detail="ワークフロー名に使用できない文字があります"
        )

    # バリデーション
    try:
        _ = Workflow.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"バリデーションエラー: {e}")

    # 既存ファイルのバックアップ
    yaml_path = WORKFLOWS_DIR / f"{name}.yaml"
    if yaml_path.exists():
        existing_content = yaml_path.read_text(encoding="utf-8")
        backup_manager.backup_workflow(name, existing_content)

    # 保存
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(yaml_content, encoding="utf-8")
    workflow_scheduler.reload_workflows()

    return {"ok": True, "name": name, "path": str(yaml_path)}
