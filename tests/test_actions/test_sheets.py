"""
ORBIT Test Suite - Google Sheets Actions
"""
import pytest

from src.app.actions.google_sheets import (
    _format_values_as_text,
    _parse_values_with_header,
    _normalize_spreadsheet_id,
    _parse_sheet_and_range,
)


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

    def test_with_none_values(self):
        """None 値を含む場合"""
        result = _format_values_as_text([
            ["A", None, "C"],
            ["D", "E", None],
        ])
        assert result == "A\t\tC\nD\tE\t"

    def test_with_empty_cells(self):
        """空文字列を含む場合"""
        result = _format_values_as_text([
            ["A", "", "C"],
            ["", "E", "F"],
        ])
        assert result == "A\t\tC\n\tE\tF"


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
            ["Alice", "30", "Tokyo"],
            ["Bob", "25", "Osaka"],
        ], header_row=True)

        assert result["headers"] == ["Name", "Age", "City"]
        assert result["rows"] == [
            {"Name": "Alice", "Age": "30", "City": "Tokyo"},
            {"Name": "Bob", "Age": "25", "City": "Osaka"},
        ]
        assert result["raw"] == [
            ["Name", "Age", "City"],
            ["Alice", "30", "Tokyo"],
            ["Bob", "25", "Osaka"],
        ]
        assert result["text"] == "Name\tAge\tCity\nAlice\t30\tTokyo\nBob\t25\tOsaka"
        assert result["row_count"] == 2
        assert result["col_count"] == 3

    def test_without_header_row(self):
        """ヘッダー行なし"""
        result = _parse_values_with_header([
            ["Alice", "30", "Tokyo"],
            ["Bob", "25", "Osaka"],
        ], header_row=False)

        assert result["headers"] == []
        assert result["rows"] == []
        assert result["raw"] == [
            ["Alice", "30", "Tokyo"],
            ["Bob", "25", "Osaka"],
        ]
        assert result["text"] == "Alice\t30\tTokyo\nBob\t25\tOsaka"
        assert result["row_count"] == 2
        assert result["col_count"] == 3

    def test_uneven_rows(self):
        """行ごとに列数が異なる場合"""
        result = _parse_values_with_header([
            ["A", "B", "C"],
            ["X", "Y"],  # 1列少ない
            ["P", "Q", "R", "S"],  # 1列多い
        ], header_row=False)

        assert result["row_count"] == 3
        assert result["col_count"] == 4  # 最大列数

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


class TestNormalizeSpreadsheetId:
    """Spreadsheet ID 正規化のテスト"""

    def test_id_only(self):
        """IDのみ"""
        assert _normalize_spreadsheet_id("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms") == \
               "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    def test_full_url(self):
        """完全なURLからIDを抽出"""
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
        assert _normalize_spreadsheet_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    def test_url_without_edit(self):
        """editなしのURL"""
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        assert _normalize_spreadsheet_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    def test_invalid_url_raises(self):
        """無効なURLはエラー"""
        with pytest.raises(ValueError, match="Google Sheets の URL ではありません"):
            _normalize_spreadsheet_id("https://example.com")

    def test_empty_id_raises(self):
        """空文字列はエラー"""
        with pytest.raises(ValueError, match="空です"):
            _normalize_spreadsheet_id("")


class TestParseSheetAndRange:
    """シート名と範囲の解析テスト"""

    def test_range_with_sheet(self):
        """range にシート名が含まれる場合"""
        result = _parse_sheet_and_range(None, "Sheet1!A1:D10")
        assert result == "Sheet1!A1:D10"

    def test_range_without_sheet(self):
        """range にシート名が含まれない場合"""
        result = _parse_sheet_and_range(None, "A1:D10")
        assert result == "A1:D10"

    def test_sheet_param_takes_precedence(self):
        """sheet パラメータが優先される"""
        result = _parse_sheet_and_range("MySheet", "Sheet1!A1:D10")
        assert result == "MySheet!A1:D10"

    def test_sheet_param_with_simple_range(self):
        """sheet パラメータと簡易範囲"""
        result = _parse_sheet_and_range("MySheet", "A1:D10")
        assert result == "MySheet!A1:D10"

    def test_sheet_param_none_with_simple_range(self):
        """sheet パラメータなしと簡易範囲"""
        result = _parse_sheet_and_range(None, "A1:D10")
        assert result == "A1:D10"
