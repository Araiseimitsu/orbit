"""
ORBIT Test Suite - Subworkflow Action
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from src.app.actions.subworkflow import action_subworkflow, CALL_CHAIN_KEY
from src.app.core.executor import Executor


@pytest.fixture
def temp_workflows_dir(tmp_path: Path):
    """一時的なワークフローディレクトリを作成"""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    
    # テスト用のサブワークフローを作成
    sub_workflow_yaml = workflows_dir / "simple_subworkflow.yaml"
    sub_workflow_yaml.write_text("""name: simple_subworkflow
trigger:
  type: manual
steps:
  - id: step_1
    type: log
    params:
      message: "Hello from subworkflow"
""", encoding="utf-8")
    
    # パラメータを受け取るサブワークフロー
    param_workflow_yaml = workflows_dir / "param_subworkflow.yaml"
    param_workflow_yaml.write_text("""name: param_subworkflow
trigger:
  type: manual
steps:
  - id: step_1
    type: log
    params:
      message: "Input: {{ input_param }}"
""", encoding="utf-8")
    
    return workflows_dir


class TestActionSubworkflow:
    """サブワークフローアクションのテスト"""

    @pytest.mark.asyncio
    async def test_basic_subworkflow_call(self, temp_workflows_dir: Path):
        """基本的なサブワークフロー呼び出し"""
        result = await action_subworkflow(
            {
                "workflow_name": "simple_subworkflow",
            },
            {
                "base_dir": temp_workflows_dir.parent,
            }
        )
        
        assert result["success"] is True
        assert result["status"] == "success"
        assert result["run_id"] is not None
        assert "step_1" in result["results"]
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_subworkflow_with_parameters(self, temp_workflows_dir: Path):
        """パラメータを渡すサブワークフロー呼び出し"""
        result = await action_subworkflow(
            {
                "workflow_name": "param_subworkflow",
                "input_param": "test_value",
            },
            {
                "base_dir": temp_workflows_dir.parent,
            }
        )
        
        assert result["success"] is True
        assert result["status"] == "success"
        assert "step_1" in result["results"]

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, temp_workflows_dir: Path):
        """循環参照の検出"""
        result = await action_subworkflow(
            {
                "workflow_name": "simple_subworkflow",
                "continue_on_error": True,  # エラーでも続行
            },
            {
                "base_dir": temp_workflows_dir.parent,
                CALL_CHAIN_KEY: ["simple_subworkflow"],  # 既に呼び出しチェーンに含まれる
            }
        )
        
        # 循環参照が検出されるべき
        assert result["success"] is False
        assert result["status"] == "failed"
        assert "Circular dependency" in result["error"]

    @pytest.mark.asyncio
    async def test_max_depth_limit(self, temp_workflows_dir: Path):
        """深度制限のテスト"""
        result = await action_subworkflow(
            {
                "workflow_name": "simple_subworkflow",
                "max_depth": 2,
                "continue_on_error": True,  # エラーでも続行
            },
            {
                "base_dir": temp_workflows_dir.parent,
                CALL_CHAIN_KEY: ["wf1", "wf2"],  # 既に深度2
            }
        )
        
        assert result["success"] is False
        assert result["status"] == "failed"
        assert "Maximum subworkflow depth" in result["error"]

    @pytest.mark.asyncio
    async def test_continue_on_error_true(self, temp_workflows_dir: Path):
        """continue_on_error=true で失敗しても続行"""
        # 存在しないワークフローを呼び出し
        result = await action_subworkflow(
            {
                "workflow_name": "nonexistent_workflow",
                "continue_on_error": True,
            },
            {
                "base_dir": temp_workflows_dir.parent,
            }
        )
        
        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["error"] is not None
        # 例外は投げられず、結果が返される

    @pytest.mark.asyncio
    async def test_missing_workflow_name(self, temp_workflows_dir: Path):
        """workflow_name が必須であることを確認"""
        with pytest.raises(ValueError, match="workflow_name is required"):
            await action_subworkflow(
                {},
                {"base_dir": temp_workflows_dir.parent}
            )

    @pytest.mark.asyncio
    async def test_workflow_not_found(self, temp_workflows_dir: Path):
        """存在しないワークフローの呼び出し"""
        with pytest.raises(FileNotFoundError, match="Failed to load workflow"):
            await action_subworkflow(
                {
                    "workflow_name": "nonexistent_workflow",
                },
                {
                    "base_dir": temp_workflows_dir.parent,
                }
            )

    @pytest.mark.asyncio
    async def test_template_rendering_in_params(self, temp_workflows_dir: Path):
        """パラメータのテンプレートレンダリング"""
        result = await action_subworkflow(
            {
                "workflow_name": "param_subworkflow",
                "input_param": "{{ parent_value }}",  # テンプレート変数
            },
            {
                "base_dir": temp_workflows_dir.parent,
                "parent_value": "rendered_value",  # 親contextの値
            }
        )
        
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_basic_variables_passed_to_subworkflow(self, temp_workflows_dir: Path):
        """基本変数がサブワークフローに渡されることを確認"""
        result = await action_subworkflow(
            {
                "workflow_name": "simple_subworkflow",
            },
            {
                "base_dir": temp_workflows_dir.parent,
                "run_id": "test_run_id",
                "now": "2024-01-01T00:00:00",
                "today": "2024-01-01",
                "today_ymd": "20240101",
            }
        )
        
        assert result["success"] is True
