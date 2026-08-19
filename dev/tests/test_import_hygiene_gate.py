"""Import-hygiene ratchet gate: the authoritative cross-package import boundary.

Wires ``dev/quality/import_hygiene_scan.py`` into the pytest/CI surface as the single
gate enforcing the import-centralization policy: one canonical
top-level export per symbol; cross-package consumers import only from the
owning package's ``__all__`` facade. Supersedes the two narrower pre-existing
gates it now subsumes:
``src/cadrumo/domain/calculations/registry/tests/test_public_api_boundaries.py``
(registry-package-scoped raw-orchestration boundary) and
``src/cadrumo/entrypoints/cli/tests/test_architecture_boundaries.py`` (CLI-package
private-domain-import subset). Their documented exceptions are seeded below as
named baseline entries so nothing that was previously tolerated silently
regresses.

Three ratcheting/pinned checks, backed by the checked-in
``dev/quality/import_hygiene_baseline.json``:

- **Family 1 (production cross-package private imports).** HARD ZERO (2026-07)
  for the exception this baseline was seeded to track: the
  ``application.review`` <-> ``application.workflow`` cycle-break was
  structurally removed by extracting the four mutually-needed runtime-bound
  names (``WorkflowEvent``, ``utc_now``, ``InvoiceReviewRecord``,
  ``LedgerReviewRecord``) into a shared leaf module,
  ``cadrumo.application._workflow_review_models``, that neither package depends
  on. The baseline's ``sites`` list is now permanently ``[]``. The gate keeps
  its ratchet/named-set-equality shape (count may not exceed the baseline;
  every current violation must be a named baseline entry) rather than a bare
  ``== []`` assertion, so a genuinely new, unrelated production exception
  is forced through the same documented-exception discipline instead of
  silently reopening tolerance for the cycle-break this pass closed. In the
  steady state (baseline ``[]``) both
  checks are equivalent to "zero production Family-1 violations".
- **Family 2 (shim / pure-reexport modules).** The gate asserts the current
  shim set is EXACTLY the dynamically loaded baseline set -- not a ceiling,
  an equality. A new undocumented shim fails; a baseline entry that stops
  being a shim also fails, forcing the baseline to be updated deliberately
  rather than silently drifting. When the baseline is empty, this is the
  canonical zero-shim gate without a mirrored count in test prose.
- **Family 2b (forwarding wrappers).** The same rule in the syntax the
  zero-definitions test cannot see. A forwarding layer written as
  ``def foo(a, *, b): return _real_foo(a, b=b)``, repeated over a package's
  surface, has plenty of real definitions and so passes Family 2 by
  construction. The gate asserts the production set of such callables equals
  the baseline's named ``exemptions`` exactly -- currently empty -- with each
  exemption keyed by ``(path, function)`` and required to state a reason.
- **Family 3 (genuine multi-sourced/duplicate symbols).** The gate asserts (a)
  none of the 7 symbols retired from the app-layer umbrella facades have
  reappeared as multi-facade symbols, and (b) every OTHER
  ``confidence="high"`` symbol declared in more than one facade's ``__all__``
  (a Case-A structural duplicate -- the genuine-duplicate class this policy
  targets) is a member of the named tolerated set. Family-3
  Case-B hits (a symbol facaded AND separately reached from a private
  submodule by an outside consumer -- overwhelmingly test-only debt tracked by
  Family 1's remaining test sweep, not a structural duplicate) are out of
  scope for this pin; they are not asserted here because they shrink as that
  sweep lands, not as a Family-3 fix.

A fourth, TEST-ONLY trio of checks backed by the checked-in
``dev/quality/import_hygiene_test_debt.json`` governs the remainder that
survives after every mechanically-facadable test-only site has been rewritten
onto its owning package's public export: a private evaluator, repository
factory, module-level cache, or constant with no sensible public-facade
promotion, plus the handful of public-named test-only reaches deliberately
declined for promotion because doing so would contradict a
package's documented architecture (e.g. ``LocalFileSystemProvider``, whose
owning package docstring states its concrete backend modules are
intentionally private behind a ``StorageProvider`` Protocol boundary). These
first two mirror the production Family-1 shape (count ratchet plus named-set
equality); the third compares PER-TRIPLE occurrence counts, closing the blind
spot the other two share -- both collapse or total away repeated occurrences of
one reach, so a dead entry becomes a spare slot that hides an unnamed
occurrence of an already-named triple. All three are governed entirely
SEPARATELY from the production baseline: a production (non-test) violation is
NEVER tolerated by the test-debt file, and the production assertions above are
unaffected by its contents.

A fifth, hard-zero check (**Family 4: underscore-named entries in
``__all__``**) asserts the live ``src/cadrumo`` tree carries no facade export
whose name starts with an underscore (a leading ``_``, not a dunder). A public
facade exporting a private-named symbol contradicts the single-canonical-
source policy the naming convention signals everywhere else in the codebase.
Unlike Families 1 and 3 this check has no ratchet or named-tolerance set: it
was closed to zero after every one of the 8 pre-existing hits was disposed of
(promoted to a public name with consumers swept, or dropped from ``__all__``
because the symbol had zero cross-package consumers), so any new hit is a
straight failure with no allowlist escape hatch.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Final, TypedDict

import pytest
from pydantic import TypeAdapter

from cadrumo.core import scan_directory
from cadrumo.tests._inventory import repo_relative
from dev._paths import REPO_ROOT
from dev.quality.import_hygiene_scan import (
    _ACCEPTED_TUI_TEXTUAL_EDGE_SHA256,
    CANONICAL_TUI_PACKAGE,
    DEMOTED_REGISTRY_LOADER_SYMBOLS,
    PKG_ROOT,
    REGISTRY_LOADER_PACKAGE,
    ImportSite,
    TuiBoundaryViolationKind,
    discover_facades,
    find_delegate_wrapper_shims,
    find_dev_tooling_import_violations,
    find_multi_sourced_symbols,
    find_private_import_violations,
    find_registry_loader_import_violations,
    find_shim_modules,
    find_tui_boundary_violations,
    find_underscore_in_all_violations,
    generate_tui_migration_manifest,
    is_shipped_module,
    iter_dynamic_import_targets,
    tui_textual_edge_sha256,
    tui_textual_edges,
    walk_module_imports,
    wheel_exclude_globs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BASELINE_PATH: Final[Path] = REPO_ROOT / "dev" / "quality" / "import_hygiene_baseline.json"
_TEST_DEBT_PATH: Final[Path] = REPO_ROOT / "dev" / "quality" / "import_hygiene_test_debt.json"


@dataclass(frozen=True)
class _BaselineSite:
    """One named, documented production Family-1 exception."""

    importer_path: str
    target_mod: str
    imported_names: tuple[str, ...]
    # Excluded from equality/hash: the line is volatile, and any peer edit that
    # shifted a documented import would otherwise break the gate. Identity is
    # (importer_path, target_mod, imported_names).
    #
    # Only ever populated on scanner-built sites, where it is read from the live
    # AST and is what every diagnostic below prints. Sites loaded from the
    # checked-in files leave it None: those files record an occurrence ordinal
    # instead, because a persisted line number is a cache of a scan with nothing
    # to invalidate it, and it had drifted on roughly half the entries -- by up
    # to 245 lines -- while reading as documentation.
    lineno: int | None = field(compare=False, default=None)


class _BaselineSiteEntry(TypedDict):
    """One JSON ``sites`` entry as checked into the baseline / test-debt files.

    ``occurrence`` is a 1-based ordinal among the entries sharing this entry's
    identity triple, in the order the reaches appear in the importing file. It
    exists because one reach can occur several times in a file -- typically the
    same function-local import in several tests -- each occurrence reasoned
    separately, so something has to say which ``reason`` belongs to which site.
    A line number used to do that job and rotted; an ordinal cannot, because the
    only thing that changes it is a change in how many times the reach occurs,
    which the occurrence gate already refuses to let pass unnoticed.
    """

    importer_path: str
    occurrence: int
    target_mod: str
    imported_names: list[str]


class _Family1Section(TypedDict):
    sites: list[_BaselineSiteEntry]


class _Family2Section(TypedDict):
    paths: list[str]


class _DelegateWrapperExemption(TypedDict):
    """One named, reasoned forwarding wrapper the gate tolerates.

    Keyed by ``(path, function)``. A line number would rot on the first edit
    that moved the callable, and the enclosing function is what the exemption
    is actually about.
    """

    path: str
    function: str
    reason: str


class _Family2DelegateSection(TypedDict):
    exemptions: list[_DelegateWrapperExemption]


class _ToleratedSymbolEntry(TypedDict):
    symbol: str
    confidence: str
    reason: str


class _Family3Section(TypedDict):
    retired_symbols_must_not_reappear: list[str]
    tolerated_multi_sourced_symbols: list[_ToleratedSymbolEntry]


class _BaselineDocument(TypedDict):
    """The checked-in ``dev/quality/import_hygiene_baseline.json`` shape (plus a ``$schema_note`` key)."""

    production_family1_cross_package_private_imports: _Family1Section
    family2_shim_modules: _Family2Section
    family2_delegate_wrapper_shims: _Family2DelegateSection
    family3_pinned_duplicate_symbols: _Family3Section


class _TestDebtDocument(TypedDict):
    """The checked-in ``dev/quality/import_hygiene_test_debt.json`` shape (plus a ``$schema_note`` key)."""

    test_only_family1_underscore_reaches: _Family1Section


_BASELINE_DOCUMENT_ADAPTER = TypeAdapter(_BaselineDocument)
_TEST_DEBT_DOCUMENT_ADAPTER = TypeAdapter(_TestDebtDocument)


def _load_baseline() -> _BaselineDocument:
    return _BASELINE_DOCUMENT_ADAPTER.validate_json(_BASELINE_PATH.read_text(encoding="utf-8"))


def _baseline_sites(baseline: _BaselineDocument) -> tuple[_BaselineSite, ...]:
    family1 = baseline["production_family1_cross_package_private_imports"]
    return tuple(
        _BaselineSite(
            importer_path=entry["importer_path"],
            target_mod=entry["target_mod"],
            imported_names=tuple(entry["imported_names"]),
        )
        for entry in family1["sites"]
    )


@cache
def _scanned_py_files() -> tuple[Path, ...]:
    """Walk the shipped package once per process.

    Seven gates in this module opened with the identical walk and five then ran
    the identical ``walk_module_imports`` pass over it. That pass measured
    18.16s and 18.25s on two consecutive calls -- it carries no memo -- so the
    module paid it once per gate for one unchanging answer.
    """
    return tuple(
        sorted(p for p in scan_directory(PKG_ROOT, pattern="*.py", recursive=True) if "__pycache__" not in p.parts)
    )


@cache
def _scanned_import_sites() -> tuple[ImportSite, ...]:
    """Collect every import site in the shipped package once per process."""
    return tuple(site for path in _scanned_py_files() for site in walk_module_imports(path))


def _package_py_files() -> list[Path]:
    """Return the shipped module list, rebuilt per caller from the cached walk.

    A list rather than the cached tuple, so each gate owns its own sequence and
    passes the scanners exactly the type they received before. Copying ~4900
    paths costs microseconds against an 18s scan.
    """
    return list(_scanned_py_files())


def _package_import_sites() -> list[ImportSite]:
    """Return every import site, rebuilt per caller from the cached pass."""
    return list(_scanned_import_sites())


def _current_production_family1_sites() -> tuple[_BaselineSite, ...]:
    """Re-run the real scanner against the live ``src/cadrumo`` tree."""
    all_sites = _package_import_sites()
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
    assert "family2_delegate_wrapper_shims" in baseline
    assert "family3_pinned_duplicate_symbols" in baseline


def test_production_family1_baseline_is_hard_zero() -> None:
    """The checked-in baseline's production Family-1 ``sites`` list must be empty.

    The ``application.review`` <-> ``application.workflow`` cycle-break this
    baseline used to carry has been structurally removed (see the shared
    ``cadrumo.application._workflow_review_models`` leaf module). ``sites`` is
    now a permanent ``[]``; this pins that the baseline itself has not
    regressed back to a ratchet allowlist for that specific exception.
    """
    baseline_sites = _baseline_sites(_load_baseline())
    assert baseline_sites == (), (
        "dev/quality/import_hygiene_baseline.json's production Family-1 'sites' must stay [] now that "
        "the application.review <-> application.workflow cycle-break has been structurally "
        "removed; do not re-populate it to tolerate that specific exception again."
    )


def test_production_family1_violations_do_not_exceed_baseline_count() -> None:
    """The gate fails if MORE production cross-package private imports appear than baselined.

    The baseline is now hard-zero (``sites == []``) for the
    ``application.review`` <-> ``application.workflow`` cycle-break this gate
    was seeded to track, so in the steady state this assertion is exactly
    ``len(current_sites) <= 0``. This is still expressed as a ratchet (not a
    bare ``== []`` on the current scan) so that a DIFFERENT, unrelated
    production Family-1 exception is forced through the same
    named-exception discipline -- added to ``sites``
    with its own reasoned entry in the same commit that introduces it -- rather
    than silently reopening tolerance for the cycle-break this pass closed.
    """
    baseline_sites = _baseline_sites(_load_baseline())
    current_sites = _current_production_family1_sites()

    assert len(current_sites) <= len(baseline_sites), (
        f"production Family-1 cross-package private-import count regressed: "
        f"{len(current_sites)} current > {len(baseline_sites)} baselined (baseline is hard-zero). "
        f"Every new site must be a documented exception added to {repo_relative(_BASELINE_PATH)} "
        "in the same commit that introduces it, or (preferably) fixed by promoting the symbol to "
        "the owning package's public facade or extracting a shared leaf module."
    )


def test_production_family1_violations_are_exactly_the_named_baseline_set() -> None:
    """Every current production violation must be a NAMED baseline entry.

    With the baseline hard-zero (``sites == []``), this reduces to asserting
    the live scan finds zero production Family-1 sites -- but keeps the
    named-set-equality shape (rather than a bare count) so a new, unnamed
    violation is reported by exact site rather than only by count, and so any
    future reasoned exception is added as a named entry, not a bare number.
    """
    baseline_sites = set(_baseline_sites(_load_baseline()))
    current_sites = set(_current_production_family1_sites())

    unnamed = sorted(
        f"{site.importer_path}:{site.lineno} imports {list(site.imported_names)} from {site.target_mod}"
        for site in current_sites - baseline_sites
    )
    assert unnamed == [], (
        "new, undocumented production Family-1 cross-package private import(s) found "
        f"(not present in {repo_relative(_BASELINE_PATH)}, which is hard-zero for the "
        "application.review <-> application.workflow cycle-break):\n  " + "\n  ".join(unnamed)
    )


def _load_test_debt() -> _TestDebtDocument:
    return _TEST_DEBT_DOCUMENT_ADAPTER.validate_json(_TEST_DEBT_PATH.read_text(encoding="utf-8"))


def _test_debt_sites(test_debt: _TestDebtDocument) -> tuple[_BaselineSite, ...]:
    family1 = test_debt["test_only_family1_underscore_reaches"]
    return tuple(
        _BaselineSite(
            importer_path=entry["importer_path"],
            target_mod=entry["target_mod"],
            imported_names=tuple(entry["imported_names"]),
        )
        for entry in family1["sites"]
    )


def _current_test_only_underscore_sites() -> tuple[_BaselineSite, ...]:
    """Re-run the real scanner and return every TEST-ONLY Family-1 violation site.

    Named "underscore" for its dominant shape (an individual per-symbol
    disposition class: a private helper, evaluator, cache, or constant with
    no sensible public-facade promotion), but also covers the handful of
    public-named test-only reaches deliberately NOT promoted
    (e.g. ``LocalFileSystemProvider``, whose owning package
    docstring documents its backend module as intentionally private behind
    a Protocol boundary) and the one structural-introspection case that
    imports a submodule's own ``__all__`` rather than a symbol through it.
    Every entry here is individually reasoned in
    ``dev/quality/import_hygiene_test_debt.json``; this is not a bulk ceiling.
    """
    all_sites = _package_import_sites()
    violations = find_private_import_violations(all_sites)
    test_only = [v for v in violations if v.is_test]
    return tuple(
        _BaselineSite(
            importer_path=v.importer_path,
            lineno=v.lineno,
            target_mod=v.target_mod,
            imported_names=tuple(v.imported_names),
        )
        for v in test_only
    )


def test_test_debt_file_is_well_formed() -> None:
    """The checked-in test-debt allowlist must exist and declare its one family."""
    assert _TEST_DEBT_PATH.is_file(), f"missing test-debt allowlist: {repo_relative(_TEST_DEBT_PATH)}"
    test_debt = _load_test_debt()
    assert "test_only_family1_underscore_reaches" in test_debt


def test_test_only_underscore_reaches_do_not_exceed_test_debt_count() -> None:
    """The gate fails if MORE test-only underscore-named private imports appear than documented.

    This is the test-debt ratchet counterpart to the production Family-1
    count check: the count may only stay flat or shrink as sites are
    promoted or rewritten onto a facade.
    """
    debt_sites = _test_debt_sites(_load_test_debt())
    current_sites = _current_test_only_underscore_sites()

    assert len(current_sites) <= len(debt_sites), (
        f"test-only underscore-named cross-package private-import count regressed: "
        f"{len(current_sites)} current > {len(debt_sites)} documented. Every new site must be a "
        f"named, reasoned entry added to {repo_relative(_TEST_DEBT_PATH)} in the same commit that "
        "introduces it, or (preferably) fixed by promoting the symbol to the owning package's "
        "public facade and rewriting the test import."
    )


def test_test_only_underscore_reaches_are_exactly_the_named_test_debt_set() -> None:
    """Every current test-only underscore-named reach must be a NAMED test-debt entry.

    Mirrors the production Family-1 set-equality gate: a bare count ratchet
    would let a new undocumented reach slip in unnoticed as long as an old
    one was rewritten in the same pass. This does NOT loosen the production
    assertion above -- a production violation is never tolerated by this
    file; this gate governs test-only debt exclusively.
    """
    debt_sites = set(_test_debt_sites(_load_test_debt()))
    current_sites = set(_current_test_only_underscore_sites())

    unnamed = sorted(
        f"{site.importer_path}:{site.lineno} imports {list(site.imported_names)} from {site.target_mod}"
        for site in current_sites - debt_sites
    )
    assert unnamed == [], (
        "new, undocumented test-only underscore-named cross-package private import(s) found "
        f"(not present in {repo_relative(_TEST_DEBT_PATH)}):\n  " + "\n  ".join(unnamed)
    )


def _site_triples(sites: tuple[_BaselineSite, ...]) -> Counter[tuple[str, str, tuple[str, ...]]]:
    """How many times each identity triple occurs in a site collection."""
    return Counter((s.importer_path, s.target_mod, s.imported_names) for s in sites)


def test_every_test_debt_entry_answers_a_live_occurrence() -> None:
    """The debt file must record each reach exactly as many times as it occurs.

    The two checks above are both blind in the same direction. Set equality
    collapses repeated occurrences of one triple, and the count ratchet
    compares totals, so an entry whose reach no longer exists is not merely
    stale -- it is a spare slot that lets an undocumented occurrence of an
    already-named triple pass both. That is not hypothetical: five entries
    had gone dead (the symbol promoted to a facade, the module renamed,
    the reach rewritten onto a public name), and the padding they left
    concealed a second undocumented reach in test_google_payloads.py.

    Comparing per-triple counts closes it from both sides at once, and does
    so without the fragility that keeps ``lineno`` out of site identity: a
    triple survives any edit that merely moves the import down the file.
    """
    debt = _site_triples(_test_debt_sites(_load_test_debt()))
    current = _site_triples(_current_test_only_underscore_sites())

    dead = sorted(
        f"{k[0]} <- {k[1]} {list(k[2])} (recorded {debt[k]}x, occurs {current[k]}x)"
        for k in debt
        if debt[k] > current[k]
    )
    undocumented = sorted(
        f"{k[0]} <- {k[1]} {list(k[2])} (occurs {current[k]}x, recorded {debt[k]}x)"
        for k in current
        if current[k] > debt[k]
    )

    assert dead == [], (
        f"test-debt entr(ies) in {repo_relative(_TEST_DEBT_PATH)} no longer answer a live reach. "
        "If the reach was promoted onto a facade or rewritten, delete the entry in the same "
        "commit; a spare slot silently widens the ratchet:\n  " + "\n  ".join(dead)
    )
    assert undocumented == [], (
        f"test-only private reach(es) occur more often than {repo_relative(_TEST_DEBT_PATH)} records, "
        "so an occurrence is unnamed. Add one reasoned entry per occurrence, or rewrite the extra "
        "reach onto the owning package's facade:\n  " + "\n  ".join(undocumented)
    )


def test_test_debt_occurrence_ordinals_are_dense_and_start_at_one() -> None:
    """Each triple's entries must be numbered 1..N with no gap or repeat.

    The ordinal is what says which ``reason`` belongs to which of several
    identical reaches in one file, so a duplicate or a hole makes two entries
    indistinguishable again -- the failure the line number used to cause by
    going stale, arriving instead by miscounting.

    Nothing here reads a file, which is the point: the check cannot be broken
    by an edit that merely moves an import. Only a change in how many times a
    reach occurs can disturb it, and that is exactly what the occurrence gate
    above already refuses to let pass unnoticed.
    """
    grouped: dict[tuple[str, str, tuple[str, ...]], list[int]] = {}
    for entry in _load_test_debt()["test_only_family1_underscore_reaches"]["sites"]:
        key = (entry["importer_path"], entry["target_mod"], tuple(entry["imported_names"]))
        grouped.setdefault(key, []).append(entry["occurrence"])

    malformed = sorted(
        f"{k[0]} <- {k[1]} {list(k[2])} numbered {sorted(v)}, expected {list(range(1, len(v) + 1))}"
        for k, v in grouped.items()
        if sorted(v) != list(range(1, len(v) + 1))
    )
    assert malformed == [], (
        f"occurrence ordinals in {repo_relative(_TEST_DEBT_PATH)} must run 1..N per reach, "
        "so every entry names a distinct occurrence:\n  " + "\n  ".join(malformed)
    )


def test_family2_shim_modules_are_exactly_the_dynamic_baseline() -> None:
    """The Family-2 shim/pure-reexport set must equal its loaded baseline exactly.

    A new undocumented shim fails (something is bypassing a facade with an
    ad-hoc re-export module); a baseline entry silently ceasing to be a shim
    also fails (the baseline must be updated deliberately, not drift unnoticed).

    Scoped to ``is_test=False``: this baseline governs the PRODUCTION shim
    policy ("no standing non-``__init__`` re-export bridge modules"). The
    test-tree subset :func:`find_shim_modules` also now walks is a distinct,
    separately-reported category -- see
    ``test_family2_test_tree_shims_are_reported_not_silent`` below -- not
    silently merged into this equality, and not silently dropped from the
    scan either.
    """
    baseline = _load_baseline()
    baseline_paths = frozenset(baseline["family2_shim_modules"]["paths"])

    py_files = _package_py_files()
    facades = discover_facades()
    shims = find_shim_modules(py_files, facades)
    current_paths = frozenset(shim.path for shim in shims if not shim.is_test)

    extra = sorted(current_paths - baseline_paths)
    missing = sorted(baseline_paths - current_paths)
    assert extra == [], f"new undocumented Family-2 shim module(s) found: {extra}"
    assert missing == [], (
        f"documented Family-2 bridge(s) no longer classified as a shim (baseline drift, update "
        f"{repo_relative(_BASELINE_PATH)}): {missing}"
    )


def test_family2_test_tree_shims_are_reported_not_silent() -> None:
    """The scanner must not go blind at the ``tests/`` boundary.

    ``find_shim_modules`` used to ``continue`` past every test-tree module
    before running any of its three shape/naming checks, so the family's
    reach was silently narrower than the "no standing non-``__init__``
    re-export bridge modules" rule it enforces: a hand-authored pure-reexport
    module living under a ``tests/`` directory was invisible to this scan no
    matter how many consumers it served. The scanner now walks the test tree
    too and tags every hit with ``is_test``; this test proves that tagging is
    load-bearing (every ``is_test=True`` hit really is a test module by the
    same two-clause definition :func:`is_test_module` applies -- a ``tests/``
    path component, or a bare ``conftest.py``/``test_*.py`` stem outside one
    -- so the split cannot be vacuously true) and that the category is not
    itself silently empty (a floor, not an exact tally -- this does not pin
    how many exist, only that the reach did not regress back to blind).
    """

    def _looks_like_test_module(path_str: str) -> bool:
        p = Path(path_str)
        if "tests" in p.parts:
            return True
        stem = p.stem
        return stem == "conftest" or stem.startswith("test_")

    py_files = _package_py_files()
    facades = discover_facades()
    shims = find_shim_modules(py_files, facades)

    test_shims = [s for s in shims if s.is_test]
    non_test_shims = [s for s in shims if not s.is_test]

    assert test_shims, (
        "Family 2 found zero test-tree shim/pure-reexport modules; if this is genuinely now "
        "empty, this floor assertion should be relaxed deliberately -- do not let it pass "
        "silently on a regressed (blind) scan reach."
    )
    misclassified_as_test = [s.path for s in test_shims if not _looks_like_test_module(s.path)]
    assert misclassified_as_test == [], f"is_test=True but not a test module by name/path: {misclassified_as_test}"
    misclassified_as_prod = [s.path for s in non_test_shims if _looks_like_test_module(s.path)]
    assert misclassified_as_prod == [], (
        f"is_test=False but looks like a test module by name/path: {misclassified_as_prod}"
    )


def _current_production_delegate_wrappers() -> tuple[tuple[str, str], ...]:
    """Re-run the real scanner and return each production wrapper's ``(path, function)``."""
    py_files = _package_py_files()
    return tuple(
        (wrapper.path, wrapper.function) for wrapper in find_delegate_wrapper_shims(py_files) if not wrapper.is_test
    )


def test_family2_delegate_wrapper_shims_are_exactly_the_documented_exemptions() -> None:
    """No public callable may exist only to re-call another package's symbol.

    The syntax half of the no-standing-bridge rule that a def-counting check
    cannot see: a module written as ``def foo(a, *, b): return _real_foo(a,
    b=b)`` repeated over a package's surface has plenty of real definitions and
    passes the Family-2 zero-definitions test by construction, while being the
    same forwarding layer with the same cost -- a second name for a symbol that
    already has a canonical home, and a second import path to it.

    Equality, not a ceiling, and no tally anywhere: a new wrapper fails, and an
    exemption whose callable stopped being a wrapper fails too, so a dead entry
    can never become a spare slot that hides a live one.
    """
    exemptions = _load_baseline()["family2_delegate_wrapper_shims"]["exemptions"]
    documented = frozenset((entry["path"], entry["function"]) for entry in exemptions)
    current = frozenset(_current_production_delegate_wrappers())

    undocumented = sorted(f"{path}::{function}" for path, function in current - documented)
    stale = sorted(f"{path}::{function}" for path, function in documented - current)
    assert undocumented == [], (
        "forwarding wrapper(s) found: each of these is a public callable whose whole body re-calls "
        "another package's symbol with its own arguments unchanged, so it owns no decision and only "
        "adds a second import path to a symbol that already has a canonical home. Point the consumers "
        "at the owning package's facade and delete the wrapper:\n  " + "\n  ".join(undocumented)
    )
    assert stale == [], (
        f"exemption(s) in {repo_relative(_BASELINE_PATH)} name a callable that is no longer a "
        "forwarding wrapper; drop the entry in the same commit that fixed it:\n  " + "\n  ".join(stale)
    )


def test_family2_delegate_wrapper_exemptions_each_state_a_reason() -> None:
    """An exemption without a stated reason is a mute button, not a judgement."""
    unreasoned = sorted(
        f"{entry['path']}::{entry['function']}"
        for entry in _load_baseline()["family2_delegate_wrapper_shims"]["exemptions"]
        if not entry["reason"].strip()
    )
    assert unreasoned == [], (
        f"every exemption in {repo_relative(_BASELINE_PATH)} must state why the wrapper stands:\n  "
        + "\n  ".join(unreasoned)
    )


_RETIRED_UMBRELLA_SYMBOL_OWNERS: Final[dict[str, str]] = {
    "CalculationRevision": "cadrumo.application.modelo",
    "CalculationRevisionAmendmentKind": "cadrumo.application.modelo",
    "ExternalEvidenceKind": "cadrumo.application.modelo",
    "WorkUnit": "cadrumo.application.modelo",
    "link_transaction": "cadrumo.application.invoices",
    "suggest_reconciliations": "cadrumo.application.invoices",
    "verify_link_consistency": "cadrumo.application.invoices",
}


def test_family3_retired_umbrella_symbols_have_not_reappeared() -> None:
    """The 7 app-layer umbrella re-exports retired from the umbrella facades must stay retired.

    Checked directly against the retired symbol's OWN facade ``__all__`` (not
    the noisy multi-sourced Case-B signal, which still flags these names
    while any test-only consumer reaches the sole domain-layer private
    submodule directly -- that is Family-1 test debt tracked by the remaining
    test sweep, not a Family-3 umbrella-retirement regression).
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
        "symbol(s) retired from the application-layer umbrella facades have "
        f"reappeared in their retired owning facade's __all__: {reappeared}. The domain package "
        "is the sole canonical source; do not re-add these to an application-layer __all__."
    )


def test_family3_genuine_duplicate_symbols_are_exactly_the_pinned_set() -> None:
    """Every Case-A (multi-facade `__all__`) Family-3 'high' confidence symbol is pinned.

    Case-A here means the symbol is declared in more than one facade's
    ``__all__`` -- the structural-duplication shape the Family-3 'genuine
    duplicate' check targets. Case-B hits (a
    facade-declared symbol ALSO reached from a private submodule by an
    outside consumer, usually a test file) are excluded from this pin: they
    are Family-1 test-only debt surfaced through the Family-3 lens and are
    tracked by the remaining test sweep, not by this Family-3 structural pin.
    """
    baseline = _load_baseline()
    tolerated_entries = baseline["family3_pinned_duplicate_symbols"]["tolerated_multi_sourced_symbols"]
    tolerated = {entry["symbol"]: entry["confidence"] for entry in tolerated_entries}

    facades = discover_facades()
    all_sites = _package_import_sites()
    multi_sourced = find_multi_sourced_symbols(facades, all_sites)

    case_a_high = [m for m in multi_sourced if m.confidence == "high" and len(m.facades) > 1]
    untolerated = sorted(f"{m.symbol} (facades={m.facades})" for m in case_a_high if m.symbol not in tolerated)

    assert untolerated == [], (
        "new genuine Family-3 multi-facade duplicate symbol(s) found (declared in >1 owning "
        f"package's __all__): {untolerated}. Either retire the redundant re-export in favour of "
        f"the sole canonical source, or add a named, justified entry to {repo_relative(_BASELINE_PATH)}."
    )


def test_family4_no_underscore_named_entries_in_any_facade_all() -> None:
    """No package facade's ``__all__`` may export a private-named (leading ``_``) symbol.

    Hard-zero check, no ratchet and no named-tolerance allowlist: a public
    facade exporting a private-named symbol contradicts the single-canonical-
    source policy. Every symbol previously found this way was disposed of by
    either promoting it to a public name (with every consumer swept in the
    same commit) or dropping it from ``__all__`` (it stayed importable
    intra-package, just not on the public facade). A new hit must be resolved
    the same way, not silenced by an allowlist entry.
    """
    facades = discover_facades()
    assert facades, "no package facades were discovered; a clean underscore scan over zero facades is not a clean tree"
    violations = find_underscore_in_all_violations(facades)

    offenders = sorted(f"{v.package}.{v.name} ({v.path})" for v in violations)
    assert offenders == [], (
        "underscore-named __all__ entr(y/ies) found -- a public facade must not export a "
        f"private-named symbol: {offenders}. Promote the symbol to a public name (rename + "
        "sweep every consumer in one commit) or drop it from __all__ (it stays importable "
        "intra-package via its owning private submodule)."
    )


# ---------------------------------------------------------------------------
# Family 7: a production module must not import a demoted registry raw-loader
# symbol from cadrumo.domain.calculations.registry
# ---------------------------------------------------------------------------
#
# Four raw-loader names (ModeloRevisionSource, ModeloSource,
# discover_modelo_sources, load_modelo_source) were demoted from the registry
# package's public __all__, and build_snapshot followed as the same
# unguarded-entry-point class as the raw loader family. Every one of the five had
# zero cross-package PRODUCTION consumers at demotion time (build_snapshot's sole external caller is a test fixture).
# The Python import itself still succeeds -- __all__ only governs star-imports
# and introspection -- so this family is the actual enforcement: it reds a NEW
# production import of any of these five names, keeping the demotion from
# being silently reopened.
#
# Hard zero, no allowlist: the current production count is zero, and every one
# of the eight raw-loader siblings that stayed exported (each with a
# documented, real external need this scanner does not gate) is excluded by
# name from DEMOTED_REGISTRY_LOADER_SYMBOLS itself, not by a per-site
# allowlist entry.


def test_no_production_import_of_a_demoted_registry_loader_symbol() -> None:
    """No production module may import a demoted registry raw-loader symbol.

    Hard-zero check: at demotion time none of the five names had a live
    production or test consumer, so any hit here is new. A genuine future need
    is served by keeping the symbol on the facade with a stated per-caller
    reason (the pattern already used for the seven siblings that stayed
    exported), never by adding an allowlist entry to this gate.
    """
    py_files = _package_py_files()
    assert py_files, f"no shipped modules found under {PKG_ROOT}; a hard-zero gate over an empty scan is not a zero"
    all_sites = _package_import_sites()
    violations = find_registry_loader_import_violations(all_sites)

    offenders = [f"{v.importer_path}:{v.lineno} imports {v.imported_names}" for v in violations]
    assert offenders == [], (
        "production import(s) of a demoted registry raw-loader symbol found: "
        f"{offenders}. Route through ValidatedRegistryAuthority, or state the real per-caller "
        "need and keep the symbol on the facade (as already done for load_registry_tree and its "
        "six siblings) -- do not add an allowlist entry to this gate."
    )


def test_the_registry_loader_gate_catches_a_planted_production_import(tmp_path: Path) -> None:
    """Anti-tautology: a planted production import of a demoted symbol MUST be caught.

    Covers both demotion rows in one proof: ``load_modelo_source`` (the raw
    loader family) and ``build_snapshot`` (the unguarded entry point).
    """
    planted = _plant_module(
        tmp_path,
        "cadrumo/planted_registry_loader.py",
        f"from {REGISTRY_LOADER_PACKAGE} import build_snapshot, load_modelo_source\n",
    )
    all_sites = walk_module_imports(planted, src_root=tmp_path)

    violations = find_registry_loader_import_violations(all_sites, src_root=tmp_path)

    assert [(v.importer_path, sorted(v.imported_names)) for v in violations] == [
        ("cadrumo/planted_registry_loader.py", ["build_snapshot", "load_modelo_source"])
    ], f"the gate failed to catch a planted production demoted-loader import; it detected {violations!r}"


def test_the_registry_loader_gate_permits_a_planted_test_import(tmp_path: Path) -> None:
    """The gate is production-only: an identical import in a test module is NOT a violation."""
    planted = _plant_module(
        tmp_path,
        "cadrumo/tests/test_planted_registry_loader.py",
        f"from {REGISTRY_LOADER_PACKAGE} import discover_modelo_sources\n",
    )
    all_sites = walk_module_imports(planted, src_root=tmp_path)

    assert find_registry_loader_import_violations(all_sites) == [], (
        "the registry-loader gate fired on a test module; this family is scoped to production imports only"
    )


def test_the_registry_loader_gate_permits_a_planted_import_of_a_kept_symbol(tmp_path: Path) -> None:
    """The gate is precise: a production import of a symbol that stayed exported is NOT a violation."""
    planted = _plant_module(
        tmp_path,
        "cadrumo/planted_registry_loader_clean.py",
        f"from {REGISTRY_LOADER_PACKAGE} import load_registry_tree\n",
    )
    all_sites = walk_module_imports(planted, src_root=tmp_path)

    assert find_registry_loader_import_violations(all_sites) == [], (
        "the registry-loader gate fired on a symbol that was deliberately kept on the facade"
    )
    assert "load_registry_tree" not in DEMOTED_REGISTRY_LOADER_SYMBOLS


def test_the_registry_loader_gate_permits_an_intra_package_import(tmp_path: Path) -> None:
    """The registry package's own modules may still reach a demoted name directly."""
    planted = _plant_module(
        tmp_path,
        "cadrumo/domain/calculations/registry/planted_internal.py",
        f"from {REGISTRY_LOADER_PACKAGE} import load_modelo_source\n",
    )
    all_sites = walk_module_imports(planted, src_root=tmp_path)

    assert find_registry_loader_import_violations(all_sites) == [], (
        "the registry-loader gate fired on an intra-package import, which is always permitted"
    )


# ---------------------------------------------------------------------------
# Family 5: a shipped module must not import the unshipped dev/ tooling
# ---------------------------------------------------------------------------
#
# RULING, stated so the next reader sees a decision rather than an oversight:
# this family is scoped to SHIPPED modules, and an excluded test tree's
# ``dev.`` import is permitted by design.
#
# The packaging config excludes every ``tests/`` tree from both the wheel and
# the sdist, so a test module's ``dev.`` import cannot reach an installed user
# -- it encodes "this suite needs the repo checkout and the dev dependency
# group", which is already true and intended. A SHIPPED module's identical
# import is a ``ModuleNotFoundError`` for every installed user while resolving
# fine in a source checkout: a defect no in-repo test run can surface. That
# asymmetry, not a style preference, is what this family gates.
#
# "Shipped" is READ from the wheel excludes rather than restated, so the gate
# stays true if the packaging config changes. It is deliberately NOT the
# scanner's ``is_test_module`` partition: a package-root ``conftest.py`` has no
# ``tests/`` path component and therefore SHIPS, so it is gated despite being
# test infrastructure by name. Reusing the name-based partition would have left
# exactly that hole.
#
# The current shipped answer is zero, so this is a hard-zero pin with no
# baseline and no allowlist. Widening it to the excluded test trees would trade
# a hard zero for a migration backlog; do that by ruling if at all, never by
# drift.


def _plant_module(root: Path, dotted_rel: str, body: str) -> Path:
    """Write a synthetic module at ``dotted_rel`` under ``root`` and return its path."""
    path = root / dotted_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_no_shipped_module_imports_the_unshipped_dev_tooling() -> None:
    """No shipped module under ``src/cadrumo`` may import ``dev.``.

    ``dev/`` is development tooling present in neither distribution, so a
    shipped module importing it raises ``ModuleNotFoundError`` for every
    installed user. Hard zero: no baseline, no allowlist. A new hit is fixed by
    moving what the shipped side needs under ``src/cadrumo``, never by
    recording a tolerated exception.
    """
    py_files = _package_py_files()
    assert py_files, f"no shipped modules found under {PKG_ROOT}; a hard-zero gate over an empty scan is not a zero"
    violations = find_dev_tooling_import_violations(py_files)

    offenders = [f"{v.importer_path}:{v.lineno} -> {v.target_mod}" for v in violations]
    assert offenders == [], (
        "shipped module(s) under src/cadrumo import the unshipped dev/ tooling, which "
        f"is a ModuleNotFoundError for every installed user: {offenders}. Move the helper the "
        "shipped side needs into src/cadrumo (or give the shipped side its own implementation "
        "where the dev tool's version is genuinely dev-specific); do not add an allowlist entry."
    )


def test_the_dev_tooling_gate_catches_a_planted_static_production_import(tmp_path: Path) -> None:
    """Anti-tautology: a planted non-test ``from dev.x import y`` MUST be caught.

    Without this proof the hard-zero assertion above is indistinguishable from
    a detector that can never fire -- the failure mode that lets a gate pass
    while blind to the thing it guards.
    """
    _plant_module(tmp_path, "cadrumo/planted_production.py", "from dev.docs.cli_reference import _force_lazy_imports\n")

    violations = find_dev_tooling_import_violations(
        [tmp_path / "cadrumo" / "planted_production.py"],
        src_root=tmp_path,
    )

    assert [(v.importer_path, v.target_mod, v.is_dynamic) for v in violations] == [
        ("cadrumo/planted_production.py", "dev.docs.cli_reference", False)
    ], f"the gate failed to catch a planted production dev-tooling import; it detected {violations!r}"


def test_the_dev_tooling_gate_catches_a_planted_bare_and_dynamic_import(tmp_path: Path) -> None:
    """Anti-tautology: bare ``import dev`` and a dynamically-built target are both caught.

    A ``dev.`` reach expressed through ``importlib.import_module`` is invisible
    to an AST import walk, so a gate covering only ``from``/``import`` forms
    would miss the aliased shape entirely.
    """
    _plant_module(
        tmp_path,
        "cadrumo/planted_dynamic.py",
        "import dev\n"
        "import importlib\n"
        "\n"
        "def load() -> object:\n"
        '    return importlib.import_module("dev.docs.cli_reference")\n',
    )

    violations = find_dev_tooling_import_violations(
        [tmp_path / "cadrumo" / "planted_dynamic.py"],
        src_root=tmp_path,
    )

    assert [(v.target_mod, v.is_dynamic) for v in violations] == [
        ("dev", False),
        ("dev.docs.cli_reference", True),
    ], f"the gate missed the bare or the dynamically-built dev target; it detected {violations!r}"

    # The dynamic extractor must also not over-reach onto a legitimate target.
    _plant_module(tmp_path, "cadrumo/planted_clean.py", 'import importlib\nimportlib.import_module("cadrumo.core")\n')
    assert find_dev_tooling_import_violations([tmp_path / "cadrumo" / "planted_clean.py"], src_root=tmp_path) == [], (
        "the gate fired on a non-dev dynamic import target"
    )

    assert iter_dynamic_import_targets(tmp_path / "cadrumo" / "planted_clean.py") == [(2, "cadrumo.core")]


def test_the_dev_tooling_gate_permits_an_excluded_test_tree_import(tmp_path: Path) -> None:
    """The ruling, proven: an identical import in an EXCLUDED test tree is NOT a violation.

    This pins the scope decision documented above. If someone later widens the
    family to the excluded test trees, this test fails and forces the change to
    be a deliberate ruling rather than a silent broadening.
    """
    body = "from dev.docs.cli_reference import _force_lazy_imports\n"
    planted = [
        _plant_module(tmp_path, "cadrumo/entrypoints/cli/tests/test_planted.py", body),
        _plant_module(tmp_path, "cadrumo/entrypoints/cli/tests/_planted_support.py", body),
        _plant_module(tmp_path, "cadrumo/tests/test_planted_root.py", body),
    ]

    violations = find_dev_tooling_import_violations(planted, src_root=tmp_path)

    assert violations == [], (
        "the dev-tooling gate fired on an EXCLUDED test module, contradicting its documented "
        f"scope: those trees ship in neither the wheel nor the sdist. {violations!r}"
    )


def test_the_dev_tooling_gate_catches_a_planted_shipped_conftest(tmp_path: Path) -> None:
    """A package-root ``conftest.py`` SHIPS, so its ``dev.`` import is a violation.

    Pins the boundary that separates this family from the scanner's name-based
    ``is_test_module`` partition. That partition calls any ``conftest`` a test
    module, but a package-root ``conftest.py`` carries no ``tests/`` path
    component and is a real wheel member -- so a name-based scope would have
    silently exempted a genuinely shipped module.
    """
    planted = _plant_module(tmp_path, "cadrumo/conftest.py", "import dev\n")

    violations = find_dev_tooling_import_violations([planted], src_root=tmp_path)

    assert [(v.importer_path, v.target_mod) for v in violations] == [("cadrumo/conftest.py", "dev")], (
        f"a shipped package-root conftest.py importing dev/ must be caught; the gate detected {violations!r}"
    )


def test_the_shipped_boundary_is_read_from_the_packaging_config() -> None:
    """The shipped/unshipped split must come from the wheel excludes, not a restated list.

    A config rename must fail loudly rather than silently classifying every
    module as shipped (noise) or none as shipped (a muted gate).
    """
    globs = wheel_exclude_globs()
    assert globs, "the wheel exclude list read from pyproject.toml is empty"

    assert is_shipped_module(PKG_ROOT / "conftest.py", exclude_globs=globs) is True
    assert is_shipped_module(PKG_ROOT / "core" / "config.py", exclude_globs=globs) is True
    assert is_shipped_module(PKG_ROOT / "tests" / "test_x.py", exclude_globs=globs) is False
    assert is_shipped_module(PKG_ROOT / "entrypoints" / "cli" / "tests" / "test_x.py", exclude_globs=globs) is False


def _scan_planted_tui_boundary(tmp_path: Path, dotted_rel: str, body: str):
    planted = _plant_module(tmp_path, dotted_rel, body)
    return find_tui_boundary_violations([planted], src_root=tmp_path)


def test_tui_boundary_is_clean_against_the_accepted_legacy_census() -> None:
    generate_tui_migration_manifest()
    source_files = scan_directory(PKG_ROOT, pattern="*.py", recursive=True)
    dev_files = sorted(
        path for path in scan_directory(REPO_ROOT / "dev", pattern="*.py", recursive=True) if "tests" not in path.parts
    )
    accepted_edges = tui_textual_edges(source_files, src_root=REPO_ROOT / "src") | tui_textual_edges(
        dev_files, src_root=REPO_ROOT
    )
    assert tui_textual_edge_sha256(accepted_edges) == _ACCEPTED_TUI_TEXTUAL_EDGE_SHA256

    violations = [
        *find_tui_boundary_violations(
            source_files,
            src_root=REPO_ROOT / "src",
            accepted_textual_edges=accepted_edges,
        ),
        *find_tui_boundary_violations(
            dev_files,
            src_root=REPO_ROOT,
            accepted_textual_edges=accepted_edges,
        ),
    ]

    assert violations == []


@pytest.mark.parametrize(
    ("dotted_rel", "body", "expected_kind"),
    (
        (
            "cadrumo/application/static_tui.py",
            f"from {CANONICAL_TUI_PACKAGE} import launcher\n",
            TuiBoundaryViolationKind.STATIC_IMPORT,
        ),
        (
            "cadrumo/application/type_tui.py",
            f"from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from {CANONICAL_TUI_PACKAGE} import App\n",
            TuiBoundaryViolationKind.TYPE_ONLY_IMPORT,
        ),
        (
            "cadrumo/application/__init__.py",
            f"from {CANONICAL_TUI_PACKAGE} import App\n__all__ = ['App']\n",
            TuiBoundaryViolationKind.REEXPORT,
        ),
        (
            "cadrumo/application/dynamic_tui.py",
            f"import importlib\nimportlib.import_module('{CANONICAL_TUI_PACKAGE}.launcher')\n",
            TuiBoundaryViolationKind.DYNAMIC_IMPORT,
        ),
        (
            "cadrumo/application/annotated_tui.py",
            f"def consume(value: '{CANONICAL_TUI_PACKAGE}.App') -> None:\n    pass\n",
            TuiBoundaryViolationKind.ANNOTATION,
        ),
        (
            "cadrumo/application/annotated_alias_tui.py",
            "import cadrumo as root\ndef consume(value: root.entrypoints.tui.App) -> None:\n    pass\n",
            TuiBoundaryViolationKind.ANNOTATION,
        ),
        (
            "cadrumo/application/registered_tui.py",
            f"registry.add('{CANONICAL_TUI_PACKAGE}.launcher:main')\n",
            TuiBoundaryViolationKind.REGISTRATION,
        ),
        (
            "cadrumo/application/registered_alias_tui.py",
            "container.provide(cadrumo.entrypoints.tui.launcher)\n",
            TuiBoundaryViolationKind.REGISTRATION,
        ),
        (
            "cadrumo/application/textual_screen.py",
            "from textual.screen import Screen\n",
            TuiBoundaryViolationKind.TEXTUAL_LOCATION,
        ),
        (
            "dev/tui/unaccepted_surface.py",
            "from textual.screen import Screen\n",
            TuiBoundaryViolationKind.TEXTUAL_LOCATION,
        ),
        (
            "cadrumo/adapters/inbound/tui/_unaccepted_surface.py",
            "from textual.screen import Screen\n",
            TuiBoundaryViolationKind.TEXTUAL_LOCATION,
        ),
        (
            "cadrumo/entrypoints/tui/app.py",
            "from cadrumo.application.operations._registry import definitions\n",
            TuiBoundaryViolationKind.PRIVATE_FACADE,
        ),
        (
            "cadrumo/entrypoints/tui/app.py",
            "from cadrumo.application.operations import _registry\n",
            TuiBoundaryViolationKind.PRIVATE_FACADE,
        ),
        (
            "cadrumo/entrypoints/tui/app.py",
            "import importlib\nimportlib.import_module('cadrumo.application.operations._registry')\n",
            TuiBoundaryViolationKind.PRIVATE_FACADE,
        ),
    ),
)
def test_tui_boundary_rejects_each_ast_bypass(
    tmp_path: Path,
    dotted_rel: str,
    body: str,
    expected_kind: TuiBoundaryViolationKind,
) -> None:
    violations = _scan_planted_tui_boundary(tmp_path, dotted_rel, body)

    assert [violation.kind for violation in violations] == [expected_kind]


def test_accepted_textual_consumer_cannot_add_a_new_textual_edge(tmp_path: Path) -> None:
    planted = _plant_module(
        tmp_path,
        "cadrumo/application/accepted_textual.py",
        "from textual.app import App\nfrom textual.containers import Container\n",
    )
    accepted = frozenset({("cadrumo.application.accepted_textual", "textual.app")})

    violations = find_tui_boundary_violations([planted], src_root=tmp_path, accepted_textual_edges=accepted)

    assert [(violation.target, violation.kind) for violation in violations] == [
        ("textual.containers", TuiBoundaryViolationKind.TEXTUAL_LOCATION)
    ]
