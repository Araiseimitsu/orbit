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
    """Google Sheets API サービスを取得"""
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"サービスアカウント認証情報が見つかりません: {credentials_path}\n"
            "Google Cloud Console でサービスアカウントを作成し、"
            "JSON キーファイルをダウンロードして配置してください。"
        )

    credentials = Credentials.from_service_account_file(
        str(credentials_path), scopes=SCOPES
    )

    service = build("sheets", "v4", credentials=credentials)
    return service


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


@register_action("sheets_read")
async def action_sheets_read(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Google Sheets からデータを読み取る

    params:
        spreadsheet_id: スプレッドシートID (URL から取得可能)
        range: 読み取り範囲 (例: "Sheet1!A1:D10", "Sheet1" など)
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

    range_notation = params.get("range")
    if not range_notation:
        raise ValueError("range は必須です (例: 'Sheet1!A1:D10')")

    header_row = params.get("header_row", True)
    credentials_file = params.get("credentials_file", DEFAULT_CREDENTIALS_FILE)

    # パス解決
    base_dir = context.get("base_dir", Path.cwd())
    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = base_dir / credentials_path

    logger.info(f"Google Sheets 読み取り開始: {spreadsheet_id} / {range_notation}")

    try:
        # API サービス取得
        service = _get_sheets_service(credentials_path)

        # データ取得
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=spreadsheet_id, range=range_notation)
            .execute()
        )

        values = result.get("values", [])

        logger.info(f"取得完了: {len(values)} 行")

        # 結果を解析
        parsed = _parse_values_with_header(values, header_row)

        return {**parsed, "spreadsheet_id": spreadsheet_id, "range": range_notation}

    except HttpError as e:
        error_msg = f"Google Sheets API エラー: {e.resp.status} - {e.reason}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    except Exception as e:
        error_msg = f"Google Sheets 読み取りエラー: {e}"
        logger.error(error_msg)
        raise


@register_action("sheets_list")
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


@register_action("sheets_append")
async def action_sheets_append(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Google Sheets に行を追加（追記）

    params:
        spreadsheet_id: スプレッドシートID
        range: 追記先の範囲（例: "Sheet1!A1" または "Sheet1"）
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

    range_notation = params.get("range")
    if not range_notation:
        raise ValueError("range は必須です (例: 'Sheet1!A1')")

    values = _normalize_values(params.get("values"))
    value_input_option = params.get("value_input_option", "USER_ENTERED")
    insert_data_option = params.get("insert_data_option", "INSERT_ROWS")
    credentials_file = params.get("credentials_file", DEFAULT_CREDENTIALS_FILE)

    base_dir = context.get("base_dir", Path.cwd())
    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = base_dir / credentials_path

    logger.info(f"Google Sheets 追記開始: {spreadsheet_id} / {range_notation}")

    try:
        service = _get_sheets_service(credentials_path)
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_notation,
                valueInputOption=value_input_option,
                insertDataOption=insert_data_option,
                body={"values": values},
            )
            .execute()
        )

        updates = result.get("updates", {})
        return {
            "spreadsheet_id": spreadsheet_id,
            "range": range_notation,
            "updated_range": updates.get("updatedRange"),
            "updated_rows": updates.get("updatedRows"),
            "updated_columns": updates.get("updatedColumns"),
            "updated_cells": updates.get("updatedCells"),
        }

    except HttpError as e:
        error_msg = f"Google Sheets API エラー: {e.resp.status} - {e.reason}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


@register_action("sheets_write")
async def action_sheets_write(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Google Sheets の指定範囲に書き込み（上書き）

    params:
        spreadsheet_id: スプレッドシートID
        range: 書き込み範囲（例: "Sheet1!A1:C2"）
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

    range_notation = params.get("range")
    if not range_notation:
        raise ValueError("range は必須です (例: 'Sheet1!A1:C2')")

    values = _normalize_values(params.get("values"))
    value_input_option = params.get("value_input_option", "USER_ENTERED")
    credentials_file = params.get("credentials_file", DEFAULT_CREDENTIALS_FILE)

    base_dir = context.get("base_dir", Path.cwd())
    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = base_dir / credentials_path

    logger.info(f"Google Sheets 書き込み開始: {spreadsheet_id} / {range_notation}")

    try:
        service = _get_sheets_service(credentials_path)
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_notation,
                valueInputOption=value_input_option,
                body={"values": values},
            )
            .execute()
        )

        return {
            "spreadsheet_id": spreadsheet_id,
            "range": range_notation,
            "updated_range": result.get("updatedRange"),
            "updated_rows": result.get("updatedRows"),
            "updated_columns": result.get("updatedColumns"),
            "updated_cells": result.get("updatedCells"),
        }

    except HttpError as e:
        error_msg = f"Google Sheets API エラー: {e.resp.status} - {e.reason}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
