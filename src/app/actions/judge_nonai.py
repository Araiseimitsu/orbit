"""
ORBIT MVP - Non-AI Judge Actions
AIを使わない判定アクション（完全一致、部分一致、正規表現、数値比較）

使用例 (YAML):
    # 完全一致判定
    - id: check_status
      type: judge_equals
      params:
        target: "{{ step_1.status }}"
        value: "completed"

    # 部分一致判定
    - id: check_error
      type: judge_contains
      params:
        target: "{{ step_1.output }}"
        text: "ERROR"

    # 正規表現判定（プリセット）
    - id: check_email
      type: judge_regex
      params:
        target: "{{ step_1.email }}"
        preset: "email"

    # 正規表現判定（カスタム）
    - id: check_pattern
      type: judge_regex
      params:
        target: "{{ step_1.value }}"
        pattern: "^\\d{3}-\\d{4}$"

    # 数値範囲判定
    - id: check_count
      type: judge_numeric
      params:
        target: "{{ step_1.count }}"
        min: 10
        max: 100
"""

import logging
import re
from typing import Any

from ..core.registry import register_action

logger = logging.getLogger(__name__)

# judge_regex プリセット定義
REGEX_PRESETS: dict[str, dict[str, str]] = {
    "email": {
        "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "description": "メールアドレス形式",
    },
    "url": {
        "pattern": r"^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=]+$",
        "description": "URL形式（http/https）",
    },
    "phone": {
        "pattern": r"^(\+81|0)\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}$",
        "description": "電話番号形式（日本国内）",
    },
    "zipcode": {
        "pattern": r"^\d{3}[-\s]?\d{4}$",
        "description": "郵便番号形式（XXX-XXXX）",
    },
    "number": {
        "pattern": r"^-?\d+(\.\d+)?$",
        "description": "数値のみ（整数・小数）",
    },
}


def _to_string(value: Any) -> str:
    """値を文字列に変換"""
    if value is None:
        return ""
    return str(value)


def _to_number(value: Any, param_name: str = "target") -> float:
    """値を数値に変換

    Args:
        value: 変換対象の値
        param_name: パラメータ名（エラーメッセージ用）

    Returns:
        変換された数値

    Raises:
        ValueError: 数値に変換できない場合
    """
    if value is None:
        raise ValueError(f"{param_name} は必須です")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        raise ValueError(f"'{value}' を数値に変換できませんでした")


@register_action(
    "judge_equals",
    metadata={
        "title": "完全一致判定",
        "description": "値が指定値と完全一致するか判定します。大文字小文字は区別しません。",
        "category": "判定",
        "color": "#f97316",
        "params": [
            {
                "key": "target",
                "description": "判定対象の値",
                "required": True,
                "example": "{{ step_1.status }}"
            },
            {
                "key": "value",
                "description": "比較する値",
                "required": True,
                "example": "completed"
            },
            {
                "key": "ignore_case",
                "description": "大文字小文字を区別しない",
                "required": False,
                "default": True,
                "example": "true"
            }
        ],
        "outputs": [
            {"key": "result", "description": "判定結果 (yes/no)"},
            {"key": "reason", "description": "判定理由"},
            {"key": "provider", "description": "判定プロバイダ (nonai)"}
        ],
        "example": """steps:
  - id: check_status
    type: judge_equals
    params:
      target: "{{ step_1.status }}"
      value: "completed"
    when:
      step: check_status
      field: result
      equals: "yes"
"""
    }
)
async def action_judge_equals(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    完全一致判定を行う

    params:
        target: 判定対象（必須）
        value: 比較値（必須）
        ignore_case: 大文字小文字区別（デフォルト: True）

    returns:
        result: "yes" | "no"
        reason: 判定理由文字列
        provider: "nonai"
    """
    target = params.get("target")
    value = params.get("value")

    if target is None:
        raise ValueError("target は必須です")
    if value is None:
        raise ValueError("value は必須です")

    ignore_case = params.get("ignore_case", True)

    target_str = _to_string(target)
    value_str = _to_string(value)

    if ignore_case:
        is_match = target_str.lower() == value_str.lower()
    else:
        is_match = target_str == value_str

    if is_match:
        result = "yes"
        reason = f"'{target_str}' は '{value_str}' と一致します"
    else:
        result = "no"
        reason = f"'{target_str}' は '{value_str}' と一致しません"

    logger.info(f"judge_equals: {reason}")

    return {
        "result": result,
        "reason": reason,
        "provider": "nonai",
    }


@register_action(
    "judge_contains",
    metadata={
        "title": "部分一致判定",
        "description": "文字列に指定文字列が含まれるか判定します。大文字小文字は区別しません。",
        "category": "判定",
        "color": "#f97316",
        "params": [
            {
                "key": "target",
                "description": "判定対象の文字列",
                "required": True,
                "example": "{{ step_1.output }}"
            },
            {
                "key": "text",
                "description": "含まれているか確認する文字列",
                "required": True,
                "example": "ERROR"
            },
            {
                "key": "ignore_case",
                "description": "大文字小文字を区別しない",
                "required": False,
                "default": True,
                "example": "true"
            }
        ],
        "outputs": [
            {"key": "result", "description": "判定結果 (yes/no)"},
            {"key": "reason", "description": "判定理由"},
            {"key": "provider", "description": "判定プロバイダ (nonai)"}
        ],
        "example": """steps:
  - id: check_error
    type: judge_contains
    params:
      target: "{{ step_1.output }}"
      text: "ERROR"
"""
    }
)
async def action_judge_contains(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    部分一致判定を行う

    params:
        target: 判定対象文字列（必須）
        text: 含まれるべき文字列（必須）
        ignore_case: 大文字小文字区別（デフォルト: True）

    returns:
        result: "yes" | "no"
        reason: 判定理由文字列
        provider: "nonai"
    """
    target = params.get("target")
    text = params.get("text")

    if target is None:
        raise ValueError("target は必須です")
    if text is None:
        raise ValueError("text は必須です")

    ignore_case = params.get("ignore_case", True)

    target_str = _to_string(target)
    text_str = _to_string(text)

    if ignore_case:
        is_match = text_str.lower() in target_str.lower()
    else:
        is_match = text_str in target_str

    if is_match:
        result = "yes"
        reason = f"'{target_str}' に '{text_str}' が含まれています"
    else:
        result = "no"
        reason = f"'{target_str}' に '{text_str}' は含まれていません"

    logger.info(f"judge_contains: {reason}")

    return {
        "result": result,
        "reason": reason,
        "provider": "nonai",
    }


@register_action(
    "judge_regex",
    metadata={
        "title": "正規表現判定",
        "description": "正規表現パターンにマッチするか判定します。プリセットまたはカスタムパターンが使用可能です。",
        "category": "判定",
        "color": "#f97316",
        "params": [
            {
                "key": "target",
                "description": "判定対象の文字列",
                "required": True,
                "example": "{{ step_1.email }}"
            },
            {
                "key": "preset",
                "description": "プリセット名 (email, url, phone, zipcode, number)",
                "required": False,
                "example": "email"
            },
            {
                "key": "pattern",
                "description": "カスタム正規表現パターン",
                "required": False,
                "example": "^\\d{3}-\\d{4}$"
            }
        ],
        "outputs": [
            {"key": "result", "description": "判定結果 (yes/no)"},
            {"key": "reason", "description": "判定理由"},
            {"key": "provider", "description": "判定プロバイダ (nonai)"},
            {"key": "matched", "description": "マッチした文字列"}
        ],
        "example": """steps:
  # プリセット使用
  - id: check_email
    type: judge_regex
    params:
      target: "{{ step_1.email }}"
      preset: "email"

  # カスタムパターン使用
  - id: check_zipcode
    type: judge_regex
    params:
      target: "{{ step_1.zipcode }}"
      pattern: "^\\\\d{3}-\\\\d{4}$"
"""
    }
)
async def action_judge_regex(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    正規表現判定を行う

    params:
        target: 判定対象文字列（必須）
        preset: プリセット名（オプション）
        pattern: カスタム正規表現パターン（オプション）

    returns:
        result: "yes" | "no"
        reason: 判定理由文字列
        provider: "nonai"
        matched: マッチした文字列（ある場合）
    """
    target = params.get("target")

    if target is None:
        raise ValueError("target は必須です")

    preset = params.get("preset")
    pattern = params.get("pattern")

    # preset または pattern のどちらかが必要
    if not preset and not pattern:
        raise ValueError(
            f"preset または pattern のいずれかを指定してください。"
            f"利用可能なプリセット: {', '.join(REGEX_PRESETS.keys())}"
        )

    # プリセットからパターンを取得
    if preset:
        if preset not in REGEX_PRESETS:
            raise ValueError(
                f"プリセット '{preset}' は存在しません。"
                f"利用可能なプリセット: {', '.join(REGEX_PRESETS.keys())}"
            )
        pattern = REGEX_PRESETS[preset]["pattern"]
        preset_desc = REGEX_PRESETS[preset]["description"]
    else:
        preset_desc = "カスタムパターン"

    target_str = _to_string(target)

    # 正規表現コンパイルとマッチ判定
    try:
        regex = re.compile(pattern)
        match = regex.search(target_str)
    except re.error as e:
        raise ValueError(f"正規表現パターンが不正です: {e}")

    if match:
        matched_text = match.group(0)
        result = "yes"
        reason = f"'{target_str}' は {preset_desc} にマッチします: '{matched_text}'"
    else:
        matched_text = ""
        result = "no"
        reason = f"'{target_str}' は {preset_desc} にマッチしません"

    logger.info(f"judge_regex: {reason}")

    return {
        "result": result,
        "reason": reason,
        "provider": "nonai",
        "matched": matched_text,
    }


@register_action(
    "judge_numeric",
    metadata={
        "title": "数値比較判定",
        "description": "数値を比較して条件を満たすか判定します。min/maxで範囲指定、equalで等値判定が可能です。",
        "category": "判定",
        "color": "#f97316",
        "params": [
            {
                "key": "target",
                "description": "判定対象の数値（文字列から自動変換）",
                "required": True,
                "example": "{{ step_1.count }}"
            },
            {
                "key": "min",
                "description": "最小値（以上）",
                "required": False,
                "example": "10"
            },
            {
                "key": "max",
                "description": "最大値（以下）",
                "required": False,
                "example": "100"
            },
            {
                "key": "equal",
                "description": "等値",
                "required": False,
                "example": "50"
            }
        ],
        "outputs": [
            {"key": "result", "description": "判定結果 (yes/no)"},
            {"key": "reason", "description": "判定理由"},
            {"key": "provider", "description": "判定プロバイダ (nonai)"}
        ],
        "example": """steps:
  # 範囲判定（10以上100以下）
  - id: check_range
    type: judge_numeric
    params:
      target: "{{ step_1.count }}"
      min: 10
      max: 100

  # 等値判定
  - id: check_equal
    type: judge_numeric
    params:
      target: "{{ step_1.count }}"
      equal: 50
"""
    }
)
async def action_judge_numeric(
    params: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    数値比較判定を行う

    params:
        target: 判定対象数値（必須）
        min: 最小値（以上、オプション）
        max: 最大値（以下、オプション）
        equal: 等値（オプション）

    returns:
        result: "yes" | "no"
        reason: 判定理由文字列
        provider: "nonai"
    """
    target = params.get("target")
    min_val = params.get("min")
    max_val = params.get("max")
    equal_val = params.get("equal")

    if target is None:
        raise ValueError("target は必須です")

    # min, max, equal の少なくとも1つが必要
    if min_val is None and max_val is None and equal_val is None:
        raise ValueError("min, max, equal のいずれか1つ以上を指定してください")

    # 数値に変換
    try:
        target_num = _to_number(target, "target")
    except ValueError as e:
        raise ValueError(e)

    # minとmaxの範囲チェック
    if min_val is not None and max_val is not None:
        min_num = _to_number(min_val, "min")
        max_num = _to_number(max_val, "max")
        if min_num > max_num:
            raise ValueError(f"min({min_num}) は max({max_num}) 以下で指定してください")

    # 判定実行
    result = "no"
    reason_parts = []

    if equal_val is not None:
        equal_num = _to_number(equal_val, "equal")
        is_equal = target_num == equal_num
        if is_equal:
            result = "yes"
            reason_parts.append(f"{equal_num} と等しい")
        else:
            reason_parts.append(f"{equal_num} と等しくない")

    if min_val is not None:
        min_num = _to_number(min_val, "min")
        is_min_ok = target_num >= min_num
        if is_min_ok:
            result = "yes"
            reason_parts.append(f"{min_num} 以上")
        else:
            result = "no"
            reason_parts.append(f"{min_num} 未満")

    if max_val is not None:
        max_num = _to_number(max_val, "max")
        is_max_ok = target_num <= max_num
        if is_max_ok:
            if min_val is None or result == "yes":
                result = "yes"
            reason_parts.append(f"{max_num} 以下")
        else:
            result = "no"
            reason_parts.append(f"{max_num} より大きい")

    # reason の組み立て
    if result == "yes":
        reason = f"{target_num} は {', '.join(reason_parts)}"
    else:
        reason = f"{target_num} は {', '.join(reason_parts)}"

    logger.info(f"judge_numeric: {reason}")

    return {
        "result": result,
        "reason": reason,
        "provider": "nonai",
    }
