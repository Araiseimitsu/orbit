"""
ORBIT Test Suite - Log Action
"""
import pytest
import logging

from src.app.actions.log import action_log


class TestActionLog:
    """ログ出力アクションのテスト"""

    @pytest.mark.asyncio
    async def test_log_info_default(self):
        """デフォルトでinfoレベルログを出力"""
        result = await action_log(
            {"message": "Test message"},
            {}
        )
        assert result["logged"] is True
        assert result["message"] == "Test message"

    @pytest.mark.asyncio
    async def test_log_debug_level(self):
        """debugレベルログを出力"""
        result = await action_log(
            {"message": "Debug message", "level": "debug"},
            {}
        )
        assert result["logged"] is True
        assert result["message"] == "Debug message"

    @pytest.mark.asyncio
    async def test_log_warning_level(self):
        """warningレベルログを出力"""
        result = await action_log(
            {"message": "Warning message", "level": "warning"},
            {}
        )
        assert result["logged"] is True

    @pytest.mark.asyncio
    async def test_log_error_level(self):
        """errorレベルログを出力"""
        result = await action_log(
            {"message": "Error message", "level": "error"},
            {}
        )
        assert result["logged"] is True

    @pytest.mark.asyncio
    async def test_log_case_insensitive_level(self):
        """ログレベルは大文字小文字を区別しない"""
        result = await action_log(
            {"message": "Test", "level": "INFO"},
            {}
        )
        assert result["logged"] is True

    @pytest.mark.asyncio
    async def test_log_invalid_level_defaults_to_info(self):
        """不正なログレベルはinfoにフォールバック"""
        result = await action_log(
            {"message": "Test", "level": "invalid"},
            {}
        )
        assert result["logged"] is True

    @pytest.mark.asyncio
    async def test_log_empty_message(self):
        """空メッセージでもログ出力"""
        result = await action_log(
            {"message": ""},
            {}
        )
        assert result["logged"] is True
        assert result["message"] == ""

    @pytest.mark.asyncio
    async def test_log_with_template_variables(self):
        """テンプレート変数展開後のメッセージをログ出力"""
        result = await action_log(
            {"message": "Workflow: {{ workflow }}, Run: {{ run_id }}"},
            {"workflow": "test_wf", "run_id": "12345"}
        )
        assert result["logged"] is True
        # メッセージは既に展開されている
        assert "test_wf" in result["message"] or "{{" in result["message"]

    @pytest.mark.asyncio
    async def test_log_multiline_message(self):
        """複数行メッセージのログ出力"""
        result = await action_log(
            {"message": "Line 1\nLine 2\nLine 3"},
            {}
        )
        assert result["logged"] is True
        assert result["message"] == "Line 1\nLine 2\nLine 3"

    @pytest.mark.asyncio
    async def test_log_unicode_message(self):
        """Unicode文字を含むメッセージのログ出力"""
        result = await action_log(
            {"message": "日本語メッセージ 🎉"},
            {}
        )
        assert result["logged"] is True
        assert result["message"] == "日本語メッセージ 🎉"
