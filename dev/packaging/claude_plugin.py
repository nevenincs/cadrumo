"""Generate the Claude plugin tree locally from one sealed Python cohort and verify it.

The plugin is the primary consumer distribution: a ``.claude-plugin/`` manifest,
the shipped skills and reference documents, an ``.mcp.json`` that launches
``cadrumo-mcp`` from the embedded product wheels, and those wheels with their
runtime dependency wheelhouse. :func:`cadrumo_harness.workspace.materialise_plugin`
writes it; this command supplies the cohort and then checks the written tree
against that cohort rather than trusting the writer.

The cohort is reused only when its manifest still verifies and it was built from
the current source; otherwise it is rebuilt through the one cohort builder. The
result is a local candidate under ``build/``. Nothing here installs it into a
Claude client, publishes a marketplace or uploads anything: the protected
release lane owns publication.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo_harness.resources import harness_root, iter_reference_documents
from cadrumo_harness.workspace import materialise_plugin
from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import content_digest, repository_files

from .build_scratch_reclaim import require_build_path
from .command_execution import run_command
from .hashing import sha256_path
from .python_cohort import PythonCohort, build_python_cohort, load_python_cohort

__all__ = ["GeneratedPlugin", "PluginTreeError", "generate_claude_plugin", "main", "verify_plugin_tree"]

DEFAULT_PLUGIN_DIR: Final[Path] = Path("build") / "claude-plugin" / "plugin"
DEFAULT_COHORT_DIR: Final[Path] = Path("build") / "claude-plugin" / "cohort"

_COHORT_MANIFEST: Final[str] = "python-cohort.json"
_PLUGIN_ROOT_VARIABLE: Final[str] = "${CLAUDE_PLUGIN_ROOT}"
_ARTIFACTS: Final[Path] = Path("artifacts") / "python"
_RETAINED_COHORT: Final[str] = "plugin-python-cohort.json"
_WHEELHOUSE: Final[str] = "wheelhouse"
_MCP_CONSOLE_SCRIPT: Final[str] = "cadrumo-mcp"
_REQUIRED_VERSION_ENV: Final[str] = f"{PRODUCT_IDENTITY.environment_prefix}MCP_REQUIRED_VERSION"
_PLUGIN_ENTRIES: Final[frozenset[str]] = frozenset({".claude-plugin", ".mcp.json", "artifacts", "reference", "skills"})


class PluginTreeError(ValueError):
    """The generated plugin tree does not carry what its cohort and harness source promise."""


@dataclass(frozen=True)
class GeneratedPlugin:
    """One verified local plugin tree and the cohort it embeds."""

    directory: Path
    cohort_directory: Path
    version: str
    source_digest: str
    skills: int
    references: int
    cohort_rebuilt: bool


def _read_json(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding=UTF_8))
    except (OSError, ValueError) as error:
        raise PluginTreeError(f"{path.name} is missing or is not JSON: {error}") from error
    if not isinstance(document, dict):
        raise PluginTreeError(f"{path.name} must hold a JSON object")
    return _object(document)


def _product_wheels(cohort: PythonCohort) -> dict[str, Path]:
    """Name each product wheel by the distribution the cohort records its digest under."""
    return dict(zip(PRODUCT_IDENTITY.cohort_distributions, cohort.product_wheels, strict=True))


def _shipped_skill_names() -> frozenset[str]:
    skills = harness_root().joinpath("skills")
    return frozenset(
        child.name for child in skills.iterdir() if child.is_dir() and child.joinpath("SKILL.md").is_file()
    )


def _verify_manifest(plugin_dir: Path, cohort: PythonCohort) -> None:
    manifest = _read_json(plugin_dir / ".claude-plugin" / "plugin.json")
    if manifest.get("name") != PRODUCT_IDENTITY.plugin_identifier:
        raise PluginTreeError(f"plugin identity drifted: {manifest.get('name')!r}")
    if manifest.get("version") != cohort.version:
        raise PluginTreeError(f"plugin version {manifest.get('version')!r} is not the cohort's {cohort.version!r}")
    if manifest.get("defaultEnabled") is not False:
        raise PluginTreeError("the plugin must not enable its MCP server on install")


def _verify_mcp_server(plugin_dir: Path, cohort: PythonCohort) -> None:
    servers = _object(_read_json(plugin_dir / ".mcp.json").get("mcpServers"))
    if set(servers) != {PRODUCT_IDENTITY.plugin_identifier}:
        raise PluginTreeError(f"the plugin must declare exactly the {PRODUCT_IDENTITY.plugin_identifier!r} server")
    server = _object(servers[PRODUCT_IDENTITY.plugin_identifier])
    args = server.get("args")
    env = _object(server.get("env"))
    if not isinstance(args, list) or _MCP_CONSOLE_SCRIPT not in args:
        raise PluginTreeError(f"the MCP server does not launch {_MCP_CONSOLE_SCRIPT}")
    embedded = f"{_PLUGIN_ROOT_VARIABLE}/{_ARTIFACTS.as_posix()}"
    for distribution, wheel in _product_wheels(cohort).items():
        if f"{embedded}/{wheel.name}" not in args:
            raise PluginTreeError(f"the MCP launch omits the embedded {distribution} wheel")
    if f"{embedded}/{_WHEELHOUSE}" not in args or "--no-index" not in args:
        raise PluginTreeError("the MCP launch must resolve only from the embedded wheelhouse")
    if env.get(_REQUIRED_VERSION_ENV) != cohort.version:
        raise PluginTreeError(f"the MCP server does not require the cohort version through {_REQUIRED_VERSION_ENV}")


def _verify_harness_payload(plugin_dir: Path) -> tuple[int, int]:
    skills_dir = plugin_dir / "skills"
    written_skills = {path.name for path in scan_directory(skills_dir) if (path / "SKILL.md").is_file()}
    expected_skills = _shipped_skill_names()
    if not expected_skills or written_skills != expected_skills:
        raise PluginTreeError(
            f"plugin skills differ from the shipped harness: missing={sorted(expected_skills - written_skills)!r}, "
            f"extra={sorted(written_skills - expected_skills)!r}"
        )
    references = {document.name: document.read_text(encoding=UTF_8) for document in iter_reference_documents()}
    written_references = {path.name for path in scan_directory(plugin_dir / "reference")}
    if written_references != set(references):
        raise PluginTreeError("plugin reference documents differ from the shipped harness")
    for name, text in references.items():
        if (plugin_dir / "reference" / name).read_text(encoding=UTF_8) != text:
            raise PluginTreeError(f"plugin reference document drifted: {name}")
    return len(written_skills), len(references)


def _object(value: object) -> dict[str, object]:
    return {str(key): item for key, item in value.items()} if isinstance(value, dict) else {}


def _declared_runtime_wheels(retained: dict[str, object]) -> dict[str, tuple[str, object]]:
    """Return ``{filename: (sha256, size)}`` for every wheel a ready runtime declares."""
    declared: dict[str, tuple[str, object]] = {}
    for runtime_value in _object(_object(retained.get("runtime_wheelhouse")).get("runtimes")).values():
        runtime = _object(runtime_value)
        if runtime.get("status") != "ready":
            continue
        for filename, record_value in _object(runtime.get("wheels")).items():
            record = _object(record_value)
            declared[filename] = (str(record.get("sha256")), record.get("size"))
    return declared


def _verify_wheelhouse(wheelhouse_dir: Path, retained: dict[str, object]) -> None:
    declared = _declared_runtime_wheels(retained)
    if not declared:
        raise PluginTreeError("the retained cohort declares no ready runtime wheels")
    present = {path.name: path for path in scan_directory(wheelhouse_dir) if path.is_file()}
    if set(present) != set(declared):
        raise PluginTreeError(
            f"runtime wheelhouse inventory drifted: missing={sorted(set(declared) - set(present))!r}, "
            f"undeclared={sorted(set(present) - set(declared))!r}"
        )
    for filename, (digest, size) in declared.items():
        if present[filename].stat().st_size != size or sha256_path(present[filename]) != digest:
            raise PluginTreeError(f"runtime wheel bytes drifted: {filename}")


def _verify_present_bytes(plugin_dir: Path, cohort: PythonCohort) -> None:
    """Hash every embedded artifact against the cohort, not against the writer's own record."""
    artifact_dir = plugin_dir / _ARTIFACTS
    retained = _read_json(artifact_dir / _RETAINED_COHORT)
    wheels = _product_wheels(cohort)
    expected_digests = {distribution: cohort.sha256[distribution] for distribution in wheels}
    if retained.get("sha256") != expected_digests:
        raise PluginTreeError("the retained cohort record does not name every product wheel's cohort digest")
    if retained.get("artifacts") != {distribution: wheel.name for distribution, wheel in wheels.items()}:
        raise PluginTreeError("the retained cohort record does not name every product wheel")
    if retained.get("version") != cohort.version or retained.get("source_digest") != cohort.source_digest:
        raise PluginTreeError("the retained cohort record names a different cohort")
    expected_files = {wheel.name for wheel in wheels.values()} | {_RETAINED_COHORT}
    present_files = {path.name for path in scan_directory(artifact_dir) if path.is_file()}
    if present_files != expected_files:
        raise PluginTreeError(
            f"embedded artifact inventory drifted: missing={sorted(expected_files - present_files)!r}, "
            f"undeclared={sorted(present_files - expected_files)!r}"
        )
    for distribution, wheel in wheels.items():
        if sha256_path(artifact_dir / wheel.name) != expected_digests[distribution]:
            raise PluginTreeError(f"embedded {distribution} wheel bytes drifted from the cohort")
    _verify_wheelhouse(artifact_dir / _WHEELHOUSE, retained)


def verify_plugin_tree(plugin_dir: Path, cohort: PythonCohort) -> tuple[int, int]:
    """Refuse a plugin tree whose identity, server, payload or bytes differ from ``cohort``.

    Returns the verified ``(skills, references)`` counts.
    """
    entries = {path.name for path in scan_directory(plugin_dir)}
    if entries != _PLUGIN_ENTRIES:
        raise PluginTreeError(f"plugin root entries drifted: {sorted(entries)!r}")
    _verify_manifest(plugin_dir, cohort)
    _verify_mcp_server(plugin_dir, cohort)
    counts = _verify_harness_payload(plugin_dir)
    _verify_present_bytes(plugin_dir, cohort)
    return counts


def _current_cohort(repo_root: Path, cohort_dir: Path) -> tuple[PythonCohort, bool]:
    """Reuse a cohort only when it verifies and was built from the current source."""
    if (cohort_dir / _COHORT_MANIFEST).is_file():
        try:
            existing = load_python_cohort(cohort_dir)
        except (SystemExit, OSError, ValueError):
            # A drifted, partial or unreadable cohort is rebuilt, never embedded.
            existing = None
        if existing is not None and existing.source_digest == content_digest(repo_root, repository_files(repo_root)):
            return existing, False
    return build_python_cohort(repo_root, cohort_dir), True


def generate_claude_plugin(
    repo_root: Path,
    *,
    plugin_dir: Path,
    cohort_dir: Path,
) -> GeneratedPlugin:
    """Write the plugin under ``plugin_dir`` from a current cohort in ``cohort_dir``, then verify it."""
    root = repo_root.resolve(strict=True)
    plugin = require_build_path(plugin_dir if plugin_dir.is_absolute() else root / plugin_dir, repo_root=root)
    cohort_path = require_build_path(cohort_dir if cohort_dir.is_absolute() else root / cohort_dir, repo_root=root)
    if plugin == cohort_path or plugin in cohort_path.parents or cohort_path in plugin.parents:
        raise PluginTreeError("the plugin and cohort directories must not contain one another")
    cohort, rebuilt = _current_cohort(root, cohort_path)
    if plugin.exists():
        shutil.rmtree(plugin)
    plugin.mkdir(parents=True)
    written = materialise_plugin(plugin, cohort=cohort)
    skills, references = verify_plugin_tree(plugin, cohort)
    if (written.skills_written, written.references_written) != (skills, references):
        raise PluginTreeError("the materialiser's counts disagree with the tree it wrote")
    return GeneratedPlugin(
        directory=plugin,
        cohort_directory=cohort.directory,
        version=cohort.version,
        source_digest=cohort.source_digest,
        skills=skills,
        references=references,
        cohort_rebuilt=rebuilt,
    )


def _claude_validate(plugin_dir: Path) -> str:
    """Run ``claude plugin validate --strict`` when the client is installed; never install anything."""
    claude = shutil.which("claude")
    if claude is None:
        return "unavailable"
    completed = run_command([claude, "plugin", "validate", "--strict", str(plugin_dir)], cwd=plugin_dir)
    if completed.returncode != 0:
        raise PluginTreeError(
            f"claude plugin validate --strict failed:\n{completed.stdout}\n{completed.stderr}",
        )
    return "passed"


def main(argv: list[str] | None = None) -> int:
    """Generate and verify the local Claude plugin tree, printing a JSON summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_PLUGIN_DIR, help="plugin directory below build/")
    parser.add_argument("--cohort-dir", type=Path, default=DEFAULT_COHORT_DIR, help="cohort directory below build/")
    arguments = parser.parse_args(argv)
    try:
        generated = generate_claude_plugin(REPO_ROOT, plugin_dir=arguments.output, cohort_dir=arguments.cohort_dir)
        validation = _claude_validate(generated.directory)
    except (PluginTreeError, ValueError) as error:
        print(f"claude plugin generation refused: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "claude_validate_strict": validation,
                "cohort_directory": str(generated.cohort_directory),
                "cohort_rebuilt": generated.cohort_rebuilt,
                "plugin_directory": str(generated.directory),
                "references": generated.references,
                "skills": generated.skills,
                "source_digest": generated.source_digest,
                "version": generated.version,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
