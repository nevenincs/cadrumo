"""Operator agent-harness: read accessor for the shipped operating layer.

The agent-harness operating layer - operator rules, tax-advisor personas, and
workflow skills - is reviewed markdown product data under
``cadrumo_harness/_data/agent/``, shipped inside this package's own wheel and
read here through the bundled-data boundary so it resolves identically under an
editable install and a built wheel.

This package is a read accessor only. It carries no tax logic and computes no
value; it hands the operating-layer text to whatever drives the agent (a prompt
assembler, the MCP server, or an operator-workspace materialiser). The capability
catalogue the agent reads first is emitted by ``cadrumo.application.operator_surface``
(surfaced by the `cadrumo` CLI).
"""

from __future__ import annotations

from collections.abc import Iterator

# nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING

from ._resources import packaged_data as _packaged_data
from ._skill_metadata import parse_skill_metadata

_UTF_8 = "utf-8"
_AGENT_SUBTREE = "agent"
_RULES = "rules"
_PERSONAS = "personas"
_SKILLS = "skills"
_MARKDOWN_SUFFIX = ".md"

if TYPE_CHECKING:
    from ._skill_metadata import SkillMetadata
    from ._workspace import (
        PRODUCT_AUTHOR_NAME,
        MarketplaceManifest,
        PluginManifest,
        WorkspaceManifest,
        materialise_marketplace,
        materialise_plugin,
        materialise_workspace,
    )


def harness_root() -> Traversable:
    """Return the bundled ``cadrumo_harness/_data/agent`` harness data root."""
    return _packaged_data(_AGENT_SUBTREE)


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
    return "\n\n".join(rule.read_text(encoding=_UTF_8).rstrip() for rule in iter_operator_rules())


def iter_personas() -> Iterator[Traversable]:
    """Yield each tax-advisor persona document, ordered by file name."""
    yield from _iter_markdown(_PERSONAS)


def _iter_skill_dirs() -> Iterator[tuple[str, Traversable]]:
    """Yield each skill's ``(directory name, SKILL.md)`` pair, ordered by name."""
    skills_root = harness_root().joinpath(_SKILLS)
    if not skills_root.is_dir():
        return
    for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir.joinpath("SKILL.md")
        if skill_md.is_file():
            yield skill_dir.name, skill_md


def iter_skill_documents() -> Iterator[Traversable]:
    """Yield each workflow skill's ``SKILL.md`` document, ordered by skill name."""
    for _name, skill_md in _iter_skill_dirs():
        yield skill_md


def iter_skill_metadata() -> Iterator[SkillMetadata]:
    """Yield every shipped skill's parsed ``SKILL.md`` metadata.

    Each frontmatter is parsed through the structured schema. A predicate that is
    present is fully validated: this raises ``SkillMetadataError`` on the first
    skill whose frontmatter is malformed, whose ``applies_when`` predicate is
    invalid, or whose declared name does not match its directory. A skill whose
    predicate has not yet been lifted from prose still loads, with
    ``applies_when`` set to ``None`` - strict presence is enforced by the coverage
    gate, not this load path, so the tree stays loadable while the lifts land.

    Returns:
        A :class:`SkillMetadata`.
    """
    from ._skill_metadata import SkillMetadataError

    for name, skill_md in _iter_skill_dirs():
        text = skill_md.read_text(encoding=_UTF_8)
        try:
            metadata = parse_skill_metadata(text)
        except SkillMetadataError as exc:
            raise SkillMetadataError(f"skill '{name}': {exc}") from exc
        if metadata.name != name:
            raise SkillMetadataError(
                f"skill '{name}': frontmatter name '{metadata.name}' does not match its directory name",
            )
        yield metadata


__all__ = [
    "PRODUCT_AUTHOR_NAME",
    "MarketplaceManifest",
    "PluginManifest",
    "WorkspaceManifest",
    "harness_root",
    "iter_operator_rules",
    "iter_personas",
    "iter_skill_documents",
    "iter_skill_metadata",
    "materialise_marketplace",
    "materialise_plugin",
    "materialise_workspace",
    "operator_rules_text",
    "parse_skill_metadata",
]


def __getattr__(name: str) -> object:
    # Lazy re-export of the workspace/plugin/marketplace materialisers and the
    # shared product-author constant to avoid an import cycle: _workspace imports
    # the iterators from this package.
    if name in {
        "PRODUCT_AUTHOR_NAME",
        "MarketplaceManifest",
        "PluginManifest",
        "WorkspaceManifest",
        "materialise_marketplace",
        "materialise_plugin",
        "materialise_workspace",
    }:
        from . import _workspace

        return getattr(_workspace, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
