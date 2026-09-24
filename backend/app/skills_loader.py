"""Agent Skills (agentskills.io SKILL.md format) loaded through Strands' AgentSkills plugin.

Built-in skills ship as files under app/skills/; custom skills and edits live in the DB.
"""

import logging
from functools import lru_cache

import yaml
from sqlalchemy.orm import Session
from strands.vended_plugins.skills import Skill

from .config import get_config
from .models import SkillOverride

log = logging.getLogger(__name__)


@lru_cache
def builtin_skills() -> dict[str, Skill]:
    skills = {}
    try:
        for s in Skill.from_directory(get_config().skills_dir):
            skills[s.name] = s
    except Exception:
        log.exception("failed to load built-in skills")
    return skills


def _render(row: SkillOverride) -> str:
    front = {"name": row.id, "description": row.description,
             "metadata": {"category": row.category, "display_name": row.name, "standards": row.standards or []}}
    if row.tools:
        front["allowed-tools"] = " ".join(row.tools)
    return f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n{row.body_md}"


def all_skills(db: Session) -> dict[str, Skill]:
    skills = dict(builtin_skills())
    for row in db.query(SkillOverride).all():
        try:
            skills[row.id] = Skill.from_content(_render(row))
        except Exception:
            log.exception("invalid custom skill %s", row.id)
    return skills


def skill_meta(skill: Skill, builtin_ids: set[str], used_by: list[str], updated_at=None) -> dict:
    md = skill.metadata or {}
    from .standards import standard_ref
    return {
        "id": skill.name, "name": md.get("display_name") or skill.name.replace("-", " ").title(),
        "description": skill.description, "category": md.get("category", "general"),
        "standards": [standard_ref(s) for s in md.get("standards") or []],
        "tools": skill.allowed_tools or [], "used_by": used_by, "builtin": skill.name in builtin_ids,
        "updated_at": updated_at.isoformat() if updated_at else None, "version": str(md.get("version", "1.0")),
    }
