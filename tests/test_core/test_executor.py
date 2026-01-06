"""
ORBIT Test Suite - Workflow Executor
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.app.core.executor import Executor, generate_run_id
from src.app.core.models import (
    Workflow,
    Step,
    TriggerManual,
    StepCondition,
)


class TestGenerateRunId:
    """実行ID生成のテスト"""

    def test_generate_run_id_format(self):
        """実行IDのフォーマット確認"""
        run_id = generate_run_id()
        assert isinstance(run_id, str)
        # YYYYMMDD_HHMMSS_xxxx 形式
        parts = run_id.split("_")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert len(parts[2]) == 4  # xxxx (hex)


class TestExecutor:
    """ワークフロー実行エンジンのテスト"""

    def test_executor_init(self, temp_base_dir):
        """初期化テスト"""
        executor = Executor(temp_base_dir)
        assert executor.base_dir == temp_base_dir
        assert executor.registry is not None

    @pytest.mark.asyncio
    async def test_run_single_step_success(self, executor, mock_action_success, reset_registry):
        """単一ステップの成功実行"""
        from src.app.core.registry import register_action

        # テストアクションを登録
        register_action("test_action")(mock_action_success)

        workflow = Workflow(
            name="test_workflow",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="test_action", params={"message": "Hello"}),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert result.workflow == "test_workflow"
        assert len(result.steps) == 1
        assert result.steps[0]["status"] == "success"
        assert result.steps[0]["result"]["text"] == "Success"

    @pytest.mark.asyncio
    async def test_run_multiple_steps(self, executor, mock_action_success, reset_registry):
        """複数ステップの順次実行"""
        from src.app.core.registry import register_action

        register_action("test_action")(mock_action_success)

        workflow = Workflow(
            name="multi_step",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="test_action", params={"message": "First"}),
                Step(id="step2", type="test_action", params={"message": "Second"}),
                Step(id="step3", type="test_action", params={"message": "Third"}),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert len(result.steps) == 3
        for step in result.steps:
            assert step["status"] == "success"

    @pytest.mark.asyncio
    async def test_run_step_failure_stops_execution(self, executor, mock_action_failure, reset_registry):
        """ステップ失敗時は実行を停止"""
        from src.app.core.registry import register_action

        async def success_action(params, context):
            return {"result": "success"}

        register_action("success_action")(success_action)
        register_action("fail_action")(mock_action_failure)

        workflow = Workflow(
            name="fail_workflow",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="success_action", params={}),
                Step(id="step2", type="fail_action", params={}),
                Step(id="step3", type="success_action", params={}),  # 実行されない
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "failed"
        assert len(result.steps) == 2  # step3は実行されない
        assert result.steps[0]["status"] == "success"
        assert result.steps[1]["status"] == "failed"
        assert "Intentional failure" in result.error

    @pytest.mark.asyncio
    async def test_run_unknown_action(self, executor, reset_registry):
        """未知のアクションタイプはエラー"""
        workflow = Workflow(
            name="unknown_action",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="unknown_action", params={}),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "failed"
        assert result.steps[0]["status"] == "failed"
        assert "Unknown action type" in result.steps[0]["error"]

    @pytest.mark.asyncio
    async def test_run_with_condition_met(self, executor, mock_action_success, reset_registry):
        """条件が一致する場合にステップを実行"""
        from src.app.core.registry import register_action

        register_action("log_action")(mock_action_success)

        workflow = Workflow(
            name="conditional",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="log_action", params={"message": "First"}),
                Step(
                    id="step2",
                    type="log_action",
                    params={"message": "Conditional"},
                    when=StepCondition(
                        step="step1",
                        field="text",
                        equals="Success",
                        match="equals"
                    ),
                ),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert len(result.steps) == 2
        assert result.steps[0]["status"] == "success"
        assert result.steps[1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_run_with_condition_not_met(self, executor, mock_action_success, reset_registry):
        """条件が一致しない場合にステップをスキップ"""
        from src.app.core.registry import register_action

        register_action("log_action")(mock_action_success)

        workflow = Workflow(
            name="conditional",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="log_action", params={"message": "First"}),
                Step(
                    id="step2",
                    type="log_action",
                    params={"message": "Conditional"},
                    when=StepCondition(
                        step="step1",
                        field="text",
                        equals="NotMatching",
                        match="equals"
                    ),
                ),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert len(result.steps) == 2
        assert result.steps[0]["status"] == "success"
        assert result.steps[1]["status"] == "skipped"
        assert "condition_not_met" in result.steps[1]["result"]["reason"]

    @pytest.mark.asyncio
    async def test_run_with_condition_contains(self, executor, mock_action_success, reset_registry):
        """containsマッチで条件判定"""
        from src.app.core.registry import register_action

        register_action("log_action")(mock_action_success)

        workflow = Workflow(
            name="conditional",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="log_action", params={"message": "Hello World"}),
                Step(
                    id="step2",
                    type="log_action",
                    params={"message": "Conditional"},
                    when=StepCondition(
                        step="step1",
                        field="text",
                        equals="Success",  # mock_action_success は "Success" を返す
                        match="contains"
                    ),
                ),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert result.steps[1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_run_with_context_propagation(self, executor, reset_registry):
        """ステップ結果が次のステップのコンテキストに引き継がれる"""
        from src.app.core.registry import register_action

        async def first_action(params, context):
            return {"value": "from_first"}

        async def second_action(params, context):
            # 前のステップの結果を参照
            prev = context.get("step1", {})
            return {"combined": f"first:{prev.get('value', '')}"}

        register_action("first_action")(first_action)
        register_action("second_action")(second_action)

        workflow = Workflow(
            name="context_test",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="first_action", params={}),
                Step(id="step2", type="second_action", params={}),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert result.steps[1]["result"]["combined"] == "first:from_first"

    @pytest.mark.asyncio
    async def test_run_with_template_variables(self, executor, reset_registry):
        """テンプレート変数が展開される"""
        from src.app.core.registry import register_action

        async def echo_action(params, context):
            return {"received": params.get("message", "")}

        register_action("echo_action")(echo_action)

        workflow = Workflow(
            name="template_test",
            trigger=TriggerManual(),
            steps=[
                Step(
                    id="step1",
                    type="echo_action",
                    params={"message": "Workflow: {{ workflow }}, Run: {{ run_id }}"},
                ),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert "template_test" in result.steps[0]["result"]["received"]
        assert result.run_id in result.steps[0]["result"]["received"]

    @pytest.mark.asyncio
    async def test_evaluate_when_missing_step(self, executor):
        """参照ステップが存在しない場合"""
        condition = StepCondition(step="nonexistent", equals="value")
        matched, reason = executor._evaluate_when(condition, {})
        assert matched is False
        assert "condition_step_missing" in reason

    @pytest.mark.asyncio
    async def test_evaluate_when_missing_field(self, executor):
        """参照フィールドが存在しない場合"""
        condition = StepCondition(step="step1", field="missing_field", equals="value")
        context = {"step1": {"other_field": "data"}}
        matched, reason = executor._evaluate_when(condition, context)
        assert matched is False
        assert "condition_field_missing" in reason

    @pytest.mark.asyncio
    async def test_evaluate_when_case_insensitive(self, executor):
        """大文字小文字を区別しない比較"""
        condition = StepCondition(
            step="step1",
            field="text",
            equals="HELLO",
            match="equals",
            case_insensitive=True
        )
        context = {"step1": {"text": "hello"}}
        matched, reason = executor._evaluate_when(condition, context)
        assert matched is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_evaluate_when_with_trim(self, executor):
        """前後空白をトリムして比較"""
        condition = StepCondition(
            step="step1",
            field="text",
            equals="hello",
            match="equals",
            trim=True
        )
        context = {"step1": {"text": "  hello  "}}
        matched, reason = executor._evaluate_when(condition, context)
        assert matched is True

    @pytest.mark.asyncio
    async def test_normalize_string(self, executor):
        """文字列正規化のテスト"""
        # trimとcase_insensitiveの組み合わせ
        result = executor._normalize_string("  HELLO  ", trim=True, case_insensitive=True)
        assert result == "hello"

        # trimのみ
        result = executor._normalize_string("  HELLO  ", trim=True, case_insensitive=False)
        assert result == "HELLO"

        # case_insensitiveのみ
        result = executor._normalize_string("HELLO", trim=False, case_insensitive=True)
        assert result == "hello"

        # なし
        result = executor._normalize_string("  HeLLo  ", trim=False, case_insensitive=False)
        assert result == "  HeLLo  "

    @pytest.mark.asyncio
    async def test_run_sets_initial_context(self, executor, reset_registry):
        """初期コンテキストが正しく設定される"""
        from src.app.core.registry import register_action

        async def check_context(params, context):
            return {
                "has_run_id": "run_id" in context,
                "has_workflow": "workflow" in context,
                "has_now": "now" in context,
                "has_base_dir": "base_dir" in context,
            }

        register_action("check_context")(check_context)

        workflow = Workflow(
            name="context_check",
            trigger=TriggerManual(),
            steps=[
                Step(id="step1", type="check_context", params={}),
            ],
        )

        result = await executor.run(workflow)

        assert result.status == "success"
        assert result.steps[0]["result"]["has_run_id"] is True
        assert result.steps[0]["result"]["has_workflow"] is True
        assert result.steps[0]["result"]["has_now"] is True
        assert result.steps[0]["result"]["has_base_dir"] is True
