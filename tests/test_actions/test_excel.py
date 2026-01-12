"""
ORBIT Test Suite - Excel Actions
"""
import pytest

from src.app.actions.excel import (
    _format_values_as_text,
    _parse_values_with_header,
    _normalize_cell_value,
)


class TestNormalizeCellValue:
    """セル値正規化のテスト"""

    def test_none_value(self):
        """None は空文字列に"""
        assert _normalize_cell_value(None) == ""

    def test_datetime_value(self):
        """datetime は YYYY/MM/DD 形式に"""
        from datetime import datetime
        dt = datetime(2025, 1, 15, 10, 30, 0)
        assert _normalize_cell_value(dt) == "2025/01/15"

    def test_date_value(self):
        """date は YYYY/MM/DD 形式に"""
        from datetime import date
        d = date(2025, 1, 15)
        assert _normalize_cell_value(d) == "2025/01/15"

    def test_string_value(self):
        """文字列はそのまま"""
        assert _normalize_cell_value("hello") == "hello"

    def test_int_value(self):
        """整数はそのまま"""
        assert _normalize_cell_value(42) == 42


class TestFormatValuesAsText:
    """2次元配列をテキストに変換する関数のテスト"""

    def test_empty_values(self):
        """空の配列"""
        assert _format_values_as_text([]) == ""

    def test_single_row(self):
        """1行のみ"""
        result = _format_values_as_text([["A", "B", "C"]])
        assert result == "A\tB\tC"

    def test_multiple_rows(self):
        """複数行"""
        result = _format_values_as_text([
            ["Header1", "Header2", "Header3"],
            ["Data1", "Data2", "Data3"],
            ["Data4", "Data5", "Data6"],
        ])
        assert result == "Header1\tHeader2\tHeader3\nData1\tData2\tData3\nData4\tData5\tData6"

    def test_with_normalized_dates(self):
        """日付形式（正規化済み）を含む場合"""
        result = _format_values_as_text([
            ["Name", "Date"],
            ["Alice", "2025/01/15"],
            ["Bob", "2025/01/16"],
        ])
        assert result == "Name\tDate\nAlice\t2025/01/15\nBob\t2025/01/16"


class TestParseValuesWithHeader:
    """値を解析してヘッダー付きの dict 形式に変換するテスト"""

    def test_empty_values(self):
        """空の配列"""
        result = _parse_values_with_header([], header_row=True)
        assert result == {
            "headers": [],
            "rows": [],
            "raw": [],
            "text": "",
            "row_count": 0,
            "col_count": 0,
        }

    def test_with_header_row(self):
        """ヘッダー行あり"""
        result = _parse_values_with_header([
            ["Name", "Age", "City"],
            ["Alice", 30, "Tokyo"],
            ["Bob", 25, "Osaka"],
        ], header_row=True)

        assert result["headers"] == ["Name", "Age", "City"]
        assert result["rows"] == [
            {"Name": "Alice", "Age": 30, "City": "Tokyo"},
            {"Name": "Bob", "Age": 25, "City": "Osaka"},
        ]
        assert result["raw"] == [
            ["Name", "Age", "City"],
            ["Alice", 30, "Tokyo"],
            ["Bob", 25, "Osaka"],
        ]
        assert result["text"] == "Name\tAge\tCity\nAlice\t30\tTokyo\nBob\t25\tOsaka"
        assert result["row_count"] == 2
        assert result["col_count"] == 3

    def test_without_header_row(self):
        """ヘッダー行なし"""
        result = _parse_values_with_header([
            ["Alice", 30, "Tokyo"],
            ["Bob", 25, "Osaka"],
        ], header_row=False)

        assert result["headers"] == []
        assert result["rows"] == []
        assert result["raw"] == [
            ["Alice", 30, "Tokyo"],
            ["Bob", 25, "Osaka"],
        ]
        assert result["text"] == "Alice\t30\tTokyo\nBob\t25\tOsaka"
        assert result["row_count"] == 2
        assert result["col_count"] == 3

    def test_text_is_tab_separated(self):
        """text 出力がタブ区切りであること"""
        result = _parse_values_with_header([
            ["H1", "H2"],
            ["v1", "v2"],
        ], header_row=True)

        # タブ区切りで確認
        lines = result["text"].split("\n")
        assert lines[0] == "H1\tH2"
        assert lines[1] == "v1\tv2"
