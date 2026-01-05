"""
ORBIT - AI フロー自動構築（Gemini）
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import requests
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from .actions.ai import DEFAULT_GEMINI_KEY_FILE, _call_gemini, _load_api_key
from .core.registry import ActionRegistry

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_MAX_TOKENS = 1400
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT = 30
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

PROJECT_CONTEXT = """\
ORBIT は n8n ライクなワークフロー実行アプリ（MVP）です。
- ワークフローは trigger と steps で構成されます。
- trigger: manual または schedule（cron）
- steps: id / type / params / when / meta
- params は Jinja2 テンプレートが利用でき、出力参照は {{ step_id.key }}。
- 共通変数: {{ run_id }}, {{ now }}, {{ today }}, {{ yesterday }}, {{ tomorrow }}, {{ today_ymd }}, {{ now_ymd_hms }}, {{ workflow }}, {{ base_dir }}
- when: 指定ステップの出力が一致した場合のみ実行。
"""


def _build_system_prompt() -> str:
    return (
        "あなたは ORBIT のワークフロー設計支援AIです。"
        "必ず JSON だけを返し、説明文やコードフェンスは出力しないでください。"
        "出力スキーマ:\n"
        "{"
        ' "name": str,'
        ' "description": str,'
        ' "enabled": bool,'
        ' "trigger": {"type": "manual" | "schedule", "cron"?: str},'
        ' "steps": ['
        '   {"id": str, "type": str, "params": object, "when"?: object, "position"?: object}'
        " ]"
        "}\n"
        "制約:\n"
        "- type は available_actions にあるもののみ使用。\n"
        "- id は英数字と _ のみ、ユニーク。\n"
        "- steps は実行順で並べる。\n"
        "- schedule の場合は cron を必須。\n"
    )


def _build_user_prompt(
    user_prompt: str,
    actions_meta: dict[str, Any],
    current_workflow: dict[str, Any] | None,
) -> str:
    actions_json = json.dumps(actions_meta, ensure_ascii=False, indent=2)
    current_json = (
        json.dumps(current_workflow, ensure_ascii=False, indent=2)
        if current_workflow
        else "null"
    )
    return (
        f"## プロジェクト概要\n{PROJECT_CONTEXT}\n\n"
        "## 利用可能アクション\n"
        f"{actions_json}\n\n"
        "## 現在のワークフロー（参考）\n"
        f"{current_json}\n\n"
        "## ユーザー要望\n"
        f"{user_prompt}\n\n"
        "上記を踏まえて、ワークフロー JSON を生成してください。"
    )


def _call_gemini_rest(
    prompt: str,
    model: str,
    api_key: str,
    system: str | None,
    max_tokens: int | None,
    temperature: float | None,
    use_search: bool,
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
        raise ValueError("AI の応答に candidates がありません")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    texts = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    text = "\n".join(texts).strip()
    if not text:
        raise ValueError("AI の応答テキストが空です")

    return {"text": text, "model": model, "provider": "gemini", "raw": data}


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("AI の応答が空です")

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("AI の応答から JSON を抽出できませんでした")

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError("AI の応答が JSON として解析できませんでした") from exc


def _sanitize_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "step"
    sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", text)
    return sanitized.strip("_") or "step"


def _unique_id(base: str, used: set[str]) -> str:
    candidate = base
    index = 1
    while candidate in used:
        index += 1
        candidate = f"{base}_{index}"
    used.add(candidate)
    return candidate


def _normalize_position(_raw: Any, index: int) -> dict[str, int]:
    return {"x": 80, "y": 80 + index * 120}


def _normalize_steps(
    raw_steps: Any,
    registry: ActionRegistry,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list):
        raise ValueError("AI の steps が配列ではありません")

    used_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            warnings.append(f"step[{index}] を読み飛ばしました（形式不正）")
            continue
        step_type = str(raw.get("type") or "").strip()
        if not step_type:
            warnings.append(f"step[{index}] に type がありません")
            continue
        if not registry.has(step_type):
            warnings.append(f"未登録アクションを除外しました: {step_type}")
            continue

        step_id = _unique_id(_sanitize_id(raw.get("id") or step_type), used_ids)
        params = raw.get("params") if isinstance(raw.get("params"), dict) else {}

        when_raw = raw.get("when")
        when = None
        if isinstance(when_raw, dict):
            step_ref = str(when_raw.get("step") or "").strip()
            equals = when_raw.get("equals")
            if step_ref and equals is not None and not (
                isinstance(equals, str) and equals.strip() == ""
            ):
                field = str(when_raw.get("field") or "text").strip() or "text"
                when = {"step": step_ref, "field": field, "equals": equals}
                if isinstance(when_raw.get("trim"), bool):
                    when["trim"] = when_raw["trim"]
                if isinstance(when_raw.get("case_insensitive"), bool):
                    when["case_insensitive"] = when_raw["case_insensitive"]

        position = _normalize_position(raw.get("position"), index)

        step_data = {"id": step_id, "type": step_type, "params": params, "position": position}
        if when:
            step_data["when"] = when

        normalized.append(step_data)

    if not normalized:
        raise ValueError("有効なステップが生成されませんでした")

    return normalized


def _normalize_trigger(raw: Any, warnings: list[str]) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {"type": "manual"}

    trigger_type = str(raw.get("type") or "manual").strip()
    if trigger_type == "schedule":
        cron = (raw.get("cron") or "").strip()
        if not cron:
            warnings.append("schedule 指定ですが cron がありません。manual に変更しました。")
            return {"type": "manual"}
        try:
            CronTrigger.from_crontab(cron, timezone=ZoneInfo("Asia/Tokyo"))
        except ValueError:
            warnings.append("cron が不正なため manual に変更しました。")
            return {"type": "manual"}
        return {"type": "schedule", "cron": cron}

    if trigger_type != "manual":
        warnings.append(f"未対応 trigger を manual に変更しました: {trigger_type}")
    return {"type": "manual"}


def _normalize_workflow(
    raw: dict[str, Any],
    registry: ActionRegistry,
    current_workflow: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    name = str(raw.get("name") or "").strip()
    if not name and current_workflow:
        name = str(current_workflow.get("name") or "").strip()
    if not name:
        name = "ai_flow"

    description = raw.get("description")
    if isinstance(description, str):
        description = description.strip()
    else:
        description = ""

    enabled = raw.get("enabled")
    if not isinstance(enabled, bool):
        enabled = True

    trigger = _normalize_trigger(raw.get("trigger"), warnings)
    steps = _normalize_steps(raw.get("steps"), registry, warnings)

    workflow = {
        "name": name,
        "description": description,
        "enabled": enabled,
        "trigger": trigger,
        "steps": steps,
    }

    return workflow, warnings


def generate_ai_flow(
    user_prompt: str,
    registry: ActionRegistry,
    base_dir: Path,
    current_workflow: dict[str, Any] | None = None,
    model: str = DEFAULT_MODEL,
    use_search: bool = True,
) -> dict[str, Any]:
    api_key = _load_api_key(DEFAULT_GEMINI_KEY_FILE, base_dir)
    actions_meta = registry.list_all_metadata()

    system = _build_system_prompt()
    prompt = _build_user_prompt(user_prompt, actions_meta, current_workflow)

    if use_search:
        result = _call_gemini_rest(
            prompt=prompt,
            model=model,
            api_key=api_key,
            system=system,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
            use_search=True,
        )
    else:
        result = _call_gemini(
            prompt=prompt,
            model=model,
            api_key=api_key,
            system=system,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
        )
    raw_text = result.get("text", "")
    payload = _extract_json(raw_text)

    workflow, warnings = _normalize_workflow(payload, registry, current_workflow)

    logger.info(
        "AI flow generated: steps=%s warnings=%s",
        len(workflow.get("steps") or []),
        len(warnings),
    )

    return {"workflow": workflow, "warnings": warnings}
