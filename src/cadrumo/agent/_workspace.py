"""Materialise a Claude-native operator workspace from the shipped harness data.

Per ADR R4 the workspace materialiser is DEMOTED from the primary delivery
vehicle to an optional Claude-native mirror: the operating layer reaches an
arbitrary MCP client through the console's floor tool, resources, and prompts,
and this materialiser is the Claude-specific enhancement that lays the same
shipped harness out in the layout a Claude Code project loads natively.

The emitted layout is the Claude-native convention for an end-user project
directory - never the repository's own vaultspec developer ``.claude/`` tree:

- workflow skills -> ``.claude/skills/<name>/SKILL.md`` (plus each skill's
  ``reference/`` progressive-disclosure material), the standard skill layout;
- tax-advisor personas -> ``.claude/agents/<name>.md``, Claude Code subagent
  definitions;
- operator operating rules -> ``.claude/rules/<name>.md``, aggregated by a root
  ``CLAUDE.md`` that ``@``-imports each rule so the always-on operating contract
  loads at session start.

This is a REPLACEMENT of the prior flat ``{rules,personas,skills}/`` layout, not
an addition (the no-legacy discipline): the flat layout is gone. It writes only
the reviewed harness markdown (no secrets, no tax data) and computes no value.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from importlib import metadata as _metadata
from importlib.resources.abc import Traversable  # nosem
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .. import __version__
from ..core.external_constants import UTF_8_ENCODING as _UTF_8
from . import harness_root, iter_operator_rules, iter_personas

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_CLAUDE_DIR = ".claude"
_RULES_SUBDIR = "rules"
_AGENTS_SUBDIR = "agents"
_SKILLS_SUBDIR = "skills"
_SKILL_ENTRYPOINT = "SKILL.md"
_CLAUDE_MEMORY_FILE = "CLAUDE.md"

# --- Claude plugin layout -------------------------------------------------
#
# The plugin layout target (ADR "Plugin generation") re-materialises the SAME
# authored harness source as a one-click Claude plugin: a ``.claude-plugin/``
# manifest, a top-level ``skills/`` and ``agents/`` tree, and an ``.mcp.json``
# declaring the stdio ``aeat-mcp`` server. The manifest schema is the one the
# live ``claude plugin validate --strict`` oracle accepts; every field name here
# is verified against that validator, not trusted from documentation.
_PLUGIN_DIR = ".claude-plugin"
_PLUGIN_MANIFEST = "plugin.json"
_PLUGIN_NAME = "aeat"
_PLUGIN_DISPLAY_NAME = "AEAT Spanish tax assistant"
# Distilled from the mcpb manifest one-liner; keeps the never-files-live boundary
# stated on the operator-facing surface.
_PLUGIN_DESCRIPTION = (
    "Operate the aeat Spanish-tax CLI: grounded search over the bundled BOE/AEAT "
    "legal corpus, situation-keyed guided workflows, and gated execution that "
    "never files to AEAT. The server advertises an orientation core by default "
    "(overview + contract + search/execute); set the surface option to 'full' to "
    "advertise every verb up front."
)
_PLUGIN_AUTHOR_NAME = "AEAT tax assistant project"
_PLUGIN_LICENSE = "Apache-2.0"
_PLUGIN_KEYWORDS = ("tax", "aeat", "spain", "irpf", "iva", "modelo")
_PLUGIN_SCHEMA = "https://anthropic.com/claude-code/plugin.schema.json"

# The plugin's stdio MCP server. ``uvx`` boots ``aeat-mcp`` from the published
# wheel pinned to the plugin's own version (D2a), so a machine with ``uv`` but no
# project checkout runs the exact server the plugin release was cut against. The
# PyPI distribution name (``aeat-cli``, the operator's registered project) differs
# from the plugin name (``aeat``) and the import package (``aeat``); the pin MUST
# carry the ``[agent]`` extra — the MCP SDK the server runs on rides that extra,
# and a bare install makes ``aeat-mcp`` refuse with the install hint. The active
# persona is wired from the ``userConfig`` persona option through the documented
# ``${user_config.persona}`` interpolation; the server validates and refuses an
# unknown persona (server-side validation is the refusal surface).
_MCP_CONFIG = ".mcp.json"
_MCP_SERVER_NAME = "aeat"
_MCP_LAUNCHER = "uvx"
_MCP_CONSOLE_SCRIPT = "aeat-mcp"
_PYPI_DISTRIBUTION = "aeat-cli"
_MCP_PERSONA_ENV = "AEAT_MCP_PERSONA"
_MCP_PERSONA_INTERPOLATION = "${user_config.persona}"
# The advertised-tool-surface toggle (ADR mcp-progressive-discovery P1). ``core``
# (default) advertises only the orientation slice; ``full`` restores the flat
# per-verb surface. Wired from the ``userConfig`` surface option; the server
# validates the value and refuses an unknown one.
_MCP_SURFACE_ENV = "AEAT_MCP_SURFACE"
_MCP_SURFACE_INTERPOLATION = "${user_config.surface}"

# --- Claude marketplace layout --------------------------------------------
#
# The marketplace layout target (ADR "Marketplace") emits the git-repo content
# a dedicated public marketplace repository serves: a ``.claude-plugin/``
# ``marketplace.json`` (marketplace name ``neve``) listing the aeat plugin plus
# the plugin tree it points
# at, materialised UNDER the marketplace root at ``plugins/aeat`` via the same
# ``materialise_plugin`` emitter, so the marketplace manifest and the plugin it
# serves cannot drift. Every field name here is the one the live
# ``claude plugin validate --strict`` oracle accepts for a marketplace manifest;
# note the validator checks the manifest shape only and does NOT resolve the
# ``plugins[].source`` path, so the generator materialises the pointed-at plugin
# itself rather than trusting the manifest alone.
_MARKETPLACE_MANIFEST = "marketplace.json"
# The marketplace NAME is the ecosystem namespace users address plugins under
# (``<plugin>@neve``), independent of the repo it is served from; kebab-case
# (lowercase) is required by the claude.ai marketplace sync.
_MARKETPLACE_NAME = "neve"
_MARKETPLACE_DESCRIPTION = "Neve plugin marketplace — Claude plugins including the aeat Spanish-tax assistant."
_MARKETPLACE_OWNER_NAME = _PLUGIN_AUTHOR_NAME
_MARKETPLACE_PLUGINS_SUBDIR = "plugins"
# The relative source the marketplace manifest points at, resolved from the
# marketplace repo root (the directory holding ``.claude-plugin/``).
_MARKETPLACE_PLUGIN_SOURCE = f"./{_MARKETPLACE_PLUGINS_SUBDIR}/{_PLUGIN_NAME}"


def _plugin_version() -> str:
    """Resolve the plugin version from installed package metadata.

    Reads the ``aeat`` distribution version through :mod:`importlib.metadata`,
    falling back to the in-package ``__version__`` when the distribution is not
    installed (an editable checkout run straight from the source tree).
    """
    try:
        return _metadata.version(_PLUGIN_NAME)
    except _metadata.PackageNotFoundError:
        return __version__


class PluginManifest(BaseModel):
    """Result of materialising a Claude plugin from the shipped harness source.

    ``skills_written`` / ``agents_written`` count the ``skills/<name>/SKILL.md``
    and ``agents/<persona>.md`` documents written at the plugin root;
    ``persona_default`` is the ``userConfig`` persona default baked into the
    manifest (empty string = the full tool surface).
    """

    model_config = _STRICT_FROZEN

    output_path: str = Field(min_length=1)
    plugin_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    skills_written: int = Field(ge=0)
    agents_written: int = Field(ge=0)
    persona_default: str = ""


class MarketplaceManifest(BaseModel):
    """Result of materialising the marketplace-served tree from the harness source.

    ``plugin_source`` is the relative ``plugins[].source`` the marketplace
    manifest points at (``./plugins/aeat``); ``plugin`` is the nested
    :class:`PluginManifest` for the plugin materialised under that source, so the
    marketplace and the plugin it serves are one emission and cannot drift.
    """

    model_config = _STRICT_FROZEN

    output_path: str = Field(min_length=1)
    marketplace_name: str = Field(min_length=1)
    plugin_source: str = Field(min_length=1)
    plugin: PluginManifest


def _write_json(dest_dir: Path, name: str, document: object) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_text(json.dumps(document, indent=2) + "\n", encoding=_UTF_8)


_PERSONA_CONFIG_KEY = "persona"
_PERSONA_CONFIG_TITLE = "Persona"
_PERSONA_CONFIG_DESCRIPTION = (
    "The harness persona scoping the tool surface; leave blank for the full "
    "surface. The aeat-mcp server validates the value and refuses an unknown "
    "persona."
)
_SURFACE_CONFIG_KEY = "surface"
_SURFACE_CONFIG_TITLE = "Tool surface"
_SURFACE_CONFIG_DEFAULT = "core"
_SURFACE_CONFIG_DESCRIPTION = (
    "Which tools the server advertises up front: 'core' (default) advertises the "
    "orientation slice plus search/execute; 'full' advertises every verb. Either "
    "way the whole verb universe stays reachable through search and execute."
)


def _plugin_user_config(persona_default: str) -> dict[str, object]:
    """Build the ``userConfig`` block declaring the persona string option.

    The plugin format offers no enum/dropdown ``userConfig`` type, so the
    persona is a string option with a default; the aeat-mcp server stays the
    refusal surface for an unknown persona.
    """
    return {
        _PERSONA_CONFIG_KEY: {
            "type": "string",
            "title": _PERSONA_CONFIG_TITLE,
            "description": _PERSONA_CONFIG_DESCRIPTION,
            "default": persona_default,
            "required": False,
        },
        _SURFACE_CONFIG_KEY: {
            "type": "string",
            "title": _SURFACE_CONFIG_TITLE,
            "description": _SURFACE_CONFIG_DESCRIPTION,
            "default": _SURFACE_CONFIG_DEFAULT,
            "required": False,
        },
    }


def _plugin_manifest_document(version: str, persona_default: str) -> dict[str, object]:
    """Build the ``.claude-plugin/plugin.json`` manifest document.

    ``name`` is the sole validator-required field; the remaining fields are the
    publication metadata a first-class external-service plugin declares.
    ``defaultEnabled`` is ``false`` per the external-service recommendation so
    the plugin never auto-activates its MCP server on install. ``userConfig``
    declares the persona option prompted on enable.
    """
    return {
        "$schema": _PLUGIN_SCHEMA,
        "name": _PLUGIN_NAME,
        "displayName": _PLUGIN_DISPLAY_NAME,
        "description": _PLUGIN_DESCRIPTION,
        "version": version,
        "author": {"name": _PLUGIN_AUTHOR_NAME},
        "license": _PLUGIN_LICENSE,
        "keywords": list(_PLUGIN_KEYWORDS),
        "defaultEnabled": False,
        "userConfig": _plugin_user_config(persona_default),
    }


def _emit_plugin_skills(output_dir: Path) -> int:
    """Copy every shipped skill subtree under the plugin's top-level ``skills/``.

    The plugin skill layout (``skills/<name>/SKILL.md`` plus each skill's
    ``reference/`` progressive-disclosure material) is the same authored source
    the workspace layout emits, moved from ``.claude/skills`` to the plugin root
    so a Claude plugin loads it natively.
    """
    skills = 0
    skills_root = harness_root().joinpath(_SKILLS_SUBDIR)
    if skills_root.is_dir():
        for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if skill_dir.is_dir() and skill_dir.joinpath(_SKILL_ENTRYPOINT).is_file():
                _copy_skill(skill_dir, output_dir / _SKILLS_SUBDIR / skill_dir.name)
                skills += 1
    return skills


_MARKDOWN_SUFFIX = ".md"
_TOOL_SCOPE_HEADING = "## Tool scope"
# Claude built-in tools that mutate the local workspace filesystem. A persona
# whose declared tool scope is read-only (orchestration only) does not carry
# them; every other persona inherits the full tool set and relies on the
# aeat-mcp server's own persona-scope gate as the refusal surface (per the ADR:
# server-side validation stays the refusal surface).
_WORKSPACE_MUTATION_TOOLS = ("Edit", "Write", "NotebookEdit")


def _persona_slug(file_name: str) -> str:
    """Return the persona slug (the ``agents/<slug>.md`` name) for a source file."""
    if file_name.endswith(_MARKDOWN_SUFFIX):
        return file_name[: -len(_MARKDOWN_SUFFIX)]
    return file_name


def _persona_description(text: str) -> str:
    """Return the persona's first body paragraph as a one-line description.

    Claude reads an agent's ``description`` frontmatter as the delegation signal,
    so the first prose paragraph (the persona's role summary, following its H1
    title) is collapsed to a single line.
    """
    para: list[str] = []
    seen_title = False
    for line in text.splitlines():
        stripped = line.strip()
        if not seen_title:
            if stripped.startswith("#"):
                seen_title = True
            continue
        if not stripped:
            if para:
                break
            continue
        para.append(stripped)
    return " ".join(para)


def _persona_is_read_only(text: str) -> bool:
    """Return whether the persona's declared ``Tool scope`` is read-only.

    The single clean signal a persona's prose exposes is its ``Tool scope``
    section opening with ``Read-only`` (the coordinator's orchestration-only
    role). Those personas map cleanly onto a Claude ``disallowedTools`` denylist
    of the workspace-mutation built-ins; a persona whose scope declares local
    state mutation does not, and inherits the full tool set.
    """
    body: list[str] = []
    collecting = False
    for line in text.splitlines():
        if line.strip() == _TOOL_SCOPE_HEADING:
            collecting = True
            continue
        if collecting:
            if line.startswith("## "):
                break
            body.append(line)
    return "\n".join(body).strip().lower().startswith("read-only")


def _persona_agent_document(slug: str, text: str) -> str:
    """Render a persona as a Claude-native ``agents/<slug>.md`` document.

    The Claude agent frontmatter carries ``name`` and ``description`` and, for a
    read-only persona, a ``disallowedTools`` denylist. It NEVER carries the
    vaultspec-style ``mode:`` field, which is not a Claude field. The persona's
    original prose follows the frontmatter unchanged as the agent's system prompt.
    """
    front = ["---", f"name: {slug}", f"description: {json.dumps(_persona_description(text))}"]
    if _persona_is_read_only(text):
        front.append("disallowedTools:")
        front.extend(f"  - {tool}" for tool in _WORKSPACE_MUTATION_TOOLS)
    front.append("---")
    return "\n".join(front) + "\n\n" + text


def _emit_plugin_agents(output_dir: Path) -> int:
    """Write each persona as a Claude-native ``agents/<slug>.md`` document."""
    agents_dir = output_dir / _AGENTS_SUBDIR
    count = 0
    for persona in iter_personas():
        slug = _persona_slug(persona.name)
        document = _persona_agent_document(slug, persona.read_text(encoding=_UTF_8))
        _write(agents_dir, persona.name, document)
        count += 1
    return count


def _mcp_config_document(version: str) -> dict[str, object]:
    """Build the plugin's ``.mcp.json`` declaring the stdio ``aeat-mcp`` server."""
    return {
        "mcpServers": {
            _MCP_SERVER_NAME: {
                "command": _MCP_LAUNCHER,
                "args": ["--from", f"{_PYPI_DISTRIBUTION}[agent]=={version}", _MCP_CONSOLE_SCRIPT],
                "env": {
                    _MCP_PERSONA_ENV: _MCP_PERSONA_INTERPOLATION,
                    _MCP_SURFACE_ENV: _MCP_SURFACE_INTERPOLATION,
                },
            },
        },
    }


def materialise_plugin(
    output_dir: Path,
    *,
    version: str | None = None,
    persona_default: str = "",
) -> PluginManifest:
    """Write the shipped harness under ``output_dir`` as a Claude plugin.

    Emits ``.claude-plugin/plugin.json`` carrying the plugin manifest (including
    the ``userConfig`` persona option), the top-level ``skills/<name>/SKILL.md``
    tree (plus each skill's ``reference/`` material), the ``agents/<persona>.md``
    tree with Claude-native frontmatter, and the ``.mcp.json`` stdio server
    declaration, all from the single authored harness source. The ``version`` is
    resolved from installed package metadata when not supplied;
    ``persona_default`` seeds the ``userConfig`` persona default.

    Returns:
        :class:`PluginManifest` describing the plugin written.
    """
    resolved_version = version or _plugin_version()

    _write_json(
        output_dir / _PLUGIN_DIR,
        _PLUGIN_MANIFEST,
        _plugin_manifest_document(resolved_version, persona_default),
    )
    skills = _emit_plugin_skills(output_dir)
    agents = _emit_plugin_agents(output_dir)
    _write_json(output_dir, _MCP_CONFIG, _mcp_config_document(resolved_version))

    return PluginManifest(
        output_path=str(output_dir),
        plugin_name=_PLUGIN_NAME,
        version=resolved_version,
        skills_written=skills,
        agents_written=agents,
        persona_default=persona_default,
    )


def _marketplace_manifest_document() -> dict[str, object]:
    """Build the ``.claude-plugin/marketplace.json`` manifest document.

    ``name``, ``owner`` (object), and ``plugins[]`` are the validator-required
    fields; ``description`` is required additionally under ``--strict`` (its
    absence is a strict-failing warning). The single ``plugins[]`` entry sources
    the plugin from the relative ``./plugins/aeat`` subtree this generator
    materialises alongside the manifest.
    """
    return {
        "name": _MARKETPLACE_NAME,
        "description": _MARKETPLACE_DESCRIPTION,
        "owner": {"name": _MARKETPLACE_OWNER_NAME},
        "plugins": [
            {"name": _PLUGIN_NAME, "source": _MARKETPLACE_PLUGIN_SOURCE},
        ],
    }


def materialise_marketplace(
    output_dir: Path,
    *,
    version: str | None = None,
    persona_default: str = "",
) -> MarketplaceManifest:
    """Write the marketplace-served tree under ``output_dir`` from the harness source.

    Emits ``.claude-plugin/marketplace.json`` listing the aeat plugin and, under
    the relative ``plugins/aeat`` source it points at, the full plugin tree via
    :func:`materialise_plugin`. Because both come from one call, the marketplace
    manifest and the plugin it serves cannot drift. ``version`` and
    ``persona_default`` pass straight through to the plugin emission.

    Returns:
        :class:`MarketplaceManifest` describing the marketplace tree written.
    """
    _write_json(output_dir / _PLUGIN_DIR, _MARKETPLACE_MANIFEST, _marketplace_manifest_document())
    plugin = materialise_plugin(
        output_dir / _MARKETPLACE_PLUGINS_SUBDIR / _PLUGIN_NAME,
        version=version,
        persona_default=persona_default,
    )

    return MarketplaceManifest(
        output_path=str(output_dir),
        marketplace_name=_MARKETPLACE_NAME,
        plugin_source=_MARKETPLACE_PLUGIN_SOURCE,
        plugin=plugin,
    )


class WorkspaceManifest(BaseModel):
    """Result of materialising a Claude-native operator workspace.

    ``rules_written`` / ``personas_written`` / ``skills_written`` count the
    ``.claude/rules``, ``.claude/agents``, and ``.claude/skills`` documents
    written; the aggregating ``CLAUDE.md`` is derived from the rules and is not
    separately counted.
    """

    model_config = _STRICT_FROZEN

    output_path: str = Field(min_length=1)
    rules_written: int = Field(ge=0)
    personas_written: int = Field(ge=0)
    skills_written: int = Field(ge=0)


def _write(dest_dir: Path, name: str, text: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_text(text, encoding=_UTF_8)


def _claude_memory(rule_names: Sequence[str]) -> str:
    """Render the root ``CLAUDE.md`` that imports every operator rule.

    Claude Code loads ``CLAUDE.md`` from the project root at session start and
    resolves ``@path`` lines as imports, so importing each ``.claude/rules``
    document makes the operator operating rules the always-on operating contract.
    """
    imports = "\n".join(f"@{_CLAUDE_DIR}/{_RULES_SUBDIR}/{name}" for name in rule_names)
    return (
        "# aeat operator workspace\n\n"
        "Claude-native materialisation of the aeat operator harness. The aeat CLI is a\n"
        "deterministic Spanish-tax tool universe; this harness is how to operate it\n"
        "safely. The operating rules imported below are your always-on operating\n"
        "contract. Tax-advisor personas are Claude subagents under\n"
        f"`{_CLAUDE_DIR}/{_AGENTS_SUBDIR}/`, and the workflow skills are under\n"
        f"`{_CLAUDE_DIR}/{_SKILLS_SUBDIR}/`.\n\n"
        "## Operating rules\n\n"
        f"{imports}\n"
    )


def materialise_workspace(output_dir: Path) -> WorkspaceManifest:
    """Write the shipped harness under ``output_dir`` in the Claude-native layout.

    Emits ``.claude/skills/<name>/SKILL.md`` (plus each skill's ``reference/``
    material), ``.claude/agents/<persona>.md``, ``.claude/rules/<rule>.md``, and a
    root ``CLAUDE.md`` importing every rule.

    Returns:
        :class:`WorkspaceManifest` describing the files written.
    """
    claude_dir = output_dir / _CLAUDE_DIR

    rules_dir = claude_dir / _RULES_SUBDIR
    rule_names: list[str] = []
    for rule in iter_operator_rules():
        _write(rules_dir, rule.name, rule.read_text(encoding=_UTF_8))
        rule_names.append(rule.name)

    agents_dir = claude_dir / _AGENTS_SUBDIR
    personas = 0
    for persona in iter_personas():
        _write(agents_dir, persona.name, persona.read_text(encoding=_UTF_8))
        personas += 1

    skills = 0
    skills_root = harness_root().joinpath(_SKILLS_SUBDIR)
    if skills_root.is_dir():
        for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if skill_dir.is_dir() and skill_dir.joinpath(_SKILL_ENTRYPOINT).is_file():
                _copy_skill(skill_dir, claude_dir / _SKILLS_SUBDIR / skill_dir.name)
                skills += 1

    _write(output_dir, _CLAUDE_MEMORY_FILE, _claude_memory(rule_names))

    return WorkspaceManifest(
        output_path=str(output_dir),
        rules_written=len(rule_names),
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
            _write(dest_dir, child.name, child.read_text(encoding=_UTF_8))
        elif child.is_dir():
            for leaf in child.iterdir():
                if leaf.is_file():
                    _write(dest_dir / child.name, leaf.name, leaf.read_text(encoding=_UTF_8))
