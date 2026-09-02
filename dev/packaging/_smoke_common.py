"""Shared verification core for the packaging smoke lanes.

Every ``smoke_*`` lane proves one installation transport (uv wheel, plain pip,
sdist, split cohort, extras, browser, Docker, dev checkout) against the SAME
artifact contract: the wheel carries exactly the tracked shipped data, its
metadata preserves prod/optional/dev intent, and the installed product answers
the CLI, storage, and bundled-data probes. This module owns that shared
contract so a lane module owns only what is unique to its transport.

It also serves the two cheap preflight commands (``dependency_surface``,
``source_preflight``), which assert the dependency and tracked-data surfaces
without building anything.

The public API below is the deliberate contract; names prefixed with an
underscore are internals of this module. Lanes import from here, never from a
sibling lane.
"""

from __future__ import annotations

import ast
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tomllib
import venv
import zipfile
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path
from typing import Any, Final

from cadrumo.core.directory_scan import iter_directory, scan_directory

from .._paths import REPO_ROOT, UTF_8
from ._command import CommandResult, run_command
from ._distribution_limits import PYPI_FILE_CAP_BYTES
from ._distribution_names import normalise_distribution_name
from ._proof_ledger import (
    ProofContractError,
    record_proof,
    recorded_proofs,
    reset_proof_ledger,
)
from .evidence import PackagingSmokeManifest
from .python_cohort import digest_install_target

__all__ = [
    "TRACKED_DATA_ROOTS",
    "DependencySurfaces",
    "ProofContractError",
    "assert_attachment_and_llm_surfaces",
    "assert_cadrumo_version_output",
    "assert_cli_smoke",
    "assert_installed_data",
    "assert_optional_extra_registry_matches_pyproject",
    "assert_wheel_contains_tracked_data",
    "assert_wheel_metadata_matches_pyproject",
    "build_companion_wheels",
    "build_sdist",
    "build_wheel",
    "clean_product_env",
    "commit_defined_build_root",
    "create_pip_venv",
    "expected_wheel_data_paths",
    "extract_source_commit",
    "find_repo_root",
    "head_extract",
    "install_targets_with_pip",
    "install_wheel",
    "isolated_product_env",
    "optional_extra_registry",
    "pyproject_surfaces",
    "record_proof",
    "recorded_proofs",
    "relative_manifest_path",
    "require_executable",
    "requirement_name",
    "reset_proof_ledger",
    "resolve_work_dir",
    "run_checked",
    "tracked_source_data_paths",
    "validate_frozen_exports",
    "venv_bin_dir",
    "venv_cadrumo_path",
    "venv_python_path",
    "wheel_metadata",
    "write_smoke_manifest",
]


_UTF_8: Final[str] = UTF_8
_REPRESENTATIVE_DATA_LEAVES = (
    "registry/aeat/modelos/036/manifest.toml",
    "registry/cadrumo/user_profile/schema.toml",
    "corpus/aeat_official/disenos_registro/modelo_100/manifest.json",
)
TRACKED_DATA_ROOTS = ("src/cadrumo/_data",)
_SOURCE_DATA_PREFIX = "src/cadrumo/_data/"
_WHEEL_DATA_PREFIX = "cadrumo/_data"
# Corpus source binaries excluded from the compact command-bearing ``cadrumo`` wheel
# by the build config; they ship in the two mandatory ``cadrumo-data-*`` distributions. A
# tracked source path is one of these when it lives under ``_data/corpus`` and
# carries a binary suffix, so the wheel-bundling parity check must not expect it
# in the
# ``cadrumo`` archive.
_CORPUS_SOURCE_PREFIX = "src/cadrumo/_data/corpus/"
_COMPANION_HOOKS = (
    "packaging/cadrumo_data_manuals/hatch_build.py",
    "packaging/cadrumo_data_official/hatch_build.py",
)
_DATA_COMPANION_PROJECTS = (
    ("cadrumo-data-manuals", "packaging/cadrumo_data_manuals", "cadrumo_data_manuals-*.whl"),
    ("cadrumo-data-official", "packaging/cadrumo_data_official", "cadrumo_data_official-*.whl"),
)
_RENTA_PDF_ALLOW_LIST = {
    f"src/cadrumo/_data/corpus/manuals/renta/{year}/part1/source.pdf"
    for year in ("2020", "2021", "2022", "2023", "2024", "2025")
} | {"src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf"}
_CORE_ABSENT_NAMES = {
    "anthropic",
    "google-api-python-client",
    "playwright",
    "pytest",
    "ruff",
    "semgrep",
    "sphinx",
    "torch",
}
# Packages that legitimately appear in the core resolution as transitive
# dependencies of a base dependency, even though they are ALSO declared under an
# optional extra (a name collision). Without this carve-out the
# "optional-leaked-into-core" export check would false-positive on the shared
# name. ``numpy`` is a permitted-but-not-required core presence: it is no longer
# declared under any extra (the ``search`` extra that listed it was retired with
# the runtime embedding stack) and no longer resolves into the product closure,
# so this entry now only tolerates it arriving transitively in a real built
# environment rather than asserting that it does.
# ``anyio`` is pulled into core by ``httpx`` (a base dependency) and is declared
# in the ``agent`` extra because the stdio MCP server imports it directly.
# ``pillow`` is pulled into core by the base ``pdfplumber`` and ``pikepdf`` PDF
# dependencies and is pinned directly in the dev group for reproducible README
# GIF generation.
# ``lxml`` is pulled into core by the base ``beautifulsoup4[lxml]`` extra - the
# AEAT adapter's one HTML constructor (``adapters/outbound/aeat/_html.py``)
# names "lxml" as BeautifulSoup's parser backend for every page read, so it is a
# runtime reliance - and is ALSO declared in the dev group, where test support imports
# ``lxml.etree`` to compile the bundled AEAT record-design XSDs. Two independent
# reliances, two declarations; the dev one must not make the runtime one read as
# a dev-only leak into core.
_CORE_PRESENT_TRANSITIVE_NAMES = {
    "numpy",
    "anyio",
    "pillow",
    "lxml",
}
_EXTRAS_PRESENT_NAMES = {
    "anthropic",
    "google-api-python-client",
    "playwright",
}
_DEV_PRESENT_NAMES = {
    "deptry",
    "pytest",
    "ruff",
    "sphinx",
    "torch",
}


@dataclass(frozen=True)
class DependencySurfaces:
    """Direct dependency names declared by project, optional, and dev surfaces."""

    project_name: str
    project_names: set[str]
    project_active_names: set[str]
    optional_names: set[str]
    optional_active_names: set[str]
    extras: set[str]
    dev_names: set[str]
    dev_active_names: set[str]

    @property
    def external_optional_names(self) -> set[str]:
        """Optional dependency names excluding self-referential aggregate extras."""
        return self.optional_names - {self.project_name}

    @property
    def external_optional_active_names(self) -> set[str]:
        """Platform-active optional dependency names excluding self-references."""
        return self.optional_active_names - {self.project_name}

    @property
    def dev_only_names(self) -> set[str]:
        """Developer dependencies that are not also runtime or optional packages."""
        return self.dev_names - self.project_names - self.optional_names - {self.project_name}

    @property
    def dev_only_active_names(self) -> set[str]:
        """Platform-active developer-only dependencies."""
        return self.dev_active_names - self.project_active_names - self.optional_active_names - {self.project_name}


def find_repo_root() -> Path:
    """Return the repository root for this module."""
    return REPO_ROOT


def head_extract(repo_root: Path, work_dir: Path) -> Path:
    """Extract a pristine ``git archive HEAD`` tree to build a lane's artifacts from.

    A working tree may carry uncommitted changes (including registry TOML
    mid-edits) that a tree-built artifact would sweep into a lane's
    registry-validation probes, failing them for reasons outside that lane's
    contract. In the multi-agent factory worktree the failure mode is sharper
    still: a build can snapshot a torn peer edit, so the artifact corresponds to
    no commit at all and the lane fails with what looks like a packaging
    regression. Building from the HEAD archive keeps the proof bound to a
    defined commit; on a clean checkout (CI) it is identical to the tree.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    archive = work_dir / "head.zip"
    extract_root = work_dir / "head"
    run_checked(
        ["git", "archive", "--format=zip", "-o", str(archive), "HEAD"],
        cwd=repo_root,
        env=_git_env(repo_root),
    )
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extract_root)
    archive.unlink()
    return extract_root


def commit_defined_build_root(repo_root: Path, work_dir: Path) -> Path:
    """Return a build root guaranteed to correspond to HEAD, extracting only if needed.

    On a clean checkout the working tree IS HEAD, so extracting it would copy
    roughly forty thousand files (measured at three minutes on the Windows
    build host) to produce a byte-identical tree. CI checks out clean, so the
    common case pays nothing. In the shared factory worktree a peer sweep makes
    the tree diverge from every commit, and that is exactly when a tree build
    can snapshot a torn edit, so there the extraction is worth its cost.
    """
    dirty = run_checked(["git", "status", "--porcelain"], cwd=repo_root, env=_git_env(repo_root)).stdout.strip()
    if not dirty:
        return repo_root
    print(
        f"working tree carries {len(dirty.splitlines())} uncommitted path(s); "
        "building from a pristine HEAD extract so the artifacts correspond to a commit",
        flush=True,
    )
    return head_extract(repo_root, work_dir)


def extract_source_commit(repo_root: Path, work_dir: Path, source_commit: str) -> Path:
    """Extract one immutable source commit rather than resolving a moving HEAD twice.

    Unlike :func:`head_extract` (bound to the ambient ``HEAD``), this pins the
    extraction to an exact commit hash — the shape a cohort-bound proof needs
    when the artifact under test (e.g. a release cohort) was built from a
    commit that may no longer be the checkout's current ``HEAD``.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    archive = work_dir / f"source-commit-{source_commit}.zip"
    extract_root = work_dir / f"source-commit-{source_commit}"
    run_checked(
        ["git", "archive", "--format=zip", "-o", str(archive), source_commit],
        cwd=repo_root,
        env=_git_env(repo_root),
    )
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extract_root)
    archive.unlink()
    return extract_root


def _wsl_path_from_windows_gitdir(gitdir: str) -> Path | None:
    """Translate a Windows gitdir pointer for WSL-mounted worktrees."""
    if os.name == "nt":
        return None
    normalized = gitdir.replace("\\", "/")
    match = re.fullmatch(r"([A-Za-z]):/(.+)", normalized)
    if match is None:
        return None
    candidate = Path("/mnt") / match.group(1).lower() / match.group(2)
    if not candidate.exists():
        return None
    return candidate


def _git_env(repo_root: Path) -> dict[str, str] | None:
    """Return environment overrides for Git when WSL reads a Windows worktree."""
    dot_git = repo_root / ".git"
    if not dot_git.is_file():
        return None
    gitdir_line = dot_git.read_text(encoding=_UTF_8).strip()
    prefix = "gitdir: "
    if not gitdir_line.startswith(prefix):
        return None
    translated = _wsl_path_from_windows_gitdir(gitdir_line.removeprefix(prefix).strip())
    if translated is None:
        return None
    return {**os.environ, "GIT_DIR": str(translated), "GIT_WORK_TREE": str(repo_root)}


def require_executable(name: str) -> str:
    """Resolve an executable from PATH or stop with an actionable error."""
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"required executable not found on PATH: {name}")
    return resolved


def run_checked(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    expected: set[int] | None = None,
) -> CommandResult:
    """Run a subprocess and replay output only when the return code is unexpected."""
    expected_codes = {0} if expected is None else expected
    completed = run_command(argv, cwd=cwd, environment=env)
    if completed.returncode not in expected_codes:
        command = " ".join(argv)
        sys.stderr.write(f"\ncommand failed ({completed.returncode}): {command}\n")
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode or 1)
    return completed


def requirement_name(requirement: str) -> str:
    """Extract the distribution name from a dependency requirement string."""
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise ValueError(f"could not parse requirement name from {requirement!r}")
    return normalise_distribution_name(match.group(1))


def _requirement_applies_to_current_platform(requirement: str) -> bool:
    """Return whether a requirement marker applies to the current smoke platform."""
    marker = requirement.partition(";")[2].strip()
    if not marker:
        return True
    match = re.fullmatch(r"sys_platform\s*==\s*['\"]([^'\"]+)['\"]", marker)
    if match is None:
        return True
    return sys.platform == match.group(1)


def _dependency_group_name(entry: str | dict[str, Any]) -> str:
    """Extract a distribution name from a dependency-group entry."""
    if isinstance(entry, str):
        return requirement_name(entry)
    name = entry.get("name")
    if not isinstance(name, str):
        raise ValueError(f"dependency-group entry is missing a string name: {entry!r}")
    return normalise_distribution_name(name)


def _dependency_group_entries(
    groups: dict[str, Any],
    group_name: str,
    *,
    stack: tuple[str, ...] = (),
) -> tuple[str | dict[str, Any], ...]:
    """Expand PEP 735 ``include-group`` entries into dependency entries."""
    if group_name in stack:
        cycle = " -> ".join((*stack, group_name))
        raise ValueError(f"dependency-group include cycle: {cycle}")
    raw_entries = groups.get(group_name, [])
    if not isinstance(raw_entries, list):
        raise ValueError(f"dependency group must be a list: {group_name!r}")

    entries: list[str | dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict) or "include-group" not in entry:
            entries.append(entry)
            continue
        included = entry["include-group"]
        if not isinstance(included, str) or not included:
            raise ValueError(f"dependency-group include must name a group: {entry!r}")
        entries.extend(_dependency_group_entries(groups, included, stack=(*stack, group_name)))
    return tuple(entries)


def _dependency_group_applies_to_current_platform(entry: str | dict[str, Any]) -> bool:
    """Return whether a dependency-group entry applies to the current platform."""
    if isinstance(entry, str):
        return _requirement_applies_to_current_platform(entry)
    marker = entry.get("marker")
    if not isinstance(marker, str):
        return True
    match = re.fullmatch(r"sys_platform\s*==\s*['\"]([^'\"]+)['\"]", marker.strip())
    if match is None:
        return True
    return sys.platform == match.group(1)


def pyproject_surfaces(repo_root: Path) -> DependencySurfaces:
    """Return project, optional, extras, and dev dependency name sets from pyproject."""
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    project = pyproject["project"]
    project_name = normalise_distribution_name(project["name"])
    project_requirements = project.get("dependencies", [])
    project_names = {requirement_name(req) for req in project.get("dependencies", [])}
    project_active_names = {
        requirement_name(req) for req in project_requirements if _requirement_applies_to_current_platform(req)
    }
    optional_dependencies = project.get("optional-dependencies", {})
    extras = {normalise_distribution_name(extra) for extra in optional_dependencies}
    optional_requirements = [req for requirements in optional_dependencies.values() for req in requirements]
    optional_names = {requirement_name(req) for req in optional_requirements}
    optional_active_names = {
        requirement_name(req) for req in optional_requirements if _requirement_applies_to_current_platform(req)
    }
    dependency_groups = pyproject.get("dependency-groups", {})
    dev_entries = _dependency_group_entries(dependency_groups, "dev")
    dev_names = {_dependency_group_name(entry) for entry in dev_entries}
    dev_active_names = {
        _dependency_group_name(entry) for entry in dev_entries if _dependency_group_applies_to_current_platform(entry)
    }
    return DependencySurfaces(
        project_name=project_name,
        project_names=project_names,
        project_active_names=project_active_names,
        optional_names=optional_names,
        optional_active_names=optional_active_names,
        extras=extras,
        dev_names=dev_names,
        dev_active_names=dev_active_names,
    )


def optional_extra_registry(repo_root: Path) -> tuple[dict[str, str], set[str]]:
    """Return capability-gated optional extras declared by the core registry."""
    source = repo_root / "src" / "cadrumo" / "core" / "_optional_extras.py"
    module = ast.parse(source.read_text(encoding=_UTF_8), filename=str(source))
    records_by_symbol: dict[str, tuple[str, str]] = {}
    tuple_symbols: set[str] = set()
    for node in module.body:
        assignments: tuple[tuple[ast.Name, ast.expr | None], ...] = ()
        if isinstance(node, ast.Assign):
            assignments = tuple((target, node.value) for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments = ((node.target, node.value),)
        for target, value in assignments:
            if target.id == "OPTIONAL_EXTRAS" and isinstance(value, ast.Tuple):
                tuple_symbols = {elt.id for elt in value.elts if isinstance(elt, ast.Name)}
                continue
            if not target.id.endswith("_EXTRA") or not isinstance(value, ast.Call):
                continue
            func = value.func
            if not isinstance(func, ast.Name) or func.id != "OptionalExtra":
                continue
            kwargs = {keyword.arg: keyword.value for keyword in value.keywords if keyword.arg is not None}
            extra = kwargs.get("extra")
            import_name = kwargs.get("import_name")
            if (
                isinstance(extra, ast.Constant)
                and isinstance(extra.value, str)
                and isinstance(import_name, ast.Constant)
                and isinstance(import_name.value, str)
            ):
                records_by_symbol[target.id] = (extra.value, import_name.value)
    if not records_by_symbol:
        raise SystemExit(f"no OptionalExtra records found in {source}")
    if not tuple_symbols:
        raise SystemExit(f"OPTIONAL_EXTRAS tuple is missing or empty in {source}")
    missing_symbols = sorted(tuple_symbols - set(records_by_symbol))
    if missing_symbols:
        raise SystemExit(f"OPTIONAL_EXTRAS references unknown symbols: {missing_symbols!r}")
    extra_to_import_name = {records_by_symbol[symbol][0]: records_by_symbol[symbol][1] for symbol in tuple_symbols}
    if len(extra_to_import_name) != len(tuple_symbols):
        raise SystemExit(f"duplicate optional-extra names in {source}: {sorted(extra_to_import_name)!r}")
    return extra_to_import_name, tuple_symbols


def assert_optional_extra_registry_matches_pyproject(repo_root: Path) -> None:
    """Verify capability-gated optional extras match pyproject declarations."""
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    optional_dependencies = pyproject["project"].get("optional-dependencies", {})
    project_name = pyproject["project"]["name"]
    registry_extras, _symbols = optional_extra_registry(repo_root)
    missing_pyproject = sorted(extra for extra in registry_extras if extra not in optional_dependencies)
    if missing_pyproject:
        raise SystemExit(
            f"core optional-extra registry names extras missing from pyproject.toml: {missing_pyproject!r}"
        )
    empty_pyproject = sorted(extra for extra in registry_extras if not optional_dependencies.get(extra))
    if empty_pyproject:
        raise SystemExit(f"capability-gated pyproject extras have no dependencies: {empty_pyproject!r}")
    aggregate = set(optional_dependencies.get("all", []))
    missing_aggregate = sorted(
        f"{project_name}[{extra}]" for extra in registry_extras if f"{project_name}[{extra}]" not in aggregate
    )
    if missing_aggregate:
        raise SystemExit(f"pyproject all extra is missing capability extras: {missing_aggregate!r}")
    record_proof("optional extra registry matches pyproject")


def wheel_metadata(wheel: Path) -> tuple[list[str], set[str]]:
    """Return wheel Requires-Dist rows and Provided-Extra names."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode(_UTF_8))
    return metadata.get_all("Requires-Dist") or [], {
        normalise_distribution_name(extra) for extra in (metadata.get_all("Provides-Extra") or [])
    }


def _format_path_sample(paths: list[str], *, limit: int = 20) -> str:
    """Format a bounded path list for actionable gate failures."""
    sample = paths[:limit]
    if len(paths) <= limit:
        return repr(sample)
    return f"{sample!r}; plus {len(paths) - limit} more"


def tracked_source_data_paths(repo_root: Path) -> set[str]:
    """Return tracked shipped-data source paths relative to the repository root."""
    result = run_checked(["git", "ls-files", *TRACKED_DATA_ROOTS], cwd=repo_root, env=_git_env(repo_root))
    tracked = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    if not tracked:
        raise SystemExit("git ls-files reported no tracked shipped data under src/cadrumo/_data")
    outside = sorted(path for path in tracked if not path.startswith(_SOURCE_DATA_PREFIX))
    if outside:
        raise SystemExit(f"git ls-files returned paths outside {_SOURCE_DATA_PREFIX}: {outside[:10]!r}")
    absent = sorted(path for path in tracked if not (repo_root / path).is_file())
    if absent:
        raise SystemExit(
            f"{len(absent)} tracked shipped-data files are absent from the worktree: "
            f"{_format_path_sample(absent)}. Reconcile these paths before packaging: restore the tracked files, "
            "or remove them from git tracking if they were intentionally retired."
        )
    missing_allow_list = sorted(_RENTA_PDF_ALLOW_LIST - tracked)
    if missing_allow_list:
        raise SystemExit(f"tracked shipped data is missing Renta PDF allow-list files: {missing_allow_list!r}")
    return tracked


def _configured_corpus_binary_suffixes(repo_root: Path) -> tuple[str, ...]:
    """Return corpus suffixes excluded by the root wheel configuration."""
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding=_UTF_8))
    excluded = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"]
    prefix = f"{_CORPUS_SOURCE_PREFIX}**/*"
    suffixes = tuple(sorted({Path(pattern).suffix.lower() for pattern in excluded if pattern.startswith(prefix)}))
    if not suffixes or "" in suffixes:
        raise SystemExit("root wheel config declares no precise corpus binary suffix exclusions")
    return suffixes


def _companion_corpus_ownership(repo_root: Path) -> dict[str, frozenset[str]]:
    """Return top-level corpus partitions and suffixes owned by companion hooks."""
    ownership: dict[str, frozenset[str]] = {}
    for relative_hook in _COMPANION_HOOKS:
        tree = ast.parse((repo_root / relative_hook).read_text(encoding=_UTF_8))
        literals: dict[str, frozenset[str]] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name not in {"_CORPUS_BINARY_SUFFIXES", "_OWNED_SUBDIRS"}:
                continue
            value = node.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "frozenset":
                value = value.args[0]
            literals[name] = frozenset(str(item).lower() for item in ast.literal_eval(value))
        missing = {"_CORPUS_BINARY_SUFFIXES", "_OWNED_SUBDIRS"} - literals.keys()
        if missing:
            raise SystemExit(
                f"companion hook {relative_hook} is missing literal ownership declarations: {sorted(missing)!r}"
            )
        suffixes = literals["_CORPUS_BINARY_SUFFIXES"]
        for subdir in literals["_OWNED_SUBDIRS"]:
            if subdir in ownership:
                raise SystemExit(f"corpus companion ownership overlaps at top-level partition: {subdir}")
            ownership[str(subdir)] = suffixes
    return ownership


def _is_corpus_source_binary(source_relative: str, suffixes: tuple[str, ...]) -> bool:
    """Return True for a tracked ``_data/corpus`` path that is an excluded source binary."""
    return source_relative.startswith(_CORPUS_SOURCE_PREFIX) and source_relative.lower().endswith(suffixes)


def _assert_split_files_have_companion_owners(repo_root: Path, paths: set[str]) -> None:
    """Verify every root-excluded corpus file is selected by one companion hook."""
    ownership = _companion_corpus_ownership(repo_root)
    unowned: list[str] = []
    for path in sorted(paths):
        relative = path.removeprefix(_CORPUS_SOURCE_PREFIX)
        subdir = relative.partition("/")[0]
        if Path(path).suffix.lower() not in ownership.get(subdir, frozenset()):
            unowned.append(path)
    if unowned:
        raise SystemExit(
            f"{len(unowned)} root-excluded corpus binaries have no companion hook owner: {_format_path_sample(unowned)}"
        )


def expected_wheel_data_paths(repo_root: Path) -> set[str]:
    """Return expected bundled-data paths inside the command-bearing wheel.

    Corpus source binaries declared by the root Hatch exclusion list are excluded:
    the wheel-split build config sheds them from this wheel and ships them in the
    two mandatory ``cadrumo-data-*`` distributions, so they are absent from the
    archive.
    Test modules under a ``_data`` ``tests/`` folder are excluded by the
    data-budget wheel boundary (tests serve no installed consumer) and are
    likewise legitimately absent.
    """
    return _expected_wheel_data_paths(repo_root, tracked_source_data_paths(repo_root))


def expected_wheel_data_paths_from_source_tree(source_root: Path) -> set[str]:
    """Derive wheel data expectations solely from one sealed extracted source tree."""
    data_root = source_root / _SOURCE_DATA_PREFIX.removesuffix("/")
    tracked = {
        path.relative_to(source_root).as_posix() for path in scan_directory(data_root, recursive=True) if path.is_file()
    }
    if not tracked:
        raise SystemExit(f"sealed source tree has no shipped data under {data_root}")
    return _expected_wheel_data_paths(source_root, tracked)


def _expected_wheel_data_paths(repo_root: Path, tracked: set[str]) -> set[str]:
    """Project one already-sealed source-data inventory into wheel member paths."""
    suffixes = _configured_corpus_binary_suffixes(repo_root)
    split_owned = {path for path in tracked if "/tests/" not in path and _is_corpus_source_binary(path, suffixes)}
    _assert_split_files_have_companion_owners(repo_root, split_owned)
    expected: set[str] = set()
    for path in tracked:
        if path in split_owned:
            continue
        if "/tests/" in path:
            continue
        expected.add(f"{_WHEEL_DATA_PREFIX}/{path.removeprefix(_SOURCE_DATA_PREFIX)}")
    return expected


def assert_wheel_contains_tracked_data(repo_root: Path, wheel: Path, expected: set[str] | None = None) -> None:
    """Verify the wheel's complete data payload equals the tracked runtime set."""
    expected_paths = expected_wheel_data_paths(repo_root) if expected is None else expected
    with zipfile.ZipFile(wheel) as archive:
        actual_paths = {
            info.filename
            for info in archive.infolist()
            if not info.is_dir() and info.filename.startswith(f"{_WHEEL_DATA_PREFIX}/")
        }
    missing = sorted(expected_paths - actual_paths)
    unexpected = sorted(actual_paths - expected_paths)
    if missing or unexpected:
        raise SystemExit(
            "wheel data payload differs from the tracked runtime set: "
            f"missing={_format_path_sample(missing)}, unexpected={_format_path_sample(unexpected)}"
        )
    record_proof("wheel tracked shipped-data payload")


def assert_wheel_metadata_matches_pyproject(repo_root: Path, wheel: Path) -> None:
    """Verify direct wheel metadata preserves prod/optional/dev intent."""
    assert_optional_extra_registry_matches_pyproject(repo_root)
    surfaces = pyproject_surfaces(repo_root)
    requires_dist, provided_extras = wheel_metadata(wheel)
    core_requires = {requirement_name(req) for req in requires_dist if "extra ==" not in req.lower()}
    optional_requires = {requirement_name(req) for req in requires_dist if "extra ==" in req.lower()}
    all_requires = {requirement_name(req) for req in requires_dist}
    missing_core = sorted(surfaces.project_names - core_requires)
    if missing_core:
        raise SystemExit(f"wheel metadata is missing project dependencies: {missing_core!r}")
    leaked_optional_core = sorted(surfaces.external_optional_names & core_requires)
    if leaked_optional_core:
        raise SystemExit(f"optional dependencies leaked into core wheel metadata: {leaked_optional_core!r}")
    missing_optional = sorted(surfaces.external_optional_names - optional_requires)
    if missing_optional:
        raise SystemExit(f"wheel metadata is missing optional dependency rows: {missing_optional!r}")
    missing_extras = sorted(surfaces.extras - provided_extras)
    if missing_extras:
        raise SystemExit(f"wheel metadata is missing optional extras: {missing_extras!r}")
    leaked_dev = sorted(surfaces.dev_only_names & all_requires)
    if leaked_dev:
        raise SystemExit(f"dev-only dependencies leaked into wheel metadata: {leaked_dev!r}")
    record_proof("wheel metadata dependency surface")


def _export_names(output: str, *, repo_root: Path | None = None) -> set[str]:
    """Return normalized package names from a requirements export.

    A dependency resolved through a ``[tool.uv.sources]`` path source (the
    not-yet-published ``cadrumo-data-*`` companions) exports as a bare local path
    row (``./packaging/cadrumo_data_manuals``) rather than a requirement string;
    resolve such a row to the referenced project's own ``[project].name`` so the
    surface checks see the real package name.

    A WORKSPACE MEMBER exports differently again -- ``-e ./src/cadrumo_harness``,
    an editable row -- so the ``-e`` marker is stripped before the path is
    resolved. Without that the row fell through to requirement parsing, the
    member's name never entered the surface, and the dev export was reported as
    missing a package that was in fact present and editable.
    """
    names: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        candidate = stripped.removeprefix("-e ").strip() if stripped.startswith("-e ") else stripped
        if candidate.startswith(("./", "../")) and repo_root is not None:
            local_pyproject = (repo_root / candidate / "pyproject.toml").resolve()
            if local_pyproject.is_file():
                local = tomllib.loads(local_pyproject.read_text(encoding=_UTF_8))
                names.add(normalise_distribution_name(local["project"]["name"]))
                continue
        names.add(requirement_name(stripped))
    return names


def _assert_export_surface(
    name: str,
    names: set[str],
    *,
    present: AbstractSet[str] = frozenset(),
    absent: AbstractSet[str] = frozenset(),
) -> None:
    """Assert selected packages are present or absent from one uv export."""
    missing = sorted(present - names)
    if missing:
        raise SystemExit(f"{name} export is missing expected packages: {missing!r}")
    leaked = sorted(absent & names)
    if leaked:
        raise SystemExit(f"{name} export contains packages outside its surface: {leaked!r}")


def validate_frozen_exports(repo_root: Path, uv: str) -> None:
    """Validate frozen lock exports for core, optional-runtime, and dev surfaces."""
    surfaces = pyproject_surfaces(repo_root)
    run_checked([uv, "lock", "--check"], cwd=repo_root)
    core = run_checked(
        [uv, "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes"],
        cwd=repo_root,
    )
    extras = run_checked(
        [uv, "export", "--frozen", "--all-extras", "--no-dev", "--no-emit-project", "--no-hashes"],
        cwd=repo_root,
    )
    dev = run_checked(
        [uv, "export", "--frozen", "--all-extras", "--all-groups", "--no-emit-project", "--no-hashes"],
        cwd=repo_root,
    )
    core_names = _export_names(core.stdout, repo_root=repo_root)
    extras_names = _export_names(extras.stdout, repo_root=repo_root)
    dev_names = _export_names(dev.stdout, repo_root=repo_root)
    _assert_export_surface(
        "core",
        core_names,
        present=surfaces.project_active_names,
        absent=(surfaces.external_optional_active_names | surfaces.dev_only_active_names | _CORE_ABSENT_NAMES)
        - _CORE_PRESENT_TRANSITIVE_NAMES,
    )
    _assert_export_surface(
        "extras",
        extras_names,
        present=surfaces.project_active_names | surfaces.external_optional_active_names | _EXTRAS_PRESENT_NAMES,
        absent=surfaces.dev_only_active_names - _CORE_PRESENT_TRANSITIVE_NAMES,
    )
    _assert_export_surface(
        "dev",
        dev_names,
        present=surfaces.project_active_names
        | surfaces.external_optional_active_names
        | surfaces.dev_active_names
        | _DEV_PRESENT_NAMES,
    )
    record_proof("frozen dependency exports")


def venv_bin_dir(venv_path: Path) -> Path:
    """Return the platform-specific virtualenv executable directory."""
    return venv_path / ("Scripts" if os.name == "nt" else "bin")


def venv_python_path(venv_path: Path) -> Path:
    """Return the virtualenv Python executable path."""
    executable = "python.exe" if os.name == "nt" else "python"
    return venv_bin_dir(venv_path) / executable


def venv_cadrumo_path(venv_path: Path) -> Path:
    """Return the virtualenv Cadrumo console-script path."""
    executable = "aeat.exe" if os.name == "nt" else "aeat"
    return venv_bin_dir(venv_path) / executable


def assert_cadrumo_version_output(version: CommandResult, *, context: str) -> None:
    """Require the installed CLI to project the canonical product identity."""
    if not version.stdout.startswith("CADRUMO "):
        raise SystemExit(f"unexpected aeat --version output {context}: {version.stdout!r}")


def build_wheel(repo_root: Path, work_dir: Path, uv: str, *, build_root: Path) -> Path:
    """Build the Cadrumo wheel into the smoke work directory.

    ``build_root`` is both the tree the wheel is built from and the authority
    for its expected shipped-data inventory. It must be a sealed source extract;
    consulting ``repo_root`` for that inventory would reintroduce dirty shared
    worktree bytes into an otherwise isolated artifact proof.
    """
    expected_data_paths = expected_wheel_data_paths_from_source_tree(build_root)
    wheel_dir = work_dir / "wheel"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    run_checked([uv, "build", "--wheel", "--out-dir", str(wheel_dir)], cwd=build_root)
    wheels = scan_directory(wheel_dir, pattern="cadrumo-*.whl")
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one Cadrumo wheel in {wheel_dir}; got {[wheel.name for wheel in wheels]!r}")
    assert_wheel_contains_tracked_data(repo_root, wheels[0], expected_data_paths)
    return wheels[0]


def build_companion_wheels(work_dir: Path, uv: str, *, build_root: Path) -> tuple[Path, Path]:
    """Build the two mandatory data companions for a complete local cohort.

    Built from ``build_root`` for the same reason as :func:`build_wheel`; pass
    a :func:`head_extract` tree so the companions correspond to a commit.
    """
    out_dir = work_dir / "companion-wheels"
    wheels: list[Path] = []
    for project_name, project_dir, wheel_glob in _DATA_COMPANION_PROJECTS:
        run_checked(
            [uv, "build", "--project", str(build_root / project_dir), "--out-dir", str(out_dir)],
            cwd=build_root,
        )
        built = scan_directory(out_dir, pattern=wheel_glob)
        if len(built) != 1:
            raise SystemExit(f"expected one {project_name} wheel in {out_dir}; got {built!r}")
        wheel = built[0]
        if wheel.stat().st_size >= PYPI_FILE_CAP_BYTES:
            raise SystemExit(
                f"{wheel.name} exceeds PyPI's 100 MB per-file cap: {wheel.stat().st_size} bytes",
            )
        wheels.append(wheel)
    if len(wheels) != 2:
        raise SystemExit(f"expected two mandatory companion wheels, got {wheels!r}")
    return wheels[0], wheels[1]


def build_sdist(work_dir: Path, uv: str, *, build_root: Path) -> Path:
    """Build the Cadrumo source distribution into the smoke work directory.

    Built from ``build_root`` so the sdist corresponds to a commit rather than
    to whatever the shared worktree happened to hold; pass a
    :func:`head_extract` tree. This is the lane that caught a torn peer edit
    live, shipping an sdist whose ``application/aggregation`` import did not
    resolve against its own ``_source_mesh`` and failing as if it were a
    packaging regression.
    """
    sdist_dir = work_dir / "sdist"
    sdist_dir.mkdir(parents=True, exist_ok=True)
    run_checked([uv, "build", "--sdist", "--out-dir", str(sdist_dir)], cwd=build_root)
    sdists = scan_directory(sdist_dir, pattern="cadrumo-*.tar.gz")
    if len(sdists) != 1:
        names = [sdist.name for sdist in sdists]
        raise SystemExit(f"expected exactly one cadrumo sdist in {sdist_dir}; got {names!r}")
    return sdists[0]


def install_wheel(
    repo_root: Path,
    work_dir: Path,
    wheel: Path,
    uv: str,
    python: str,
    *,
    extras: tuple[str, ...] = (),
    companion_wheels: tuple[Path, ...] = (),
) -> Path:
    """Install the command wheel and supplied companions into a fresh virtualenv."""
    venv_path = work_dir / "venv"
    run_checked([uv, "venv", str(venv_path), "--python", python], cwd=repo_root)
    # Digest-pinned direct URL requirements: the installer verifies every
    # artifact's bytes at install time and records the digest channel that
    # assert_installed_cohort later re-checks.
    target = digest_install_target("cadrumo", wheel, extras=extras)
    companion_targets = tuple(
        digest_install_target(companion.name.split("-")[0].replace("_", "-"), companion)
        for companion in companion_wheels
    )
    run_checked(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(venv_python_path(venv_path)),
            target,
            *companion_targets,
        ],
        cwd=repo_root,
    )
    run_checked([uv, "pip", "check", "--python", str(venv_python_path(venv_path))], cwd=repo_root)
    record_proof("fresh uv virtualenv install")
    record_proof("pip dependency check")
    return venv_path


def create_pip_venv(work_dir: Path, python_executable: str) -> Path:
    """Create a clean virtualenv and ensure a real ``pip`` is present.

    ``venv --with-pip`` runs ``ensurepip``, whose bundled-wheel install is
    unreliable on the uv-managed python-build-standalone interpreter this smoke
    runs under (it fails outright on the self-hosted macOS runner). When
    ensurepip fails the venv is created WITHOUT pip and pip is seeded with uv;
    the cadrumo wheel is still installed by that plain ``pip`` afterwards, so
    the "installs under real pip" contract this lane proves is preserved - only
    the bootstrap of pip itself changes.

    The interpreter is linked with the platform-default strategy (symlinks on
    POSIX, copies on Windows). A COPIED python-build-standalone binary loses its
    ``@executable_path``-relative ``libpython`` on macOS and aborts (SIGABRT) on
    every launch; a symlink resolves through to the real interpreter's lib dir.
    """
    use_symlinks = os.name != "nt"
    venv_path = work_dir / "pip-venv"
    try:
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=use_symlinks).create(venv_path)
    except subprocess.CalledProcessError:
        shutil.rmtree(venv_path, ignore_errors=True)
        venv.EnvBuilder(with_pip=False, clear=False, symlinks=use_symlinks).create(venv_path)
        run_checked(
            ["uv", "pip", "install", "--python", str(venv_python_path(venv_path)), "pip"],
            cwd=work_dir,
        )
    python = venv_python_path(venv_path)
    version = run_checked([str(python), "--version"], cwd=work_dir)
    requested_major_minor = ".".join(python_executable.split(".")[:2])
    if python_executable[0].isdigit() and requested_major_minor not in version.stdout:
        raise SystemExit(
            f"pip venv interpreter {version.stdout.strip()!r} does not match requested {python_executable!r}"
        )
    record_proof("stdlib venv creation")
    return venv_path


def install_targets_with_pip(
    work_dir: Path,
    targets: tuple[str, ...],
    venv_path: Path,
) -> None:
    """Install explicit local targets in one pip transaction."""
    python = venv_python_path(venv_path)
    run_checked(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            *targets,
        ],
        cwd=work_dir,
    )
    run_checked([str(python), "-m", "pip", "check"], cwd=work_dir)
    record_proof("exact local cohort install with pip")
    record_proof("pip dependency check")


def _json_payload(output: str) -> dict[str, Any]:
    """Parse a CLI JSON envelope from subprocess stdout."""
    start = output.find("{")
    if start < 0:
        raise SystemExit(f"command did not emit a JSON envelope: {output!r}")
    try:
        payload = json.loads(output[start:])
    except json.JSONDecodeError as exc:
        raise SystemExit(f"command emitted invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"command JSON envelope was not an object: {payload!r}")
    return payload


def clean_product_env() -> dict[str, str]:
    """Return the process environment without host Cadrumo configuration."""
    return {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}


def isolated_product_env(storage_root: Path) -> dict[str, str]:
    """Return a clean product environment rooted in isolated temporary storage."""
    return {
        **clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(storage_root / 'cadrumo.db').as_posix()}",
    }


def assert_installed_data(work_dir: Path, venv_path: Path) -> None:
    """Verify representative bundled data leaves through the installed package."""
    leaves_literal = repr(list(_REPRESENTATIVE_DATA_LEAVES))
    code = f"""
from importlib.resources import files

root = files("cadrumo").joinpath("_data")
missing = []
for rel in {leaves_literal}:
    if not root.joinpath(*rel.split("/")).is_file():
        missing.append(rel)
if missing:
    raise SystemExit(f"missing installed bundled data leaves: {{missing!r}}")
print(root)
"""
    runtime_root = work_dir / "installed-data-state"
    env = isolated_product_env(runtime_root)
    run_checked([str(venv_python_path(venv_path)), "-c", code], cwd=work_dir, env=env)
    record_proof("installed bundled data resources")


def assert_attachment_and_llm_surfaces(work_dir: Path, venv_path: Path) -> None:
    """Verify installed attachment storage and LLM optional-boundary behavior."""
    runtime_root = work_dir / "runtime-surfaces"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_root_literal = repr(str(runtime_root))
    code = f"""
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

from cadrumo.llm.client import LLMClient
from cadrumo.llm.errors import LLMConfigError
from cadrumo.llm.models import LLMProvider
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.sql import SecureObjectRepository, dispose_engine, get_engine
from cadrumo.core.config import Settings
from cadrumo.domain.attachments import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    AttachmentKind,
    AttachmentSource,
    add_attachment,
    list_attachments,
    load_attachment,
)

root = Path({runtime_root_literal})
root.mkdir(parents=True, exist_ok=True)
settings = Settings(
    cadrumo_database_url=f"sqlite:///{{(root / 'attachments.db').as_posix()}}",
    cadrumo_local_storage_root=root / "state",
)
session = BucketSession.open(
    bucket_id="packaging-smoke",
    kek=os.urandom(32),
    dek=os.urandom(32),
    idle_minutes=15,
    opened_at=datetime.now(UTC).replace(microsecond=0),
    unsecured_backend=True,
)
payload = b"%PDF-1.4\\n%cadrumo-packaging-attachment-smoke\\n"
try:
    engine = get_engine(settings)
    with activate_session(session):
        store = AttachmentStore(objects=SecureObjectRepository(engine=engine))
        attachment = add_attachment(
            store,
            content=AttachmentBytesContent(data=payload),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.LOCAL_FILE,
                source_reference="packaging-smoke.pdf",
                mime_type="application/pdf",
                captured_at=datetime.now(UTC).replace(microsecond=0),
                bucket_id="packaging-smoke",
                link_transaction_ids=("tx-packaging-smoke",),
            ),
        )
        expected = hashlib.sha256(payload).hexdigest()
        if attachment.attachment_id != expected:
            raise SystemExit(f"attachment digest mismatch: {{attachment.attachment_id}} != {{expected}}")
        if store.read_bytes(attachment.attachment_id) != payload:
            raise SystemExit("attachment bytes did not round-trip")
        loaded = load_attachment(store, attachment.attachment_id)
        if loaded.attachment_id != attachment.attachment_id:
            raise SystemExit("attachment manifest did not round-trip")
        listed = tuple(list_attachments(store))
        if [item.attachment_id for item in listed] != [attachment.attachment_id]:
            raise SystemExit(f"unexpected attachment listing: {{listed!r}}")
finally:
    session.close()
    dispose_engine(settings)

try:
    LLMClient(settings=Settings(cadrumo_local_storage_root=root / "llm-state"))._build_adapter(LLMProvider.ANTHROPIC)
except LLMConfigError as exc:
    if exc.suggestion != "pip install cadrumo[anthropic]":
        raise SystemExit(f"unexpected Anthropic install hint: {{exc.suggestion!r}}")
else:
    raise SystemExit("Anthropic adapter unexpectedly built in a core wheel install")

print("attachment-and-llm-surfaces-ok")
"""
    env = {
        **clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(runtime_root / "import-state"),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(runtime_root / 'import-state.db').as_posix()}",
    }
    run_checked([str(venv_python_path(venv_path)), "-c", code], cwd=work_dir, env=env)
    record_proof("attachment storage round-trip")
    record_proof("core LLM missing-extra boundary")


def assert_cli_smoke(work_dir: Path, venv_path: Path) -> None:
    """Run installed CLI smoke checks against the clean wheel venv."""
    cadrumo = str(venv_cadrumo_path(venv_path))
    version = run_checked(
        [cadrumo, "--version"],
        cwd=work_dir,
        env=isolated_product_env(work_dir / "version-state"),
    )
    assert_cadrumo_version_output(version, context="in core venv")

    default_root = work_dir / "default-check-state"
    default_env = isolated_product_env(default_root)
    default_check = run_checked(
        [cadrumo, "--format", "json", "config", "check"],
        cwd=work_dir,
        env=default_env,
        expected={1, 2},
    )
    default_payload = _json_payload(default_check.stdout)
    if default_payload.get("status") != "success" or default_payload.get("result", {}).get("ok") is not False:
        raise SystemExit(
            f"default config check did not report typed missing-dependency diagnostics: {default_payload!r}"
        )

    storage_root = work_dir / "profile-root"
    storage_root.mkdir(parents=True, exist_ok=True)
    env = {
        **clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
        "CADRUMO_OUTPUT_LANGUAGE": "en",
        "CADRUMO_SECRET_PASSPHRASE": secrets.token_urlsafe(24),
        # Headless custody: the AUTO backend writes to the OS keychain, which
        # a self-hosted runner's service session refuses (macOS launchd has no
        # unlocked login keychain - AUTH_STORAGE_KEYRING_UNAVAILABLE on the
        # first run on a fresh macOS host). The passphrase-backed file backend is the
        # smoke's posture everywhere, and keeps smoke runs from writing real
        # keys into any host keychain.
        "CADRUMO_SECRET_STORE_BACKEND": "unsecured",
    }
    create = run_checked(
        [
            cadrumo,
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "packaging-smoke",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "00000000T",
            "--name",
            "Packaging",
            "--surnames",
            "Smoke",
            "--irpf-income-categories",
            "actividad_economica",
            # Choose a comunidad autónoma explicitly: leaving it unset makes the
            # create envelope carry a `ccaa_defaulted` warning notice, which
            # flips the envelope status to "warning" and reds this success probe.
            "--tax-residence-ccaa",
            "madrid",
            "--quiet",
            "--accept-defaults",
            "--no-llm-vision",
            "--no-google-export",
        ],
        cwd=work_dir,
        env=env,
    )
    create_payload = _json_payload(create.stdout)
    if create_payload.get("status") != "success":
        raise SystemExit(f"profile create did not succeed: {create_payload!r}")

    ready = run_checked([cadrumo, "--format", "json", "config", "check"], cwd=work_dir, env=env)
    ready_payload = _json_payload(ready.stdout)
    result = ready_payload.get("result", {})
    if ready_payload.get("status") != "success" or result.get("ok") is not True or result.get("issues") != []:
        raise SystemExit(f"opted-out config check did not pass cleanly: {ready_payload!r}")
    record_proof("installed CLI config/profile smoke")


def resolve_work_dir(repo_root: Path, requested: str | None, *, prefix: str = "core") -> Path:
    """Resolve a new packaging smoke work directory."""
    if requested is not None:
        path = Path(requested).resolve()
        if path.exists() and any(iter_directory(path)):
            raise SystemExit(f"--work-dir must be empty or absent: {path}")
        path.mkdir(parents=True, exist_ok=True)
        return path
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = repo_root / "var" / "packaging-smoke" / f"{prefix}-{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def relative_manifest_path(work_dir: Path, path: Path) -> str:
    """Return a stable manifest path, relative to the smoke work dir when possible."""
    resolved_work_dir = work_dir.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_work_dir).as_posix()
    except ValueError:
        return str(resolved_path)


def write_smoke_manifest(
    work_dir: Path,
    *,
    lane: str,
    artifacts: dict[str, str],
    declared: tuple[str, ...],
    details: dict[str, Any] | None = None,
) -> Path:
    """Write the record for one successful run, deriving its checks from the ledger.

    ``declared`` is the contract the form promises to satisfy. The written
    ``checks`` are the RECORDED proofs, never the declaration, so a claim cannot
    appear unless its assertion ran. A declared claim that was never recorded
    raises :class:`ProofContractError` before anything is written.

    :class:`PackagingSmokeManifest` is unchanged — ``checks`` keeps its name,
    type and schema, so every existing evidence row stays valid and readable.
    Only the provenance of the value changes, from a hand-written literal to a
    derived record.

    Raises:
        ProofContractError: On a declared claim with no recorded assertion.
    """
    recorded = recorded_proofs()
    unperformed = [claim for claim in declared if claim not in recorded]
    if unperformed:
        raise ProofContractError(
            f"{lane}: declared proofs never executed: {unperformed!r}; recorded this run: {list(recorded)!r}",
        )
    manifest = PackagingSmokeManifest(
        ok=True,
        lane=lane,
        completed_at=datetime.now(UTC),
        work_dir=str(work_dir.resolve()),
        artifacts=artifacts,
        checks=recorded,
        details=details or None,
    )
    path = work_dir / "packaging-smoke-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding=_UTF_8, newline="\n")
    return path
