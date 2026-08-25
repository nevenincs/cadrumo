"""Fixed-point gates for public core defining-module relocations."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from dev.quality.import_hygiene_scan import (
    CanonicalAuthoritySpec,
    CanonicalAuthorityTarget,
    scan_canonical_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

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
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
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
    assert scan_canonical_authority(_AUTHORITY_SPEC) == []


def test_fixed_point_helpers_reject_legacy_shapes(tmp_path: Path) -> None:
    """The strengthened census has positive controls for every forbidden shape."""
    synthetic_path = tmp_path / "synthetic_public_authority_cutover.py"
    retired_private_module = next(iter(_RETIRED_PRIVATE_MODULES))
    samples = (
        f"import {_CORE_PACKAGE} as core\ncore.scan_directory\n",
        f"from {_CORE_PACKAGE} import scan_directory as local_scan\n",
        f"import importlib\nimportlib.import_module({retired_private_module!r})\n",
        f"import importlib\nmodule_name = {retired_private_module!r}\nimportlib.import_module(module_name)\n",
        f"import importlib\ngetattr(importlib.import_module({_CORE_PACKAGE!r}), 'scan_directory')\n",
        "from unrelated.directory_scan import scan_directory\n",
        "exports = scan_directory\n",
        "__all__ = ['scan_directory']\n",
        "_LAZY_EXPORTS = {'scan_directory': '.directory_scan'}\n",
        "lazy = {'scan_directory': '.directory_scan'}\n_LAZY_EXPORTS = lazy\n",
        "_LAZY_EXPORTS = dict(scan_directory='.directory_scan')\n",
        f"import importlib as il\nname = {retired_private_module!r}\nil.import_module(name)\n",
        f"from importlib import import_module as load\nname = {retired_private_module!r}\nload(name)\n",
        f"def local():\n    name = {retired_private_module!r}\n    return importlib.import_module(name)\n",
    )
    for source in samples:
        synthetic_path.write_text(source, encoding="utf-8")
        findings = scan_canonical_authority(_AUTHORITY_SPEC, (synthetic_path,))
        assert any("canonical definition" not in finding.kind for finding in findings), source
        synthetic_path.unlink()
