"""
Notion 連携アクション

Notion API を使用してデータベース検索やページ作成を行う。

API キー設定:
    環境変数 NOTION_API_KEY または secrets/notion_api_key.txt に Notion API キー

使用例 (YAML):
    - id: query_db
      type: notion_query_database
      params:
        database_id: "0123456789abcdef0123456789abcdef"
        filter: |
          {
            "property": "Status",
            "select": {"equals": "Done"}
          }
        page_size: 50

    - id: create_page
      type: notion_create_page
      params:
        database_id: "0123456789abcdef0123456789abcdef"
        properties: |
          {
            "Name": {
              "title": [{"text": {"content": "新しいタスク"}}]
            }
          }
        content: "これはページの本文です"
        icon: "📝"

    - id: update_page
      type: notion_update_page
      params:
        page_id: "{{ create_page.page_id }}"
        properties: |
          {
            "Status": {"select": {"name": "Done"}}
          }
        icon: "✅"
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
                "key": "filter",
                "description": "フィルタ条件（JSON または辞書）",
                "required": False,
                "example": '{"property": "Status", "select": {"equals": "Done"}}'
            },
            {
                "key": "sorts",
                "description": "ソート条件（JSON または配列）",
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
        filter: フィルタ条件（JSON または辞書、オプション）
        sorts: ソート条件（JSON または配列、オプション）
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

    # オプションパラメータ
    filter_obj = _normalize_json(params.get("filter"))
    sorts = _normalize_json(params.get("sorts"))
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
                "key": "properties",
                "description": "ページプロパティ（JSON または辞書）",
                "required": True,
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
        properties: ページプロパティ（JSON または辞書、必須）
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

    properties = _normalize_json(params.get("properties"))
    if not properties:
        raise ValueError("properties は必須です")
    if not isinstance(properties, dict):
        raise ValueError("properties は辞書形式で指定してください")

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
                "key": "properties",
                "description": "更新するプロパティ（JSON または辞書）",
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
        properties: 更新するプロパティ（JSON または辞書、オプション）
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

    # オプションパラメータ
    properties = _normalize_json(params.get("properties"))
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
