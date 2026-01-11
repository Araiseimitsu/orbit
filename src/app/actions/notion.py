"""
Notion 連携アクション

Notion API を使用してデータベース検索やページ作成を行う。

API キー設定:
    環境変数 NOTION_API_KEY または secrets/notion_api_key.txt に Notion API キー

使用例 (YAML):
    # データベース検索（シンプル形式）- 推奨
    - id: query_db
      type: notion_query_database
      params:
        database_id: "0123456789abcdef0123456789abcdef"
        filter_simple:
          Status: "完了"
          Priority: ">5"
          Completed: true
        sorts_simple:
          - Created: desc
          - Priority: asc
        page_size: 50

    # データベース検索（Notion API形式）- 上級者向け
    - id: query_db_advanced
      type: notion_query_database
      params:
        database_id: "0123456789abcdef0123456789abcdef"
        filter: |
          {
            "property": "Status",
            "select": {"equals": "Done"}
          }
        sorts: |
          [
            {"property": "Created", "direction": "descending"}
          ]
        page_size: 50

    # ページ作成（シンプル形式）- 推奨
    - id: create_page
      type: notion_create_page
      params:
        database_id: "0123456789abcdef0123456789abcdef"
        properties_simple:
          Name: "新しいタスク"
          Status: "進行中"
          Priority: 5
          Due: "2026-01-15"
          Completed: false
        content: "これはページの本文です"
        icon: "📝"

    # ページ更新（シンプル形式）- 推奨
    - id: update_page
      type: notion_update_page
      params:
        page_id: "{{ create_page.page_id }}"
        properties_simple:
          Status: "完了"
          Priority: 10
        icon: "✅"

    # ページ作成（Notion API形式）- 上級者向け
    - id: create_page_advanced
      type: notion_create_page
      params:
        database_id: "0123456789abcdef0123456789abcdef"
        properties: |
          {
            "Name": {
              "title": [{"text": {"content": "新しいタスク"}}]
            },
            "Status": {
              "select": {"name": "進行中"}
            }
          }
        content: "これはページの本文です"
        icon: "📝"
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import requests

from ..core.registry import register_action
from ..core.retry import retry_async

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_NOTION_KEY_FILE = "secrets/notion_api_key.txt"
DEFAULT_NOTION_KEY_ENV = "NOTION_API_KEY"
NOTION_API_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_TIMEOUT = 30


def _coerce_int(value: Any, label: str) -> int | None:
    """
    値を int に強制変換

    テンプレート変数からの値を厳密に int に変換する。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} は整数で指定してください")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError(f"{label} は整数で指定してください")
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"{label} は整数で指定してください") from exc
    raise ValueError(f"{label} は整数で指定してください")


def _load_api_key(file_path: str, base_dir: Path, env_var_name: str = "NOTION_API_KEY") -> str:
    """
    API キーを環境変数 → ファイルの順で読み込む

    Args:
        file_path: フォールバック用ファイルパス
        base_dir: ベースディレクトリ
        env_var_name: 環境変数名

    Returns:
        API キー文字列

    Raises:
        FileNotFoundError: 環境変数もファイルも存在しない
        ValueError: APIキーが空
    """
    import os

    # 環境変数を優先
    api_key = os.getenv(env_var_name)
    if api_key:
        api_key = api_key.strip()
        if api_key:
            logger.debug(f"API key loaded from environment variable: {env_var_name}")
            return api_key

    # フォールバック: ファイルから読み込み
    path = Path(file_path)
    if not path.is_absolute():
        path = base_dir / path

    if not path.exists():
        raise FileNotFoundError(
            f"API キーが見つかりません。\n"
            f"環境変数 {env_var_name} またはファイル {path} に設定してください。"
        )

    key = path.read_text().strip()
    if not key:
        raise ValueError(f"API キーファイルが空です: {path}")

    logger.debug(f"API key loaded from file: {path}")
    return key


def _normalize_json(value: Any) -> dict | list | None:
    """
    JSON 文字列を dict/list に正規化

    Args:
        value: JSON 文字列、dict、list、または None

    Returns:
        dict、list、または None

    Raises:
        ValueError: JSON として解析できない
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON として解析できません: {text[:100]}...") from exc
    raise ValueError("辞書、配列、またはJSON文字列で指定してください")


def _normalize_content(content: Any) -> list[dict] | None:
    """
    content パラメータをブロック配列に正規化

    Args:
        content: プレーンテキスト、JSON 文字列、またはブロック配列

    Returns:
        ブロック配列、または None
    """
    if content is None:
        return None

    # すでにブロック配列の場合
    if isinstance(content, list):
        return content

    # JSON 文字列の場合
    if isinstance(content, str):
        text = content.strip()
        if not text:
            return None

        # JSON として解析を試みる
        if text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # プレーンテキストとして扱う（段落ブロックに変換）
        return [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            }
        ]

    raise ValueError("content はブロック配列、JSON文字列、またはプレーンテキストで指定してください")


def _normalize_properties_simple(properties_simple: dict[str, Any]) -> dict[str, Any]:
    """
    シンプルな key-value 形式のプロパティを Notion API 形式に変換

    Args:
        properties_simple: シンプルな辞書（例: {"Name": "タスク名", "Status": "完了"}）

    Returns:
        Notion API 形式のプロパティ辞書

    変換ルール:
        - "Name", "Title", "名前" → title
        - 文字列 → rich_text
        - 数値（int/float） → number
        - 日付文字列（YYYY-MM-DD） → date
        - ブール値 → checkbox
        - リスト → multi_select（文字列リストの場合）
    """
    import re
    from datetime import datetime

    result: dict[str, Any] = {}

    # Title フィールド候補
    TITLE_KEYS = {"name", "title", "名前", "タイトル"}

    for key, value in properties_simple.items():
        if value is None:
            continue

        key_lower = key.lower()

        # Title プロパティ（最優先）
        if key_lower in TITLE_KEYS:
            result[key] = {
                "title": [{"type": "text", "text": {"content": str(value)}}]
            }
        # ブール値 → checkbox
        elif isinstance(value, bool):
            result[key] = {"checkbox": value}
        # 数値 → number
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = {"number": value}
        # リスト → multi_select
        elif isinstance(value, list):
            # 文字列リストの場合
            if all(isinstance(v, str) for v in value):
                result[key] = {
                    "multi_select": [{"name": str(v)} for v in value if v]
                }
            else:
                # 混合型リストは文字列化して rich_text に
                text = ", ".join(str(v) for v in value)
                result[key] = {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                }
        # 文字列
        elif isinstance(value, str):
            value_str = value.strip()
            if not value_str:
                continue

            # 日付形式（YYYY-MM-DD または YYYY-MM-DD HH:MM:SS）
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2}(?::\d{2})?)?$", value_str)
            if date_match:
                try:
                    # 日付バリデーション
                    datetime.fromisoformat(value_str.replace(" ", "T"))
                    # date プロパティ（start のみ）
                    result[key] = {"date": {"start": date_match.group(1)}}
                    continue
                except ValueError:
                    pass

            # 通常の文字列 → rich_text
            result[key] = {
                "rich_text": [{"type": "text", "text": {"content": value_str}}]
            }
        else:
            # その他の型は文字列化
            result[key] = {
                "rich_text": [{"type": "text", "text": {"content": str(value)}}]
            }

    return result


def _normalize_filter_simple(filter_simple: dict[str, Any]) -> dict[str, Any]:
    """
    シンプルな key-value 形式のフィルタを Notion API 形式に変換

    Args:
        filter_simple: シンプルな辞書（例: {"Status": "完了", "Priority": ">5"}）

    Returns:
        Notion API 形式のフィルタ辞書

    変換ルール:
        - "値" → equals
        - ">値" → greater_than
        - ">=値" → greater_than_or_equal_to
        - "<値" → less_than
        - "<=値" → less_than_or_equal_to
        - "!=値" → does_not_equal
        - 複数条件は and で結合
    """
    import re
    from datetime import datetime

    if not filter_simple:
        return {}

    filters = []

    for key, value in filter_simple.items():
        if value is None:
            continue

        filter_obj: dict[str, Any] = {"property": key}

        # ブール値 → checkbox
        if isinstance(value, bool):
            filter_obj["checkbox"] = {"equals": value}
        # 数値 → number
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            filter_obj["number"] = {"equals": value}
        # 文字列
        elif isinstance(value, str):
            value_str = value.strip()
            if not value_str:
                continue

            # 比較演算子を解析
            operator_match = re.match(r"^(>=|<=|>|<|!=)\s*(.+)$", value_str)
            if operator_match:
                operator, operand = operator_match.groups()
                operand = operand.strip()

                # 数値比較
                try:
                    num_value = float(operand)
                    operator_map = {
                        ">": "greater_than",
                        ">=": "greater_than_or_equal_to",
                        "<": "less_than",
                        "<=": "less_than_or_equal_to",
                        "!=": "does_not_equal"
                    }
                    filter_obj["number"] = {operator_map[operator]: num_value}
                except ValueError:
                    # 日付比較
                    if re.match(r"^\d{4}-\d{2}-\d{2}", operand):
                        try:
                            datetime.fromisoformat(operand.replace(" ", "T"))
                            operator_map = {
                                ">": "after",
                                ">=": "on_or_after",
                                "<": "before",
                                "<=": "on_or_before",
                                "!=": "does_not_equal"
                            }
                            filter_obj["date"] = {operator_map[operator]: operand.split()[0]}
                        except ValueError:
                            # 文字列として扱う
                            filter_obj["rich_text"] = {"contains": operand}
                    else:
                        # 文字列として扱う（!= の場合）
                        if operator == "!=":
                            filter_obj["select"] = {"does_not_equal": operand}
                        else:
                            filter_obj["rich_text"] = {"contains": operand}
            else:
                # 演算子なし → equals
                # 日付形式チェック
                if re.match(r"^\d{4}-\d{2}-\d{2}", value_str):
                    try:
                        datetime.fromisoformat(value_str.replace(" ", "T"))
                        filter_obj["date"] = {"equals": value_str.split()[0]}
                    except ValueError:
                        # select として扱う
                        filter_obj["select"] = {"equals": value_str}
                else:
                    # select として扱う（Status, Priority 等）
                    filter_obj["select"] = {"equals": value_str}
        else:
            # その他の型は文字列化して select
            filter_obj["select"] = {"equals": str(value)}

        filters.append(filter_obj)

    # 単一条件の場合はそのまま、複数条件の場合は and で結合
    if len(filters) == 0:
        return {}
    elif len(filters) == 1:
        return filters[0]
    else:
        return {"and": filters}


def _normalize_sorts_simple(sorts_simple: list[dict[str, str]] | list[str]) -> list[dict[str, str]]:
    """
    シンプルなソート指定を Notion API 形式に変換

    Args:
        sorts_simple: シンプルなリスト（例: [{"Created": "desc"}, {"Priority": "asc"}] または ["Created:desc", "Priority"]）

    Returns:
        Notion API 形式のソート配列

    変換ルール:
        - {"プロパティ名": "desc"} → {"property": "プロパティ名", "direction": "descending"}
        - {"プロパティ名": "asc"} → {"property": "プロパティ名", "direction": "ascending"}
        - "プロパティ名:desc" → {"property": "プロパティ名", "direction": "descending"}
        - "プロパティ名" → {"property": "プロパティ名", "direction": "ascending"}（デフォルト）
    """
    if not sorts_simple:
        return []

    result = []

    for sort_item in sorts_simple:
        # 辞書形式
        if isinstance(sort_item, dict):
            for prop_name, direction in sort_item.items():
                direction_str = str(direction).lower()
                if direction_str in ("desc", "descending", "down"):
                    result.append({"property": prop_name, "direction": "descending"})
                else:
                    result.append({"property": prop_name, "direction": "ascending"})
        # 文字列形式
        elif isinstance(sort_item, str):
            # "プロパティ名:desc" 形式
            if ":" in sort_item:
                prop_name, direction = sort_item.split(":", 1)
                prop_name = prop_name.strip()
                direction = direction.strip().lower()
                if direction in ("desc", "descending", "down"):
                    result.append({"property": prop_name, "direction": "descending"})
                else:
                    result.append({"property": prop_name, "direction": "ascending"})
            else:
                # プロパティ名のみ → 昇順
                result.append({"property": sort_item.strip(), "direction": "ascending"})

    return result


def _extract_error_detail(response: requests.Response | None) -> str:
    """
    Notion API エラーレスポンスから詳細メッセージを抽出

    Args:
        response: requests.Response オブジェクト

    Returns:
        エラー詳細メッセージ
    """
    if response is None:
        return ""
    try:
        payload = response.json()
    except ValueError:
        return (response.text or "").strip()

    if isinstance(payload, dict):
        # Notion API は "message" キーにエラー詳細を返す
        return str(payload.get("message") or "").strip()
    return ""


def _build_headers(api_key: str) -> dict[str, str]:
    """
    Notion API リクエストヘッダーを構築

    Args:
        api_key: Notion API キー

    Returns:
        ヘッダー辞書
    """
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


@retry_async(
    max_attempts=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(
        requests.exceptions.RequestException,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ),
)
async def _query_database(
    database_id: str,
    api_key: str,
    filter_obj: dict | None = None,
    sorts: list | None = None,
    page_size: int = 100,
    start_cursor: str | None = None,
) -> dict[str, Any]:
    """
    Notion データベースを検索（リトライ付き）

    Args:
        database_id: データベースID
        api_key: Notion API キー
        filter_obj: フィルタ条件
        sorts: ソート条件
        page_size: 取得件数（最大100）
        start_cursor: ページネーション用カーソル

    Returns:
        Notion API レスポンス

    Raises:
        requests.HTTPError: API エラー
    """
    loop = asyncio.get_event_loop()

    def _do_request():
        url = f"{NOTION_API_BASE}/databases/{database_id}/query"
        headers = _build_headers(api_key)
        payload: dict[str, Any] = {"page_size": page_size}

        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    return await loop.run_in_executor(None, _do_request)


@retry_async(
    max_attempts=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(
        requests.exceptions.RequestException,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ),
)
async def _create_page(
    database_id: str,
    properties: dict,
    api_key: str,
    children: list[dict] | None = None,
    icon: str | None = None,
    cover: str | None = None,
) -> dict[str, Any]:
    """
    Notion ページを作成（リトライ付き）

    Args:
        database_id: 親データベースID
        properties: ページプロパティ
        api_key: Notion API キー
        children: ページ本文（ブロック配列）
        icon: アイコン（emoji または URL）
        cover: カバー画像URL

    Returns:
        Notion API レスポンス

    Raises:
        requests.HTTPError: API エラー
    """
    loop = asyncio.get_event_loop()

    def _do_request():
        url = f"{NOTION_API_BASE}/pages"
        headers = _build_headers(api_key)
        payload: dict[str, Any] = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }

        if children:
            payload["children"] = children

        if icon:
            # emoji または URL
            if len(icon) <= 2:  # emoji
                payload["icon"] = {"type": "emoji", "emoji": icon}
            else:  # URL
                payload["icon"] = {"type": "external", "external": {"url": icon}}

        if cover:
            payload["cover"] = {"type": "external", "external": {"url": cover}}

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    return await loop.run_in_executor(None, _do_request)


@retry_async(
    max_attempts=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(
        requests.exceptions.RequestException,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ),
)
async def _update_page(
    page_id: str,
    properties: dict | None,
    api_key: str,
    archived: bool | None = None,
    icon: str | None = None,
    cover: str | None = None,
) -> dict[str, Any]:
    """
    Notion ページを更新（リトライ付き）

    Args:
        page_id: ページID
        properties: 更新するプロパティ（None の場合更新しない）
        api_key: Notion API キー
        archived: アーカイブ（削除）フラグ
        icon: アイコン（emoji または URL）
        cover: カバー画像URL

    Returns:
        Notion API レスポンス

    Raises:
        requests.HTTPError: API エラー
    """
    loop = asyncio.get_event_loop()

    def _do_request():
        url = f"{NOTION_API_BASE}/pages/{page_id}"
        headers = _build_headers(api_key)
        payload: dict[str, Any] = {}

        if properties is not None:
            payload["properties"] = properties

        if archived is not None:
            payload["archived"] = archived

        if icon:
            # emoji または URL
            if len(icon) <= 2:  # emoji
                payload["icon"] = {"type": "emoji", "emoji": icon}
            else:  # URL
                payload["icon"] = {"type": "external", "external": {"url": icon}}

        if cover:
            payload["cover"] = {"type": "external", "external": {"url": cover}}

        response = requests.patch(
            url,
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    return await loop.run_in_executor(None, _do_request)


@register_action(
    "notion_query_database",
    metadata={
        "title": "Notion DB 検索",
        "description": "Notionデータベースから条件に合うページを取得します。",
        "category": "Notion",
        "color": "#000000",
        "params": [
            {
                "key": "database_id",
                "description": "データベースID（URL から取得可能）",
                "required": True,
                "example": "0123456789abcdef0123456789abcdef"
            },
            {
                "key": "filter_simple",
                "description": "フィルタ条件（シンプル形式：辞書で指定）※推奨",
                "required": False,
                "example": '{"Status": "完了", "Priority": ">5"}'
            },
            {
                "key": "filter",
                "description": "フィルタ条件（Notion API形式：上級者向け）",
                "required": False,
                "example": '{"property": "Status", "select": {"equals": "Done"}}'
            },
            {
                "key": "sorts_simple",
                "description": "ソート条件（シンプル形式：リストで指定）※推奨",
                "required": False,
                "example": '[{"Created": "desc"}, {"Priority": "asc"}]'
            },
            {
                "key": "sorts",
                "description": "ソート条件（Notion API形式：上級者向け）",
                "required": False,
                "example": '[{"property": "Created", "direction": "descending"}]'
            },
            {
                "key": "page_size",
                "description": "取得件数（最大100）",
                "required": False,
                "default": 100,
                "example": "50"
            },
            {
                "key": "start_cursor",
                "description": "ページネーション用カーソル",
                "required": False,
                "example": "{{ previous_step.next_cursor }}"
            },
            {
                "key": "api_key",
                "description": "Notion API キー（直接指定）",
                "required": False,
                "example": "secret_xxx"
            },
            {
                "key": "api_key_file",
                "description": "API キーのファイルパス",
                "required": False,
                "default": "secrets/notion_api_key.txt",
                "example": "secrets/notion_api_key.txt"
            }
        ],
        "outputs": [
            {"key": "results", "description": "ページオブジェクトの配列"},
            {"key": "has_more", "description": "次のページがあるか"},
            {"key": "next_cursor", "description": "次のページのカーソル"},
            {"key": "page_count", "description": "取得したページ数"},
            {"key": "database_id", "description": "データベースID"}
        ]
    }
)
async def action_notion_query_database(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Notion データベースから条件に合うページを取得

    params:
        database_id: データベースID（必須）
        filter_simple: フィルタ条件（シンプル形式、推奨）
        filter: フィルタ条件（Notion API形式、上級者向け）
        sorts_simple: ソート条件（シンプル形式、推奨）
        sorts: ソート条件（Notion API形式、上級者向け）
        page_size: 取得件数（デフォルト: 100、最大: 100）
        start_cursor: ページネーション用カーソル（オプション）
        api_key: Notion API キー（直接指定、オプション）
        api_key_file: API キーのファイルパス（オプション）

    context:
        base_dir: プロジェクトルート

    Returns:
        {
            "results": [...],          # ページオブジェクトの配列
            "has_more": bool,          # 次のページがあるか
            "next_cursor": str | None, # 次のページのカーソル
            "page_count": int,         # 取得したページ数
            "database_id": str         # データベースID
        }
    """
    # パラメータ取得とバリデーション
    database_id = params.get("database_id")
    if not database_id:
        raise ValueError("database_id は必須です")

    # API キー読み込み
    base_dir = context.get("base_dir", Path.cwd())
    api_key = params.get("api_key")
    if isinstance(api_key, str):
        api_key = api_key.strip()
    if not api_key:
        api_key_file = params.get("api_key_file", DEFAULT_NOTION_KEY_FILE)
        api_key = _load_api_key(str(api_key_file), base_dir, DEFAULT_NOTION_KEY_ENV)

    # フィルタ処理（filter_simple を優先）
    filter_simple = params.get("filter_simple")
    filter_obj = params.get("filter")

    if filter_simple is not None:
        # YAML から辞書として取得した場合はそのまま、JSON 文字列の場合は変換
        if isinstance(filter_simple, str):
            filter_simple = _normalize_json(filter_simple)
        if not isinstance(filter_simple, dict):
            raise ValueError("filter_simple は辞書形式で指定してください")
        # シンプル形式を Notion API 形式に変換
        filter_obj = _normalize_filter_simple(filter_simple)
    elif filter_obj is not None:
        # 従来の filter パラメータ
        filter_obj = _normalize_json(filter_obj)

    # ソート処理（sorts_simple を優先）
    sorts_simple = params.get("sorts_simple")
    sorts = params.get("sorts")

    if sorts_simple is not None:
        # YAML からリストとして取得した場合はそのまま、JSON 文字列の場合は変換
        if isinstance(sorts_simple, str):
            sorts_simple = _normalize_json(sorts_simple)
        if not isinstance(sorts_simple, list):
            raise ValueError("sorts_simple はリスト形式で指定してください")
        # シンプル形式を Notion API 形式に変換
        sorts = _normalize_sorts_simple(sorts_simple)
    elif sorts is not None:
        # 従来の sorts パラメータ
        sorts = _normalize_json(sorts)
    page_size = _coerce_int(params.get("page_size"), "page_size") or 100
    start_cursor = params.get("start_cursor")

    if page_size < 1 or page_size > 100:
        raise ValueError("page_size は1〜100の範囲で指定してください")

    logger.info(f"Notion DB 検索開始: database_id={database_id}")

    try:
        result = await _query_database(
            database_id=database_id,
            api_key=api_key,
            filter_obj=filter_obj,
            sorts=sorts,
            page_size=page_size,
            start_cursor=start_cursor,
        )

        logger.info(f"Notion DB 検索完了: {len(result.get('results', []))} 件取得")

        return {
            "results": result.get("results", []),
            "has_more": result.get("has_more", False),
            "next_cursor": result.get("next_cursor"),
            "page_count": len(result.get("results", [])),
            "database_id": database_id,
        }

    except requests.HTTPError as exc:
        detail = _extract_error_detail(exc.response)
        logger.error(f"Notion API エラー: {exc} {f'detail={detail}' if detail else ''}")
        if detail:
            raise RuntimeError(f"Notion API エラー: {detail}") from exc
        raise


@register_action(
    "notion_create_page",
    metadata={
        "title": "Notion ページ作成",
        "description": "Notionデータベースに新しいページを作成します。",
        "category": "Notion",
        "color": "#000000",
        "params": [
            {
                "key": "database_id",
                "description": "親データベースID",
                "required": True,
                "example": "0123456789abcdef0123456789abcdef"
            },
            {
                "key": "properties_simple",
                "description": "ページプロパティ（シンプル形式：辞書で指定）※推奨",
                "required": False,
                "example": '{"Name": "新しいタスク", "Status": "進行中", "Priority": 5}'
            },
            {
                "key": "properties",
                "description": "ページプロパティ（Notion API形式：上級者向け）",
                "required": False,
                "example": '{"Name": {"title": [{"text": {"content": "新しいタスク"}}]}}'
            },
            {
                "key": "content",
                "description": "ページ本文（ブロック配列、または簡易テキスト文字列）",
                "required": False,
                "example": "これはページの本文です"
            },
            {
                "key": "icon",
                "description": "アイコン（emoji または URL）",
                "required": False,
                "example": "📝"
            },
            {
                "key": "cover",
                "description": "カバー画像URL",
                "required": False,
                "example": "https://example.com/cover.jpg"
            },
            {
                "key": "api_key",
                "description": "Notion API キー（直接指定）",
                "required": False,
                "example": "secret_xxx"
            },
            {
                "key": "api_key_file",
                "description": "API キーのファイルパス",
                "required": False,
                "default": "secrets/notion_api_key.txt",
                "example": "secrets/notion_api_key.txt"
            }
        ],
        "outputs": [
            {"key": "page_id", "description": "作成されたページID"},
            {"key": "url", "description": "ページURL"},
            {"key": "properties", "description": "プロパティ"},
            {"key": "created_time", "description": "作成日時（ISO 8601）"},
            {"key": "database_id", "description": "親データベースID"}
        ]
    }
)
async def action_notion_create_page(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Notion データベースに新しいページを作成

    params:
        database_id: 親データベースID（必須）
        properties_simple: ページプロパティ（シンプル形式、推奨）
        properties: ページプロパティ（Notion API形式、上級者向け）
        content: ページ本文（ブロック配列、または簡易テキスト、オプション）
        icon: アイコン（emoji または URL、オプション）
        cover: カバー画像URL（オプション）
        api_key: Notion API キー（直接指定、オプション）
        api_key_file: API キーのファイルパス（オプション）

    context:
        base_dir: プロジェクトルート

    Returns:
        {
            "page_id": str,           # 作成されたページID
            "url": str,               # ページURL
            "properties": dict,       # プロパティ
            "created_time": str,      # 作成日時（ISO 8601）
            "database_id": str        # 親データベースID
        }
    """
    # パラメータ取得とバリデーション
    database_id = params.get("database_id")
    if not database_id:
        raise ValueError("database_id は必須です")

    # properties_simple と properties の両方をサポート
    properties_simple = params.get("properties_simple")
    properties = params.get("properties")

    # properties_simple を優先
    if properties_simple is not None:
        # YAML から辞書として取得した場合はそのまま、JSON 文字列の場合は変換
        if isinstance(properties_simple, str):
            properties_simple = _normalize_json(properties_simple)
        if not isinstance(properties_simple, dict):
            raise ValueError("properties_simple は辞書形式で指定してください")
        # シンプル形式を Notion API 形式に変換
        properties = _normalize_properties_simple(properties_simple)
    elif properties is not None:
        # 従来の properties パラメータ
        properties = _normalize_json(properties)
        if not isinstance(properties, dict):
            raise ValueError("properties は辞書形式で指定してください")
    else:
        raise ValueError("properties_simple または properties のいずれかは必須です")

    # API キー読み込み
    base_dir = context.get("base_dir", Path.cwd())
    api_key = params.get("api_key")
    if isinstance(api_key, str):
        api_key = api_key.strip()
    if not api_key:
        api_key_file = params.get("api_key_file", DEFAULT_NOTION_KEY_FILE)
        api_key = _load_api_key(str(api_key_file), base_dir, DEFAULT_NOTION_KEY_ENV)

    # オプションパラメータ
    children = _normalize_content(params.get("content"))
    icon = params.get("icon")
    cover = params.get("cover")

    logger.info(f"Notion ページ作成開始: database_id={database_id}")

    try:
        result = await _create_page(
            database_id=database_id,
            properties=properties,
            api_key=api_key,
            children=children,
            icon=icon,
            cover=cover,
        )

        page_id = result.get("id")
        logger.info(f"Notion ページ作成完了: page_id={page_id}")

        return {
            "page_id": page_id,
            "url": result.get("url"),
            "properties": result.get("properties"),
            "created_time": result.get("created_time"),
            "database_id": database_id,
        }

    except requests.HTTPError as exc:
        detail = _extract_error_detail(exc.response)
        logger.error(f"Notion API エラー: {exc} {f'detail={detail}' if detail else ''}")
        if detail:
            raise RuntimeError(f"Notion API エラー: {detail}") from exc
        raise


@register_action(
    "notion_update_page",
    metadata={
        "title": "Notion ページ更新",
        "description": "Notionの既存ページを更新します（プロパティ、アーカイブ、アイコン等）。",
        "category": "Notion",
        "color": "#000000",
        "params": [
            {
                "key": "page_id",
                "description": "ページID",
                "required": True,
                "example": "0123456789abcdef0123456789abcdef"
            },
            {
                "key": "properties_simple",
                "description": "更新するプロパティ（シンプル形式：辞書で指定）※推奨",
                "required": False,
                "example": '{"Status": "完了", "Priority": 10}'
            },
            {
                "key": "properties",
                "description": "更新するプロパティ（Notion API形式：上級者向け）",
                "required": False,
                "example": '{"Status": {"select": {"name": "Done"}}}'
            },
            {
                "key": "archived",
                "description": "アーカイブ（削除）するかどうか",
                "required": False,
                "default": False,
                "example": "false"
            },
            {
                "key": "icon",
                "description": "アイコン（emoji または URL）",
                "required": False,
                "example": "✅"
            },
            {
                "key": "cover",
                "description": "カバー画像URL",
                "required": False,
                "example": "https://example.com/cover.jpg"
            },
            {
                "key": "api_key",
                "description": "Notion API キー（直接指定）",
                "required": False,
                "example": "secret_xxx"
            },
            {
                "key": "api_key_file",
                "description": "API キーのファイルパス",
                "required": False,
                "default": "secrets/notion_api_key.txt",
                "example": "secrets/notion_api_key.txt"
            }
        ],
        "outputs": [
            {"key": "page_id", "description": "ページID"},
            {"key": "url", "description": "ページURL"},
            {"key": "properties", "description": "更新後のプロパティ"},
            {"key": "archived", "description": "アーカイブ状態"},
            {"key": "last_edited_time", "description": "最終更新日時（ISO 8601）"}
        ]
    }
)
async def action_notion_update_page(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Notion の既存ページを更新

    params:
        page_id: ページID（必須）
        properties_simple: 更新するプロパティ（シンプル形式、推奨）
        properties: 更新するプロパティ（Notion API形式、上級者向け）
        archived: アーカイブ（削除）フラグ（オプション）
        icon: アイコン（emoji または URL、オプション）
        cover: カバー画像URL（オプション）
        api_key: Notion API キー（直接指定、オプション）
        api_key_file: API キーのファイルパス（オプション）

    context:
        base_dir: プロジェクトルート

    Returns:
        {
            "page_id": str,              # ページID
            "url": str,                  # ページURL
            "properties": dict,          # 更新後のプロパティ
            "archived": bool,            # アーカイブ状態
            "last_edited_time": str      # 最終更新日時（ISO 8601）
        }
    """
    # パラメータ取得とバリデーション
    page_id = params.get("page_id")
    if not page_id:
        raise ValueError("page_id は必須です")

    # API キー読み込み
    base_dir = context.get("base_dir", Path.cwd())
    api_key = params.get("api_key")
    if isinstance(api_key, str):
        api_key = api_key.strip()
    if not api_key:
        api_key_file = params.get("api_key_file", DEFAULT_NOTION_KEY_FILE)
        api_key = _load_api_key(str(api_key_file), base_dir, DEFAULT_NOTION_KEY_ENV)

    # properties_simple と properties の両方をサポート
    properties_simple = params.get("properties_simple")
    properties = params.get("properties")

    # properties_simple を優先
    if properties_simple is not None:
        # YAML から辞書として取得した場合はそのまま、JSON 文字列の場合は変換
        if isinstance(properties_simple, str):
            properties_simple = _normalize_json(properties_simple)
        if not isinstance(properties_simple, dict):
            raise ValueError("properties_simple は辞書形式で指定してください")
        # シンプル形式を Notion API 形式に変換
        properties = _normalize_properties_simple(properties_simple)
    elif properties is not None:
        # 従来の properties パラメータ
        properties = _normalize_json(properties)
    archived = params.get("archived")
    if archived is not None:
        if isinstance(archived, str):
            archived = archived.lower() in ("true", "1", "yes")
        archived = bool(archived)

    icon = params.get("icon")
    cover = params.get("cover")

    # 少なくとも1つの更新項目が必要
    if properties is None and archived is None and not icon and not cover:
        raise ValueError("更新する項目（properties、archived、icon、cover）のいずれかを指定してください")

    logger.info(f"Notion ページ更新開始: page_id={page_id}")

    try:
        result = await _update_page(
            page_id=page_id,
            properties=properties,
            api_key=api_key,
            archived=archived,
            icon=icon,
            cover=cover,
        )

        logger.info(f"Notion ページ更新完了: page_id={page_id}")

        return {
            "page_id": result.get("id"),
            "url": result.get("url"),
            "properties": result.get("properties"),
            "archived": result.get("archived", False),
            "last_edited_time": result.get("last_edited_time"),
        }

    except requests.HTTPError as exc:
        detail = _extract_error_detail(exc.response)
        logger.error(f"Notion API エラー: {exc} {f'detail={detail}' if detail else ''}")
        if detail:
            raise RuntimeError(f"Notion API エラー: {detail}") from exc
        raise
