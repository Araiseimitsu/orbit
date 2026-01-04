"""
ORBIT MVP - Workflow YAML Loader
"""
import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import Workflow, WorkflowInfo

logger = logging.getLogger(__name__)


class WorkflowLoader:
    """ワークフローYAMLローダー"""

    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir

    def _get_yaml_files(self) -> list[Path]:
        """YAMLファイル一覧を取得"""
        files = []
        if self.workflows_dir.exists():
            files.extend(self.workflows_dir.glob("*.yaml"))
            files.extend(self.workflows_dir.glob("*.yml"))
        return sorted(files, key=lambda x: x.stem)

    def load_workflow(self, name: str, templates_dir: bool = False) -> tuple[Workflow | None, str | None]:
        """
        ワークフローを読み込み、バリデーション

        Args:
            name: ワークフロー名
            templates_dir: テンプレートディレクトリから読み込むかどうか

        Returns:
            (Workflow, None) - 成功時
            (None, error_message) - 失敗時
        """
        # テンプレートディレクトリから読み込む場合
        if templates_dir:
            base_dir = self.workflows_dir / "templates"
        else:
            base_dir = self.workflows_dir

        yaml_path = base_dir / f"{name}.yaml"
        yml_path = base_dir / f"{name}.yml"

        file_path = yaml_path if yaml_path.exists() else yml_path if yml_path.exists() else None

        if not file_path:
            return None, f"ワークフロー '{name}' が見つかりません"

        try:
            content = file_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)

            if data is None:
                return None, "YAMLファイルが空です"

            workflow = Workflow.model_validate(data)
            return workflow, None

        except yaml.YAMLError as e:
            logger.error(f"YAML parse error: {name} - {e}")
            return None, f"YAML構文エラー: {e}"

        except ValidationError as e:
            errors = []
            for error in e.errors():
                loc = " -> ".join(str(x) for x in error["loc"])
                errors.append(f"{loc}: {error['msg']}")
            error_msg = "\n".join(errors)
            logger.error(f"Validation error: {name} - {error_msg}")
            return None, f"バリデーションエラー:\n{error_msg}"

        except Exception as e:
            logger.error(f"Unexpected error loading {name}: {e}")
            return None, f"予期しないエラー: {e}"

    def get_yaml_content(self, name: str) -> str:
        """YAML内容を文字列で取得"""
        yaml_path = self.workflows_dir / f"{name}.yaml"
        yml_path = self.workflows_dir / f"{name}.yml"

        file_path = yaml_path if yaml_path.exists() else yml_path if yml_path.exists() else None

        if file_path and file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return ""

    def list_workflows(self) -> list[WorkflowInfo]:
        """
        全ワークフローを一覧取得（バリデーション込み）
        """
        workflows = []

        for yaml_file in self._get_yaml_files():
            name = yaml_file.stem
            workflow, error = self.load_workflow(name)

            if workflow:
                info = WorkflowInfo(
                    name=workflow.name,
                    filename=yaml_file.name,
                    status="未実行",
                    last_run=None,
                    trigger_type=workflow.trigger.type,
                    step_count=len(workflow.steps),
                    is_valid=True,
                    error=None,
                    enabled=workflow.enabled
                )
            else:
                info = WorkflowInfo(
                    name=name,
                    filename=yaml_file.name,
                    status="エラー",
                    last_run=None,
                    trigger_type="unknown",
                    step_count=0,
                    is_valid=False,
                    error=error,
                    enabled=False
                )

            workflows.append(info)

        return workflows
