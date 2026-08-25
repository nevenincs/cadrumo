"""Focused unit tests for the temporal-revision-selection helper.

`select_revision` funnels every snapshot resolution. It has three
failure modes (no-match, ambiguous-selection, mismatching revision_id)
and four filter modes (filing_year, period, on= date window, and
revision_id). Indirect coverage exists through the snapshot suite,
but the committed registry is designed without overlapping revisions
so the `ambiguous revision selection` branch is never exercised in
the registry-load tests. A regression in the dedup check would
otherwise land silently.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from .....core import RegistryAuthorityGrade, scan_directory
from ..errors import (
    AmbiguousRevisionSelectionError,
    NoRevisionForPeriodError,
    RegistrySnapshotError,
)
from .._relations import relation_source_requirements
from .._schema import ModeloDefinition
from .._temporal import select_revision
from .._validate_revision_rules import validate_revision_windows
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_modelo_100() -> ModeloDefinition:
    modelo, _catalogues = _committed_modelo("100")
    return modelo


def test_select_revision_returns_the_matching_year_revision() -> None:
    modelo = _committed_modelo_100()

    revision = select_revision(modelo, filing_year=2025, period="0A")

    assert revision.id == "2025"


def test_snapshot_normalises_a_case_variant_period_to_the_declared_token() -> None:
    """A valid lower-case token must not survive into the snapshot verbatim.

    ``select_revision`` matches selectors case-insensitively and returns the
    caller's token unchanged, so the snapshot boundary is where the canonical
    form is resolved. Without it the snapshot disagreed with itself: its
    ``filing_period`` normalised through ``Period`` while ``period`` did not.
    """
    snapshot = _committed_snapshot("100", 2025, "0a", grade=RegistryAuthorityGrade.CALCULATION)

    assert snapshot.period == "0A"
    assert snapshot.filing_period is not None
    assert snapshot.filing_period.code == snapshot.period
    assert (
        snapshot.revision.id
        == _committed_snapshot("100", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION).revision.id
    )


def test_case_variant_periods_activate_the_same_relation_requirements() -> None:
    """Relation activation is exact-membership, so case must not silence it.

    A lower-case ``0a`` selected the same M100 revision as ``0A`` while
    activating none of its relation declarations -- the caller got a successful
    snapshot and a clean-looking empty obligation set instead of the required
    cross-model inputs.
    """
    canonical = _committed_snapshot("100", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    variant = _committed_snapshot("100", 2025, "0a", grade=RegistryAuthorityGrade.CALCULATION)

    canonical_requirements = relation_source_requirements(
        canonical.revision,
        filing_year=2025,
        period=canonical.period,
    )
    variant_requirements = relation_source_requirements(
        variant.revision,
        filing_year=2025,
        period=variant.period,
    )

    assert canonical_requirements, "the M100 2025 revision must declare relation requirements"
    assert variant_requirements == canonical_requirements


def test_case_variant_period_still_refuses_an_undeclared_token() -> None:
    """Normalisation must not widen the accepted set beyond declared periods."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="0b")


def test_select_revision_raises_when_no_revision_matches_year() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2099, period="0A")


def test_select_revision_raises_when_period_not_declared_by_selector() -> None:
    """Renta is annual-only — period='0A' is the lone declared period."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="3T")


def test_select_revision_honours_explicit_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    revision = select_revision(modelo, filing_year=2024, period="0A", revision_id="2024")

    assert revision.id == "2024"


def test_select_revision_rejects_mismatching_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2024, period="0A", revision_id="not-a-real-id")


def test_select_revision_filters_by_on_date_outside_validity_window() -> None:
    """An on= date well before every revision's valid_from must surface
    as no-revision, not silently pick the closest revision."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="0A", on=date(1900, 1, 1))


def test_select_revision_raises_on_ambiguous_selection() -> None:
    """The dedup check fires when two revisions both match the
    requested year + period (+ optional on= window). Forge a twin
    revision so the candidates list grows past length 1."""
    modelo = _committed_modelo_100()
    original = modelo.revisions["2025"]
    twin = original.model_copy(update={"id": "2025-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(RegistrySnapshotError, match="ambiguous revision selection"):
        select_revision(mutated, filing_year=2025, period="0A")


def test_no_revision_raises_typed_subclass_with_structured_natural_key() -> None:
    """The no-candidate branch raises the typed subclass carrying the
    natural key as structured fields, not only inside the message.

    A consumer dispatches by ``except NoRevisionForPeriodError`` and reads
    ``modelo_id`` / ``filing_year`` / ``period`` / ``revision_id`` from the
    typed fields. The subclass is still catchable as the parent type, so
    every existing ``except RegistrySnapshotError`` site keeps working."""
    modelo = _committed_modelo_100()

    with pytest.raises(NoRevisionForPeriodError) as excinfo:
        select_revision(modelo, filing_year=2099, period="0A", revision_id="r9")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    assert err.filing_year == 2099
    assert err.period == "0A"
    assert err.revision_id == "r9"


def test_ambiguous_selection_raises_typed_subclass_with_candidate_ids() -> None:
    """The dedup branch raises the typed subclass carrying the candidate
    revision ids as a structured, sorted tuple — independent of the
    human-readable message wording (the whole point of the refactor).

    Designed so a rewording of the ``str()`` message would not change the
    assertion: the candidate ids are read from ``candidate_ids``, never
    parsed out of the message."""
    modelo = _committed_modelo_100()
    original = modelo.revisions["2025"]
    twin = original.model_copy(update={"id": "2025-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(AmbiguousRevisionSelectionError) as excinfo:
        select_revision(mutated, filing_year=2025, period="0A")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    # Sorted tuple of every matching revision id, read from the typed field.
    assert err.candidate_ids == ("2025", "2025-twin")


def test_revision_validation_reports_non_adjacent_overlap_before_runtime_ambiguity() -> None:
    """A long revision cannot hide its overlap behind a shorter middle revision."""

    modelo = _committed_modelo_100()
    template = modelo.revisions["2025"]
    revision_a = template.model_copy(
        update={"id": "window-a", "valid_from": date(2020, 1, 1), "valid_to": date(2030, 12, 31)},
    )
    revision_b = template.model_copy(
        update={"id": "window-b", "valid_from": date(2021, 1, 1), "valid_to": date(2022, 12, 31)},
    )
    revision_c = template.model_copy(
        update={"id": "window-c", "valid_from": date(2025, 1, 1), "valid_to": date(2026, 12, 31)},
    )
    mutated = modelo.model_copy(
        update={"revisions": {revision.id: revision for revision in (revision_a, revision_b, revision_c)}},
    )

    failures = validate_revision_windows(mutated)

    assert "modelo 100: revisions 'window-a' and 'window-c' overlap on period selector" in failures
    with pytest.raises(AmbiguousRevisionSelectionError) as excinfo:
        select_revision(mutated, filing_year=2025, period="0A", on=date(2025, 6, 1))
    assert excinfo.value.candidate_ids == ("window-a", "window-c")


def test_revision_validation_accepts_disjoint_windows_with_shared_period_selector() -> None:
    """Period-selector reuse remains valid when every date window is disjoint."""

    modelo = _committed_modelo_100()
    template = modelo.revisions["2025"]
    revisions = tuple(
        template.model_copy(update={"id": revision_id, "valid_from": valid_from, "valid_to": valid_to})
        for revision_id, valid_from, valid_to in (
            ("window-a", date(2020, 1, 1), date(2022, 12, 31)),
            ("window-b", date(2023, 1, 1), date(2024, 12, 31)),
            ("window-c", date(2025, 1, 1), date(2026, 12, 31)),
        )
    )
    mutated = modelo.model_copy(update={"revisions": {revision.id: revision for revision in revisions}})

    assert validate_revision_windows(mutated) == []


_CADRUMO_ROOT = Path(__file__).resolve().parents[4]

#: Production modules sanctioned to pass ``revision_id`` INTO ``select_revision``.
#: Both do so as a narrowing assertion alongside the law-determined
#: ``filing_year``/``period`` axes, never as the sole selector: ``_snapshot`` is
#: the resolver internal that funnels every snapshot, and ``work_addressing``
#: is the creation-time assertion path that accepts an explicit ``--revision``
#: only when it equals the law-determined pick (per the
#: aeat-registry-authority-flow discipline).
_SANCTIONED_REVISION_ID_SITES = frozenset(
    {
        "domain/calculations/registry/_snapshot.py",
        "application/modelo/work_addressing.py",
    },
)


def _select_revision_calls_in_tree(tree: ast.AST, relpath: str) -> list[tuple[str, int, frozenset[str]]]:
    """Extract every ``select_revision(...)`` call from one parsed module tree.

    Returns ``(relpath, line number, keyword-name set)`` per call. ``filing_year``
    and ``period`` are keyword-only parameters of ``select_revision``, so their
    presence in the keyword-name set is a faithful proxy for "the law-determined
    axes drove this selection". Shared by the production audit and its
    discrimination proof so both exercise the identical extraction logic.
    """
    calls: list[tuple[str, int, frozenset[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name != "select_revision":
            continue
        keywords = frozenset(kw.arg for kw in node.keywords if kw.arg is not None)
        calls.append((relpath, node.lineno, keywords))
    return calls


def _law_determined_violations(
    calls: list[tuple[str, int, frozenset[str]]],
) -> tuple[list[tuple[str, int, list[str]]], list[str]]:
    """Classify call sites: under-specified selections and unsanctioned injections.

    ``under_specified`` are calls missing a law-determined axis (``filing_year``
    or ``period``) — a revision-id-only or otherwise non-period-driven selection.
    ``unsanctioned`` are modules that pass ``revision_id`` into resolution outside
    the two sanctioned assertion sites. Both classes are the injection defect the
    aeat-registry-authority-flow rule bars.
    """
    under_specified = [(rel, line, sorted(kw)) for rel, line, kw in calls if not {"filing_year", "period"} <= kw]
    unsanctioned = sorted({rel for rel, _line, kw in calls if "revision_id" in kw} - _SANCTIONED_REVISION_ID_SITES)
    return under_specified, unsanctioned


def _production_select_revision_calls() -> list[tuple[str, int, frozenset[str]]]:
    """AST-collect every production ``select_revision(...)`` call site (tests excluded)."""
    calls: list[tuple[str, int, frozenset[str]]] = []
    for path in scan_directory(_CADRUMO_ROOT, pattern="*.py", recursive=True, prune_directories=("tests",)):
        if path.name == "conftest.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls.extend(_select_revision_calls_in_tree(tree, path.relative_to(_CADRUMO_ROOT).as_posix()))
    return calls


def test_every_production_select_revision_call_is_law_determined() -> None:
    """No production ``select_revision`` call selects by an injected revision id.

    ``select_revision`` funnels every snapshot resolution (see the module
    docstring). This AST audit proves that every production call drives the
    selection from the law-determined ``(filing_year, period)`` axes and that a
    stored/explicit ``revision_id`` is only ever passed as a NARROWING assertion
    alongside those axes, and only at the two sanctioned sites. A new call that
    omits the law-determined axes (a revision_id-only injection) or that feeds a
    ``revision_id`` into resolution from an unreviewed site fails here — the
    exact defect class the aeat-registry-authority-flow rule bars.
    """
    calls = _production_select_revision_calls()
    assert calls, (
        "AST audit found no production select_revision call sites; the gate would "
        "be vacuous — confirm the resolver name or path traversal did not drift"
    )

    under_specified, unsanctioned = _law_determined_violations(calls)
    assert not under_specified, (
        "select_revision call(s) omit the law-determined filing_year/period axes, so "
        f"selection is not period-driven (an injection risk): {under_specified}"
    )
    assert not unsanctioned, (
        "new production site(s) pass revision_id into select_revision resolution; prove they "
        "only assert-equal against the law-determined pick (never inject) and, if so, enroll "
        f"them in _SANCTIONED_REVISION_ID_SITES: {unsanctioned}"
    )


def test_law_determined_gate_catches_injected_revision_id_selection() -> None:
    """Discrimination proof: the audit FAILS on a deliberately-wrong injection.

    Feeds synthetic module sources through the SAME extraction and classification
    the production gate runs, proving the gate cannot silently pass green while the
    invariant is broken. A revision-id-only selection (no law-determined axes) is
    flagged as under-specified; a ``revision_id`` fed into resolution from an
    unsanctioned module is flagged as an unsanctioned injection; and the correct
    law-determined assertion shape passes clean.
    """
    rogue_rel = "application/modelo/_rogue_injection_path.py"

    # (a) revision_id-only selection: the law-determined axes are absent entirely.
    injected = ast.parse("select_revision(definition, revision_id=stored_unit.revision_id)")
    under, _unsanctioned = _law_determined_violations(_select_revision_calls_in_tree(injected, rogue_rel))
    assert under, "gate FAILED to flag a revision_id-only injection (missing law-determined axes)"

    # (b) revision_id passed into resolution from an unsanctioned module.
    rogue_site = ast.parse("select_revision(definition, filing_year=y, period=p, revision_id=stored_unit.revision_id)")
    _under, unsanctioned = _law_determined_violations(_select_revision_calls_in_tree(rogue_site, rogue_rel))
    assert unsanctioned == [rogue_rel], (
        f"gate FAILED to flag a revision_id injected from an unsanctioned site: {unsanctioned}"
    )

    # (c) the correct law-determined shape is NOT false-flagged.
    law_determined = ast.parse("select_revision(definition, filing_year=y, period=p)")
    under_ok, unsanctioned_ok = _law_determined_violations(
        _select_revision_calls_in_tree(law_determined, "application/modelo/_ok_path.py"),
    )
    assert not under_ok and not unsanctioned_ok, "gate false-flagged a correct law-determined call"
