"""
ORBIT Test Suite - File Operations Actions
"""
import pytest
from pathlib import Path

from src.app.actions.file_ops import action_file_write, action_file_read


class TestActionFileWrite:
    """ファイル書き込みアクションのテスト"""

    @pytest.mark.asyncio
    async def test_write_file_absolute_path(self, temp_dir):
        """絶対パスでファイル書き込み"""
        test_file = temp_dir / "test.txt"
        result = await action_file_write(
            {"path": str(test_file), "content": "Hello, World!"},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        assert result["size"] == len("Hello, World!")
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_file_relative_path(self, temp_dir):
        """相対パスでファイル書き込み"""
        result = await action_file_write(
            {"path": "output/test.txt", "content": "Relative path test"},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        test_file = temp_dir / "output" / "test.txt"
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "Relative path test"

    @pytest.mark.asyncio
    async def test_write_file_creates_directories(self, temp_dir):
        """必要なディレクトリを作成して書き込み"""
        result = await action_file_write(
            {"path": "deep/nested/path/test.txt", "content": "Nested"},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        test_file = temp_dir / "deep" / "nested" / "path" / "test.txt"
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_write_file_overwrites_existing(self, temp_dir):
        """既存ファイルを上書き"""
        test_file = temp_dir / "overwrite.txt"
        test_file.write_text("Original content", encoding="utf-8")

        result = await action_file_write(
            {"path": str(test_file), "content": "New content"},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        assert test_file.read_text(encoding="utf-8") == "New content"

    @pytest.mark.asyncio
    async def test_write_file_empty_content(self, temp_dir):
        """空内容の書き込み"""
        test_file = temp_dir / "empty.txt"
        result = await action_file_write(
            {"path": str(test_file), "content": ""},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        assert result["size"] == 0
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_write_file_unicode_content(self, temp_dir):
        """Unicode文字の書き込み"""
        test_file = temp_dir / "unicode.txt"
        result = await action_file_write(
            {"path": str(test_file), "content": "日本語 🎉 Ñoño"},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        content = test_file.read_text(encoding="utf-8")
        assert content == "日本語 🎉 Ñoño"

    @pytest.mark.asyncio
    async def test_write_file_multiline_content(self, temp_dir):
        """複数行内容の書き込み"""
        test_file = temp_dir / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3"
        result = await action_file_write(
            {"path": str(test_file), "content": content},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        assert test_file.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_write_file_missing_path(self, temp_dir):
        """path未指定時はエラー"""
        with pytest.raises(ValueError, match="path is required"):
            await action_file_write(
                {"content": "Test"},
                {"base_dir": temp_dir}
            )

    @pytest.mark.asyncio
    async def test_write_file_custom_encoding(self, temp_dir):
        """カスタムエンコーディングで書き込み"""
        test_file = temp_dir / "encoding.txt"
        result = await action_file_write(
            {"path": str(test_file), "content": "Shift-JIS text", "encoding": "shift-jis"},
            {"base_dir": temp_dir}
        )
        assert result["written"] is True
        # shift-jisで読み込めることを確認
        content = test_file.read_text(encoding="shift-jis")
        assert content == "Shift-JIS text"


class TestActionFileRead:
    """ファイル読み込みアクションのテスト"""

    @pytest.mark.asyncio
    async def test_read_file_absolute_path(self, temp_dir):
        """絶対パスでファイル読み込み"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        result = await action_file_read(
            {"path": str(test_file)},
            {"base_dir": temp_dir}
        )
        assert result["content"] == "Hello, World!"
        assert result["size"] == len("Hello, World!")

    @pytest.mark.asyncio
    async def test_read_file_relative_path(self, temp_dir):
        """相対パスでファイル読み込み"""
        test_file = temp_dir / "subdir" / "test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Relative path content", encoding="utf-8")

        result = await action_file_read(
            {"path": "subdir/test.txt"},
            {"base_dir": temp_dir}
        )
        assert result["content"] == "Relative path content"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_dir):
        """存在しないファイルの読み込みはエラー"""
        with pytest.raises(FileNotFoundError, match="File not found"):
            await action_file_read(
                {"path": "nonexistent.txt"},
                {"base_dir": temp_dir}
            )

    @pytest.mark.asyncio
    async def test_read_file_empty(self, temp_dir):
        """空ファイルの読み込み"""
        test_file = temp_dir / "empty.txt"
        test_file.write_text("", encoding="utf-8")

        result = await action_file_read(
            {"path": str(test_file)},
            {"base_dir": temp_dir}
        )
        assert result["content"] == ""
        assert result["size"] == 0

    @pytest.mark.asyncio
    async def test_read_file_unicode(self, temp_dir):
        """Unicode文字の読み込み"""
        test_file = temp_dir / "unicode.txt"
        content = "日本語 🎉 Ñoño"
        test_file.write_text(content, encoding="utf-8")

        result = await action_file_read(
            {"path": str(test_file)},
            {"base_dir": temp_dir}
        )
        assert result["content"] == content

    @pytest.mark.asyncio
    async def test_read_file_multiline(self, temp_dir):
        """複数行ファイルの読み込み"""
        test_file = temp_dir / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3"
        test_file.write_text(content, encoding="utf-8")

        result = await action_file_read(
            {"path": str(test_file)},
            {"base_dir": temp_dir}
        )
        assert result["content"] == content

    @pytest.mark.asyncio
    async def test_read_file_missing_path(self, temp_dir):
        """path未指定時はエラー"""
        with pytest.raises(ValueError, match="path is required"):
            await action_file_read(
                {},
                {"base_dir": temp_dir}
            )

    @pytest.mark.asyncio
    async def test_read_file_custom_encoding(self, temp_dir):
        """カスタムエンコーディングで読み込み"""
        test_file = temp_dir / "encoding.txt"
        # shift-jisで書き込み
        test_file.write_bytes("Shift-JIS text".encode("shift-jis"))

        result = await action_file_read(
            {"path": str(test_file), "encoding": "shift-jis"},
            {"base_dir": temp_dir}
        )
        assert result["content"] == "Shift-JIS text"

    @pytest.mark.asyncio
    async def test_write_and_read_roundtrip(self, temp_dir):
        """書き込みと読み込みのラウンドトリップ"""
        test_path = temp_dir / "roundtrip.txt"
        original_content = "Original content\nwith newlines"

        # 書き込み
        await action_file_write(
            {"path": str(test_path), "content": original_content},
            {"base_dir": temp_dir}
        )

        # 読み込み
        result = await action_file_read(
            {"path": str(test_path)},
            {"base_dir": temp_dir}
        )

        assert result["content"] == original_content
