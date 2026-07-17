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

from .._errors import (
    AmbiguousRevisionSelectionError,
    NoRevisionForPeriodError,
    RegistrySnapshotError,
)
from .._schema import ModeloDefinition
from .._temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_modelo_100() -> ModeloDefinition:
    modelo, _catalogues = _committed_modelo("100")
    return modelo


def test_select_revision_returns_the_matching_year_revision() -> None:
    modelo = _committed_modelo_100()

    revision = select_revision(modelo, filing_year=2025, period="0A")

    assert revision.id == "2025"


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


_CADRUMO_ROOT = Path(__file__).resolve().parents[4]

#: Production modules sanctioned to pass ``revision_id`` INTO ``select_revision``.
#: Both do so as a narrowing assertion alongside the law-determined
#: ``filing_year``/``period`` axes, never as the sole selector: ``_snapshot`` is
#: the resolver internal that funnels every snapshot, and ``_work_addressing``
#: is the creation-time assertion path that accepts an explicit ``--revision``
#: only when it equals the law-determined pick (per the
#: revision-resolution-is-law-determined discipline).
_SANCTIONED_REVISION_ID_SITES = frozenset(
    {
        "domain/calculations/registry/_snapshot.py",
        "application/modelo/_work_addressing.py",
    },
)


def _production_select_revision_calls() -> list[tuple[str, int, frozenset[str]]]:
    """AST-collect every production ``select_revision(...)`` call site.

    Returns ``(repo-relative posix path, line number, keyword-name set)`` for
    each call outside the test tree. ``filing_year`` and ``period`` are
    keyword-only parameters of ``select_revision``, so their presence in the
    keyword-name set is a faithful proxy for "the law-determined axes drove
    this selection".
    """
    calls: list[tuple[str, int, frozenset[str]]] = []
    for path in _CADRUMO_ROOT.rglob("*.py"):
        if "tests" in path.parts or path.name == "conftest.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name != "select_revision":
                continue
            keywords = frozenset(kw.arg for kw in node.keywords if kw.arg is not None)
            calls.append((path.relative_to(_CADRUMO_ROOT).as_posix(), node.lineno, keywords))
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
    exact defect class the revision-resolution-is-law-determined rule bars.
    """
    calls = _production_select_revision_calls()
    assert calls, (
        "AST audit found no production select_revision call sites; the gate would "
        "be vacuous — confirm the resolver name or path traversal did not drift"
    )

    under_specified = [(rel, line, sorted(kw)) for rel, line, kw in calls if not {"filing_year", "period"} <= kw]
    assert not under_specified, (
        "select_revision call(s) omit the law-determined filing_year/period axes, so "
        f"selection is not period-driven (an injection risk): {under_specified}"
    )

    revision_id_sites = {rel for rel, _line, kw in calls if "revision_id" in kw}
    unsanctioned = revision_id_sites - _SANCTIONED_REVISION_ID_SITES
    assert not unsanctioned, (
        "new production site(s) pass revision_id into select_revision resolution; prove they "
        "only assert-equal against the law-determined pick (never inject) and, if so, enroll "
        f"them in _SANCTIONED_REVISION_ID_SITES: {sorted(unsanctioned)}"
    )
