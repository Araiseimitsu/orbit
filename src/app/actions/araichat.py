"""
ARAICHAT メッセージ送信アクション

ARAICHAT の統合APIに対してメッセージを送信する。
"""
from __future__ import annotations

import json
import logging
import time
import mimetypes
from pathlib import Path
from typing import Any

import requests

from ..core.registry import register_action

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://araichat-966672454924.asia-northeast1.run.app"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_API_KEY_FILE = "secrets/araichat_api_key.txt"
ACTION_TYPE = "araichat_send_message"


def _coerce_int(value: Any, label: str) -> int | None:
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


def _load_api_key(file_path: str, base_dir: Path, env_var_name: str = "ARAICHAT_API_KEY") -> str:
    """
    API キーを環境変数 → ファイルの順で読み込む

    Args:
        file_path: フォールバック用ファイルパス
        base_dir: ベースディレクトリ
        env_var_name: 環境変数名

    Returns:
        API キー文字列
    """
    import os

    # 環境変数を優先
    api_key = os.getenv(env_var_name)
    if api_key:
        api_key = api_key.strip()
        if api_key:
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

    return key


def _normalize_files(value: Any, base_dir: Path) -> list[Path]:
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        if text.startswith("[") or text.startswith('"'):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("files は配列または文字列（JSON可）で指定してください") from exc
            if isinstance(parsed, list):
                value = parsed
            elif isinstance(parsed, str):
                value = [parsed]
            else:
                raise ValueError("files は配列または文字列で指定してください")
        else:
            value = [text]

    if not isinstance(value, list):
        raise ValueError("files は配列または文字列で指定してください")

    paths: list[Path] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("files は文字列配列で指定してください")
        item_text = item.strip()
        if not item_text:
            continue
        path = Path(item_text)
        if not path.is_absolute():
            path = base_dir / path
        if not path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {path}")
        if not path.is_file():
            raise ValueError(f"ディレクトリは指定できません: {path}")
        paths.append(path)

    return paths


def _extract_error_detail(response: requests.Response | None) -> str:
    if response is None:
        return ""
    try:
        payload = response.json()
    except ValueError:
        return (response.text or "").strip()

    if isinstance(payload, dict):
        return str(payload.get("detail") or payload.get("message") or "").strip()
    return ""


@register_action(
    ACTION_TYPE,
    metadata={
        "title": "ARAICHAT 送信",
        "description": "ARAICHAT の統合APIに対してメッセージを送信します。",
        "category": "外部連携",
        "params": [
            {
                "key": "text",
                "description": "送信するテキスト（text または files のいずれか必須）",
                "required": False,
                "example": "こんにちは"
            },
            {
                "key": "files",
                "description": "添付ファイル（文字列/配列/JSON文字列も可）。Windowsパスはエクスプローラーからコピーしたそのまま使用可能",
                "required": False,
                "example": 'C:\\Users\\winni\\my_projects\\1\\orbit\\runs\\output\\sample.html または ["runs/output/file1.txt", "runs/output/file2.png"]'
            },
            {
                "key": "room_id",
                "description": "送信先ルームID",
                "required": True,
                "example": "your-room-id"
            },
            {
                "key": "api_key",
                "description": "統合APIキー（直接指定）",
                "required": False,
                "example": "your-api-key"
            },
            {
                "key": "api_key_file",
                "description": "APIキーのファイルパス（未指定時は ARAICHAT_API_KEY または既定ファイル）",
                "required": False,
                "example": "secrets/araichat_api_key.txt"
            },
            {
                "key": "timeout",
                "description": "タイムアウト秒（デフォルト: 30）",
                "required": False,
                "default": 30,
                "example": "30"
            },
            {
                "key": "retries",
                "description": "リトライ回数（デフォルト: 3）",
                "required": False,
                "default": 3,
                "example": "3"
            }
        ],
        "outputs": [
            {"key": "message_id", "description": "メッセージID"},
            {"key": "room_id", "description": "ルームID"},
            {"key": "files", "description": "添付ファイル"},
            {"key": "created_at", "description": "作成日時"},
            {"key": "status_code", "description": "HTTPステータスコード"}
        ]
    }
)
async def action_araichat_send_message(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    ARAICHAT にメッセージを送信する

    params:
        text: 送信するテキスト（text または files のいずれか必須）
        files: 添付ファイル（文字列/配列/JSON文字列も可）。Windowsパスは \\ または / で指定
        room_id: 送信先ルームID（必須）
        api_key: 統合APIキー（直接指定）
        api_key_file: APIキーのファイルパス（未指定時は ARAICHAT_API_KEY または既定ファイル）
        timeout: タイムアウト秒（デフォルト: 30）
        retries: リトライ回数（デフォルト: 3）

    context:
        base_dir: プロジェクトルート

    returns:
        {
            "message_id": "...",
            "room_id": "...",
            "files": [...],
            "created_at": "...",
            "status_code": 200,
            "response": {...}
        }
    """
    base_dir = context.get("base_dir", Path.cwd())

    text = params.get("text")
    if isinstance(text, str):
        text = text.strip()
    if text == "":
        text = None

    files = _normalize_files(params.get("files"), base_dir)

    if not text and not files:
        raise ValueError("text または files のいずれかを指定してください")

    base_url = DEFAULT_BASE_URL.rstrip("/")

    room_id = params.get("room_id")
    if room_id is None:
        raise ValueError("room_id は必須です")
    room_id = str(room_id).strip()
    if not room_id:
        raise ValueError("room_id は必須です")

    api_key = params.get("api_key")
    if isinstance(api_key, str):
        api_key = api_key.strip()
    if not api_key:
        api_key_file = params.get("api_key_file", DEFAULT_API_KEY_FILE)
        api_key = _load_api_key(str(api_key_file), base_dir, "ARAICHAT_API_KEY")

    timeout = _coerce_int(params.get("timeout"), "timeout")
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    if timeout <= 0:
        raise ValueError("timeout は1以上で指定してください")

    retries = _coerce_int(params.get("retries"), "retries")
    if retries is None:
        retries = DEFAULT_RETRIES
    if retries <= 0:
        raise ValueError("retries は1以上で指定してください")

    url = f"{base_url}/api/integrations/send/{room_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {}
    if text:
        payload["text"] = text

    logger.info(
        "ARAICHAT 送信開始: room_id=%s files=%s",
        room_id,
        len(files),
    )

    for attempt in range(1, retries + 1):
        files_payload: list[tuple[str, tuple[str, Any, str]]] = []
        try:
            if files:
                files_payload = [
                    (
                        "files",
                        (
                            path.name,
                            open(path, "rb"),
                            mimetypes.guess_type(path.name)[0]
                            or "application/octet-stream",
                        ),
                    )
                    for path in files
                ]

            response = requests.post(
                url,
                headers=headers,
                data=payload,
                files=files_payload if files_payload else None,
                timeout=timeout,
            )
            response.raise_for_status()

            try:
                result = response.json()
            except ValueError:
                result = {"raw": response.text}

            logger.info(
                "ARAICHAT 送信成功: room_id=%s message_id=%s",
                room_id,
                result.get("message_id") if isinstance(result, dict) else None,
            )

            return {
                "message_id": result.get("message_id") if isinstance(result, dict) else None,
                "room_id": result.get("room_id") if isinstance(result, dict) else room_id,
                "files": result.get("files") if isinstance(result, dict) else None,
                "created_at": result.get("created_at") if isinstance(result, dict) else None,
                "status_code": response.status_code,
                "response": result,
            }

        except requests.HTTPError as exc:
            detail = _extract_error_detail(exc.response)
            logger.warning(
                "ARAICHAT HTTP エラー (attempt %s/%s): %s %s",
                attempt,
                retries,
                exc,
                f"detail={detail}" if detail else "",
            )
            if attempt >= retries:
                if detail:
                    raise RuntimeError(f"ARAICHAT HTTP エラー: {detail}") from exc
                raise

        except requests.RequestException as exc:
            logger.warning(
                "ARAICHAT リクエストエラー (attempt %s/%s): %s",
                attempt,
                retries,
                exc,
            )
            if attempt >= retries:
                raise

        finally:
            for _, (_, file_handle, _) in files_payload:
                try:
                    file_handle.close()
                except Exception:
                    pass

        if attempt < retries:
            wait_time = 2 * attempt
            logger.info("%s秒後にリトライします...", wait_time)
            time.sleep(wait_time)

    raise RuntimeError("ARAICHAT 送信に失敗しました")
