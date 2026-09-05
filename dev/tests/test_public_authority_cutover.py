"""Fixed-point gates for public core defining-module relocations."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import (
    CanonicalAuthoritySpec,
    CanonicalAuthorityTarget,
    scan_canonical_authority,
    tracked_live_files,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.timeout(600)]
"""The 600-second budget is contention, not a slow test.

Measured at 251.96s under the repository's default `-n auto`
parallelism - 84% of the 300-second ceiling - for
``test_static_authority_census_is_at_the_direct_module_fixed_point``.

The ceiling is wall clock and its expiry does not fail the test: the
thread method kills the worker, and every sibling scheduled on it is
reported as never having run. `--dist=loadfile` puts this whole module on
one worker, so the margin here is shared, not per-case.

The walk itself stays real; resolving the live first-party graph is what
costs the minutes.
"""

_TARGETS = {
    "credentials": {
        "LENGTH_ALONE_IS_STRONG",
        "LENGTH_FAIR_FLOOR",
        "PROFILE_PASSWORD_MAX_SCALARS",
        "PROFILE_PASSWORD_MAX_UTF8_BYTES",
        "PROFILE_PASSWORD_MIN_SCALARS",
        "PassphraseStrength",
        "ProfilePasswordAssessment",
        "ProfilePasswordRefusalReason",
        "assess_passphrase_strength",
        "assess_profile_password",
    },
    "directory_scan": {"DirectoryEntryKind", "iter_directory", "scan_directory"},
}
_ALL_TARGETS = frozenset().union(*_TARGETS.values())
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
# Build retired paths from components so this gate cannot accidentally satisfy
# its own string-remnant census by embedding the forbidden spellings.
_CORE_PACKAGE = ".".join(("cadrumo", "core"))
_RETIRED_QUALIFIED_REFERENCES = frozenset(
    f"{_CORE_PACKAGE}.{name}" for name in ("assess_profile_password", "scan_directory")
)
_RETIRED_PRIVATE_MODULES = frozenset(f"{_CORE_PACKAGE}.{name}" for name in ("_credentials", "_directory_scan"))
_AUTHORITY_SPEC = CanonicalAuthoritySpec(
    targets=tuple(
        CanonicalAuthorityTarget(
            module=f"{_CORE_PACKAGE}.{module}",
            path=_REPOSITORY_ROOT / "src/cadrumo/core" / f"{module}.py",
            symbols=frozenset(symbols),
        )
        for module, symbols in _TARGETS.items()
    ),
    retired_modules=_RETIRED_PRIVATE_MODULES,
    facade_modules=frozenset({_CORE_PACKAGE}),
    forbidden_text_references=_RETIRED_QUALIFIED_REFERENCES | _RETIRED_PRIVATE_MODULES,
)


def _production_and_docs_corpus() -> tuple[Path, ...]:
    """Return tracked shipped, packaging, and public-documentation authority surfaces."""
    roots = tuple((_REPOSITORY_ROOT / name).resolve() for name in ("docs", "packaging", "src"))
    return tuple(path for path in tracked_live_files() if any(path.is_relative_to(root) for root in roots))


def test_each_relocated_symbol_has_one_public_definition() -> None:
    """The move leaves one definition in the public module and no old files."""
    core_root = _REPOSITORY_ROOT / "src" / "cadrumo" / "core"
    assert not (core_root / "_credentials.py").exists()
    assert not (core_root / "_directory_scan.py").exists()

    for module_name, names in _TARGETS.items():
        module = importlib.import_module(f"cadrumo.core.{module_name}")
        expected = set(names)
        assert set(module.__all__) == expected
        for name in names:
            value = getattr(module, name)
            if hasattr(value, "__module__"):
                assert value.__module__ == module.__name__


def test_core_namespace_has_no_relocated_bindings() -> None:
    """The package facade cannot resolve either relocated authority."""
    core = importlib.import_module("cadrumo.core")
    assert not _ALL_TARGETS & set(core.__all__)
    for name in _ALL_TARGETS:
        assert not hasattr(core, name)


def test_static_authority_census_is_at_the_direct_module_fixed_point() -> None:
    """Definitions, imports, dataflow, dynamic access, exports, and strings stay canonical."""
    assert scan_canonical_authority(_AUTHORITY_SPEC, _production_and_docs_corpus()) == []


def test_fixed_point_helpers_reject_legacy_shapes(tmp_path: Path) -> None:
    """The strengthened census has positive controls for every forbidden shape."""
    synthetic_path = tmp_path / "synthetic_public_authority_cutover.py"
    retired_private_module = next(iter(_RETIRED_PRIVATE_MODULES))
    samples = (
        (f"import {_CORE_PACKAGE} as core\ncore.scan_directory\n", {"facade import/package access"}),
        (
            f"from {_CORE_PACKAGE} import scan_directory as local_scan\n",
            {"aliased authority import", "facade import/package access", "non-canonical authority import"},
        ),
        (
            f"import importlib\nimportlib.import_module({retired_private_module!r})\n",
            {"dynamic authority import/access"},
        ),
        (
            f"import importlib\nmodule_name = {retired_private_module!r}\nimportlib.import_module(module_name)\n",
            {"dynamic authority import/access"},
        ),
        (
            f"import importlib\ngetattr(importlib.import_module({_CORE_PACKAGE!r}), 'scan_directory')\n",
            {"facade import/package access"},
        ),
        ("from unrelated.directory_scan import scan_directory\n", {"non-canonical authority import"}),
        ("exports = scan_directory\n", {"indirect authority symbol consumer"}),
        (
            f"from {_CORE_PACKAGE}.directory_scan import scan_directory\nexports = scan_directory\n",
            {"aliased authority binding"},
        ),
        ("__all__ = ['scan_directory']\n", {"indirect authority export"}),
        ("_LAZY_EXPORTS = {'scan_directory': '.directory_scan'}\n", {"indirect authority export"}),
        ("lazy = {'scan_directory': '.directory_scan'}\n_LAZY_EXPORTS = lazy\n", {"indirect authority export"}),
        ("_LAZY_EXPORTS = dict(scan_directory='.directory_scan')\n", {"indirect authority export"}),
        (
            f"import importlib as il\nname = {retired_private_module!r}\nil.import_module(name)\n",
            {"dynamic authority import/access"},
        ),
        (
            f"from importlib import import_module as load\nname = {retired_private_module!r}\nload(name)\n",
            {"dynamic authority import/access"},
        ),
        (
            "import importlib\n"
            "def local():\n"
            f"    name = {retired_private_module!r}\n"
            "    return importlib.import_module(name)\n",
            {"dynamic authority import/access"},
        ),
        (
            f"import {_CORE_PACKAGE} as core\nsetattr(core, 'scan_directory', object())\n",
            {"dynamic authority export"},
        ),
        ("globals()['scan_directory'] = object()\n", {"dynamic authority export"}),
    )
    mutant_spec = CanonicalAuthoritySpec(
        targets=_AUTHORITY_SPEC.targets,
        retired_modules=_AUTHORITY_SPEC.retired_modules,
        facade_modules=_AUTHORITY_SPEC.facade_modules,
        export_container_names=_AUTHORITY_SPEC.export_container_names,
        forbid_import_aliases=_AUTHORITY_SPEC.forbid_import_aliases,
        forbid_qualified_access=_AUTHORITY_SPEC.forbid_qualified_access,
    )
    owner_paths = tuple(target.path for target in mutant_spec.targets)
    for source, expected in samples:
        synthetic_path.write_text(source, encoding="utf-8")
        findings = scan_canonical_authority(mutant_spec, (*owner_paths, synthetic_path))
        assert {finding.kind for finding in findings} == expected, source
        synthetic_path.unlink()
