"""Operator agent-harness: read accessor for the shipped operating layer.

The agent-harness operating layer - operator rules, tax-advisor personas, and
workflow skills - is reviewed markdown product data under ``aeat/_data/agent/``,
shipped inside the wheel and read here through the bundled-data boundary so it
resolves identically under an editable install and a built wheel.

This package is a read accessor only. It carries no tax logic and computes no
value; it hands the operating-layer text to whatever drives the agent (a prompt
assembler, the MCP server, or an operator-workspace materialiser). The capability
catalogue the agent reads first is emitted by ``aeat app contract --format json``.
"""

from __future__ import annotations

from collections.abc import Iterator
from importlib.resources.abc import Traversable

from ..core.resources import packaged_data

_AGENT_SUBTREE = "agent"
_RULES = "rules"
_PERSONAS = "personas"
_SKILLS = "skills"
_MARKDOWN_SUFFIX = ".md"


def harness_root() -> Traversable:
    """Return the bundled ``aeat/_data/agent`` harness data root."""
    return packaged_data(_AGENT_SUBTREE)


def _iter_markdown(*parts: str) -> Iterator[Traversable]:
    """Yield the markdown leaves directly under ``agent/<parts...>`` in name order."""
    node = harness_root()
    for part in parts:
        node = node.joinpath(part)
    if not node.is_dir():
        return
    for child in sorted(node.iterdir(), key=lambda item: item.name):
        if child.is_file() and child.name.endswith(_MARKDOWN_SUFFIX):
            yield child


def iter_operator_rules() -> Iterator[Traversable]:
    """Yield each operator operating-rule document, ordered by file name."""
    yield from _iter_markdown(_RULES)


def operator_rules_text() -> str:
    """Return the concatenated operator operating-rule documents.

    The rules are joined in file-name order with a blank line between them, ready
    to load into an agent's always-on operating context.
    """
    return "\n\n".join(rule.read_text(encoding="utf-8").rstrip() for rule in iter_operator_rules())


def iter_personas() -> Iterator[Traversable]:
    """Yield each tax-advisor persona document, ordered by file name."""
    yield from _iter_markdown(_PERSONAS)


def iter_skill_documents() -> Iterator[Traversable]:
    """Yield each workflow skill's ``SKILL.md`` document, ordered by skill name."""
    skills_root = harness_root().joinpath(_SKILLS)
    if not skills_root.is_dir():
        return
    for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir.joinpath("SKILL.md")
        if skill_md.is_file():
            yield skill_md


__all__ = [
    "harness_root",
    "iter_operator_rules",
    "iter_personas",
    "iter_skill_documents",
    "operator_rules_text",
]
