"""
ORBIT MVP - FastAPI Application Entry Point
"""

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# アクション登録（インポート時に自動登録）
from . import actions  # noqa: F401
from .core.backup import BackupManager
from .core.executor import Executor
from .core.loader import WorkflowLoader
from .core.models import Workflow
from .core.registry import get_registry
from .core.run_logger import RunLogger
from .core.scheduler import WorkflowScheduler

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
backup_manager = BackupManager(BACKUPS_DIR, max_backups=10)
workflow_scheduler = WorkflowScheduler(loader, executor, run_logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: スケジューラーの起動/停止を管理"""
    # 起動時: スケジューラー開始
    logger.info("Starting ORBIT application...")

    # ログローテーション実行
    cleanup_result = run_logger.cleanup(retention_days=30)
    logger.info(f"Log cleanup: {cleanup_result['deleted_count']} old files removed")

    workflow_scheduler.start()
    registered = workflow_scheduler.register_workflows()
    logger.info(f"Scheduler ready: {registered} workflows registered")
    try:
        workflow_scheduler.scheduler.add_job(
            run_logger.cleanup,
            trigger=CronTrigger.from_crontab("0 3 * * *", timezone=ZoneInfo("Asia/Tokyo")),
            kwargs={"retention_days": 30},
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
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def build_editor_data(workflow: Workflow | None) -> dict:
    """ビジュアルエディタ向けのデータを構築"""
    if not workflow:
        return {
            "name": "",
            "description": "",
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
                "when": step.when.model_dump(exclude_defaults=True) if step.when else None,
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
        "enabled": workflow.enabled,
        "trigger": trigger_data,
        "steps": steps,
    }


def get_workflow_status(workflow_name: str) -> tuple[str, str | None]:
    """ワークフローの最新ステータスと実行時刻を取得"""
    latest = run_logger.get_latest_run(workflow_name)
    if latest:
        status_map = {
            "success": "成功",
            "failed": "失敗",
            "running": "実行中",
        }
        return status_map.get(latest.status, latest.status), latest.started_at
    return "未実行", None


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
    workflows = loader.list_workflows()
    query = (q or "").strip()

    # 最新実行ステータスを反映
    for wf in workflows:
        if wf.is_valid:
            wf.status, wf.last_run = get_workflow_status(wf.name)

    if query:
        lowered = query.lower()
        workflows = [
            wf for wf in workflows if (wf.name or "").lower().find(lowered) != -1
        ]

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "workflows": workflows, "search_query": query},
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

    workflow_options = sorted({wf.name for wf in loader.list_workflows() if wf.name})
    if workflow and workflow not in workflow_options:
        workflow_options = [workflow, *workflow_options]
    runs = run_logger.get_all_runs(limit=per_page, offset=offset, workflow_filter=workflow)
    total_runs = run_logger.count_all_runs(workflow_filter=workflow)
    total_pages = (total_runs + per_page - 1) // per_page  # 切り上げ

    return templates.TemplateResponse(
        "runs.html",
        {
            "request": request,
            "runs": runs,
            "workflow_filter": workflow,
            "workflow_options": workflow_options,
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
                templates.append({
                    "name": yaml_file.stem,
                    "title": workflow.name,
                    "description": workflow.description or "",
                    "filename": yaml_file.name
                })

    return templates.TemplateResponse(
        "new_workflow.html",
        {
            "request": request,
            "templates": templates
        },
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
        raise HTTPException(status_code=400, detail=f"テンプレートの読み込みに失敗: {error}")

    actions = sorted(get_registry().list_actions())
    editor_data = build_editor_data(workflow)
    config_json = json.dumps(
        {
            "workflow": editor_data,
            "actions": actions,
            "mode": "new",
            "saveUrl": "/api/workflows/save",
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
    try:
        workflow, error = loader.load_workflow(name)

        if error or not workflow:
            # エラートーストを返す
            from datetime import datetime

            from .core.models import RunLog

            error_run = RunLog(
                workflow=name,
                run_id=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[-4:]}",
                status="failed",
                started_at=datetime.now().isoformat(),
                ended_at=datetime.now().isoformat(),
                error=error or "Workflow not found",
                step_results={},
            )
            return templates.TemplateResponse(
                "partials/run_result.html",
                {"request": request, "run": error_run, "workflow_name": name},
            )

        # ワークフロー実行
        run_log = await executor.run(workflow)

        # ログ保存
        run_logger.save(run_log)

        # レスポンス（トースト通知）
        return templates.TemplateResponse(
            "partials/run_result.html",
            {"request": request, "run": run_log, "workflow_name": name},
        )

    except Exception as e:
        # 予期しないエラーをキャッチ
        logger.exception(f"Unexpected error running workflow {name}")
        from datetime import datetime

        from .core.models import RunLog

        error_run = RunLog(
            workflow=name,
            run_id=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[-4:]}",
            status="failed",
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat(),
            error=f"{type(e).__name__}: {str(e)}",
            step_results={},
        )
        return templates.TemplateResponse(
            "partials/run_result.html",
            {"request": request, "run": error_run, "workflow_name": name},
        )


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
                raise HTTPException(status_code=400, detail="条件の形式が正しくありません")
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
