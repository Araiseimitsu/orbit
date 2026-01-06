"""
ORBIT Test Suite - Pydantic Models
"""
import pytest
from pydantic import ValidationError

from src.app.core.models import (
    TriggerManual,
    TriggerSchedule,
    TriggerWebhook,
    Step,
    StepCondition,
    Workflow,
    WorkflowInfo,
    RunLog,
)


class TestTriggerManual:
    """手動トリガーのテスト"""

    def test_create_manual_trigger(self):
        """手動トリガーを作成"""
        trigger = TriggerManual()
        assert trigger.type == "manual"

    def test_manual_trigger_serialization(self):
        """手動トリガーのシリアライズ"""
        trigger = TriggerManual()
        data = trigger.model_dump()
        assert data == {"type": "manual"}


class TestTriggerSchedule:
    """スケジュールトリガーのテスト"""

    def test_create_schedule_trigger(self):
        """スケジュールトリガーを作成"""
        trigger = TriggerSchedule(cron="0 9 * * *")
        assert trigger.type == "schedule"
        assert trigger.cron == "0 9 * * *"

    def test_schedule_trigger_missing_cron(self):
        """cron式未指定時はバリデーションエラー"""
        with pytest.raises(ValidationError) as exc_info:
            TriggerSchedule()
        assert "cron" in str(exc_info.value).lower()


class TestTriggerWebhook:
    """Webhookトリガーのテスト"""

    def test_create_webhook_trigger(self):
        """Webhookトリガーを作成"""
        trigger = TriggerWebhook(path="/webhook/test")
        assert trigger.type == "webhook"
        assert trigger.path == "/webhook/test"

    def test_webhook_trigger_optional_path(self):
        """pathは省略可能"""
        trigger = TriggerWebhook()
        assert trigger.type == "webhook"
        assert trigger.path is None


class TestStepCondition:
    """ステップ条件のテスト"""

    def test_create_condition_with_defaults(self):
        """デフォルト値で条件を作成"""
        condition = StepCondition(step="step1", equals="value")
        assert condition.step == "step1"
        assert condition.equals == "value"
        assert condition.field == "text"
        assert condition.match == "equals"
        assert condition.trim is True
        assert condition.case_insensitive is True

    def test_create_condition_custom_field(self):
        """カスタムフィールドで条件を作成"""
        condition = StepCondition(
            step="step1", field="status", equals="success"
        )
        assert condition.field == "status"

    def test_create_condition_contains_match(self):
        """containsマッチで条件を作成"""
        condition = StepCondition(
            step="step1", equals="keyword", match="contains"
        )
        assert condition.match == "contains"

    def test_condition_missing_step(self):
        """step未指定時はバリデーションエラー"""
        with pytest.raises(ValidationError) as exc_info:
            StepCondition(equals="value")
        assert "step" in str(exc_info.value).lower()


class TestStep:
    """ステップのテスト"""

    def test_create_step_minimal(self):
        """最小限のパラメータでステップを作成"""
        step = Step(id="step1", type="log")
        assert step.id == "step1"
        assert step.type == "log"
        assert step.params == {}
        assert step.when is None
        assert step.meta is None

    def test_create_step_with_params(self):
        """パラメータ付きでステップを作成"""
        step = Step(
            id="step1", type="log", params={"message": "Hello"}
        )
        assert step.params == {"message": "Hello"}

    def test_create_step_with_condition(self):
        """条件付きステップを作成"""
        condition = StepCondition(step="step1", equals="value")
        step = Step(id="step2", type="log", when=condition)
        assert step.when == condition

    def test_create_step_with_meta(self):
        """メタ情報付きステップを作成"""
        step = Step(
            id="step1",
            type="log",
            meta={"position": {"x": 100, "y": 200}}
        )
        assert step.meta == {"position": {"x": 100, "y": 200}}

    def test_step_missing_id(self):
        """id未指定時はバリデーションエラー"""
        with pytest.raises(ValidationError) as exc_info:
            Step(type="log")
        assert "id" in str(exc_info.value).lower()

    def test_step_missing_type(self):
        """type未指定時はバリデーションエラー"""
        with pytest.raises(ValidationError) as exc_info:
            Step(id="step1")
        assert "type" in str(exc_info.value).lower()


class TestWorkflow:
    """ワークフローのテスト"""

    def test_create_workflow_minimal(self):
        """最小限のパラメータでワークフローを作成"""
        workflow = Workflow(
            name="test_workflow",
            trigger=TriggerManual(),
            steps=[Step(id="step1", type="log")],
        )
        assert workflow.name == "test_workflow"
        assert workflow.trigger.type == "manual"
        assert len(workflow.steps) == 1
        assert workflow.enabled is True
        assert workflow.description is None

    def test_workflow_with_schedule_trigger(self):
        """スケジュールトリガー付きワークフローを作成"""
        workflow = Workflow(
            name="scheduled_workflow",
            trigger=TriggerSchedule(cron="0 9 * * *"),
            steps=[Step(id="step1", type="log")],
        )
        assert workflow.trigger.type == "schedule"
        assert workflow.trigger.cron == "0 9 * * *"

    def test_workflow_with_description(self):
        """説明付きワークフローを作成"""
        workflow = Workflow(
            name="test_workflow",
            trigger=TriggerManual(),
            steps=[Step(id="step1", type="log")],
            description="Test workflow description",
        )
        assert workflow.description == "Test workflow description"

    def test_workflow_disabled(self):
        """無効化されたワークフローを作成"""
        workflow = Workflow(
            name="test_workflow",
            trigger=TriggerManual(),
            steps=[Step(id="step1", type="log")],
            enabled=False,
        )
        assert workflow.enabled is False

    def test_workflow_multiple_steps(self):
        """複数ステップを持つワークフローを作成"""
        workflow = Workflow(
            name="multi_step_workflow",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="log"),
                Step(id="step2", type="log"),
                Step(id="step3", type="log"),
            ],
        )
        assert len(workflow.steps) == 3

    def test_workflow_missing_name(self):
        """name未指定時はバリデーションエラー"""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                trigger=TriggerManual(),
                steps=[Step(id="step1", type="log")],
            )
        assert "name" in str(exc_info.value).lower()

    def test_workflow_empty_steps(self):
        """ステップが空の場合はバリデーションエラー"""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                name="test",
                trigger=TriggerManual(),
                steps=[],
            )
        assert "steps" in str(exc_info.value).lower() or "at least" in str(exc_info.value).lower()

    def test_workflow_serialization(self):
        """ワークフローのシリアライズ"""
        workflow = Workflow(
            name="test_workflow",
            trigger=TriggerManual(),
            steps=[Step(id="step1", type="log")],
        )
        data = workflow.model_dump()
        assert data["name"] == "test_workflow"
        assert data["trigger"]["type"] == "manual"
        assert len(data["steps"]) == 1


class TestWorkflowInfo:
    """ワークフロー情報のテスト"""

    def test_create_workflow_info(self):
        """ワークフロー情報を作成"""
        info = WorkflowInfo(
            name="test_workflow",
            filename="test_workflow.yaml",
        )
        assert info.name == "test_workflow"
        assert info.filename == "test_workflow.yaml"
        assert info.status == "未実行"
        assert info.last_run is None
        assert info.trigger_type == "manual"
        assert info.step_count == 0
        assert info.is_valid is True
        assert info.error is None
        assert info.enabled is True

    def test_workflow_info_with_all_fields(self):
        """全フィールド指定でワークフロー情報を作成"""
        info = WorkflowInfo(
            name="test_workflow",
            filename="test_workflow.yaml",
            status="成功",
            last_run="2025-01-15 10:30:00",
            trigger_type="schedule",
            cron="0 9 * * *",
            step_count=3,
            is_valid=True,
            error=None,
            enabled=True,
        )
        assert info.status == "成功"
        assert info.last_run == "2025-01-15 10:30:00"
        assert info.trigger_type == "schedule"
        assert info.cron == "0 9 * * *"
        assert info.step_count == 3


class TestRunLog:
    """実行ログのテスト"""

    def test_create_run_log_initial(self):
        """初期状態の実行ログを作成"""
        log = RunLog(
            run_id="20250115_103000_abcd",
            workflow="test_workflow",
            status="running",
            started_at="2025-01-15T10:30:00+09:00",
        )
        assert log.run_id == "20250115_103000_abcd"
        assert log.workflow == "test_workflow"
        assert log.status == "running"
        assert log.started_at == "2025-01-15T10:30:00+09:00"
        assert log.ended_at is None
        assert log.error is None
        assert log.steps == []

    def test_create_run_log_success(self):
        """成功状態の実行ログを作成"""
        log = RunLog(
            run_id="20250115_103000_abcd",
            workflow="test_workflow",
            status="success",
            started_at="2025-01-15T10:30:00+09:00",
            ended_at="2025-01-15T10:30:05+09:00",
            steps=[
                {
                    "id": "step1",
                    "type": "log",
                    "status": "success",
                    "result": {"text": "Hello"},
                }
            ],
        )
        assert log.status == "success"
        assert log.ended_at == "2025-01-15T10:30:05+09:00"
        assert len(log.steps) == 1

    def test_create_run_log_failed(self):
        """失敗状態の実行ログを作成"""
        log = RunLog(
            run_id="20250115_103000_abcd",
            workflow="test_workflow",
            status="failed",
            started_at="2025-01-15T10:30:00+09:00",
            ended_at="2025-01-15T10:30:03+09:00",
            error="Step failed: Unknown action",
        )
        assert log.status == "failed"
        assert log.error == "Step failed: Unknown action"

    def test_run_log_invalid_status(self):
        """不正なステータスではバリデーションエラー"""
        with pytest.raises(ValidationError):
            RunLog(
                run_id="20250115_103000_abcd",
                workflow="test_workflow",
                status="invalid",  # 不正なステータス
                started_at="2025-01-15T10:30:00+09:00",
            )
