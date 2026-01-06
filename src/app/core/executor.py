"""
ORBIT MVP - Workflow Executor
ワークフローを直列実行するエンジン
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from pathlib import Path

from .models import Workflow, RunLog, StepCondition
from .registry import get_registry
from .templating import render_params

logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))

# デフォルトのステップ実行タイムアウト（秒）
DEFAULT_STEP_TIMEOUT = 300  # 5分


def generate_run_id() -> str:
    """実行ID生成: YYYYMMDD_HHMMSS_xxxx"""
    import secrets
    now = datetime.now(JST)
    suffix = secrets.token_hex(2)
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{suffix}"


class Executor:
    """ワークフロー実行エンジン"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.registry = get_registry()

    @staticmethod
    def _normalize_string(value: str, trim: bool, case_insensitive: bool) -> str:
        text = value
        if trim:
            text = text.strip()
        if case_insensitive:
            text = text.lower()
        return text

    def _evaluate_when(
        self, condition: StepCondition, context: dict[str, Any]
    ) -> tuple[bool, str | None]:
        step_result = context.get(condition.step)
        if step_result is None:
            return False, f"condition_step_missing:{condition.step}"

        if isinstance(step_result, dict):
            actual = step_result.get(condition.field)
        else:
            actual = getattr(step_result, condition.field, None)

        if actual is None:
            return False, f"condition_field_missing:{condition.field}"

        expected = condition.equals
        if isinstance(actual, str) and isinstance(expected, str):
            left = self._normalize_string(
                actual, condition.trim, condition.case_insensitive
            )
            right = self._normalize_string(
                expected, condition.trim, condition.case_insensitive
            )
            if condition.match == "contains":
                return right in left, None
            return left == right, None

        return actual == expected, None

    async def run(self, workflow: Workflow) -> RunLog:
        """
        ワークフローを実行

        Args:
            workflow: 実行するワークフロー

        Returns:
            RunLog: 実行結果
        """
        run_id = generate_run_id()
        started_at = datetime.now(JST)
        today = started_at.date()

        # コンテキスト初期化
        context: dict[str, Any] = {
            "run_id": run_id,
            "workflow": workflow.name,
            "now": started_at.isoformat(),
            "base_dir": self.base_dir,
            "today": today.isoformat(),
            "yesterday": (today - timedelta(days=1)).isoformat(),
            "tomorrow": (today + timedelta(days=1)).isoformat(),
            "today_ymd": started_at.strftime("%Y%m%d"),
            "now_ymd_hms": started_at.strftime("%Y%m%d_%H%M%S"),
        }

        # 実行ログ初期化
        run_log = RunLog(
            run_id=run_id,
            workflow=workflow.name,
            status="running",
            started_at=started_at.isoformat(),
            steps=[],
        )

        logger.info(f"Starting workflow: {workflow.name} (run_id: {run_id})")

        try:
            # ステップを順番に実行
            for step in workflow.steps:
                if step.when:
                    matched, reason = self._evaluate_when(step.when, context)
                    if not matched:
                        skip_reason = reason or "condition_not_met"
                        logger.info(
                            f"Skipping step: {step.id} (reason: {skip_reason})"
                        )
                        run_log.steps.append(
                            {
                                "id": step.id,
                                "type": step.type,
                                "status": "skipped",
                                "result": {
                                    "reason": skip_reason,
                                    "when": step.when.model_dump(),
                                },
                            }
                        )
                        continue
                step_result = await self._execute_step(step.id, step.type, step.params, context)
                run_log.steps.append(step_result)

                if step_result["status"] == "failed":
                    run_log.status = "failed"
                    run_log.error = step_result.get("error")
                    break
                else:
                    # 成功した結果を context に格納（次ステップで参照可能）
                    context[step.id] = step_result.get("result", {})

            else:
                # 全ステップ成功
                run_log.status = "success"

        except Exception as e:
            logger.exception(f"Workflow execution error: {e}")
            run_log.status = "failed"
            run_log.error = str(e)

        # 終了時刻
        ended_at = datetime.now(JST)
        run_log.ended_at = ended_at.isoformat()

        logger.info(
            f"Workflow completed: {workflow.name} "
            f"(status: {run_log.status}, duration: {(ended_at - started_at).total_seconds():.2f}s)"
        )

        return run_log

    async def _execute_step(
        self,
        step_id: str,
        step_type: str,
        params: dict[str, Any],
        context: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        単一ステップを実行

        Args:
            step_id: ステップID
            step_type: アクションタイプ
            params: パラメータ
            context: コンテキスト
            timeout: タイムアウト秒数（Noneでデフォルト値使用）

        Returns:
            {
                "id": step_id,
                "type": step_type,
                "status": "success" | "failed",
                "result": {...},   # 成功時
                "error": "..."     # 失敗時
            }
        """
        logger.debug(f"Executing step: {step_id} (type: {step_type})")

        # アクション取得
        action = self.registry.get(step_type)
        if not action:
            error_msg = f"Unknown action type: {step_type}"
            logger.error(error_msg)
            return {
                "id": step_id,
                "type": step_type,
                "status": "failed",
                "error": error_msg,
            }

        # タイムアウト設定
        step_timeout = timeout if timeout is not None else DEFAULT_STEP_TIMEOUT

        try:
            # パラメータをテンプレートレンダリング
            rendered_params = render_params(params, context)

            # アクション実行（タイムアウト付き）
            result = await asyncio.wait_for(
                action(rendered_params, context),
                timeout=step_timeout
            )

            logger.debug(f"Step completed: {step_id}")
            return {
                "id": step_id,
                "type": step_type,
                "status": "success",
                "result": result,
            }

        except asyncio.TimeoutError:
            error_msg = f"Step execution timed out after {step_timeout} seconds"
            logger.error(f"Step timed out: {step_id} - {error_msg}")
            return {
                "id": step_id,
                "type": step_type,
                "status": "failed",
                "error": error_msg,
            }

        except Exception as e:
            logger.exception(f"Step failed: {step_id} - {e}")
            return {
                "id": step_id,
                "type": step_type,
                "status": "failed",
                "error": str(e),
            }
