"""
Google Sheets アクション

サービスアカウント認証を使用して Google Sheets と連携する。

設定:
    secrets/google_service_account.json にサービスアカウントの
    認証情報ファイルを配置すること。

使用例 (YAML):
    - id: read_sheet
      type: sheets_read
      params:
        spreadsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        range: "Sheet1!A1:D10"
        # オプション
        header_row: true  # 1行目をヘッダーとして扱う (デフォルト: true)
        credentials_file: "secrets/google_service_account.json"  # デフォルト

    - id: append_sheet
      type: sheets_append
      params:
        spreadsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        range: "Sheet1!A1"
        values: [["A", "B", "C"], ["1", "2", "3"]]
        value_input_option: "USER_ENTERED"

    - id: write_sheet
      type: sheets_write
      params:
        spreadsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        range: "Sheet1!A1:C2"
        values: [["A", "B", "C"], ["1", "2", "3"]]
        value_input_option: "USER_ENTERED"
"""

import json
import logging
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..core.registry import register_action

logger = logging.getLogger(__name__)

# Google Sheets API のスコープ（読み書き）
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# デフォルトの認証情報ファイルパス
DEFAULT_CREDENTIALS_FILE = "secrets/google_service_account.json"


def _get_sheets_service(credentials_path: Path):
    """
    Google Sheets API サービスを取得

    環境変数 GOOGLE_APPLICATION_CREDENTIALS を優先し、
    なければ credentials_path を使用する。
    """
    import os

    # 環境変数を優先
    env_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_creds:
        env_path = Path(env_creds)
        if env_path.exists():
            logger.debug(f"Using credentials from env: {env_path}")
            credentials = Credentials.from_service_account_file(
                str(env_path), scopes=SCOPES
            )
            service = build("sheets", "v4", credentials=credentials)
            return service

    # フォールバック: パラメータ指定のパス
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"サービスアカウント認証情報が見つかりません。\n"
            f"環境変数 GOOGLE_APPLICATION_CREDENTIALS またはファイル {credentials_path} に設定してください。"
        )

    logger.debug(f"Using credentials from file: {credentials_path}")
    credentials = Credentials.from_service_account_file(
        str(credentials_path), scopes=SCOPES
    )

    service = build("sheets", "v4", credentials=credentials)
    return service


def _normalize_spreadsheet_id(id_or_url: str) -> str:
    """
    Google Sheets IDまたはURLからIDを抽出・正規化

    Args:
        id_or_url: Spreadsheet ID または Google Sheets URL

    Returns:
        正規化されたSpreadsheet ID

    Examples:
        - "1AbCdEfGhIjKlMnOpQrStUvWxYz" → "1AbCdEfGhIjKlMnOpQrStUvWxYz"
        - "https://docs.google.com/spreadsheets/d/1AbCdEfGh.../edit" → "1AbCdEfGh..."
    """
    import re
    from urllib.parse import urlparse

    if not id_or_url:
        raise ValueError("Spreadsheet ID または URL が空です")

    id_or_url = str(id_or_url).strip()

    # URLの場合はIDを抽出
    if id_or_url.startswith("http://") or id_or_url.startswith("https://"):
        # URLをパース
        parsed = urlparse(id_or_url)

        # Google Sheets URLかチェック
        if "docs.google.com" not in parsed.netloc:
            raise ValueError(
                f"Google Sheets の URL ではありません: {id_or_url}\n"
                f"https://docs.google.com/spreadsheets/... の形式で指定してください。"
            )

        # パスから ID を抽出
        # 形式: /spreadsheets/d/{id}/edit
        # または: /spreadsheets/d/{id}
        path = parsed.path
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', path)

        if not match:
            raise ValueError(
                f"URLからSpreadsheet IDを抽出できません: {id_or_url}\n"
                f"正しいGoogle Sheets URLを指定してください。"
            )

        extracted_id = match.group(1)
        id_or_url = extracted_id

    # IDの形式をバリデーション（Google Sheets IDは英数字とハイフン、アンダースコア）
    if not re.match(r'^[a-zA-Z0-9-_]+$', id_or_url):
        raise ValueError(
            f"無効なSpreadsheet ID形式です: {id_or_url}\n"
            f"英数字、ハイフン、アンダースコアのみ使用可能です。"
        )

    return id_or_url


def _normalize_values(values: Any) -> list[list[Any]]:
    """
    values を 2次元配列に正規化

    - list[list[Any]] をそのまま許可
    - 文字列の場合は JSON として解釈を試みる
    """
    if values is None:
        raise ValueError("values は必須です")
    if isinstance(values, str):
        values_str = values.strip()
        if not values_str:
            raise ValueError("values は必須です")
        try:
            values = json.loads(values_str)
        except json.JSONDecodeError as e:
            raise ValueError("values は2次元配列(JSON)で指定してください") from e

    if not isinstance(values, list):
        raise ValueError("values は2次元配列で指定してください")
    if values and not all(isinstance(row, list) for row in values):
        raise ValueError("values は2次元配列で指定してください")
    return values


def _parse_sheet_and_range(sheet: str | None, range_param: str) -> str:
    """
    sheet パラメータと range パラメータから最終的な範囲文字列を返す

    優先順位:
    1. sheet パラメータが指定されていれば、それを使用
    2. range に "!" が含まれていれば、分割して使用（後方互換）
    3. どちらもなければ、range をそのまま使用（シート名なし）

    Args:
        sheet: シート名（オプショナル）
        range_param: 範囲（例: "A1:D10" または "Sheet1!A1:D10"）

    Returns:
        最終的な範囲文字列（例: "Sheet1!A1:D10" または "A1:D10"）

    Examples:
        >>> _parse_sheet_and_range("Sheet1", "A1:D10")
        "Sheet1!A1:D10"

        >>> _parse_sheet_and_range(None, "Sheet2!B1:C10")
        "Sheet2!B1:C10"

        >>> _parse_sheet_and_range("Sheet1", "Sheet2!A1:D10")
        "Sheet1!A1:D10"  # sheet パラメータを優先

        >>> _parse_sheet_and_range(None, "A1:D10")
        "A1:D10"
    """
    if "!" in range_param:
        # 従来の "Sheet1!A1:D10" 形式
        parts = range_param.split("!", 1)
        extracted_sheet = parts[0]
        extracted_range = parts[1] if len(parts) > 1 else ""

        # sheet パラメータが指定されていればそちらを優先
        final_sheet = sheet if sheet else extracted_sheet
        final_range = extracted_range
    else:
        # range に "!" がない場合
        final_sheet = sheet if sheet else ""
        final_range = range_param

    # 最終的な range 文字列を生成
    if final_sheet:
        return f"{final_sheet}!{final_range}"
    else:
        return final_range


def _parse_values_with_header(
    values: list[list[Any]], header_row: bool
) -> dict[str, Any]:
    """
    値を解析してヘッダー付きの dict 形式に変換

    Args:
        values: API から返された 2D リスト
        header_row: 1行目をヘッダーとして扱うか

    Returns:
        {
            "headers": ["col1", "col2", ...],
            "rows": [{"col1": "val1", "col2": "val2", ...}, ...],
            "raw": [[...], [...], ...]
        }
    """
    if not values:
        return {"headers": [], "rows": [], "raw": [], "row_count": 0, "col_count": 0}

    if header_row and len(values) >= 1:
        headers = [str(h) if h else f"col_{i}" for i, h in enumerate(values[0])]
        data_rows = values[1:]

        rows = []
        for row in data_rows:
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ""
            rows.append(row_dict)

        return {
            "headers": headers,
            "rows": rows,
            "raw": values,
            "row_count": len(data_rows),
            "col_count": len(headers),
        }
    else:
        # ヘッダーなし: raw データのみ返す
        col_count = max(len(row) for row in values) if values else 0
        return {
            "headers": [],
            "rows": [],
            "raw": values,
            "row_count": len(values),
            "col_count": col_count,
        }


@register_action(
    "sheets_read",
    metadata={
        "title": "Google Sheets 読み込み",
        "description": "Google Sheetsからデータを読み取ります。",
        "category": "Google Sheets",
        "color": "#84cc16",
        "params": [
            {
                "key": "spreadsheet_id",
                "description": "スプレッドシートID（Google SheetsのURLをそのまま貼り付け可能、またはIDのみ）",
                "required": True,
                "example": "https://docs.google.com/spreadsheets/d/1AbCdEfGh... または 1AbCdEfGh...",
            },
            {
                "key": "sheet",
                "description": "シート名（オプショナル）。指定時は range のシート名より優先されます。",
                "required": False,
                "example": "Sheet1",
            },
            {
                "key": "range",
                "description": "読み取り範囲。'Sheet1!A1:D10' 形式、または sheet パラメータと組み合わせて 'A1:D10' 形式で指定可能",
                "required": True,
                "example": "A1:D10",
            },
            {
                "key": "header_row",
                "description": "1行目をヘッダーとして扱う",
                "required": False,
                "default": True,
                "example": "true",
            },
            {
                "key": "credentials_file",
                "description": "認証情報ファイルパス",
                "required": False,
                "default": "secrets/google_service_account.json",
                "example": "secrets/google_service_account.json",
            },
        ],
        "outputs": [
            {"key": "headers", "description": "ヘッダー行"},
            {"key": "rows", "description": "データ行"},
            {"key": "raw", "description": "生データ"},
            {"key": "row_count", "description": "行数"},
            {"key": "col_count", "description": "列数"},
            {"key": "spreadsheet_id", "description": "スプレッドシートID"},
            {"key": "range", "description": "範囲"},
        ],
    },
)
async def action_sheets_read(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Google Sheets からデータを読み取る

    params:
        spreadsheet_id: スプレッドシートID (URL から取得可能)
        sheet: シート名（オプショナル）。指定時は range のシート名より優先されます。
        range: 読み取り範囲 (例: "Sheet1!A1:D10", "Sheet1", "A1:D10" など)
        header_row: 1行目をヘッダーとして扱う (デフォルト: true)
        credentials_file: 認証情報ファイルパス (デフォルト: secrets/google_service_account.json)

    context:
        base_dir: プロジェクトルートパス

    Returns:
        {
            "headers": [...],
            "rows": [{...}, ...],
            "raw": [[...], ...],
            "row_count": int,
            "col_count": int,
            "spreadsheet_id": str,
            "range": str
        }
    """
    # パラメータ取得
    spreadsheet_id = params.get("spreadsheet_id")
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id は必須です")

    # spreadsheet_id を正規化（URL対応）
    spreadsheet_id = _normalize_spreadsheet_id(spreadsheet_id)

    sheet_param = params.get("sheet")
    range_notation = params.get("range")
    if not range_notation:
        raise ValueError("range は必須です (例: 'Sheet1!A1:D10' または 'A1:D10')")

    header_row = params.get("header_row", True)
    credentials_file = params.get("credentials_file", DEFAULT_CREDENTIALS_FILE)

    # パス解決
    base_dir = context.get("base_dir", Path.cwd())
    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = base_dir / credentials_path

    # シート名と範囲を解析
    final_range = _parse_sheet_and_range(sheet_param, range_notation)

    logger.info(f"Google Sheets 読み取り開始: {spreadsheet_id} / {final_range}")

    try:
        # API サービス取得
        service = _get_sheets_service(credentials_path)

        # データ取得
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=spreadsheet_id, range=final_range)
            .execute()
        )

        values = result.get("values", [])

        logger.info(f"取得完了: {len(values)} 行")

        # 結果を解析
        parsed = _parse_values_with_header(values, header_row)

        return {**parsed, "spreadsheet_id": spreadsheet_id, "range": final_range}

    except HttpError as e:
        error_msg = f"Google Sheets API エラー: {e.resp.status} - {e.reason}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    except Exception as e:
        error_msg = f"Google Sheets 読み取りエラー: {e}"
        logger.error(error_msg)
        raise


@register_action(
    "sheets_list",
    metadata={
        "title": "Google Sheets シート一覧",
        "description": "スプレッドシート内のシート一覧を取得します。",
        "category": "Google Sheets",
        "color": "#84cc16",
        "params": [
            {
                "key": "spreadsheet_id",
                "description": "スプレッドシートID",
                "required": True,
                "example": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
            },
            {
                "key": "credentials_file",
                "description": "認証情報ファイルパス",
                "required": False,
                "default": "secrets/google_service_account.json",
                "example": "secrets/google_service_account.json",
            },
        ],
        "outputs": [
            {"key": "sheets", "description": "シート情報のリスト"},
            {"key": "title", "description": "スプレッドシートのタイトル"},
            {"key": "spreadsheet_id", "description": "スプレッドシートID"},
        ],
    },
)
async def action_sheets_list(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    スプレッドシート内のシート一覧を取得

    params:
        spreadsheet_id: スプレッドシートID
        credentials_file: 認証情報ファイルパス (オプション)

    Returns:
        {
            "sheets": [{"id": int, "title": str, "index": int}, ...],
            "title": str,  # スプレッドシートのタイトル
            "spreadsheet_id": str
        }
    """
    spreadsheet_id = params.get("spreadsheet_id")
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id は必須です")

    # spreadsheet_id を正規化（URL対応）
    spreadsheet_id = _normalize_spreadsheet_id(spreadsheet_id)

    credentials_file = params.get("credentials_file", DEFAULT_CREDENTIALS_FILE)

    base_dir = context.get("base_dir", Path.cwd())
    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = base_dir / credentials_path

    logger.info(f"シート一覧取得: {spreadsheet_id}")

    try:
        service = _get_sheets_service(credentials_path)

        result = (
            service.spreadsheets()
            .get(
                spreadsheetId=spreadsheet_id,
                fields="properties.title,sheets.properties",
            )
            .execute()
        )

        title = result.get("properties", {}).get("title", "")
        sheets_data = result.get("sheets", [])

        sheets = []
        for sheet in sheets_data:
            props = sheet.get("properties", {})
            sheets.append(
                {
                    "id": props.get("sheetId"),
                    "title": props.get("title"),
                    "index": props.get("index"),
                }
            )

        logger.info(f"シート数: {len(sheets)}")

        return {"sheets": sheets, "title": title, "spreadsheet_id": spreadsheet_id}

    except HttpError as e:
        error_msg = f"Google Sheets API エラー: {e.resp.status} - {e.reason}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


@register_action(
    "sheets_append",
    metadata={
        "title": "Google Sheets 追記",
        "description": "Google Sheetsの最後に行を追加（追記）します。",
        "category": "Google Sheets",
        "color": "#84cc16",
        "params": [
            {
                "key": "spreadsheet_id",
                "description": "スプレッドシートID",
                "required": True,
                "example": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
            },
            {
                "key": "sheet",
                "description": "シート名（オプショナル）。指定時は range のシート名より優先されます。",
                "required": False,
                "example": "Sheet1",
            },
            {
                "key": "range",
                "description": "追記先の範囲。'Sheet1!A1' 形式、または sheet パラメータと組み合わせて 'A1' 形式で指定可能",
                "required": True,
                "example": "A1",
            },
            {
                "key": "values",
                "description": "2次元配列 or JSON文字列（AIの出力 text を使う場合は {{ ai_generate_1.text | fromjson }} のように変換）",
                "required": True,
                "example": "{{ ai_generate_1.text | fromjson }}",
            },
            {
                "key": "value_input_option",
                "description": "RAW / USER_ENTERED",
                "required": False,
                "default": "USER_ENTERED",
                "example": "USER_ENTERED",
            },
            {
                "key": "insert_data_option",
                "description": "INSERT_ROWS / OVERWRITE",
                "required": False,
                "default": "INSERT_ROWS",
                "example": "INSERT_ROWS",
            },
            {
                "key": "credentials_file",
                "description": "認証情報ファイルパス",
                "required": False,
                "default": "secrets/google_service_account.json",
                "example": "secrets/google_service_account.json",
            },
        ],
        "outputs": [
            {"key": "spreadsheet_id", "description": "スプレッドシートID"},
            {"key": "range", "description": "範囲"},
            {"key": "updated_range", "description": "更新範囲"},
            {"key": "updated_rows", "description": "更新行数"},
            {"key": "updated_columns", "description": "更新列数"},
            {"key": "updated_cells", "description": "更新セル数"},
        ],
    },
)
async def action_sheets_append(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Google Sheets に行を追加（追記）

    params:
        spreadsheet_id: スプレッドシートID
        sheet: シート名（オプショナル）。指定時は range のシート名より優先されます。
        range: 追記先の範囲（例: "Sheet1!A1", "Sheet1", "A1" など）
        values: 2次元配列 or JSON文字列
        value_input_option: RAW / USER_ENTERED (デフォルト: USER_ENTERED)
        insert_data_option: INSERT_ROWS / OVERWRITE (デフォルト: INSERT_ROWS)
        credentials_file: 認証情報ファイルパス (オプション)

    Returns:
        {
            "spreadsheet_id": str,
            "range": str,
            "updated_range": str,
            "updated_rows": int,
            "updated_columns": int,
            "updated_cells": int
        }
    """
    spreadsheet_id = params.get("spreadsheet_id")
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id は必須です")

    # spreadsheet_id を正規化（URL対応）
    spreadsheet_id = _normalize_spreadsheet_id(spreadsheet_id)

    sheet_param = params.get("sheet")
    range_notation = params.get("range")
    if not range_notation:
        raise ValueError("range は必須です (例: 'Sheet1!A1' または 'A1')")

    values = _normalize_values(params.get("values"))
    value_input_option = params.get("value_input_option", "USER_ENTERED")
    insert_data_option = params.get("insert_data_option", "INSERT_ROWS")
    credentials_file = params.get("credentials_file", DEFAULT_CREDENTIALS_FILE)

    base_dir = context.get("base_dir", Path.cwd())
    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = base_dir / credentials_path

    # シート名と範囲を解析
    final_range = _parse_sheet_and_range(sheet_param, range_notation)

    logger.info(f"Google Sheets 追記開始: {spreadsheet_id} / {final_range}")

    try:
        service = _get_sheets_service(credentials_path)
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=final_range,
                valueInputOption=value_input_option,
                insertDataOption=insert_data_option,
                body={"values": values},
            )
            .execute()
        )

        updates = result.get("updates", {})
        return {
            "spreadsheet_id": spreadsheet_id,
            "range": final_range,
            "updated_range": updates.get("updatedRange"),
            "updated_rows": updates.get("updatedRows"),
            "updated_columns": updates.get("updatedColumns"),
            "updated_cells": updates.get("updatedCells"),
        }

    except HttpError as e:
        error_msg = f"Google Sheets API エラー: {e.resp.status} - {e.reason}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


@register_action(
    "sheets_write",
    metadata={
        "title": "Google Sheets 書き込み",
        "description": "Google Sheetsの指定範囲にデータを書き込みます（上書き）。",
        "category": "Google Sheets",
        "color": "#84cc16",
        "params": [
            {
                "key": "spreadsheet_id",
                "description": "スプレッドシートID",
                "required": True,
                "example": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
            },
            {
                "key": "sheet",
                "description": "シート名（オプショナル）。指定時は range のシート名より優先されます。",
                "required": False,
                "example": "Sheet1",
            },
            {
                "key": "range",
                "description": "書き込み範囲。開始セルのみ（例: 'A1'）指定でデータサイズに合わせて自動拡張、範囲指定（例: 'A1:C2'）で指定範囲内のみ書き込み。'Sheet1!A1:C2' 形式、または sheet パラメータと組み合わせて 'A1:C2' 形式でも指定可能",
                "required": True,
                "example": "A1",
            },
            {
                "key": "values",
                "description": "2次元配列 or JSON文字列（例: {{ step_id.raw }} / AIの出力 text は {{ ai_generate_1.text | fromjson }}）",
                "required": True,
                "example": "{{ ai_generate_1.text | fromjson }}",
            },
            {
                "key": "value_input_option",
                "description": "RAW / USER_ENTERED",
                "required": False,
                "default": "USER_ENTERED",
                "example": "USER_ENTERED",
            },
            {
                "key": "credentials_file",
                "description": "認証情報ファイルパス",
                "required": False,
                "default": "secrets/google_service_account.json",
                "example": "secrets/google_service_account.json",
            },
        ],
        "outputs": [
            {"key": "spreadsheet_id", "description": "スプレッドシートID"},
            {"key": "range", "description": "範囲"},
            {"key": "updated_range", "description": "更新範囲"},
            {"key": "updated_rows", "description": "更新行数"},
            {"key": "updated_columns", "description": "更新列数"},
            {"key": "updated_cells", "description": "更新セル数"},
        ],
    },
)
async def action_sheets_write(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Google Sheets の指定範囲に書き込み（上書き）

    params:
        spreadsheet_id: スプレッドシートID
        sheet: シート名（オプショナル）。指定時は range のシート名より優先されます。
        range: 書き込み範囲（例: "Sheet1!A1:C2", "A1:C2" など）
        values: 2次元配列 or JSON文字列
        value_input_option: RAW / USER_ENTERED (デフォルト: USER_ENTERED)
        credentials_file: 認証情報ファイルパス (オプション)

    Returns:
        {
            "spreadsheet_id": str,
            "range": str,
            "updated_range": str,
            "updated_rows": int,
            "updated_columns": int,
            "updated_cells": int
        }
    """
    spreadsheet_id = params.get("spreadsheet_id")
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id は必須です")

    # spreadsheet_id を正規化（URL対応）
    spreadsheet_id = _normalize_spreadsheet_id(spreadsheet_id)

    sheet_param = params.get("sheet")
    range_notation = params.get("range")
    if not range_notation:
        raise ValueError("range は必須です (例: 'Sheet1!A1:C2' または 'A1:C2')")

    values = _normalize_values(params.get("values"))
    value_input_option = params.get("value_input_option", "USER_ENTERED")
    credentials_file = params.get("credentials_file", DEFAULT_CREDENTIALS_FILE)

    base_dir = context.get("base_dir", Path.cwd())
    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = base_dir / credentials_path

    # シート名と範囲を解析
    final_range = _parse_sheet_and_range(sheet_param, range_notation)

    logger.info(f"Google Sheets 書き込み開始: {spreadsheet_id} / {final_range}")

    try:
        service = _get_sheets_service(credentials_path)
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=final_range,
                valueInputOption=value_input_option,
                body={"values": values},
            )
            .execute()
        )

        return {
            "spreadsheet_id": spreadsheet_id,
            "range": final_range,
            "updated_range": result.get("updatedRange"),
            "updated_rows": result.get("updatedRows"),
            "updated_columns": result.get("updatedColumns"),
            "updated_cells": result.get("updatedCells"),
        }

    except HttpError as e:
        error_msg = f"Google Sheets API エラー: {e.resp.status} - {e.reason}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
