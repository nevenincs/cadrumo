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

import filecmp
import json
import re
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.product_identity import PRODUCT_IDENTITY

from .resources import harness_root, iter_operator_rules, iter_reference_documents

_UTF_8 = "utf-8"

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_CLAUDE_DIR = ".claude"
_RULES_SUBDIR = "rules"
_SKILLS_SUBDIR = "skills"
_REFERENCE_SUBDIR = "reference"
_SKILL_ENTRYPOINT = "SKILL.md"
_CLAUDE_MEMORY_FILE = "CLAUDE.md"

# --- Claude plugin layout -------------------------------------------------
#
# The plugin layout target re-materialises the SAME authored harness source
# as a one-click Claude plugin: a ``.claude-plugin/``
# manifest, a top-level ``skills/`` and ``reference/`` tree, and an
# ``.mcp.json`` declaring the stdio ``cadrumo-mcp`` server. The manifest schema is the one the
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
    "queries against the published tax authority and registered operations under "
    "an explicitly approved profile grant. Cadrumo "
    "is read-only toward AEAT and never files - live submission is impossible and "
    "the taxpayer files outside the app. All financial data stays on-host in "
    "encrypted storage; only what the conversation shows reaches the model "
    "provider. Each connection binds one exact profile; authorization controls "
    "which operations and results are available.\n"
    "Español: Opera Cadrumo, la CLI determinista de impuestos españoles, desde "
    "Claude: consultas a la autoridad tributaria publicada y operaciones "
    "registradas bajo una autorización de perfil aprobada explícitamente. "
    "Cadrumo es de solo lectura frente "
    "a la AEAT y nunca presenta declaraciones - la presentación en vivo es "
    "imposible y el contribuyente presenta fuera de la aplicación. Todos los datos "
    "financieros permanecen en el equipo en almacenamiento cifrado; solo lo que "
    "muestra la conversación llega al proveedor del modelo. Cada conexión se "
    "vincula a un perfil exacto; la autorización controla qué operaciones y "
    "resultados están disponibles."
)
# The single product author-identity string, derived from the central product
# identity, declared once in this defining workspace module.
PRODUCT_AUTHOR_NAME = f"{PRODUCT_IDENTITY.display_name} tax assistant project"
_PLUGIN_AUTHOR_NAME = PRODUCT_AUTHOR_NAME
_PLUGIN_LICENSE = "Apache-2.0"
_PLUGIN_KEYWORDS = (PRODUCT_IDENTITY.plugin_identifier, "tax", "aeat", "spain", "irpf", "iva", "modelo")
_PLUGIN_SCHEMA = "https://anthropic.com/claude-code/plugin.schema.json"

# ``uvx`` launches the exact root and mandatory companion wheels
# embedded beneath ``${CLAUDE_PLUGIN_ROOT}``. There is no index-backed or
# source-checkout form. The plugin supplies its release
# version through ``CADRUMO_MCP_REQUIRED_VERSION`` so a stale, incomplete, or
# mixed installed cohort refuses before opening the protocol transport.
_MCP_CONFIG = ".mcp.json"
_MCP_SERVER_NAME = "cadrumo"
_MCP_LAUNCHER = "uvx"
_MCP_CONSOLE_SCRIPT = "cadrumo-mcp"
_MCP_REQUIRED_VERSION_ENV = f"{PRODUCT_IDENTITY.environment_prefix}MCP_REQUIRED_VERSION"
_CLAUDE_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"
_PLUGIN_ARTIFACTS_SUBDIR = Path("artifacts") / "python"
_PLUGIN_COHORT_MANIFEST = "plugin-python-cohort.json"
_PYTHON_COHORT_WHEELS = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
_PLUGIN_COHORT_SCHEMA = "cadrumo.plugin-python-cohort.v2"
_RUNTIME_WHEELHOUSE_SCHEMA = "cadrumo.runtime-wheelhouse.v3"
_RUNTIME_WHEELHOUSE_MANIFEST = "runtime-wheelhouse.json"
_RUNTIME_WHEELHOUSE_PREFIX = "wheels/"


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a string-keyed object at every JSON object level."""
    return dict(pairs)


def _string_keyed_object(value: object) -> dict[str, object] | None:
    """Narrow an object decoded through the string-keyed JSON object hook."""
    if not isinstance(value, dict):
        return None
    # `_json_object` receives JSON member names, which the decoder defines as
    # strings, and installs this type at every object level.
    return cast(dict[str, object], value)


_RUNTIME_WHEELHOUSE_SUBDIR = "wheelhouse"
_SUPPORTED_WHEELHOUSE_TARGETS = frozenset({"linux-aarch64", "linux-x86-64", "macos-arm64", "windows-x86-64"})
_RUNTIME_WHEELHOUSE_FLOORS = {
    "linux-aarch64": "glibc-2.28",
    "linux-x86-64": "glibc-2.28",
    "macos-arm64": "macos-14.0",
    "windows-x86-64": "windows-10",
}


class PluginManifest(BaseModel):
    """Result of materialising a Claude plugin from the shipped harness source.

    ``skills_written`` / ``references_written`` count the
    ``skills/<name>/SKILL.md`` and ``reference/<document>.md`` documents written
    at the plugin root.
    """

    model_config = _STRICT_FROZEN

    output_path: str = Field(min_length=1)
    plugin_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    skills_written: int = Field(ge=0)
    references_written: int = Field(ge=0)


class _PluginPythonCohort(Protocol):
    """Validated Python release cohort consumed by the plugin emitter."""

    @property
    def directory(self) -> Path: ...

    @property
    def source_digest(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def root_wheel(self) -> Path: ...

    @property
    def runtime_wheelhouse(self) -> Path: ...

    @property
    def runtime_wheelhouse_manifest(self) -> Mapping[str, object]: ...

    @property
    def manuals_wheel(self) -> Path: ...

    @property
    def official_wheel(self) -> Path: ...

    @property
    def sha256(self) -> Mapping[str, str]: ...


def _write_json(dest_dir: Path, name: str, document: object) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_text(json.dumps(document, indent=2) + "\n", encoding=_UTF_8, newline="\n")


def _plugin_user_config() -> dict[str, object]:
    """Configure one immutable profile and an optional nonsecret key reference."""
    return {
        "profile_id": {
            "type": "string",
            "title": "Cadrumo profile ID",
            "description": (
                "Exact profile UUID. Labels do not select agent authority, and the person's sign-in "
                "serves this profile only while it is the selected one."
            ),
            "required": True,
        },
        "credential_reference": {
            "type": "string",
            "title": "Protected credential reference",
            "description": (
                "Nonsecret reference UUID from approved enrollment. "
                "Leave empty to follow the person's sign-in or to request authorization."
            ),
            "default": "",
            "required": False,
        },
    }


def _plugin_manifest_document(version: str) -> dict[str, object]:
    """Build the ``.claude-plugin/plugin.json`` manifest document.

    ``name`` is the sole validator-required field; the remaining fields are the
    publication metadata a first-class external-service plugin declares.
    ``defaultEnabled`` is ``false`` per the external-service recommendation so
    the plugin never auto-activates its MCP server on install. ``userConfig``
    declares the exact profile and protected credential reference.
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
        "userConfig": _plugin_user_config(),
    }


_FRONTMATTER_FENCE = "---\n"


def _after_frontmatter(document: str, inserted: str) -> str:
    """Put ``inserted`` between a document's frontmatter and its body, changing neither."""
    if not inserted or not document.startswith(_FRONTMATTER_FENCE):
        return inserted + document
    opening = len(_FRONTMATTER_FENCE)
    frontmatter, closed, body = document[opening:].partition(f"\n{_FRONTMATTER_FENCE}")
    if not closed:
        return inserted + document
    return f"{_FRONTMATTER_FENCE}{frontmatter}\n{_FRONTMATTER_FENCE}\n{inserted}{body.lstrip(chr(10))}"


def _emit_plugin_skills(output_dir: Path, references: Sequence[Traversable]) -> int:
    """Copy every shipped skill subtree under the plugin's top-level ``skills/``.

    The plugin skill layout (``skills/<name>/SKILL.md`` plus each skill's
    ``reference/`` progressive-disclosure material) is the same authored source
    the workspace layout emits, moved from ``.claude/skills`` to the plugin root
    so a Claude plugin loads it natively. A skill names commands, so each one
    is also told where the plugin's reference documents are.
    """
    pointer = _plugin_reference_pointer(references)
    skills = 0
    skills_root = harness_root().joinpath(_SKILLS_SUBDIR)
    if skills_root.is_dir():
        for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if skill_dir.is_dir() and skill_dir.joinpath(_SKILL_ENTRYPOINT).is_file():
                written = output_dir / _SKILLS_SUBDIR / skill_dir.name
                _copy_skill(skill_dir, written)
                authored = skill_dir.joinpath(_SKILL_ENTRYPOINT).read_text(encoding=_UTF_8)
                _write(written, _SKILL_ENTRYPOINT, _after_frontmatter(authored, pointer))
                skills += 1
    return skills


def _document_title(text: str) -> str:
    """Return a markdown document's level-one heading, which says what the document is."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError("a reference document opens with a level-one heading")


def _plugin_reference_pointer(references: Sequence[Traversable]) -> str:
    """Tell a plugin skill where the shipped reference documents are and what each one is.

    A workspace is told by its operating rules, which a plugin does not carry,
    so every plugin skill is told here. Each document is named by
    its own title, under the plugin root that Claude replaces with where the
    plugin is installed when it loads the skill.
    """
    if not references:
        return ""
    listed = "\n".join(
        f"- `{_CLAUDE_PLUGIN_ROOT}/{_REFERENCE_SUBDIR}/{reference.name}`: "
        f"{_document_title(reference.read_text(encoding=_UTF_8))}"
        for reference in references
    )
    return (
        "Reference documents ship with this plugin. The text below names command-line commands; through MCP\n"
        "you do a command's work with the tools its row names: an operation for `execute`, an act for\n"
        "`installation`, a query for `authority`, or an action for `session`. Open the document you need and\n"
        "read it there, never from memory:\n\n"
        f"{listed}\n\n"
    )


def _emit_plugin_references(output_dir: Path) -> tuple[Traversable, ...]:
    """Copy every shipped reference document under the plugin's top-level ``reference/``."""
    references = tuple(iter_reference_documents())
    for reference in references:
        _write(output_dir / _REFERENCE_SUBDIR, reference.name, reference.read_text(encoding=_UTF_8))
    return references


def _cohort_wheels(cohort: _PluginPythonCohort) -> dict[str, Path]:
    return {
        "cadrumo": cohort.root_wheel,
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
        f"{root}/{wheels['cadrumo'].name}",
        "--with",
        f"{root}/{wheels['cadrumo-data-manuals'].name}",
        "--with",
        f"{root}/{wheels['cadrumo-data-official'].name}",
        _MCP_CONSOLE_SCRIPT,
        "--profile-id",
        "${user_config.profile_id}",
        "--credential-reference",
        "${user_config.credential_reference}",
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
    resolved = artifact_dir.resolve()
    source_directory = cohort.directory.resolve(strict=True)
    if source_directory == resolved or source_directory in resolved.parents or resolved in source_directory.parents:
        raise ValueError("plugin output artifact directory must not overlap the source cohort")
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True)
    retained = _verify_and_copy_cohort_wheels(cohort, artifact_dir)
    wheelhouse = _extract_runtime_wheelhouse(cohort, artifact_dir / _RUNTIME_WHEELHOUSE_SUBDIR)
    _write_json(
        artifact_dir,
        _PLUGIN_COHORT_MANIFEST,
        {
            "artifacts": retained,
            "runtime_wheelhouse": wheelhouse,
            "runtime_wheelhouse_sha256": cohort.sha256["runtime-wheelhouse"],
            "schema": _PLUGIN_COHORT_SCHEMA,
            "sha256": {distribution: cohort.sha256[distribution] for distribution in _PYTHON_COHORT_WHEELS},
            "source_digest": cohort.source_digest,
            "version": cohort.version,
        },
    )


def _extract_runtime_wheelhouse(
    cohort: _PluginPythonCohort,
    destination: Path,
) -> dict[str, object]:
    """Extract all ready runtime closures into one plugin candidate directory."""
    archive_digest = sha256_hex(cohort.runtime_wheelhouse.read_bytes())
    if archive_digest != cohort.sha256["runtime-wheelhouse"]:
        raise ValueError(
            "cohort artifact digest mismatch for 'runtime-wheelhouse': "
            f"expected {cohort.sha256['runtime-wheelhouse']}, got {archive_digest}"
        )
    with zipfile.ZipFile(cohort.runtime_wheelhouse) as archive:
        names = archive.namelist()
        _validate_runtime_wheelhouse_members(names)
        document = _read_runtime_wheelhouse_manifest(archive, cohort)
        runtimes = _runtime_wheelhouse_runtimes(document)
        expected_members = {_RUNTIME_WHEELHOUSE_MANIFEST}
        destination.mkdir(parents=True)
        ready_runtime = False
        for python_version, runtime_value in sorted(runtimes.items()):
            ready_runtime = (
                _extract_runtime_wheelhouse_runtime(
                    archive, destination, expected_members, python_version, runtime_value
                )
                or ready_runtime
            )
        if not ready_runtime:
            raise ValueError("runtime wheelhouse has no ready runtime closure")
        if set(names) != expected_members:
            raise ValueError("runtime wheelhouse member inventory drifted")
    return {str(key): value for key, value in document.items()}


def _validate_runtime_wheelhouse_members(names: list[str]) -> None:
    if names.count(_RUNTIME_WHEELHOUSE_MANIFEST) != 1 or len(names) != len(set(names)):
        raise ValueError("runtime wheelhouse has a missing or duplicate member")


def _read_runtime_wheelhouse_manifest(archive: zipfile.ZipFile, cohort: _PluginPythonCohort) -> dict[str, object]:
    document = _string_keyed_object(
        json.loads(archive.read(_RUNTIME_WHEELHOUSE_MANIFEST), object_pairs_hook=_json_object)
    )
    if document is None:
        raise ValueError("runtime wheelhouse manifest must be an object with string keys")
    if set(document) != {"lock_sha256", "platform_floors", "runtimes", "schema"}:
        raise ValueError("runtime wheelhouse manifest schema drifted")
    if document != dict(cohort.runtime_wheelhouse_manifest):
        raise ValueError("runtime wheelhouse manifest drifted from the validated cohort")
    if document.get("schema") != _RUNTIME_WHEELHOUSE_SCHEMA:
        raise ValueError("runtime wheelhouse identity drifted")
    if document.get("platform_floors") != _RUNTIME_WHEELHOUSE_FLOORS:
        raise ValueError("runtime wheelhouse platform support floor drifted")
    return document


def _runtime_wheelhouse_runtimes(document: Mapping[str, object]) -> dict[str, object]:
    runtimes = _string_keyed_object(document.get("runtimes"))
    if not (runtimes is not None and runtimes):
        raise ValueError("runtime wheelhouse declares no runtimes")
    return runtimes


def _extract_runtime_wheelhouse_runtime(
    archive: zipfile.ZipFile,
    destination: Path,
    expected_members: set[str],
    python_version: object,
    runtime_value: object,
) -> bool:
    runtime = _validated_runtime_declaration(python_version, runtime_value)
    status = runtime["status"]
    if status == "missing-wheel":
        if set(runtime) != {"missing", "python", "status"}:
            raise ValueError(f"runtime wheelhouse missing-wheel record drifted: {python_version!r}")
        return False
    if status != "ready" or set(runtime) != {"platforms", "python", "status", "wheels"}:
        raise ValueError(f"runtime wheelhouse runtime status is invalid: {python_version!r}")
    platforms = _string_keyed_object(runtime.get("platforms"))
    wheels = _string_keyed_object(runtime.get("wheels"))
    if platforms is None or frozenset(platforms) != _SUPPORTED_WHEELHOUSE_TARGETS:
        raise ValueError(f"runtime wheelhouse platform closure is incomplete: {python_version!r}")
    if not (wheels is not None and wheels):
        raise ValueError(f"runtime wheelhouse declares no wheels: {python_version!r}")
    _extract_runtime_wheelhouse_wheels(archive, destination, expected_members, python_version, wheels)
    _validate_runtime_platform_closures(platforms, wheels, python_version)
    return True


def _validated_runtime_declaration(python_version: object, runtime_value: object) -> dict[str, object]:
    runtime = _string_keyed_object(runtime_value)
    if (
        not isinstance(python_version, str)
        or re.fullmatch(r"3\.[0-9]+", python_version) is None
        or runtime is None
        or runtime.get("python") != python_version
    ):
        raise ValueError(f"runtime wheelhouse runtime declaration is invalid: {python_version!r}")
    return runtime


def _extract_runtime_wheelhouse_wheels(
    archive: zipfile.ZipFile,
    destination: Path,
    expected_members: set[str],
    python_version: object,
    wheels: Mapping[str, object],
) -> None:
    for filename, record in sorted(wheels.items()):
        record_object = _validated_runtime_wheel_record(filename, record)
        member = f"{_RUNTIME_WHEELHOUSE_PREFIX}{python_version}/{filename}"
        expected_members.add(member)
        payload = archive.read(member)
        if len(payload) != record_object.get("size") or sha256_hex(payload) != record_object.get("sha256"):
            raise ValueError(f"runtime wheelhouse wheel bytes drifted: {python_version}/{filename!r}")
        destination_path = destination / filename
        if destination_path.exists() and destination_path.read_bytes() != payload:
            raise ValueError(f"runtime wheelhouse runtime variants disagree: {filename!r}")
        destination_path.write_bytes(payload)


def _validated_runtime_wheel_record(filename: object, record: object) -> dict[str, object]:
    record_object = _string_keyed_object(record)
    if (
        not isinstance(filename, str)
        or PurePosixPath(filename).name != filename
        or not filename.endswith(".whl")
        or record_object is None
        or set(record_object) != {"distribution", "sha256", "size", "version"}
    ):
        raise ValueError(f"runtime wheelhouse record is invalid: {filename!r}")
    return record_object


def _validate_runtime_platform_closures(
    platforms: Mapping[str, object], wheels: Mapping[str, object], python_version: object
) -> None:
    for target, rows_value in platforms.items():
        rows = _string_keyed_object(rows_value)
        if not (rows is not None and rows):
            raise ValueError(f"runtime wheelhouse target closure is empty: {python_version}/{target!r}")
        _validate_runtime_target_rows(rows, wheels, python_version, target)


def _validate_runtime_target_rows(
    rows: Mapping[str, object], wheels: Mapping[str, object], python_version: object, target: str
) -> None:
    for distribution, filename in rows.items():
        record = _string_keyed_object(wheels.get(filename)) if isinstance(filename, str) else None
        if not isinstance(distribution, str) or record is None:
            raise ValueError(f"runtime wheelhouse target references an unknown wheel: {python_version}/{target!r}")
        if record.get("distribution") != distribution:
            raise ValueError(f"runtime wheelhouse target swaps distribution bytes: {python_version}/{target!r}")


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
    cohort: _PluginPythonCohort,
) -> PluginManifest:
    """Write the shipped harness under ``output_dir`` as a Claude plugin.

    Emits ``.claude-plugin/plugin.json`` carrying the plugin manifest (including
    the ``userConfig`` profile binding), the top-level ``skills/<name>/SKILL.md``
    tree (plus each skill's ``reference/`` material), the ``reference/<document>.md`` documents
    each skill is pointed at, and the ``.mcp.json`` stdio server
    declaration, all from the single authored harness source. The validated
    ``cohort`` supplies the plugin version and every exact product wheel; the
    plugin embeds and launches that closed set without an index, installed
    package metadata, ambient executable, or project checkout.

    Returns:
        :class:`PluginManifest` describing the plugin written.
    """
    resolved_version = cohort.version

    _write_json(
        output_dir / _PLUGIN_DIR,
        _PLUGIN_MANIFEST,
        _plugin_manifest_document(resolved_version),
    )
    references = _emit_plugin_references(output_dir)
    skills = _emit_plugin_skills(output_dir, references)
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
        references_written=len(references),
    )


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
