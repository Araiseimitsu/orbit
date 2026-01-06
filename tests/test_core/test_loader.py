"""
ORBIT Test Suite - Workflow YAML Loader
"""
import pytest

from src.app.core.loader import WorkflowLoader
from src.app.core.models import Workflow, TriggerManual, TriggerSchedule


class TestWorkflowLoader:
    """WorkflowLoaderのテスト"""

    def test_init(self, temp_workflows_dir):
        """初期化テスト"""
        loader = WorkflowLoader(temp_workflows_dir)
        assert loader.workflows_dir == temp_workflows_dir

    def test_load_workflow_success(self, temp_workflows_dir, sample_workflow_yaml):
        """正常なワークフローの読み込み"""
        # サンプルYAMLを書き込み
        (temp_workflows_dir / "sample.yaml").write_text(
            sample_workflow_yaml, encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("sample")

        assert error is None
        assert workflow is not None
        assert workflow.name == "sample_workflow"
        assert workflow.trigger.type == "manual"
        assert len(workflow.steps) == 1
        assert workflow.steps[0].id == "hello"

    def test_load_workflow_with_condition(self, temp_workflows_dir, sample_workflow_yaml_with_condition):
        """条件付きステップを含むワークフローの読み込み"""
        (temp_workflows_dir / "conditional.yaml").write_text(
            sample_workflow_yaml_with_condition, encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("conditional")

        assert error is None
        assert workflow is not None
        assert len(workflow.steps) == 2
        assert workflow.steps[1].when is not None
        assert workflow.steps[1].when.step == "step1"

    def test_load_workflow_not_found(self, temp_workflows_dir):
        """存在しないワークフローの読み込み"""
        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("nonexistent")

        assert workflow is None
        assert error is not None
        assert "見つかりません" in error or "not found" in error.lower()

    def test_load_workflow_invalid_yaml_syntax(self, temp_workflows_dir):
        """YAML構文エラー"""
        (temp_workflows_dir / "invalid.yaml").write_text(
            "name: test\n  trigger:",  # 不正なYAML
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("invalid")

        assert workflow is None
        assert error is not None
        assert "構文エラー" in error or "yaml" in error.lower()

    def test_load_workflow_validation_error(self, temp_workflows_dir, sample_workflow_yaml_invalid):
        """バリデーションエラー"""
        (temp_workflows_dir / "invalid.yaml").write_text(
            sample_workflow_yaml_invalid, encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("invalid")

        assert workflow is None
        assert error is not None
        assert "バリデーションエラー" in error or "validation" in error.lower()

    def test_load_workflow_empty_file(self, temp_workflows_dir):
        """空のYAMLファイル"""
        (temp_workflows_dir / "empty.yaml").write_text("", encoding="utf-8")

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("empty")

        assert workflow is None
        assert error is not None
        assert "空" in error or "empty" in error.lower()

    def test_load_workflow_yml_extension(self, temp_workflows_dir, sample_workflow_yaml):
        """.yml拡張子のファイルを読み込み"""
        (temp_workflows_dir / "sample.yml").write_text(
            sample_workflow_yaml, encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("sample")

        assert error is None
        assert workflow is not None
        assert workflow.name == "sample_workflow"

    def test_load_workflow_yaml_priority_over_yml(self, temp_workflows_dir):
        """.yamlと.yml両方がある場合は.yamlを優先"""
        (temp_workflows_dir / "sample.yaml").write_text(
            "name: from_yaml\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )
        (temp_workflows_dir / "sample.yml").write_text(
            "name: from_yml\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("sample")

        assert error is None
        assert workflow.name == "from_yaml"

    def test_get_yaml_content(self, temp_workflows_dir, sample_workflow_yaml):
        """YAML内容を文字列で取得"""
        (temp_workflows_dir / "sample.yaml").write_text(
            sample_workflow_yaml, encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        content = loader.get_yaml_content("sample")

        assert content == sample_workflow_yaml

    def test_get_yaml_content_not_found(self, temp_workflows_dir):
        """存在しないファイルのYAML内容取得"""
        loader = WorkflowLoader(temp_workflows_dir)
        content = loader.get_yaml_content("nonexistent")
        assert content == ""

    def test_list_workflows_empty(self, temp_workflows_dir):
        """空ディレクトリで一覧取得"""
        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()
        assert workflows == []

    def test_list_workflows_single(self, temp_workflows_dir, sample_workflow_yaml):
        """単一ワークフローの一覧取得"""
        (temp_workflows_dir / "test.yaml").write_text(
            sample_workflow_yaml, encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()

        assert len(workflows) == 1
        assert workflows[0].name == "sample_workflow"
        assert workflows[0].is_valid is True
        assert workflows[0].error is None

    def test_list_workflows_multiple(self, temp_workflows_dir):
        """複数ワークフローの一覧取得"""
        (temp_workflows_dir / "workflow1.yaml").write_text(
            "name: workflow1\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )
        (temp_workflows_dir / "workflow2.yaml").write_text(
            "name: workflow2\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()

        assert len(workflows) == 2
        names = {w.name for w in workflows}
        assert names == {"workflow1", "workflow2"}

    def test_list_workflows_with_invalid(self, temp_workflows_dir, sample_workflow_yaml_invalid):
        """不正なワークフローを含む一覧取得"""
        (temp_workflows_dir / "valid.yaml").write_text(
            "name: valid\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )
        (temp_workflows_dir / "invalid.yaml").write_text(
            sample_workflow_yaml_invalid, encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()

        assert len(workflows) == 2

        # 有効なワークフロー
        valid = next(w for w in workflows if w.name == "valid")
        assert valid.is_valid is True
        assert valid.error is None

        # 無効なワークフロー
        invalid = next(w for w in workflows if w.name == "invalid")
        assert invalid.is_valid is False
        assert invalid.error is not None

    def test_list_workflows_schedule_trigger(self, temp_workflows_dir):
        """スケジュールトリガー付きワークフローの一覧"""
        (temp_workflows_dir / "scheduled.yaml").write_text(
            "name: scheduled\ntrigger:\n  type: schedule\n  cron: '0 9 * * *'\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()

        assert len(workflows) == 1
        assert workflows[0].trigger_type == "schedule"
        assert workflows[0].cron == "0 9 * * *"

    def test_list_workflows_sorting(self, temp_workflows_dir):
        """一覧がファイル名順にソートされている"""
        (temp_workflows_dir / "zebra.yaml").write_text(
            "name: zebra\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )
        (temp_workflows_dir / "alpha.yaml").write_text(
            "name: alpha\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )
        (temp_workflows_dir / "beta.yaml").write_text(
            "name: beta\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()

        assert len(workflows) == 3
        names = [w.name for w in workflows]
        assert names == ["alpha", "beta", "zebra"]

    def test_list_workflows_step_count(self, temp_workflows_dir):
        """ステップ数のカウント"""
        (temp_workflows_dir / "multi.yaml").write_text(
            """name: multi
trigger:
  type: manual
steps:
  - id: s1
    type: log
  - id: s2
    type: log
  - id: s3
    type: log""",
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()

        assert len(workflows) == 1
        assert workflows[0].step_count == 3

    def test_list_workflows_disabled(self, temp_workflows_dir):
        """無効化されたワークフローの一覧"""
        (temp_workflows_dir / "disabled.yaml").write_text(
            "name: disabled\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log\nenabled: false",
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflows = loader.list_workflows()

        assert len(workflows) == 1
        assert workflows[0].enabled is False

    def test_load_workflow_from_templates_dir(self, temp_workflows_dir):
        """テンプレートディレクトリから読み込み"""
        templates_dir = temp_workflows_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        (templates_dir / "template.yaml").write_text(
            "name: template\ntrigger:\n  type: manual\nsteps:\n  - id: s1\n    type: log",
            encoding="utf-8"
        )

        loader = WorkflowLoader(temp_workflows_dir)
        workflow, error = loader.load_workflow("template", templates_dir=True)

        assert error is None
        assert workflow is not None
        assert workflow.name == "template"

    def test_list_workflows_nonexistent_directory(self, temp_dir):
        """存在しないディレクトリでの一覧取得"""
        # temp_dir の中に存在しないサブディレクトリを指定
        loader = WorkflowLoader(temp_dir / "nonexistent_subdir")
        workflows = loader.list_workflows()
        assert workflows == []

    def test_get_yaml_files(self, temp_workflows_dir):
        """YAMLファイル一覧の取得"""
        (temp_workflows_dir / "test1.yaml").write_text("test")
        (temp_workflows_dir / "test2.yml").write_text("test")
        (temp_workflows_dir / "readme.md").write_text("readme")

        loader = WorkflowLoader(temp_workflows_dir)
        files = loader._get_yaml_files()

        assert len(files) == 2
        stems = {f.stem for f in files}
        assert stems == {"test1", "test2"}
