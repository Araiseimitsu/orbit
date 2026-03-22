"""
ORBIT - スキルローダー

skills/<スキル名>/SKILL.md を読み込む（YAML フロントマター + Markdown 本文）。
スキルは AI アクションで使用され、システムプロンプトに統合される。
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 先頭の YAML フロントマター（--- ... ---）を本文と分離する
_SKILL_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_skill_md(path: Path) -> dict[str, Any] | None:
    """SKILL.md を title / description / instruction に正規化する。"""
    raw = path.read_text(encoding="utf-8").lstrip("\ufeff")
    folder_name = path.parent.name

    m = _SKILL_FRONTMATTER.match(raw)
    if not m:
        instruction = raw.strip()
        if not instruction:
            logger.warning("スキル %s の本文が空です", folder_name)
            return None
        return {
            "name": folder_name,
            "title": folder_name,
            "description": "",
            "instruction": instruction,
        }

    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        logger.warning("スキル %s のフロントマター解析に失敗: %s", folder_name, e)
        return None

    if not isinstance(fm, dict):
        fm = {}

    body = raw[m.end() :].lstrip("\n")
    if not body.strip():
        logger.warning("スキル %s の本文（instruction）が空です", folder_name)
        return None

    title = fm.get("title") or fm.get("name") or folder_name
    return {
        "name": folder_name,
        "title": str(title),
        "description": str(fm.get("description", "") or ""),
        "instruction": body.rstrip(),
    }


def load_skill(skills_dir: Path, name: str) -> dict[str, Any] | None:
    """スキルを名前（フォルダ名）で読み込む"""
    path = skills_dir / name / "SKILL.md"
    if not path.is_file():
        return None
    try:
        return _parse_skill_md(path)
    except OSError as e:
        logger.warning("スキル %s の読み込みに失敗: %s", name, e)
        return None


def load_skills(skills_dir: Path, names: list[str]) -> list[dict[str, Any]]:
    """複数スキルを読み込む（存在しないスキルは警告してスキップ）"""
    skills = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        skill = load_skill(skills_dir, name)
        if skill:
            skills.append(skill)
        else:
            logger.warning("スキル '%s' が見つかりません", name)
    return skills


def list_skills(skills_dir: Path) -> list[dict[str, str]]:
    """利用可能なスキル一覧を返す（各 skills/<name>/SKILL.md）"""
    if not skills_dir.exists():
        return []

    result = []
    for child in sorted(skills_dir.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        skill_path = child / "SKILL.md"
        if not skill_path.is_file():
            continue
        try:
            data = _parse_skill_md(skill_path)
            if data:
                result.append({
                    "name": data["name"],
                    "title": data["title"],
                    "description": data["description"],
                })
        except OSError as e:
            logger.warning("スキル %s の読み込みに失敗: %s", child.name, e)

    return result


def build_system_prompt_with_skills(
    base_system: str | None,
    skills: list[dict[str, Any]],
) -> str:
    """スキルの instruction をシステムプロンプトに統合する"""
    parts = []

    for skill in skills:
        title = skill.get("title", skill.get("name", ""))
        instruction = skill.get("instruction", "")
        if instruction:
            if title:
                parts.append(f"[スキル: {title}]\n{instruction}")
            else:
                parts.append(instruction)

    if base_system:
        parts.append(base_system)

    return "\n\n".join(parts)
