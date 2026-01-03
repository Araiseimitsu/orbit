"""
ORBIT MVP - Workflow Scheduler
APSchedulerを使用したスケジュール実行管理
"""
import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from .loader import WorkflowLoader
    from .executor import Executor
    from .run_logger import RunLogger
    from .models import Workflow

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """ワークフロースケジューラー"""

    def __init__(
        self,
        loader: "WorkflowLoader",
        executor: "Executor",
        run_logger: "RunLogger"
    ):
        self.loader = loader
        self.executor = executor
        self.run_logger = run_logger
        self.scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
        self._registered_jobs: dict[str, str] = {}  # workflow_name -> job_id

    def start(self) -> None:
        """スケジューラーを開始"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def stop(self) -> None:
        """スケジューラーを停止"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def register_workflows(self) -> int:
        """
        全ワークフローをスキャンして、scheduleトリガーを登録

        Returns:
            登録したジョブ数
        """
        workflows = self.loader.list_workflows()
        registered_count = 0

        for wf_info in workflows:
            if not wf_info.is_valid:
                continue

            if wf_info.trigger_type != "schedule":
                continue

            # ワークフローを読み込み
            workflow, error = self.loader.load_workflow(wf_info.name)
            if workflow is None or error:
                logger.warning(f"Failed to load workflow for scheduling: {wf_info.name}")
                continue

            # スケジュール登録
            if self._register_job(workflow):
                registered_count += 1

        logger.info(f"Registered {registered_count} scheduled workflows")
        return registered_count

    def _register_job(self, workflow: "Workflow") -> bool:
        """
        ワークフローをスケジューラーに登録

        Returns:
            登録成功したかどうか
        """
        # scheduleトリガーの場合のみ
        if workflow.trigger.type != "schedule":
            return False
        if not workflow.enabled:
            logger.info(f"Workflow disabled, skipping schedule: {workflow.name}")
            return False

        cron_expr = workflow.trigger.cron  # type: ignore

        try:
            # cron式をパース
            trigger = CronTrigger.from_crontab(cron_expr)

            # 既存のジョブがあれば削除
            if workflow.name in self._registered_jobs:
                old_job_id = self._registered_jobs[workflow.name]
                self.scheduler.remove_job(old_job_id)
                logger.debug(f"Removed old job: {workflow.name}")

            # ジョブ登録
            job = self.scheduler.add_job(
                self._execute_workflow,
                trigger=trigger,
                args=[workflow.name],
                id=f"workflow_{workflow.name}",
                name=f"Workflow: {workflow.name}",
                replace_existing=True,
            )

            self._registered_jobs[workflow.name] = job.id
            logger.info(f"Scheduled workflow: {workflow.name} (cron: {cron_expr})")
            return True

        except ValueError as e:
            logger.error(f"Invalid cron expression for {workflow.name}: {cron_expr} - {e}")
            return False

    async def _execute_workflow(self, workflow_name: str) -> None:
        """
        スケジュール実行のコールバック
        """
        logger.info(f"[Scheduler] Executing workflow: {workflow_name}")

        try:
            # ワークフロー読み込み
            workflow, error = self.loader.load_workflow(workflow_name)
            if workflow is None or error:
                logger.error(f"[Scheduler] Failed to load workflow: {workflow_name} - {error}")
                return

            # 実行
            run_log = await self.executor.run(workflow)

            # ログ保存
            self.run_logger.save(run_log)

            logger.info(
                f"[Scheduler] Workflow completed: {workflow_name} "
                f"(status: {run_log.status})"
            )

        except Exception as e:
            logger.exception(f"[Scheduler] Error executing workflow {workflow_name}: {e}")

    def get_scheduled_jobs(self) -> list[dict]:
        """登録済みジョブ一覧を取得"""
        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
            })
        return jobs

    def reload_workflows(self) -> int:
        """
        ワークフローを再読み込み

        Returns:
            登録したジョブ数
        """
        # 全ジョブを削除
        for job_id in list(self._registered_jobs.values()):
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
        self._registered_jobs.clear()

        # 再登録
        return self.register_workflows()
