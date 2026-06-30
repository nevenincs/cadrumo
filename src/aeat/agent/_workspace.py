"""Materialise an operator workspace from the shipped harness data.

Writes the shipped operator rules, personas, and skills out of the wheel into an
operator-chosen directory so an end-user agent runtime can load them. This is the
distinct, end-user operator workspace - never the repository's vaultspec developer
``.claude/`` tree. It writes only the reviewed harness markdown (no secrets, no tax
data) and computes no value.
"""

from __future__ import annotations

from importlib.resources.abc import Traversable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from . import harness_root, iter_operator_rules, iter_personas

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class WorkspaceManifest(BaseModel):
    """Result of materialising an operator workspace."""

    model_config = _STRICT_FROZEN

    output_path: str = Field(min_length=1)
    rules_written: int = Field(ge=0)
    personas_written: int = Field(ge=0)
    skills_written: int = Field(ge=0)


def _write(dest_dir: Path, name: str, text: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_text(text, encoding="utf-8")


def materialise_workspace(output_dir: Path) -> WorkspaceManifest:
    """Write the shipped harness rules, personas, and skills under ``output_dir``.

    The layout is ``output_dir/{rules,personas,skills}/...``. Each skill is written
    as ``skills/<skill-name>/SKILL.md``. Returns a manifest of what was written.
    """
    rules_dir = output_dir / "rules"
    rules = 0
    for rule in iter_operator_rules():
        _write(rules_dir, rule.name, rule.read_text(encoding="utf-8"))
        rules += 1

    personas_dir = output_dir / "personas"
    personas = 0
    for persona in iter_personas():
        _write(personas_dir, persona.name, persona.read_text(encoding="utf-8"))
        personas += 1

    skills = 0
    skills_root = harness_root().joinpath("skills")
    if skills_root.is_dir():
        for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if skill_dir.is_dir() and skill_dir.joinpath("SKILL.md").is_file():
                _copy_skill(skill_dir, output_dir / "skills" / skill_dir.name)
                skills += 1

    return WorkspaceManifest(
        output_path=str(output_dir),
        rules_written=rules,
        personas_written=personas,
        skills_written=skills,
    )


def _copy_skill(skill_dir: Traversable, dest_dir: Path) -> None:
    """Copy a skill's whole subtree (``SKILL.md`` plus the ``reference/`` material).

    The progressive-disclosure reference a SKILL.md cites must travel with it, or a
    materialised workspace loses the deeper material the operator is told to read.
    """
    for child in skill_dir.iterdir():
        if child.is_file():
            _write(dest_dir, child.name, child.read_text(encoding="utf-8"))
        elif child.is_dir():
            for leaf in child.iterdir():
                if leaf.is_file():
                    _write(dest_dir / child.name, leaf.name, leaf.read_text(encoding="utf-8"))
