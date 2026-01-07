"""
ORBIT MVP - Template Rendering
Jinja2 を使ったパラメータの変数展開
"""
import logging
from typing import Any

from jinja2 import Environment, BaseLoader, UndefinedError

logger = logging.getLogger(__name__)

# Jinja2 環境（文字列テンプレート用）
_env = Environment(loader=BaseLoader())


def render_value(value: Any, context: dict[str, Any]) -> Any:
    """
    値をテンプレートレンダリング

    文字列なら Jinja2 で展開、dictやlistは再帰的に処理
    """
    if isinstance(value, str):
        return render_string(value, context)
    elif isinstance(value, dict):
        return {k: render_value(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [render_value(item, context) for item in value]
    else:
        return value


def render_string(template_str: str, context: dict[str, Any]) -> Any:
    """
    文字列を Jinja2 でレンダリング

    {{ step_id.output_key }} のような変数参照を展開

    単一変数参照（例: "{{ step_id.raw }}"）の場合は、
    元の型（リスト、辞書など）を保持して返す
    """
    if "{{" not in template_str and "{%" not in template_str:
        return template_str

    # 単一変数参照チェック: "{{ var }}" のみで構成される場合
    stripped = template_str.strip()
    if stripped.startswith("{{") and stripped.endswith("}}"):
        # Jinja2式として評価して元の型を保持
        expr = stripped[2:-2].strip()
        try:
            # コンテキストから直接値を取得
            if expr in context:
                return context[expr]
            # ドット記法（step_1.raw）に対応
            parts = expr.split(".")
            if parts[0] in context:
                value = context[parts[0]]
                for part in parts[1:]:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = getattr(value, part, None)
                    if value is None:
                        break
                if value is not None:
                    return value
        except (KeyError, AttributeError, TypeError):
            pass

    # 通常の文字列レンダリング（複数の変数を含む場合など）
    try:
        template = _env.from_string(template_str)
        return template.render(**context)
    except UndefinedError as e:
        logger.warning(f"Template variable not found: {e}")
        return template_str
    except Exception as e:
        logger.error(f"Template render error: {e}")
        return template_str


def render_params(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    paramsの全フィールドをテンプレートレンダリング
    """
    return render_value(params, context)
