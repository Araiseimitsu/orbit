"""
ORBIT Test Suite - Template Rendering
"""
import pytest

from src.app.core.templating import (
    render_string,
    render_value,
    render_params,
)


class TestRenderString:
    """文字列レンダリングのテスト"""

    def test_render_string_simple_variable(self):
        """単純な変数展開"""
        result = render_string("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"

    def test_render_string_multiple_variables(self):
        """複数の変数展開"""
        result = render_string(
            "{{ greeting }} {{ name }}!",
            {"greeting": "Hello", "name": "World"}
        )
        assert result == "Hello World!"

    def test_render_string_no_template(self):
        """テンプレートなしの文字列はそのまま返す"""
        result = render_string("Plain text", {"name": "World"})
        assert result == "Plain text"

    def test_render_string_missing_variable(self):
        """未定義変数は空文字に置換される（Jinja2デフォルト動作）"""
        result = render_string("Hello {{ missing }}", {})
        # Jinja2のデフォルト動作では未定義変数は空文字になる
        assert result == "Hello "

    def test_render_string_nested_variable(self):
        """ネストした変数展開"""
        result = render_string(
            "{{ user.name }}",
            {"user": {"name": "Alice"}}
        )
        assert result == "Alice"

    def test_render_string_with_filter(self):
        """Jinja2フィルターを使用"""
        result = render_string(
            "{{ name | upper }}",
            {"name": "alice"}
        )
        assert result == "ALICE"

    def test_render_string_expression(self):
        """式を含むテンプレート"""
        result = render_string(
            "Count: {{ items | length }}",
            {"items": [1, 2, 3, 4, 5]}
        )
        assert result == "Count: 5"

    def test_render_string_condition(self):
        """条件式を含むテンプレート"""
        result = render_string(
            "{% if show %}Visible{% else %}Hidden{% endif %}",
            {"show": True}
        )
        assert result == "Visible"

    def test_render_string_special_characters(self):
        """特殊文字を含む文字列"""
        result = render_string(
            "Path: {{ path }}",
            {"path": "C:\\Users\\test"}
        )
        assert result == "Path: C:\\Users\\test"


class TestRenderValue:
    """値レンダリングのテスト"""

    def test_render_value_string(self):
        """文字列値のレンダリング"""
        result = render_value("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"

    def test_render_value_int(self):
        """整数値はそのまま返す"""
        result = render_value(42, {"name": "World"})
        assert result == 42

    def test_render_value_float(self):
        """浮動小数点数値はそのまま返す"""
        result = render_value(3.14, {})
        assert result == 3.14

    def test_render_value_bool(self):
        """真偽値はそのまま返す"""
        result = render_value(True, {})
        assert result is True

    def test_render_value_none(self):
        """Noneはそのまま返す"""
        result = render_value(None, {})
        assert result is None

    def test_render_value_dict(self):
        """辞書の再帰的レンダリング"""
        result = render_value(
            {
                "greeting": "Hello {{ name }}",
                "count": "{{ count }}",
                "nested": {
                    "message": "{{ outer }} {{ inner }}"
                }
            },
            {"name": "World", "count": "42", "outer": "A", "inner": "B"}
        )
        assert result == {
            "greeting": "Hello World",
            "count": "42",
            "nested": {
                "message": "A B"
            }
        }

    def test_render_value_list(self):
        """リストの再帰的レンダリング"""
        result = render_value(
            ["{{ a }}", "{{ b }}", "static"],
            {"a": "1", "b": "2"}
        )
        assert result == ["1", "2", "static"]

    def test_render_value_nested_list(self):
        """ネストしたリストのレンダリング"""
        result = render_value(
            [["{{ a }}", "{{ b }}"], ["{{ c }}"]],
            {"a": "1", "b": "2", "c": "3"}
        )
        assert result == [["1", "2"], ["3"]]

    def test_render_value_list_of_dicts(self):
        """辞書のリストのレンダリング"""
        result = render_value(
            [
                {"name": "{{ name1 }}", "value": "{{ val1 }}"},
                {"name": "{{ name2 }}", "value": "{{ val2 }}"},
            ],
            {"name1": "A", "val1": "1", "name2": "B", "val2": "2"}
        )
        assert result == [
            {"name": "A", "value": "1"},
            {"name": "B", "value": "2"},
        ]

    def test_render_value_empty_dict(self):
        """空辞書のレンダリング"""
        result = render_value({}, {})
        assert result == {}

    def test_render_value_empty_list(self):
        """空リストのレンダリング"""
        result = render_value([], {})
        assert result == []


class TestRenderParams:
    """パラメータレンダリングのテスト"""

    def test_render_params_simple(self):
        """単純なパラメータレンダリング"""
        params = {"message": "Hello {{ name }}"}
        result = render_params(params, {"name": "World"})
        assert result == {"message": "Hello World"}

    def test_render_params_multiple_fields(self):
        """複数フィールドのレンダリング"""
        params = {
            "greeting": "Hello {{ name }}",
            "farewell": "Goodbye {{ name }}",
            "static": "unchanged",
        }
        result = render_params(params, {"name": "World"})
        assert result == {
            "greeting": "Hello World",
            "farewell": "Goodbye World",
            "static": "unchanged",
        }

    def test_render_params_with_workflow_context(self):
        """ワークフロー変数を含むレンダリング"""
        params = {
            "message": "Workflow: {{ workflow }}, Run: {{ run_id }}"
        }
        result = render_params(
            params,
            {"workflow": "test_wf", "run_id": "20250115_103000_abcd"}
        )
        assert result == {
            "message": "Workflow: test_wf, Run: 20250115_103000_abcd"
        }

    def test_render_params_with_base_dir(self):
        """base_dir変数を含むレンダリング"""
        params = {"path": "{{ base_dir }}/output.txt"}
        result = render_params(params, {"base_dir": "/home/user"})
        assert result == {"path": "/home/user/output.txt"}

    def test_render_params_with_step_reference(self):
        """ステップ結果を参照するレンダリング"""
        params = {"content": "Previous: {{ step1.result }}"}
        result = render_params(
            params,
            {"step1": {"result": "Success"}}
        )
        assert result == {"content": "Previous: Success"}

    def test_render_params_complex_structure(self):
        """複雑な構造のパラメータレンダリング"""
        params = {
            "files": [
                "{{ base_dir }}/file1.txt",
                "{{ base_dir }}/file2.txt",
            ],
            "options": {
                "output": "{{ run_id }}.txt",
                "verbose": True,
            },
        }
        result = render_params(
            params,
            {"base_dir": "/tmp", "run_id": "test_run"}
        )
        assert result == {
            "files": ["/tmp/file1.txt", "/tmp/file2.txt"],
            "options": {"output": "test_run.txt", "verbose": True},
        }

    def test_render_params_preserves_non_string_types(self):
        """文字列以外の型を保持する"""
        params = {
            "count": 5,
            "enabled": True,
            "ratio": 0.75,
        }
        result = render_params(params, {})
        assert result == params

    def test_render_params_with_empty_string_value(self):
        """空文字列値のレンダリング"""
        params = {"message": ""}
        result = render_params(params, {})
        assert result == {"message": ""}

    def test_render_params_with_none_value(self):
        """None値のレンダリング"""
        params = {"value": None}
        result = render_params(params, {})
        assert result == {"value": None}
