"""Materialise a Claude-native operator workspace from the shipped harness data.

The MCP server exposes registered tools to MCP clients. This optional
materialiser lays the shipped harness out in the layout a Claude Code project
loads natively.

The emitted layout is the Claude-native convention for an end-user project
directory - never the repository's own developer tooling ``.claude/`` tree:

- workflow skills -> ``.claude/skills/<name>/SKILL.md`` (plus each skill's
  ``reference/`` progressive-disclosure material), the standard skill layout;
- operator operating rules -> ``.claude/rules/<name>.md``, aggregated by a root
  ``CLAUDE.md`` that ``@``-imports each rule so the always-on operating contract
  loads at session start;
- generated reference documents -> ``.claude/reference/<name>.md``, which a rule
  names and the agent opens when it needs them.

This is a REPLACEMENT of the prior flat ``{rules,skills}/`` layout, not
an addition (the no-legacy discipline): the flat layout is gone. It writes only
the reviewed harness markdown (no secrets, no tax data) and computes no value.
"""

from __future__ import annotations

from collections.abc import Sequence
from importlib.resources.abc import Traversable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .resources import harness_root, iter_operator_rules, iter_reference_documents

_UTF_8 = "utf-8"

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_CLAUDE_DIR = ".claude"
_RULES_SUBDIR = "rules"
_SKILLS_SUBDIR = "skills"
_REFERENCE_SUBDIR = "reference"
_SKILL_ENTRYPOINT = "SKILL.md"
_CLAUDE_MEMORY_FILE = "CLAUDE.md"


class WorkspaceManifest(BaseModel):
    """Result of materialising a Claude-native operator workspace.

    ``rules_written`` / ``skills_written`` / ``references_written`` count the
    ``.claude/rules``, ``.claude/skills`` and ``.claude/reference`` documents written; the
    aggregating ``CLAUDE.md`` is derived from the rules and is not separately
    counted.
    """

    model_config = _STRICT_FROZEN

    output_path: str = Field(min_length=1)
    rules_written: int = Field(ge=0)
    skills_written: int = Field(ge=0)
    references_written: int = Field(ge=0)


def _write(dest_dir: Path, name: str, text: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_text(text, encoding=_UTF_8, newline="\n")


def _claude_memory(rule_names: Sequence[str]) -> str:
    """Render the root ``CLAUDE.md`` that imports every operator rule.

    Claude Code loads ``CLAUDE.md`` from the project root at session start and
    resolves ``@path`` lines as imports, so importing each ``.claude/rules``
    document makes the operator operating rules the always-on operating contract.
    """
    imports = "\n".join(f"@{_CLAUDE_DIR}/{_RULES_SUBDIR}/{name}" for name in rule_names)
    return (
        "# Cadrumo operator workspace\n\n"
        "Claude-native materialisation of the Cadrumo operator harness. The Cadrumo CLI is a\n"
        "deterministic Spanish-tax tool universe; this harness is how to operate it\n"
        "safely. The operating rules imported below are your always-on operating\n"
        "contract. The workflow skills are under\n"
        f"`{_CLAUDE_DIR}/{_SKILLS_SUBDIR}/`. The reference documents the rules send you to\n"
        f"are under `{_CLAUDE_DIR}/{_REFERENCE_SUBDIR}/`.\n\n"
        "## Operating rules\n\n"
        f"{imports}\n"
    )


def materialise_workspace(output_dir: Path) -> WorkspaceManifest:
    """Write the shipped harness under ``output_dir`` in the Claude-native layout.

    Emits ``.claude/skills/<name>/SKILL.md`` (plus each skill's ``reference/``
    material), ``.claude/rules/<rule>.md``,
    ``.claude/reference/<document>.md``, and a root ``CLAUDE.md`` importing every
    rule.

    Returns:
        :class:`WorkspaceManifest` describing the files written.
    """
    claude_dir = output_dir / _CLAUDE_DIR

    rules_dir = claude_dir / _RULES_SUBDIR
    rule_names: list[str] = []
    for rule in iter_operator_rules():
        _write(rules_dir, rule.name, rule.read_text(encoding=_UTF_8))
        rule_names.append(rule.name)

    skills = 0
    skills_root = harness_root().joinpath(_SKILLS_SUBDIR)
    if skills_root.is_dir():
        for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if skill_dir.is_dir() and skill_dir.joinpath(_SKILL_ENTRYPOINT).is_file():
                _copy_skill(skill_dir, claude_dir / _SKILLS_SUBDIR / skill_dir.name)
                skills += 1

    # A rule names these documents and reads none of them in, so they travel beside the rules.
    reference_dir = claude_dir / _REFERENCE_SUBDIR
    references = 0
    for reference in iter_reference_documents():
        _write(reference_dir, reference.name, reference.read_text(encoding=_UTF_8))
        references += 1

    _write(output_dir, _CLAUDE_MEMORY_FILE, _claude_memory(rule_names))

    return WorkspaceManifest(
        output_path=str(output_dir),
        rules_written=len(rule_names),
        skills_written=skills,
        references_written=references,
    )


def _copy_skill(skill_dir: Traversable, dest_dir: Path) -> None:
    """Copy a skill's whole subtree (``SKILL.md`` plus the ``reference/`` material).

    The progressive-disclosure reference a SKILL.md cites must travel with it, or a
    materialised workspace loses the deeper material the operator is told to read.
    """
    for child in skill_dir.iterdir():
        if child.is_file():
            _write(dest_dir, child.name, child.read_text(encoding=_UTF_8))
        elif child.is_dir():
            for leaf in child.iterdir():
                if leaf.is_file():
                    _write(dest_dir / child.name, leaf.name, leaf.read_text(encoding=_UTF_8))
