"""Import-hygiene ratchet gate: the authoritative cross-package import boundary.

Wires ``dev/import_hygiene_scan.py`` into the pytest/CI surface as the single
gate enforcing the ``import-centralization`` ADR's Ruling 1 (one canonical
top-level export per symbol; cross-package consumers import only from the
owning package's ``__all__`` facade). Supersedes the two narrower pre-existing
gates it now subsumes:
``src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py``
(registry-package-scoped raw-orchestration boundary) and
``src/aeat/entrypoints/cli/tests/test_architecture_boundaries.py`` (CLI-package
private-domain-import subset). Their documented exceptions are seeded below as
named baseline entries so nothing that was previously tolerated silently
regresses.

Three ratcheting/pinned checks, backed by the checked-in
``dev/import_hygiene_baseline.json``:

- **Family 1 (production cross-package private imports).** The gate fails if
  the current non-test violation COUNT exceeds the baseline, or if the current
  violation SET is not a subset of the named baseline sites (a new, unnamed
  violation fails even if an old one was fixed in the same pass, keeping the
  baseline honest as a named allowlist rather than a bare counter). A closing
  commit that fixes a violation shrinks ``sites`` in the same commit
  (``aeat-architecture-boundaries`` relocation-atomicity discipline). Wave W06
  flips ``sites`` to ``[]`` once production reaches hard zero.
- **Family 2 (shim / pure-reexport modules).** The gate asserts the current
  shim set is EXACTLY the 6 documented bridges named in the baseline -- not a
  ceiling, an equality. A new undocumented shim fails; a bridge that stops
  being a shim (a real implementation lands in it) also fails, forcing the
  baseline to be updated deliberately rather than silently drifting.
- **Family 3 (genuine multi-sourced/duplicate symbols).** The gate asserts (a)
  none of the 7 symbols retired from the app-layer umbrella facades in Wave
  W03.P88 have reappeared as multi-facade symbols, and (b) every OTHER
  ``confidence="high"`` symbol declared in more than one facade's ``__all__``
  (a Case-A structural duplicate -- the genuine-duplicate class the ADR
  targets) is a member of the named tolerated set. Family-3 Case-B hits (a
  symbol facaded AND separately reached from a private submodule by an
  outside consumer -- overwhelmingly test-only debt tracked by Family 1's
  Wave W05 test sweep, not a structural duplicate) are out of scope for this
  pin; they are not asserted here because they shrink as Wave W05 lands, not
  as a Family-3 fix.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest
from dev.import_hygiene_scan import (
    PKG_ROOT,
    discover_facades,
    find_multi_sourced_symbols,
    find_private_import_violations,
    find_shim_modules,
    walk_module_imports,
)

from ..core.paths import PROJECT_ROOT
from ._inventory import repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BASELINE_PATH: Final[Path] = PROJECT_ROOT / "dev" / "import_hygiene_baseline.json"


@dataclass(frozen=True)
class _BaselineSite:
    """One named, documented production Family-1 exception."""

    importer_path: str
    lineno: int
    target_mod: str
    imported_names: tuple[str, ...]


def _load_baseline() -> dict[str, object]:
    return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))


def _baseline_sites(baseline: dict[str, object]) -> tuple[_BaselineSite, ...]:
    family1 = baseline["production_family1_cross_package_private_imports"]
    return tuple(
        _BaselineSite(
            importer_path=entry["importer_path"],
            lineno=entry["lineno"],
            target_mod=entry["target_mod"],
            imported_names=tuple(entry["imported_names"]),
        )
        for entry in family1["sites"]
    )


def _current_production_family1_sites() -> tuple[_BaselineSite, ...]:
    """Re-run the real scanner against the live ``src/aeat`` tree."""
    py_files = sorted(p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    all_sites = [site for path in py_files for site in walk_module_imports(path)]
    violations = find_private_import_violations(all_sites)
    non_test = [v for v in violations if not v.is_test]
    return tuple(
        _BaselineSite(
            importer_path=v.importer_path,
            lineno=v.lineno,
            target_mod=v.target_mod,
            imported_names=tuple(v.imported_names),
        )
        for v in non_test
    )


def test_baseline_file_is_well_formed() -> None:
    """The checked-in baseline must exist and declare all three families."""
    assert _BASELINE_PATH.is_file(), f"missing ratchet baseline: {repo_relative(_BASELINE_PATH)}"
    baseline = _load_baseline()

    assert "production_family1_cross_package_private_imports" in baseline
    assert "family2_shim_modules" in baseline
    assert "family3_pinned_duplicate_symbols" in baseline


def test_production_family1_violations_do_not_exceed_baseline_count() -> None:
    """The gate fails if MORE production cross-package private imports appear than baselined.

    This is the ratchet: the count may only stay flat or shrink. It is
    computed from a live AST scan of ``src/aeat`` on every run, so it cannot
    go stale.
    """
    baseline_sites = _baseline_sites(_load_baseline())
    current_sites = _current_production_family1_sites()

    assert len(current_sites) <= len(baseline_sites), (
        f"production Family-1 cross-package private-import count regressed: "
        f"{len(current_sites)} current > {len(baseline_sites)} baselined. "
        f"Every new site must be a documented exception added to {repo_relative(_BASELINE_PATH)} "
        "in the same commit that introduces it, or (preferably) fixed by promoting the symbol to "
        "the owning package's public facade."
    )


def test_production_family1_violations_are_exactly_the_named_baseline_set() -> None:
    """Every current production violation must be a NAMED baseline entry.

    A bare count ratchet would let a new violation slip in unnoticed as long
    as an old one was fixed in the same pass (net count unchanged). Asserting
    set equality against the named sites keeps the baseline an honest,
    reviewable allowlist -- not a silent counter -- per the
    ``no-dormant-source-resolvers`` / ``no-silent-under-declaration`` family of
    disciplines: an unrouted, unnamed violation must surface, never hide
    behind another site's fix.
    """
    baseline_sites = set(_baseline_sites(_load_baseline()))
    current_sites = set(_current_production_family1_sites())

    unnamed = sorted(
        f"{site.importer_path}:{site.lineno} imports {list(site.imported_names)} from {site.target_mod}"
        for site in current_sites - baseline_sites
    )
    assert unnamed == [], (
        "new, undocumented production Family-1 cross-package private import(s) found "
        f"(not present in {repo_relative(_BASELINE_PATH)}):\n  " + "\n  ".join(unnamed)
    )


def test_family2_shim_modules_are_exactly_the_documented_bridges() -> None:
    """The Family-2 shim/pure-reexport set must equal the 6 documented bridges exactly.

    A new undocumented shim fails (something is bypassing a facade with an
    ad-hoc re-export module); a bridge silently ceasing to be a shim also
    fails (the baseline must be updated deliberately, not drift unnoticed).
    """
    baseline = _load_baseline()
    baseline_paths = frozenset(baseline["family2_shim_modules"]["paths"])

    py_files = sorted(p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    facades = discover_facades()
    shims = find_shim_modules(py_files, facades)
    current_paths = frozenset(shim.path for shim in shims)

    extra = sorted(current_paths - baseline_paths)
    missing = sorted(baseline_paths - current_paths)
    assert extra == [], f"new undocumented Family-2 shim module(s) found: {extra}"
    assert missing == [], (
        f"documented Family-2 bridge(s) no longer classified as a shim (baseline drift, update "
        f"{repo_relative(_BASELINE_PATH)}): {missing}"
    )


_RETIRED_UMBRELLA_SYMBOL_OWNERS: Final[dict[str, str]] = {
    "CalculationRevision": "aeat.application.modelo",
    "CalculationRevisionAmendmentKind": "aeat.application.modelo",
    "ExternalEvidenceKind": "aeat.application.modelo",
    "WorkUnit": "aeat.application.modelo",
    "link_transaction": "aeat.application.invoices",
    "suggest_reconciliations": "aeat.application.invoices",
    "verify_link_consistency": "aeat.application.invoices",
}


def test_family3_retired_umbrella_symbols_have_not_reappeared() -> None:
    """The 7 app-layer umbrella re-exports retired in Wave W03.P88 must stay retired.

    Checked directly against the retired symbol's OWN facade ``__all__`` (not
    the noisy multi-sourced Case-B signal, which still flags these names
    while any test-only consumer reaches the sole domain-layer private
    submodule directly -- that is Family-1 test debt tracked by Wave W05, not
    a Family-3 umbrella-retirement regression).
    """
    baseline = _load_baseline()
    retired = baseline["family3_pinned_duplicate_symbols"]["retired_symbols_must_not_reappear"]
    assert set(retired) == set(_RETIRED_UMBRELLA_SYMBOL_OWNERS), (
        "baseline retired-symbol set drifted from the gate's owner map"
    )

    facades = discover_facades()
    reappeared = sorted(
        symbol
        for symbol in retired
        if (owner := facades.get(_RETIRED_UMBRELLA_SYMBOL_OWNERS[symbol])) is not None
        and owner.has_real_all
        and symbol in owner.all_names
    )

    assert reappeared == [], (
        "symbol(s) retired from the application-layer umbrella facades in Wave W03.P88 have "
        f"reappeared in their retired owning facade's __all__: {reappeared}. The domain package "
        "is the sole canonical source; do not re-add these to an application-layer __all__."
    )


def test_family3_genuine_duplicate_symbols_are_exactly_the_pinned_set() -> None:
    """Every Case-A (multi-facade `__all__`) Family-3 'high' confidence symbol is pinned.

    Case-A here means the symbol is declared in more than one facade's
    ``__all__`` -- the structural-duplication shape the ADR's Family-3
    'genuine duplicate' finding targets. Case-B hits (a facade-declared symbol
    ALSO reached from a private submodule by an outside consumer, usually a
    test file) are excluded from this pin: they are Family-1 test-only debt
    surfaced through the Family-3 lens and are tracked by Wave W05's test
    sweep, not by this Family-3 structural pin.
    """
    baseline = _load_baseline()
    tolerated_entries = baseline["family3_pinned_duplicate_symbols"]["tolerated_multi_sourced_symbols"]
    tolerated = {entry["symbol"]: entry["confidence"] for entry in tolerated_entries}

    py_files = sorted(p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    facades = discover_facades()
    all_sites = [site for path in py_files for site in walk_module_imports(path)]
    multi_sourced = find_multi_sourced_symbols(facades, all_sites)

    case_a_high = [m for m in multi_sourced if m.confidence == "high" and len(m.facades) > 1]
    untolerated = sorted(f"{m.symbol} (facades={m.facades})" for m in case_a_high if m.symbol not in tolerated)

    assert untolerated == [], (
        "new genuine Family-3 multi-facade duplicate symbol(s) found (declared in >1 owning "
        f"package's __all__): {untolerated}. Either retire the redundant re-export in favour of "
        f"the sole canonical source, or add a named, justified entry to {repo_relative(_BASELINE_PATH)}."
    )
