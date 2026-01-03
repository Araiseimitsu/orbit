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

from ..core.registry import register_action

logger = logging.getLogger(__name__)

# デフォルトの API キーファイルパス
DEFAULT_GEMINI_KEY_FILE = "secrets/gemini_api_key.txt"


def _load_api_key(file_path: str, base_dir: Path) -> str:
    """ファイルから API キーを読み込む"""
    path = Path(file_path)
    if not path.is_absolute():
        path = base_dir / path

    if not path.exists():
        raise FileNotFoundError(
            f"API キーファイルが見つかりません: {path}\n"
            f"{path.name} に API キーを配置してください。"
        )

    key = path.read_text().strip()
    if not key:
        raise ValueError(f"API キーファイルが空です: {path}")

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
        model_client = genai.GenerativeModel(
            model,
            system_instruction=system
        )

    # 生成設定
    generation_config = {}
    if max_tokens:
        generation_config["max_output_tokens"] = max_tokens
    if temperature is not None:
        generation_config["temperature"] = temperature

    logger.info(f"Gemini 生成開始: model={model}")

    result = model_client.generate_content(
        prompt,
        generation_config=generation_config if generation_config else None
    )

    return {
        "text": result.text,
        "model": model,
        "provider": "gemini",
        "finish_reason": result.candidates[0].finish_reason.name if result.candidates else None,
        "prompt_tokens": result.usage_metadata.total_token_count if hasattr(result, "usage_metadata") else None,
    }


@register_action("ai_generate")
async def action_ai_generate(
    params: dict[str, Any],
    context: dict[str, Any]
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
        api_key_file: API キーファイルパス (オプション、デフォルト: secrets/*_api_key.txt)

    Returns:
        {
            "text": "生成されたテキスト",
            "model": "使用したモデル名",
            "provider": "gemini",
            "finish_reason": "完了理由",
            "prompt_tokens": int,
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
    max_tokens = params.get("max_tokens")
    temperature = params.get("temperature")

    # API キーの読み込み
    base_dir = context.get("base_dir", Path.cwd())

    if provider != "gemini":
        raise ValueError(f"未対応の provider です: {provider}")

    api_key_file = params.get("api_key_file", DEFAULT_GEMINI_KEY_FILE)
    api_key = _load_api_key(api_key_file, base_dir)

    return _call_gemini(
        prompt=prompt,
        model=model,
        api_key=api_key,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
    )
