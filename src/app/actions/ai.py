"""
ORBIT MVP - AI アクション

Gemini を使用したテキスト生成アクション。

API キー設定:
    secrets/gemini_api_key.txt に Gemini API キー

使用例 (YAML):
    - id: generate
      type: ai_generate
      params:
        model: gemini-2.5-flash-lite
        prompt: "次の要約を作成: {{ step_1.text }}"
        system: "あなたは優秀なアシスタントです"
        max_tokens: 1000
"""

import logging
from pathlib import Path
from typing import Any

import google.generativeai as genai
import requests

from ..core.registry import register_action

logger = logging.getLogger(__name__)

# デフォルトの API キーファイルパス
DEFAULT_GEMINI_KEY_FILE = "secrets/gemini_api_key.txt"
DEFAULT_TIMEOUT = 30
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


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


def _coerce_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} は数値で指定してください")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{label} は数値で指定してください") from exc
    raise ValueError(f"{label} は数値で指定してください")


def _coerce_bool(value: Any, label: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"{label} は true/false で指定してください")
    if isinstance(value, str):
        text = value.strip().lower()
        if text == "":
            return None
        if text in ("true", "1", "yes", "on"):
            return True
        if text in ("false", "0", "no", "off"):
            return False
    raise ValueError(f"{label} は true/false で指定してください")


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


def _call_gemini(
    prompt: str,
    model: str,
    api_key: str,
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Gemini API を呼び出す"""
    genai.configure(api_key=api_key)

    model_client = genai.GenerativeModel(model)

    # システムプロンプトの設定
    if system:
        # Gemini では system_instruction として設定
        model_client = genai.GenerativeModel(model, system_instruction=system)

    # 生成設定
    generation_config = {}
    if max_tokens:
        generation_config["max_output_tokens"] = max_tokens
    if temperature is not None:
        generation_config["temperature"] = temperature

    logger.info(f"Gemini 生成開始: model={model}")

    result = model_client.generate_content(
        prompt, generation_config=generation_config if generation_config else None
    )

    return {
        "text": result.text,
        "model": model,
        "provider": "gemini",
        "finish_reason": result.candidates[0].finish_reason.name
        if result.candidates
        else None,
        "prompt_tokens": result.usage_metadata.total_token_count
        if hasattr(result, "usage_metadata")
        else None,
    }


def _call_gemini_rest(
    prompt: str,
    model: str,
    api_key: str,
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    use_search: bool = False,
) -> dict[str, Any]:
    url = f"{GEMINI_API_BASE}/{model}:generateContent"
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    generation_config: dict[str, Any] = {}
    if max_tokens:
        generation_config["maxOutputTokens"] = max_tokens
    if temperature is not None:
        generation_config["temperature"] = temperature
    if generation_config:
        payload["generationConfig"] = generation_config
    if use_search:
        payload["tools"] = [{"google_search": {}}]

    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
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
    text = "\n".join(texts).strip()
    if not text:
        raise ValueError("Gemini の応答テキストが空です")

    grounding = candidate.get("groundingMetadata") if isinstance(candidate, dict) else None
    usage = data.get("usageMetadata") if isinstance(data, dict) else None

    return {
        "text": text,
        "model": model,
        "provider": "gemini",
        "finish_reason": candidate.get("finishReason"),
        "prompt_tokens": usage.get("totalTokenCount") if isinstance(usage, dict) else None,
        "grounding": grounding,
        "raw": data,
    }


@register_action(
    "ai_generate",
    metadata={
        "title": "AI 生成",
        "description": "プロンプトをAIに渡してテキストを生成します。",
        "category": "AI",
        "params": [
            {
                "key": "prompt",
                "description": "生成指示",
                "required": True,
                "example": "次を要約: {{ step_1.text }}"
            },
            {
                "key": "system",
                "description": "システムプロンプト",
                "required": False,
                "example": "あなたは優秀なアシスタントです"
            },
            {
                "key": "provider",
                "description": "プロバイダー",
                "required": False,
                "default": "gemini",
                "example": "gemini"
            },
            {
                "key": "model",
                "description": "モデル名",
                "required": False,
                "example": "gemini-2.5-flash-lite"
            },
            {
                "key": "max_tokens",
                "description": "最大出力トークン数",
                "required": False,
                "example": "1000"
            },
            {
                "key": "temperature",
                "description": "温度パラメータ（0.0〜1.0）",
                "required": False,
                "example": "0.7"
            },
            {
                "key": "use_search",
                "description": "Web検索（Google Search）を有効化する",
                "required": False,
                "example": "true"
            },
            {
                "key": "api_key_file",
                "description": "APIキーのファイルパス",
                "required": False,
                "example": "secrets/gemini_api_key.txt"
            }
        ],
        "outputs": [
            {"key": "text", "description": "生成テキスト"},
            {"key": "model", "description": "使用モデル"},
            {"key": "provider", "description": "プロバイダー"},
            {"key": "finish_reason", "description": "完了理由"},
            {"key": "prompt_tokens", "description": "入力トークン数"},
            {"key": "grounding", "description": "Web検索の根拠情報（ある場合）"}
        ]
    }
)
async def action_ai_generate(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    AI でテキストを生成する

    params:
        provider: "gemini" のみ (デフォルト: gemini)
        model: モデル名
            - Gemini: "gemini-2.5-flash-lite", "gemini-1.5-pro", etc.
        prompt: プロンプトテキスト (必須)
        system: システムプロンプト (オプション)
        max_tokens: 最大出力トークン数 (オプション)
        temperature: 温度パラメータ 0.0-1.0 (オプション)
        use_search: Web検索（Google Search）を有効化 (オプション)
        api_key_file: API キーファイルパス (オプション、デフォルト: secrets/*_api_key.txt)

    Returns:
        {
            "text": "生成されたテキスト",
            "model": "使用したモデル名",
            "provider": "gemini",
            "finish_reason": "完了理由",
            "prompt_tokens": int,
            "grounding": dict | None,
            ...
        }
    """
    provider = params.get("provider", "gemini").lower()
    model = params.get("model")
    prompt = params.get("prompt")

    if not prompt:
        raise ValueError("prompt は必須です")

    # デフォルトモデル
    if not model:
        model = "gemini-2.5-flash-lite"

    # オプションパラメータ
    system = params.get("system")
    max_tokens = _coerce_int(params.get("max_tokens"), "max_tokens")
    temperature = _coerce_float(params.get("temperature"), "temperature")
    use_search = _coerce_bool(params.get("use_search"), "use_search")
    if use_search is None:
        use_search = False

    # API キーの読み込み
    base_dir = context.get("base_dir", Path.cwd())

    if provider != "gemini":
        raise ValueError(f"未対応の provider です: {provider}")

    api_key_file = params.get("api_key_file", DEFAULT_GEMINI_KEY_FILE)
    api_key = _load_api_key(api_key_file, base_dir, "GEMINI_API_KEY")

    if use_search:
        return _call_gemini_rest(
            prompt=prompt,
            model=model,
            api_key=api_key,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            use_search=True,
        )

    return _call_gemini(
        prompt=prompt,
        model=model,
        api_key=api_key,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
    )
