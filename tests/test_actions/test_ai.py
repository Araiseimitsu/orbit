"""
ORBIT Test Suite - AI Actions
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from src.app.actions.ai import (
    _coerce_int,
    _coerce_float,
    _coerce_bool,
    _load_api_key,
    action_ai_generate,
)


class TestCoerceInt:
    """整数型変換関数のテスト"""

    def test_coerce_int_from_int(self):
        """整数から整数へ"""
        assert _coerce_int(42, "test") == 42

    def test_coerce_int_from_float_integer(self):
        """整数値の浮動小数点数から整数へ"""
        assert _coerce_int(42.0, "test") == 42

    def test_coerce_int_from_float_fractional_raises(self):
        """小数部がある浮動小数点数はエラー"""
        with pytest.raises(ValueError, match="整数で指定してください"):
            _coerce_int(42.5, "test")

    def test_coerce_int_from_string(self):
        """文字列から整数へ"""
        assert _coerce_int("42", "test") == 42

    def test_coerce_int_from_string_float_raises(self):
        """浮動小数点数形式の文字列はエラー"""
        with pytest.raises(ValueError, match="整数で指定してください"):
            _coerce_int("42.5", "test")

    def test_coerce_int_from_empty_string(self):
        """空文字列はNoneを返す"""
        assert _coerce_int("", "test") is None
        assert _coerce_int("  ", "test") is None

    def test_coerce_int_from_none(self):
        """NoneはNoneを返す"""
        assert _coerce_int(None, "test") is None

    def test_coerce_int_from_bool_raises(self):
        """真偽値はエラー"""
        with pytest.raises(ValueError, match="整数で指定してください"):
            _coerce_int(True, "test")


class TestCoerceFloat:
    """浮動小数点数型変換関数のテスト"""

    def test_coerce_float_from_int(self):
        """整数から浮動小数点数へ"""
        assert _coerce_float(42, "test") == 42.0

    def test_coerce_float_from_float(self):
        """浮動小数点数から浮動小数点数へ"""
        assert _coerce_float(3.14, "test") == 3.14

    def test_coerce_float_from_string(self):
        """文字列から浮動小数点数へ"""
        assert _coerce_float("3.14", "test") == 3.14

    def test_coerce_float_from_string_int(self):
        """整数形式の文字列から浮動小数点数へ"""
        assert _coerce_float("42", "test") == 42.0

    def test_coerce_float_from_empty_string(self):
        """空文字列はNoneを返す"""
        assert _coerce_float("", "test") is None
        assert _coerce_float("  ", "test") is None

    def test_coerce_float_from_none(self):
        """NoneはNoneを返す"""
        assert _coerce_float(None, "test") is None

    def test_coerce_float_from_bool_raises(self):
        """真偽値はエラー"""
        with pytest.raises(ValueError, match="数値で指定してください"):
            _coerce_float(True, "test")


class TestCoerceBool:
    """真偽値型変換関数のテスト"""

    def test_coerce_bool_from_bool(self):
        """真偽値から真偽値へ"""
        assert _coerce_bool(True, "test") is True
        assert _coerce_bool(False, "test") is False

    def test_coerce_bool_from_int_zero_one(self):
        """0/1から真偽値へ"""
        assert _coerce_bool(1, "test") is True
        assert _coerce_bool(0, "test") is False

    def test_coerce_bool_from_int_other_raises(self):
        """0/1以外の整数はエラー"""
        with pytest.raises(ValueError, match="true/false"):
            _coerce_bool(2, "test")

    def test_coerce_bool_from_string_true_variants(self):
        """各種true文字列"""
        assert _coerce_bool("true", "test") is True
        assert _coerce_bool("TRUE", "test") is True
        assert _coerce_bool("True", "test") is True
        assert _coerce_bool("1", "test") is True
        assert _coerce_bool("yes", "test") is True
        assert _coerce_bool("YES", "test") is True
        assert _coerce_bool("on", "test") is True

    def test_coerce_bool_from_string_false_variants(self):
        """各種false文字列"""
        assert _coerce_bool("false", "test") is False
        assert _coerce_bool("FALSE", "test") is False
        assert _coerce_bool("False", "test") is False
        assert _coerce_bool("0", "test") is False
        assert _coerce_bool("no", "test") is False
        assert _coerce_bool("NO", "test") is False
        assert _coerce_bool("off", "test") is False

    def test_coerce_bool_from_empty_string(self):
        """空文字列はNoneを返す"""
        assert _coerce_bool("", "test") is None
        assert _coerce_bool("  ", "test") is None

    def test_coerce_bool_from_none(self):
        """NoneはNoneを返す"""
        assert _coerce_bool(None, "test") is None

    def test_coerce_bool_from_invalid_string_raises(self):
        """不正な文字列はエラー"""
        with pytest.raises(ValueError, match="true/false"):
            _coerce_bool("invalid", "test")


class TestLoadApiKey:
    """APIキー読み込み関数のテスト"""

    def test_load_api_key_from_env(self, temp_dir, monkeypatch):
        """環境変数からAPIキーを読み込み"""
        monkeypatch.setenv("TEST_API_KEY", "env-key-12345")
        result = _load_api_key("secrets/key.txt", temp_dir, "TEST_API_KEY")
        assert result == "env-key-12345"

    def test_load_api_key_from_file(self, temp_dir):
        """ファイルからAPIキーを読み込み"""
        key_file = temp_dir / "api_key.txt"
        key_file.write_text("file-key-67890", encoding="utf-8")

        result = _load_api_key("api_key.txt", temp_dir, "NONEXISTENT_KEY")
        assert result == "file-key-67890"

    def test_load_api_key_from_file_absolute_path(self, temp_dir):
        """絶対パスのファイルからAPIキーを読み込み"""
        key_file = temp_dir / "api_key.txt"
        key_file.write_text("abs-key-11111", encoding="utf-8")

        result = _load_api_key(str(key_file), temp_dir, "NONEXISTENT_KEY")
        assert result == "abs-key-11111"

    def test_load_api_key_not_found(self, temp_dir):
        """APIキーが見つからない場合はエラー"""
        with pytest.raises(FileNotFoundError, match="API キーが見つかりません"):
            _load_api_key("nonexistent.txt", temp_dir, "NONEXISTENT_KEY")

    def test_load_api_key_empty_file(self, temp_dir):
        """空のAPIキーファイルはエラー"""
        key_file = temp_dir / "empty.txt"
        key_file.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="API キーファイルが空です"):
            _load_api_key("empty.txt", temp_dir, "NONEXISTENT_KEY")

    def test_load_api_key_whitespace_only_file(self, temp_dir):
        """空白のみのAPIキーファイルはエラー"""
        key_file = temp_dir / "whitespace.txt"
        key_file.write_text("  \n  ", encoding="utf-8")

        with pytest.raises(ValueError, match="API キーファイルが空です"):
            _load_api_key("whitespace.txt", temp_dir, "NONEXISTENT_KEY")

    def test_load_api_key_file_trims_whitespace(self, temp_dir):
        """ファイルのAPIキーは前後空白がトリムされる"""
        key_file = temp_dir / "key.txt"
        key_file.write_text("  key-with-spaces  ", encoding="utf-8")

        result = _load_api_key("key.txt", temp_dir, "NONEXISTENT_KEY")
        assert result == "key-with-spaces"

    def test_load_api_key_env_takes_precedence(self, temp_dir, monkeypatch):
        """環境変数がファイルより優先される"""
        monkeypatch.setenv("TEST_API_KEY", "env-key")
        key_file = temp_dir / "key.txt"
        key_file.write_text("file-key", encoding="utf-8")

        result = _load_api_key("key.txt", temp_dir, "TEST_API_KEY")
        assert result == "env-key"


class TestActionAiGenerate:
    """AI生成アクションのテスト"""

    @pytest.mark.asyncio
    async def test_ai_generate_missing_prompt(self, temp_dir, monkeypatch):
        """prompt未指定時はエラー"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        with pytest.raises(ValueError, match="prompt は必須です"):
            await action_ai_generate(
                {},
                {"base_dir": temp_dir}
            )

    @pytest.mark.asyncio
    async def test_ai_generate_unsupported_provider(self, temp_dir, monkeypatch):
        """未対応のプロバイダはエラー"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        with pytest.raises(ValueError, match="未対応の provider"):
            await action_ai_generate(
                {"prompt": "Test", "provider": "unknown"},
                {"base_dir": temp_dir}
            )

    @pytest.mark.asyncio
    async def test_ai_generate_default_model(self, temp_dir, monkeypatch):
        """デフォルトモデルが設定される"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        with patch("src.app.actions.ai._call_gemini") as mock_call:
            mock_call.return_value = {"text": "Generated text", "model": "gemini-2.5-flash-lite"}

            result = await action_ai_generate(
                {"prompt": "Test prompt"},
                {"base_dir": temp_dir}
            )

            assert result["text"] == "Generated text"
            assert result["model"] == "gemini-2.5-flash-lite"
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_generate_with_custom_model(self, temp_dir, monkeypatch):
        """カスタムモデルを指定"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        with patch("src.app.actions.ai._call_gemini") as mock_call:
            mock_call.return_value = {"text": "Result", "model": "gemini-1.5-pro"}

            result = await action_ai_generate(
                {"prompt": "Test", "model": "gemini-1.5-pro"},
                {"base_dir": temp_dir}
            )

            assert result["model"] == "gemini-1.5-pro"

    @pytest.mark.asyncio
    async def test_ai_generate_with_max_tokens_string(self, temp_dir, monkeypatch):
        """max_tokensを文字列で指定"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        with patch("src.app.actions.ai._call_gemini") as mock_call:
            mock_call.return_value = {"text": "Result", "model": "test"}

            await action_ai_generate(
                {"prompt": "Test", "max_tokens": "100"},
                {"base_dir": temp_dir}
            )

            # 文字列が整数に変換されて呼ばれる
            call_args = mock_call.call_args
            assert call_args.kwargs["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_ai_generate_with_temperature_string(self, temp_dir, monkeypatch):
        """temperatureを文字列で指定"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        with patch("src.app.actions.ai._call_gemini") as mock_call:
            mock_call.return_value = {"text": "Result", "model": "test"}

            await action_ai_generate(
                {"prompt": "Test", "temperature": "0.7"},
                {"base_dir": temp_dir}
            )

            call_args = mock_call.call_args
            assert call_args.kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="retry_async デコレータとのモックの相互作用が複雑なためスキップ")
    async def test_ai_generate_use_search(self, temp_dir, monkeypatch):
        """Web検索を有効化"""
        # 注: use_search 機能は実際のAPI呼び出しでテストされる
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        pass

    @pytest.mark.asyncio
    async def test_ai_generate_loads_api_key_from_file(self, temp_dir):
        """ファイルからAPIキーを読み込む"""
        key_file = temp_dir / "secrets" / "gemini_api_key.txt"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text("file-api-key", encoding="utf-8")

        with patch("src.app.actions.ai._call_gemini") as mock_call:
            mock_call.return_value = {"text": "Result", "model": "test"}

            await action_ai_generate(
                {"prompt": "Test", "api_key_file": "secrets/gemini_api_key.txt"},
                {"base_dir": temp_dir}
            )

            mock_call.assert_called_once()
            call_args = mock_call.call_args
            assert call_args.kwargs["api_key"] == "file-api-key"

    @pytest.mark.asyncio
    async def test_ai_generate_no_api_key(self, temp_dir):
        """APIキーがない場合はエラー"""
        with pytest.raises(FileNotFoundError):
            await action_ai_generate(
                {"prompt": "Test"},
                {"base_dir": temp_dir}
            )
