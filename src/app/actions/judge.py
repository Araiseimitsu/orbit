"""
ORBIT MVP - Judge Action
AIによるyes/no判定アクション

API キー設定:
    secrets/gemini_api_key.txt に Gemini API キー

使用例 (YAML):
    - id: judge_error
      type: judge
      params:
        target: "{{ step_1.text }}"
        question: "このテキストにエラーが含まれているか"

    - id: on_error
      type: log
      params:
        message: "エラーが検出されました"
      when:
        step: judge_error
        field: result
        equals: "yes"
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import requests

from ..core.registry import register_action
from ..core.retry import retry_async

logger = logging.getLogger(__name__)

# デフォルトの API キーファイルパス
DEFAULT_GEMINI_KEY_FILE = "secrets/gemini_api_key.txt"
DEFAULT_GEMINI_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_TIMEOUT = 30
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _load_api_key(file_path: str, base_dir: Path, env_var_name: str) -> str:
    """
    API キーを環境変数 → ファイルの順で読み込む

    Args:
        file_path: フォールバック用ファイルパス
        base_dir: ベースディレクトリ
        env_var_name: 環境変数名（例: "GEMINI_API_KEY"）

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


@retry_async(
    max_attempts=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError),
)
async def _call_judge_gemini(
    target: str,
    question: str,
    api_key: str,
    model: str = "gemini-2.5-flash-lite",
) -> dict[str, Any]:
    """
    Gemini API で yes/no 判定を実行

    Args:
        target: 判定対象テキスト
        question: 判定質問（例: "エラーが含まれているか"）
        api_key: Gemini API キー
        model: モデル名

    Returns:
        {
            "result": "yes" | "no",
            "raw": "生の応答テキスト",
            "reason": "判定理由",
            "model": "使用モデル"
        }
    """
    loop = asyncio.get_event_loop()

    def _do_request():
        # プロンプト構築
        prompt = f"""次の判定を行ってください。

【判定対象】
{target}

【判定質問】
{question}

【出力形式】
必ず以下のJSON形式のみで回答してください（それ以外の文字列を含めないでください）：
{{"result": "yes" または "no", "reason": "判定理由（簡潔に）"}}"""

        url = f"{GEMINI_API_BASE}/{model}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 500,
            }
        }

        response = requests.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    data = await loop.run_in_executor(None, _do_request)

    # 応答からテキストを抽出
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not candidates:
        raise ValueError("Gemini の応答に candidates がありません")
    candidate = candidates[0] if isinstance(candidates[0], dict) else {}
    content = candidate.get("content") if isinstance(candidate, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    texts: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    raw = "\n".join(texts).strip()
    if not raw:
        raise ValueError("Gemini の応答テキストが空です")

    # JSONをパース
    reason = ""
    result = ""

    # マークダウンコードブロックを除去
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if json_match:
        json_text = json_match.group(1).strip()
    else:
        json_text = raw

    # JSONオブジェクトを探す
    obj_match = re.search(r'\{[^{}]*"result"\s*:\s*"[^"]*"[^{}]*\}', json_text)
    if obj_match:
        json_text = obj_match.group(0)

    try:
        parsed = json.loads(json_text)
        result = parsed.get("result", "").lower().strip()
        reason = parsed.get("reason", "")
    except (json.JSONDecodeError, ValueError):
        # JSONパース失敗時はテキストからyes/noを抽出
        lower_raw = raw.lower()
        if "yes" in lower_raw or "はい" in raw:
            result = "yes"
        elif "no" in lower_raw or "いいえ" in raw:
            result = "no"
        else:
            result = "no"
        reason = raw

    # resultを正規化
    if result in ("yes", "y", "true", "1", "はい"):
        result = "yes"
    elif result in ("no", "n", "false", "0", "いいえ"):
        result = "no"
    else:
        # デフォルトはno
        result = "no"

    return {
        "result": result,
        "raw": raw,
        "reason": reason,
        "model": model,
        "provider": "gemini",
    }


@register_action(
    "judge",
    metadata={
        "title": "AI判定",
        "description": "テキストに対してAIでyes/no判定を行います。条件分岐に使用できます。",
        "category": "AI",
        "params": [
            {
                "key": "target",
                "description": "判定対象テキスト（Jinja2テンプレート可）",
                "required": True,
                "example": "{{ step_1.text }}"
            },
            {
                "key": "question",
                "description": "判定質問（例: エラーが含まれているか）",
                "required": True,
                "example": "このテキストにエラーが含まれているか"
            },
            {
                "key": "model",
                "description": "モデル名",
                "required": False,
                "example": "gemini-2.5-flash-lite"
            },
            {
                "key": "api_key_file",
                "description": "APIキーのファイルパス",
                "required": False,
                "example": "secrets/gemini_api_key.txt"
            }
        ],
        "outputs": [
            {"key": "result", "description": "判定結果 (yes/no)"},
            {"key": "raw", "description": "生の応答テキスト"},
            {"key": "reason", "description": "判定理由"},
            {"key": "model", "description": "使用モデル"}
        ],
        "example": """steps:
  - id: judge_error
    type: judge
    params:
      target: "{{ step_1.text }}"
      question: "このテキストにエラーが含まれているか"

  - id: on_error
    type: log
    params:
      message: "エラーが検出されました: {{ step_1.reason }}"
    when:
      step: judge_error
      field: result
      equals: "yes" """
    }
)
async def action_judge(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    AI で yes/no 判定を行う

    params:
        target: 判定対象テキスト（必須）
        question: 判定質問（必須）
        model: モデル名（デフォルト: gemini-2.5-flash-lite）
        api_key_file: APIキーファイルパス（オプション）

    returns:
        result: "yes" | "no"
        raw: 生の応答
        reason: 判定理由
        model: 使用モデル
        provider: "gemini"
    """
    target = params.get("target")
    question = params.get("question")
    model = params.get("model", "gemini-2.5-flash-lite")

    if not target:
        raise ValueError("target は必須です")
    if not question:
        raise ValueError("question は必須です")

    # API キーの読み込み
    base_dir = context.get("base_dir", Path.cwd())
    api_key_file = params.get("api_key_file", DEFAULT_GEMINI_KEY_FILE)
    api_key = _load_api_key(api_key_file, base_dir, DEFAULT_GEMINI_KEY_ENV)

    # 判定実行
    result = await _call_judge_gemini(target, question, api_key, model)
    return result
