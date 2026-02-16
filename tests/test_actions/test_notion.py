"""
ORBIT Test Suite - Notion Actions
"""

from src.app.actions.notion import _normalize_filter_simple, _normalize_properties_simple


class TestNormalizeFilterSimple:
    """filter_simple 正規化のテスト"""

    def test_date_equals_iso_format(self):
        """YYYY-MM-DD は date.equals に変換される"""
        result = _normalize_filter_simple({"セット日": "2026-02-12"})
        assert result == {
            "property": "セット日",
            "date": {"equals": "2026-02-12"},
        }

    def test_date_compare_iso_format(self):
        """比較演算子つき YYYY-MM-DD は date 比較に変換される"""
        result = _normalize_filter_simple({"セット日": ">=2026-02-12"})
        assert result == {
            "property": "セット日",
            "date": {"on_or_after": "2026-02-12"},
        }

    def test_date_equals_japanese_format_is_not_date(self):
        """YYYY年M月D日 は date としては扱わない"""
        result = _normalize_filter_simple({"セット日": "2026年2月12日"})
        assert result == {
            "property": "セット日",
            "select": {"equals": "2026年2月12日"},
        }

    def test_non_date_string_remains_select(self):
        """日付でない文字列は select.equals のまま"""
        result = _normalize_filter_simple({"Status": "完了"})
        assert result == {
            "property": "Status",
            "select": {"equals": "完了"},
        }


class TestNormalizePropertiesSimple:
    """properties_simple 正規化のテスト"""

    def test_date_start_iso_format(self):
        """YYYY-MM-DD は date.start に変換される"""
        result = _normalize_properties_simple({"セット日": "2026-02-12"})
        assert result == {
            "セット日": {"date": {"start": "2026-02-12"}},
        }

    def test_date_start_japanese_format_is_not_date(self):
        """YYYY年M月D日 は date としては扱わない"""
        result = _normalize_properties_simple({"セット日": "2026年2月12日"})
        assert result == {
            "セット日": {
                "rich_text": [{"type": "text", "text": {"content": "2026年2月12日"}}]
            },
        }
