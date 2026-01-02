"""
ORBIT MVP - FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .core.loader import WorkflowLoader
from .core.executor import Executor
from .core.run_logger import RunLogger
from .core.scheduler import WorkflowScheduler

# アクション登録（インポート時に自動登録）
from . import actions  # noqa: F401

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ディレクトリ設定
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKFLOWS_DIR = BASE_DIR / "workflows"
RUNS_DIR = BASE_DIR / "runs"
TEMPLATES_DIR = Path(__file__).resolve().parent / "ui" / "templates"

# Jinja2 テンプレート設定
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# コンポーネント初期化
loader = WorkflowLoader(WORKFLOWS_DIR)
executor = Executor(BASE_DIR)
run_logger = RunLogger(RUNS_DIR)
workflow_scheduler = WorkflowScheduler(loader, executor, run_logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: スケジューラーの起動/停止を管理"""
    # 起動時: スケジューラー開始
    logger.info("Starting ORBIT application...")
    workflow_scheduler.start()
    registered = workflow_scheduler.register_workflows()
    logger.info(f"Scheduler ready: {registered} workflows registered")

    yield

    # 停止時: スケジューラー停止
    logger.info("Shutting down ORBIT application...")
    workflow_scheduler.stop()


# FastAPI アプリケーション（lifespanを設定）
app = FastAPI(
    title="ORBIT",
    description="n8nライクなワークフロー実行アプリ（MVP）",
    version="0.1.0",
    lifespan=lifespan
)


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


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """ダッシュボード - ワークフロー一覧"""
    workflows = loader.list_workflows()

    # 最新実行ステータスを反映
    for wf in workflows:
        if wf.is_valid:
            wf.status, wf.last_run = get_workflow_status(wf.name)

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "workflows": workflows}
    )


@app.get("/workflows/{name}", response_class=HTMLResponse)
async def workflow_detail(request: Request, name: str):
    """ワークフロー詳細画面"""
    workflow, error = loader.load_workflow(name)
    yaml_content = loader.get_yaml_content(name)

    # 実行履歴を取得
    runs = run_logger.get_runs_for_workflow(name, limit=20)

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
            "next_run": next_run
        }
    )


@app.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, workflow: str | None = None):
    """実行履歴一覧"""
    runs = run_logger.get_all_runs(limit=100, workflow_filter=workflow)

    return templates.TemplateResponse(
        "runs.html",
        {
            "request": request,
            "runs": runs,
            "workflow_filter": workflow
        }
    )


@app.post("/api/workflows/{name}/run", response_class=HTMLResponse)
async def run_workflow(request: Request, name: str):
    """
    ワークフローを手動実行（HTMX用）

    成功時: トースト通知用のHTMLを返す
    失敗時: エラー表示用のHTMLを返す
    """
    workflow, error = loader.load_workflow(name)

    if error or not workflow:
        raise HTTPException(status_code=400, detail=error or "Workflow not found")

    # ワークフロー実行
    run_log = await executor.run(workflow)

    # ログ保存
    run_logger.save(run_log)

    # レスポンス（トースト通知）
    return templates.TemplateResponse(
        "partials/run_result.html",
        {
            "request": request,
            "run": run_log,
            "workflow_name": name
        }
    )


@app.get("/api/scheduler/jobs")
async def get_scheduled_jobs():
    """登録済みスケジュールジョブ一覧（デバッグ用）"""
    return {"jobs": workflow_scheduler.get_scheduled_jobs()}


@app.post("/api/scheduler/reload")
async def reload_scheduler():
    """スケジューラーのワークフロー再読み込み"""
    count = workflow_scheduler.reload_workflows()
    return {"message": f"Reloaded {count} scheduled workflows"}
