"""
ORBIT Test Suite - 共通フィクスチャ
"""
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.core.models import (
    Workflow,
    Step,
    TriggerManual,
    TriggerSchedule,
    StepCondition,
)
from src.app.core.executor import Executor


@pytest.fixture
def project_root() -> Path:
    """プロジェクトルートパス"""
    return Path(__file__).parent.parent


@pytest.fixture
def temp_dir():
    """一時ディレクトリ"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_workflows_dir(temp_dir):
    """一時ワークフローディレクトリ"""
    workflows_dir = temp_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    return workflows_dir


@pytest.fixture
def mock_workflow():
    """テスト用モックワークフロー"""
    return Workflow(
        name="test_workflow",
        trigger=TriggerManual(),
        steps=[
            Step(id="step1", type="log", params={"message": "Hello {{ workflow }}"}),
        ],
    )


@pytest.fixture
def mock_workflow_with_schedule():
    """スケジュールトリガー付きモックワークフロー"""
    return Workflow(
        name="scheduled_workflow",
        trigger=TriggerSchedule(cron="0 9 * * *"),
        steps=[
            Step(id="step1", type="log", params={"message": "Scheduled task"}),
        ],
    )


@pytest.fixture
def mock_workflow_with_condition():
    """条件付きステップを含むモックワークフロー"""
    return Workflow(
        name="conditional_workflow",
        trigger=TriggerManual(),
        steps=[
            Step(id="step1", type="log", params={"message": "First step"}),
            Step(
                id="step2",
                type="log",
                params={"message": "Conditional step"},
                when=StepCondition(
                    step="step1",
                    field="text",
                    equals="First step",
                    match="equals",
                ),
            ),
        ],
    )


@pytest.fixture
def temp_base_dir(temp_dir):
    """一時ベースディレクトリ（runs/用）"""
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.fixture
def executor(temp_base_dir):
    """テスト用エグゼキューター"""
    return Executor(temp_base_dir)


@pytest.fixture
def mock_action_success():
    """成功するモックアクション"""
    async def _action(params: dict, context: dict) -> dict:
        return {"text": "Success", "output": params.get("message", "")}

    return _action


@pytest.fixture
def mock_action_failure():
    """失敗するモックアクション"""
    async def _action(params: dict, context: dict) -> dict:
        raise RuntimeError("Intentional failure")

    return _action


@pytest.fixture
def sample_workflow_yaml():
    """サンプルワークフローYAML"""
    return """
name: sample_workflow
trigger:
  type: manual
steps:
  - id: hello
    type: log
    params:
      message: "Hello, World!"
"""


@pytest.fixture
def sample_workflow_yaml_with_condition():
    """条件付きステップを含むサンプルワークフローYAML"""
    return """
name: conditional_workflow
trigger:
  type: manual
steps:
  - id: step1
    type: log
    params:
      message: "First step"
  - id: step2
    type: log
    params:
      message: "Second step"
    when:
      step: step1
      field: text
      equals: "First step"
      match: equals
"""


@pytest.fixture
def sample_workflow_yaml_invalid():
    """不正なサンプルワークフローYAML"""
    return """
name: invalid_workflow
trigger:
  type: invalid_type
steps:
  - id: step1
    type: unknown_action
    params:
      message: "Test"
"""


@pytest.fixture
def mock_datetime(monkeypatch):
    """日時モックフィクスチャ"""

    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            base = datetime(2025, 1, 15, 10, 30, 0)
            if tz:
                return base.replace(tzinfo=tz)
            return base

        @classmethod
        def strftime(cls, format_str):
            return cls.now().strftime(format_str)

    mock_dt = MockDatetime()
    monkeypatch.setattr("src.app.core.executor.datetime", mock_dt)
    return mock_dt


@pytest.fixture
def mock_run_id(monkeypatch):
    """固定のrun_idを返すモック"""
    monkeypatch.setattr(
        "src.app.core.executor.secrets",
        MagicMock(token_hex=lambda x: "abcd"),
    )
    return "20250115_103000_abcd"


@pytest.fixture(autouse=True)
def reset_registry():
    """各テスト前にレジストリをリセット"""
    from src.app.core.registry import ActionRegistry

    # レジストリのインスタンスをリセット
    ActionRegistry._instance = None
    ActionRegistry._actions = {}
    ActionRegistry._metadata = {}

    yield

    # テスト後もクリーンアップ
    ActionRegistry._instance = None
    ActionRegistry._actions = {}
    ActionRegistry._metadata = {}
