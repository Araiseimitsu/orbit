"""
ORBIT MVP - Template Rendering
Jinja2 を使ったパラメータの変数展開
"""

import ast
import json
import logging
import re
from typing import Any

from jinja2 import BaseLoader, Environment
from jinja2.runtime import Undefined

logger = logging.getLogger(__name__)

# Jinja2 環境（文字列テンプレート用）
_env = Environment(loader=BaseLoader())


def _tojson_utf8(value: Any, indent: int | None = None) -> str:
    """日本語をエスケープせずにJSON文字列化する（ワークフロー用）"""
    indent_value: int | None
    if indent is None:
        indent_value = None
    else:
        try:
            indent_value = int(indent)
        except (TypeError, ValueError):
            indent_value = None

    return json.dumps(value, ensure_ascii=False, indent=indent_value, default=str)


_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def _strip_or_extract_code_block(text: str) -> str:
    """```json ... ``` の内側があればそれを優先して返す"""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    match = _CODE_BLOCK_RE.search(cleaned)
    if match:
        return (match.group(1) or "").strip()
    return cleaned


def _extract_balanced_json_like(text: str) -> str | None:
    """文字列中から最初の JSON（object/array）らしき塊を抽出する。

    - 先頭の '{' または '[' から開始
    - 文字列リテラル（"...")内の括弧は無視
    - {} と [] のネストを両方追跡

    Returns:
        抽出できた場合は部分文字列、できなければ None
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    start_candidates = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
    if not start_candidates:
        return None

    start = min(start_candidates)

    open_to_close = {"{": "}", "[": "]"}
    close_to_open = {"}": "{", "]": "["}

    stack: list[str] = []
    in_string = False
    escape = False

    for idx in range(start, len(cleaned)):
        ch = cleaned[idx]

        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch in open_to_close:
            stack.append(ch)
            continue

        if ch in close_to_open:
            if not stack:
                return None
            expected_open = close_to_open[ch]
            if stack[-1] != expected_open:
                return None
            stack.pop()
            if not stack:
                return cleaned[start : idx + 1]

    return None


def _is_safe_literal(value: Any) -> bool:
    """ast.literal_eval の結果が安全なJSON互換型かを確認"""
    if value is None:
        return True
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_safe_literal(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_safe_literal(v) for k, v in value.items())
    return False


def _fromjson(value: Any) -> Any:
    """JSON文字列をPythonオブジェクトへ変換する。

    ワークフローでAI出力（text）を2次元配列に戻す用途を想定。

    - ```json ... ``` のコードブロックがあれば内側を優先
    - JSON全体が返ってこない場合は、本文から最初のJSON塊（{} / []）を抽出して解析
    - それでも失敗した場合は、Pythonリテラル（[['a', ...]]）を ast.literal_eval でフォールバック

    注意:
        テンプレートからは例外を投げず、失敗時は ValueError を発生させる。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    cleaned = _strip_or_extract_code_block(value)
    if not cleaned:
        return None

    # まずは全体をJSONとして解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 本文から最初のJSON塊を抽出して再試行
    extracted = _extract_balanced_json_like(cleaned)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            cleaned = extracted

    # フォールバック: Pythonリテラル（シングルクォート等）
    try:
        parsed = ast.literal_eval(cleaned)
    except Exception as exc:
        raise ValueError("fromjson: JSONとして解析できません") from exc

    if not _is_safe_literal(parsed):
        raise ValueError("fromjson: 許可されない型が含まれています")

    return parsed


_env.filters["tojson_utf8"] = _tojson_utf8
_env.filters["fromjson"] = _fromjson


def render_value(value: Any, context: dict[str, Any]) -> Any:
    """値をテンプレートレンダリング

    - 文字列なら Jinja2 で展開
    - dict / list は再帰的に処理
    """
    if isinstance(value, str):
        return render_string(value, context)
    if isinstance(value, dict):
        return {k: render_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    return value


def render_string(template_str: str, context: dict[str, Any]) -> Any:
    """文字列を Jinja2 でレンダリング

    - {{ step_id.output_key }} のような変数参照を展開
    - 単一の式（例: "{{ step_1.raw | fromjson }}"）の場合は、元の型（list/dict/int等）を保持して返す
    """
    if "{{" not in template_str and "{%" not in template_str:
        return template_str

    stripped = template_str.strip()

    # 単一式: "{{ ... }}" のみ
    if stripped.startswith("{{") and stripped.endswith("}}") and "{%" not in stripped:
        expr = stripped[2:-2].strip()
        try:
            compiled = _env.compile_expression(expr)
            value = compiled(**context)
            if isinstance(value, Undefined):
                return ""
            return value
        except Exception as exc:
            logger.warning(f"Template expression eval error: {exc}")
            # 失敗時は通常レンダリングへフォールバック

    try:
        template = _env.from_string(template_str)
        return template.render(**context)
    except Exception as exc:
        logger.error(f"Template render error: {exc}")
        return template_str


def render_params(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """paramsの全フィールドをテンプレートレンダリング"""
    return render_value(params, context)
