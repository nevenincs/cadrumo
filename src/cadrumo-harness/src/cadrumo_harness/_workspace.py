"""Materialise a Claude-native operator workspace from the shipped harness data.

The workspace materialiser is an optional Claude-native mirror, not the primary
delivery vehicle: the operating layer reaches an arbitrary MCP client through
the console's floor tool, resources, and prompts, and this materialiser is the
Claude-specific enhancement that lays the same shipped harness out in the
layout a Claude Code project loads natively.

The emitted layout is the Claude-native convention for an end-user project
directory - never the repository's own developer tooling ``.claude/`` tree:

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

import filecmp
import json
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from importlib.resources.abc import Traversable  # nosem
from pathlib import Path, PurePosixPath
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core import PRODUCT_IDENTITY
from cadrumo.core.hashing import sha256_hex

from . import harness_root, iter_operator_rules, iter_personas

_UTF_8 = "utf-8"

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_CLAUDE_DIR = ".claude"
_RULES_SUBDIR = "rules"
_AGENTS_SUBDIR = "agents"
_SKILLS_SUBDIR = "skills"
_SKILL_ENTRYPOINT = "SKILL.md"
_CLAUDE_MEMORY_FILE = "CLAUDE.md"

# --- Claude plugin layout -------------------------------------------------
#
# The plugin layout target re-materialises the SAME authored harness source
# as a one-click Claude plugin: a ``.claude-plugin/``
# manifest, a top-level ``skills/`` and ``agents/`` tree, and an ``.mcp.json``
# declaring the stdio ``cadrumo-mcp`` server. The manifest schema is the one the
# live ``claude plugin validate --strict`` oracle accepts; every field name here
# is verified against that validator, not trusted from documentation.
_PLUGIN_DIR = ".claude-plugin"
_PLUGIN_MANIFEST = "plugin.json"
_PLUGIN_NAME = PRODUCT_IDENTITY.plugin_identifier
_PLUGIN_DISPLAY_NAME = f"{PRODUCT_IDENTITY.display_name} Spanish tax assistant"
# Bilingual (English + Spanish) product copy, approved through this project's
# docs-authority process. The labeled sections (English: / Español:) satisfy
# the verifier's bilingual claim-parity parser. Wording changes must re-enter
# through a new approval record and re-enrollment in verify_distribution_identity.py.
_PLUGIN_DESCRIPTION = (
    "English: Operate Cadrumo, the deterministic Spanish-tax CLI, from Claude: "
    "grounded search over the bundled BOE/AEAT legal corpus, situation-keyed guided "
    "workflows, and human-confirmed execution of every state-changing step. Cadrumo "
    "is read-only toward AEAT and never files - live submission is impossible and "
    "the taxpayer files outside the app. All financial data stays on-host in "
    "encrypted storage; only what the conversation shows reaches the model "
    "provider. The server advertises an orientation core by default (overview + "
    "contract + search/execute); set the surface option to 'full' to advertise "
    "every verb up front.\n"
    "Español: Opera Cadrumo, la CLI determinista de impuestos españoles, desde "
    "Claude: búsqueda fundamentada sobre el corpus legal BOE/AEAT incluido, flujos "
    "guiados según la situación del contribuyente y ejecución con confirmación "
    "humana de cada paso que modifica el estado. Cadrumo es de solo lectura frente "
    "a la AEAT y nunca presenta declaraciones - la presentación en vivo es "
    "imposible y el contribuyente presenta fuera de la aplicación. Todos los datos "
    "financieros permanecen en el equipo en almacenamiento cifrado; solo lo que "
    "muestra la conversación llega al proveedor del modelo. El servidor anuncia por "
    "defecto un núcleo de orientación (visión general + contrato + buscar/ejecutar); "
    "configura la opción de superficie en 'full' para anunciar todos los verbos "
    "desde el inicio."
)
# The single product author-identity string, derived from the central product
# identity. Shared by the plugin, marketplace, and shipped MCPB manifests so all
# three read one declaration; exposed through the ``cadrumo_harness`` facade.
PRODUCT_AUTHOR_NAME = f"{PRODUCT_IDENTITY.display_name} tax assistant project"
_PLUGIN_AUTHOR_NAME = PRODUCT_AUTHOR_NAME
_PLUGIN_LICENSE = "Apache-2.0"
_PLUGIN_KEYWORDS = (PRODUCT_IDENTITY.plugin_identifier, "tax", "aeat", "spain", "irpf", "iva", "modelo")
_PLUGIN_SCHEMA = "https://anthropic.com/claude-code/plugin.schema.json"

# ``uvx`` launches the exact harness, root, and mandatory companion wheels
# embedded beneath ``${CLAUDE_PLUGIN_ROOT}``. There is no index-backed or
# source-checkout form. The plugin supplies its release
# version through ``CADRUMO_MCP_REQUIRED_VERSION`` so a stale, incomplete, or
# mixed installed cohort refuses before opening the protocol transport.
_MCP_CONFIG = ".mcp.json"
_MCP_SERVER_NAME = "cadrumo"
_MCP_LAUNCHER = "uvx"
_MCP_CONSOLE_SCRIPT = "cadrumo-mcp"
_MCP_PERSONA_ENV = f"{PRODUCT_IDENTITY.environment_prefix}MCP_PERSONA"
_MCP_PERSONA_INTERPOLATION = "${user_config.persona}"
# The advertised-tool-surface toggle. ``core`` (default) advertises only the
# orientation slice; ``full`` restores the flat
# per-verb surface. Wired from the ``userConfig`` surface option; the server
# validates the value and refuses an unknown one.
_MCP_SURFACE_ENV = f"{PRODUCT_IDENTITY.environment_prefix}MCP_SURFACE"
_MCP_SURFACE_INTERPOLATION = "${user_config.surface}"
_MCP_REQUIRED_VERSION_ENV = f"{PRODUCT_IDENTITY.environment_prefix}MCP_REQUIRED_VERSION"
_CLAUDE_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"
_PLUGIN_ARTIFACTS_SUBDIR = Path("artifacts") / "python"
_PLUGIN_COHORT_MANIFEST = "plugin-python-cohort.json"
_PYTHON_COHORT_WHEELS = (
    "cadrumo",
    "cadrumo-harness",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
_PLUGIN_COHORT_SCHEMA = "cadrumo.plugin-python-cohort.v1"
_RUNTIME_WHEELHOUSE_SCHEMA = "cadrumo.runtime-wheelhouse.v2"
_RUNTIME_WHEELHOUSE_MANIFEST = "runtime-wheelhouse.json"
_RUNTIME_WHEELHOUSE_PREFIX = "wheels/"
_RUNTIME_WHEELHOUSE_SUBDIR = "wheelhouse"
_SUPPORTED_WHEELHOUSE_TARGETS = frozenset(
    {"linux-aarch64", "linux-x86-64", "macos-arm64", "windows-x86-64"}
)
_RUNTIME_WHEELHOUSE_FLOORS = {
    "linux-aarch64": "glibc-2.17",
    "linux-x86-64": "glibc-2.17",
    "macos-arm64": "macos-11.0",
    "windows-x86-64": "windows-10",
}

# --- Claude marketplace layout --------------------------------------------
#
# The marketplace layout target emits the git-repo content a dedicated public
# marketplace repository serves: a ``.claude-plugin/``
# ``marketplace.json`` (marketplace name ``neve``) listing the Cadrumo plugin plus
# the plugin tree it points
# at, materialised UNDER the marketplace root at ``plugins/cadrumo`` via the same
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
_MARKETPLACE_DESCRIPTION = (
    "English: Neve plugin marketplace - Claude plugins including the Cadrumo "
    "Spanish-tax assistant: read-only toward AEAT, it never files (the taxpayer "
    "files outside the app), every state change needs human confirmation, financial "
    "data stays on-host in encrypted storage, and only the conversation reaches the "
    "model provider.\n"
    "Español: Marketplace de plugins de Neve - plugins de Claude, incluido el "
    "asistente de impuestos españoles Cadrumo: de solo lectura frente a la AEAT, "
    "nunca presenta declaraciones (el contribuyente presenta fuera de la "
    "aplicación), cada cambio de estado requiere confirmación humana, los datos "
    "financieros permanecen en el equipo en almacenamiento cifrado y solo la "
    "conversación llega al proveedor del modelo."
)
_MARKETPLACE_OWNER_NAME = _PLUGIN_AUTHOR_NAME
_MARKETPLACE_PLUGINS_SUBDIR = "plugins"
# The relative source the marketplace manifest points at, resolved from the
# marketplace repo root (the directory holding ``.claude-plugin/``).
_MARKETPLACE_PLUGIN_SOURCE = f"./{_MARKETPLACE_PLUGINS_SUBDIR}/{_PLUGIN_NAME}"
# The prior plugin identity this product retires, declared as data the publisher
# reads at merge time.
#
# It rides a SIDECAR beside the manifest rather than a field inside it, and the
# reason is measured rather than stylistic: the manifest is governed by the live
# ``claude plugin validate --strict`` oracle, and that oracle REJECTS the field.
# Two marketplace trees generated from this emitter, identical but for the key,
# validate as pass (exit 0) and fail (exit 1, "Unknown field 'supersedes'.
# Claude Code ignores it at load time"). So the manifest is the wrong home twice
# over: the declaration would be ignored by the very consumer the manifest
# exists for, and carrying it would force a choice between a red gate and
# retiring the oracle. The sidecar keeps the served manifest byte-shaped exactly
# as the validator accepts while the declaration still ships with every cohort,
# which is the property the retirement rests on -- it is re-verified on every
# publication, so a replay, a stale manifest, or a stranger reclaiming the
# abandoned name is refused again rather than once.
_MARKETPLACE_SUPERSEDES_MANIFEST = "supersedes.json"
_MARKETPLACE_SUPERSEDED_PLUGINS = ("aeat",)


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
    manifest points at (``./plugins/cadrumo``); ``plugin`` is the nested
    :class:`PluginManifest` for the plugin materialised under that source, so the
    marketplace and the plugin it serves are one emission and cannot drift.
    """

    model_config = _STRICT_FROZEN

    output_path: str = Field(min_length=1)
    marketplace_name: str = Field(min_length=1)
    plugin_source: str = Field(min_length=1)
    plugin: PluginManifest


class _PluginPythonCohort(Protocol):
    """Validated Python release cohort consumed by the plugin emitter."""

    directory: Path
    source_commit: str
    version: str
    harness_version: str
    root_wheel: Path
    harness_wheel: Path
    runtime_wheelhouse: Path
    runtime_wheelhouse_manifest: Mapping[str, object]
    manuals_wheel: Path
    official_wheel: Path
    sha256: Mapping[str, str]


def _write_json(dest_dir: Path, name: str, document: object) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_text(json.dumps(document, indent=2) + "\n", encoding=_UTF_8, newline="\n")


_PERSONA_CONFIG_KEY = "persona"
_PERSONA_CONFIG_TITLE = "Persona"
_PERSONA_CONFIG_DESCRIPTION = (
    "The harness persona scoping the tool surface; leave blank for the full "
    "surface. The cadrumo-mcp server validates the value and refuses an unknown "
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
    persona is a string option with a default; the cadrumo-mcp server stays the
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
# cadrumo-mcp server's own persona-scope gate as the refusal surface:
# server-side validation stays the refusal surface.
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
    harness-authoring ``mode:`` field, which is not a Claude field. The persona's
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


def _cohort_wheels(cohort: _PluginPythonCohort) -> dict[str, Path]:
    return {
        "cadrumo": cohort.root_wheel,
        "cadrumo-harness": cohort.harness_wheel,
        "cadrumo-data-manuals": cohort.manuals_wheel,
        "cadrumo-data-official": cohort.official_wheel,
    }


def _mcp_args(cohort: _PluginPythonCohort) -> list[str]:
    """Return an index-free launch over only the plugin-retained wheel cohort."""
    root = f"{_CLAUDE_PLUGIN_ROOT}/{_PLUGIN_ARTIFACTS_SUBDIR.as_posix()}"
    wheels = _cohort_wheels(cohort)
    return [
        "--isolated",
        "--no-config",
        "--no-sources",
        "--offline",
        "--no-index",
        "--find-links",
        f"{root}/{_RUNTIME_WHEELHOUSE_SUBDIR}",
        "--no-python-downloads",
        "--from",
        f"{root}/{wheels['cadrumo-harness'].name}",
        "--with",
        f"{root}/{wheels['cadrumo'].name}",
        "--with",
        f"{root}/{wheels['cadrumo-data-manuals'].name}",
        "--with",
        f"{root}/{wheels['cadrumo-data-official'].name}",
        _MCP_CONSOLE_SCRIPT,
    ]


def _mcp_config_document(version: str, cohort: _PluginPythonCohort) -> dict[str, object]:
    """Build the plugin's ``.mcp.json`` declaring the stdio ``cadrumo-mcp`` server."""
    return {
        "mcpServers": {
            _MCP_SERVER_NAME: {
                "command": _MCP_LAUNCHER,
                "args": _mcp_args(cohort),
                "env": {
                    _MCP_REQUIRED_VERSION_ENV: version,
                    _MCP_PERSONA_ENV: _MCP_PERSONA_INTERPOLATION,
                    _MCP_SURFACE_ENV: _MCP_SURFACE_INTERPOLATION,
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONPATH": "",
                },
            },
        },
    }


def _materialise_plugin_python_cohort(
    output_dir: Path,
    cohort: _PluginPythonCohort,
) -> None:
    artifact_dir = output_dir / _PLUGIN_ARTIFACTS_SUBDIR
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    resolved = artifact_dir.resolve()
    if cohort.directory == resolved or cohort.directory in resolved.parents or resolved in cohort.directory.parents:
        raise ValueError("plugin output artifact directory must not overlap the source cohort")
    artifact_dir.mkdir(parents=True)
    retained = _verify_and_copy_cohort_wheels(cohort, artifact_dir)
    wheelhouse = _extract_runtime_wheelhouse(cohort, artifact_dir / _RUNTIME_WHEELHOUSE_SUBDIR)
    _write_json(
        artifact_dir,
        _PLUGIN_COHORT_MANIFEST,
        {
            "artifacts": retained,
            "harness_version": cohort.harness_version,
            "runtime_wheelhouse": wheelhouse,
            "runtime_wheelhouse_sha256": cohort.sha256["runtime-wheelhouse"],
            "schema": _PLUGIN_COHORT_SCHEMA,
            "sha256": {distribution: cohort.sha256[distribution] for distribution in _PYTHON_COHORT_WHEELS},
            "source_commit": cohort.source_commit,
            "version": cohort.version,
        },
    )


def _extract_runtime_wheelhouse(
    cohort: _PluginPythonCohort,
    destination: Path,
) -> dict[str, object]:
    """Extract only the complete, digest-bound lock wheelhouse into the plugin."""
    archive_digest = sha256_hex(cohort.runtime_wheelhouse.read_bytes())
    if archive_digest != cohort.sha256["runtime-wheelhouse"]:
        raise ValueError(
            "cohort artifact digest mismatch for 'runtime-wheelhouse': "
            f"expected {cohort.sha256['runtime-wheelhouse']}, got {archive_digest}"
        )
    with zipfile.ZipFile(cohort.runtime_wheelhouse) as archive:
        names = archive.namelist()
        if names.count(_RUNTIME_WHEELHOUSE_MANIFEST) != 1 or len(names) != len(set(names)):
            raise ValueError("runtime wheelhouse has a missing or duplicate member")
        document = json.loads(archive.read(_RUNTIME_WHEELHOUSE_MANIFEST))
        if not isinstance(document, dict) or set(document) != {
            "lock_sha256",
            "platform_floors",
            "platforms",
            "python",
            "schema",
            "wheels",
        }:
            raise ValueError("runtime wheelhouse manifest schema drifted")
        if document != dict(cohort.runtime_wheelhouse_manifest):
            raise ValueError("runtime wheelhouse manifest drifted from the validated cohort")
        if document.get("schema") != _RUNTIME_WHEELHOUSE_SCHEMA or document.get("python") != "3.13":
            raise ValueError("runtime wheelhouse identity drifted")
        if document.get("platform_floors") != _RUNTIME_WHEELHOUSE_FLOORS:
            raise ValueError("runtime wheelhouse platform support floor drifted")
        platforms = document.get("platforms")
        wheels = document.get("wheels")
        if not isinstance(platforms, dict) or set(platforms) != _SUPPORTED_WHEELHOUSE_TARGETS:
            raise ValueError("runtime wheelhouse platform closure is incomplete")
        if not isinstance(wheels, dict) or not wheels:
            raise ValueError("runtime wheelhouse declares no wheels")
        expected_members = {
            _RUNTIME_WHEELHOUSE_MANIFEST,
            *(f"{_RUNTIME_WHEELHOUSE_PREFIX}{filename}" for filename in wheels),
        }
        if set(names) != expected_members:
            raise ValueError("runtime wheelhouse member inventory drifted")
        destination.mkdir(parents=True)
        for filename, record in sorted(wheels.items()):
            if (
                not isinstance(filename, str)
                or PurePosixPath(filename).name != filename
                or not filename.endswith(".whl")
                or not isinstance(record, dict)
                or set(record) != {"distribution", "sha256", "size", "version"}
            ):
                raise ValueError(f"runtime wheelhouse record is invalid: {filename!r}")
            payload = archive.read(f"{_RUNTIME_WHEELHOUSE_PREFIX}{filename}")
            if len(payload) != record.get("size") or sha256_hex(payload) != record.get("sha256"):
                raise ValueError(f"runtime wheelhouse wheel bytes drifted: {filename!r}")
            (destination / filename).write_bytes(payload)
        for target, rows in platforms.items():
            if not isinstance(rows, dict) or not rows:
                raise ValueError(f"runtime wheelhouse target closure is empty: {target!r}")
            for distribution, filename in rows.items():
                record = wheels.get(filename) if isinstance(filename, str) else None
                if not isinstance(distribution, str) or not isinstance(record, dict):
                    raise ValueError(
                        f"runtime wheelhouse target references an unknown wheel: {target!r}"
                    )
                if record.get("distribution") != distribution:
                    raise ValueError(
                        f"runtime wheelhouse target swaps distribution bytes: {target!r}/{distribution!r}"
                    )
    return {str(key): value for key, value in document.items()}


def _verify_and_copy_cohort_wheels(cohort: _PluginPythonCohort, artifact_dir: Path) -> dict[str, str]:
    """Digest-verify and byte-verify each cohort wheel copied into ``artifact_dir``.

    Returns the retained ``{distribution: filename}`` map. Raises on a digest
    mismatch against the cohort manifest or on any post-copy byte drift.
    """
    retained: dict[str, str] = {}
    wheels = _cohort_wheels(cohort)
    for distribution in _PYTHON_COHORT_WHEELS:
        source = wheels[distribution]
        actual_digest = sha256_hex(source.read_bytes())
        if actual_digest != cohort.sha256[distribution]:
            raise ValueError(
                f"cohort artifact digest mismatch for {distribution!r}: "
                f"expected {cohort.sha256[distribution]}, got {actual_digest}",
            )
        destination = artifact_dir / source.name
        shutil.copy2(source, destination)
        if not filecmp.cmp(source, destination, shallow=False):
            raise ValueError(f"copied plugin wheel bytes drifted for {distribution!r}")
        retained[distribution] = destination.name
    return retained


def materialise_plugin(
    output_dir: Path,
    *,
    persona_default: str = "",
    cohort: _PluginPythonCohort,
) -> PluginManifest:
    """Write the shipped harness under ``output_dir`` as a Claude plugin.

    Emits ``.claude-plugin/plugin.json`` carrying the plugin manifest (including
    the ``userConfig`` persona option), the top-level ``skills/<name>/SKILL.md``
    tree (plus each skill's ``reference/`` material), the ``agents/<persona>.md``
    tree with Claude-native frontmatter, and the ``.mcp.json`` stdio server
    declaration, all from the single authored harness source. The validated
    ``cohort`` supplies the plugin version and every exact product wheel; the
    plugin embeds and launches that closed set without an index, installed
    package metadata, ambient executable, or project checkout. ``persona_default``
    seeds the ``userConfig`` persona default.

    Returns:
        :class:`PluginManifest` describing the plugin written.
    """
    resolved_version = cohort.version

    _write_json(
        output_dir / _PLUGIN_DIR,
        _PLUGIN_MANIFEST,
        _plugin_manifest_document(resolved_version, persona_default),
    )
    skills = _emit_plugin_skills(output_dir)
    agents = _emit_plugin_agents(output_dir)
    _materialise_plugin_python_cohort(output_dir, cohort)
    _write_json(
        output_dir,
        _MCP_CONFIG,
        _mcp_config_document(resolved_version, cohort),
    )

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
    the plugin from the relative ``./plugins/cadrumo`` subtree this generator
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
    persona_default: str = "",
    cohort: _PluginPythonCohort,
) -> MarketplaceManifest:
    """Write the marketplace-served tree under ``output_dir`` from the harness source.

    Emits ``.claude-plugin/marketplace.json`` listing the Cadrumo plugin and, under
    the relative ``plugins/cadrumo`` source it points at, the full plugin tree via
    :func:`materialise_plugin`. Because both come from one call, the marketplace
    manifest and the plugin it serves cannot drift. The required validated
    ``cohort`` and ``persona_default`` pass straight through to plugin emission.

    Also emits the ``.claude-plugin/supersedes.json`` sidecar naming the prior
    plugin identities this product retires, which the publisher reads at merge
    time. It is a sidecar rather than a manifest field because the strict plugin
    validator rejects unknown manifest fields; see the constant's comment for the
    measurement.

    Returns:
        :class:`MarketplaceManifest` describing the marketplace tree written.
    """
    _write_json(output_dir / _PLUGIN_DIR, _MARKETPLACE_MANIFEST, _marketplace_manifest_document())
    _write_json(
        output_dir / _PLUGIN_DIR,
        _MARKETPLACE_SUPERSEDES_MANIFEST,
        {"supersedes": list(_MARKETPLACE_SUPERSEDED_PLUGINS)},
    )
    plugin = materialise_plugin(
        output_dir / _MARKETPLACE_PLUGINS_SUBDIR / _PLUGIN_NAME,
        persona_default=persona_default,
        cohort=cohort,
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
