"""Verify declared dependency surfaces, optional capabilities, and wheel metadata."""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cadrumo.core.toml import load_toml, parse_toml
from dev._paths import UTF_8

from ._distribution_names import normalise_distribution_name
from .lane_verification_core import run_checked
from .proof_ledger import (
    record_proof,
)
from .wheel_metadata import read_wheel_metadata

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
    # mcp requires pywin32 on win32, so the harness dependency carries it into the
    # core export on Windows without the project declaring it.
    "pywin32",
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


#: SGR colour sequences `uv export` emits when it judges the stream a terminal.
#: They precede the payload, so a comment line reads as `\x1b[32m# ...` and never
#: matches a bare `#` prefix test. The export parser strips them rather than
#: depending on the producer's colour decision.
_ANSI_SGR = re.compile(r"\x1b\[[0-9;]*m")


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


def _requirement_names(requirements: list[str], *, active_only: bool = False) -> set[str]:
    return {
        requirement_name(requirement)
        for requirement in requirements
        if not active_only or _requirement_applies_to_current_platform(requirement)
    }


def _dependency_names(entries: tuple[str | dict[str, Any], ...], *, active_only: bool = False) -> set[str]:
    return {
        _dependency_group_name(entry)
        for entry in entries
        if not active_only or _dependency_group_applies_to_current_platform(entry)
    }


def pyproject_surfaces(repo_root: Path) -> DependencySurfaces:
    """Return project, optional, extras, and dev dependency name sets from pyproject."""
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = load_toml(handle)
    project = pyproject["project"]
    project_name = normalise_distribution_name(project["name"])
    project_requirements = project.get("dependencies", [])
    project_names = _requirement_names(project_requirements)
    project_active_names = _requirement_names(project_requirements, active_only=True)
    optional_dependencies = project.get("optional-dependencies", {})
    extras = {normalise_distribution_name(extra) for extra in optional_dependencies}
    optional_requirements = [req for requirements in optional_dependencies.values() for req in requirements]
    optional_names = _requirement_names(optional_requirements)
    optional_active_names = _requirement_names(optional_requirements, active_only=True)
    dependency_groups = pyproject.get("dependency-groups", {})
    dev_entries = _dependency_group_entries(dependency_groups, "dev")
    dev_names = _dependency_names(dev_entries)
    dev_active_names = _dependency_names(dev_entries, active_only=True)
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


def _module_assignments(node: ast.stmt) -> tuple[tuple[ast.Name, ast.expr | None], ...]:
    if isinstance(node, ast.Assign):
        return tuple((target, node.value) for target in node.targets if isinstance(target, ast.Name))
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return ((node.target, node.value),)
    return ()


def _constant_string(value: ast.expr | None) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _optional_extra_record(target: ast.Name, value: ast.expr | None) -> tuple[str, str] | None:
    if not target.id.endswith("_EXTRA") or not isinstance(value, ast.Call):
        return None
    func = value.func
    if not isinstance(func, ast.Name) or func.id != "OptionalExtra":
        return None
    kwargs = {keyword.arg: keyword.value for keyword in value.keywords if keyword.arg is not None}
    extra = _constant_string(kwargs.get("extra"))
    import_name = _constant_string(kwargs.get("import_name"))
    if extra is not None and import_name is not None:
        return extra, import_name
    return None


def _optional_registry_symbols(module: ast.Module) -> tuple[dict[str, tuple[str, str]], set[str]]:
    records_by_symbol: dict[str, tuple[str, str]] = {}
    tuple_symbols: set[str] = set()
    for node in module.body:
        for target, value in _module_assignments(node):
            if target.id == "OPTIONAL_EXTRAS" and isinstance(value, ast.Tuple):
                tuple_symbols = {elt.id for elt in value.elts if isinstance(elt, ast.Name)}
                continue
            record = _optional_extra_record(target, value)
            if record is not None:
                records_by_symbol[target.id] = record
    return records_by_symbol, tuple_symbols


def optional_extra_registry(repo_root: Path) -> tuple[dict[str, str], set[str]]:
    """Return capability-gated optional extras declared by the core registry."""
    source = repo_root / "src" / "cadrumo" / "core" / "optional_extras.py"
    module = ast.parse(source.read_text(encoding=UTF_8), filename=str(source))
    records_by_symbol, tuple_symbols = _optional_registry_symbols(module)
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
        pyproject = load_toml(handle)
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
    metadata = read_wheel_metadata(wheel)
    return metadata.get_all("Requires-Dist") or [], {
        normalise_distribution_name(extra) for extra in (metadata.get_all("Provides-Extra") or [])
    }


def _metadata_requirements(requires_dist: list[str]) -> tuple[set[str], set[str], set[str]]:
    core = {requirement_name(req) for req in requires_dist if "extra ==" not in req.lower()}
    optional = {requirement_name(req) for req in requires_dist if "extra ==" in req.lower()}
    all_names = {requirement_name(req) for req in requires_dist}
    return core, optional, all_names


def assert_wheel_metadata_matches_pyproject(repo_root: Path, wheel: Path) -> None:
    """Verify direct wheel metadata preserves prod/optional/dev intent."""
    assert_optional_extra_registry_matches_pyproject(repo_root)
    surfaces = pyproject_surfaces(repo_root)
    requires_dist, provided_extras = wheel_metadata(wheel)
    core_requires, optional_requires, all_requires = _metadata_requirements(requires_dist)
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
    for line in _ANSI_SGR.sub("", output).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        candidate = stripped.removeprefix("-e ").strip() if stripped.startswith("-e ") else stripped
        if candidate.startswith(("./", "../")) and repo_root is not None:
            local_pyproject = (repo_root / candidate / "pyproject.toml").resolve()
            if local_pyproject.is_file():
                local = parse_toml(local_pyproject.read_text(encoding=UTF_8))
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
