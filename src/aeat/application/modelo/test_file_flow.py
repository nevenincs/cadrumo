"""Integration tests for the modelo calculate / verify / file flow.

These tests exercise the full lifecycle:

* Two ``calculate`` invocations under the same work unit produce
  two distinct ``CalculationRevision`` records — the "toilet-break"
  scenario the operator described.
* ``mark_revision_verified_complete`` requires DRAFT state.
* ``file_modelo_revision`` requires VERIFIED_COMPLETE state.
* Filing advances the work unit's ``filed_calculation_revision_id``
  and ``current_filing_record_id`` pointers atomically.
* Re-filing a later verified revision supersedes the prior filing
  record and transitions the prior filed revision to
  ``FILED_SUPERSEDED`` without losing audit history.
* The filing-record catalogue exposes ``current_for(...)`` and
  ``history_for(...)`` queries that resolve the single canonical
  filed answer and the full audit chain respectively.

The tests inject purely in-memory fake repositories. No SQL
backend is required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aeat.application.modelo import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    FilingRecordNotFoundError,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_work_unit,
    list_calculation_revisions,
    list_filing_records,
    mark_revision_verified_complete,
)
from aeat.domain.modelos._calculation_revision import (
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from aeat.domain.modelos._filing_record import FilingRecordCatalogue, FilingRecordStatus
from aeat.domain.modelos._work_unit import WorkUnitCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 15, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 1, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC)
_T5 = datetime(2026, 1, 16, 13, 0, 0, tzinfo=UTC)


class _InMemoryWorkUnitRepository:
    def __init__(self) -> None:
        self._catalogue = WorkUnitCatalogue()

    def load(self) -> WorkUnitCatalogue:
        return self._catalogue

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        self._catalogue = catalogue


class _InMemoryCalculationRevisionRepository:
    def __init__(self) -> None:
        self._catalogue = CalculationRevisionCatalogue()

    def load(self) -> CalculationRevisionCatalogue:
        return self._catalogue

    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        self._catalogue = catalogue


class _InMemoryFilingRecordRepository:
    def __init__(self) -> None:
        self._catalogue = FilingRecordCatalogue()

    def load(self) -> FilingRecordCatalogue:
        return self._catalogue

    def save(self, catalogue: FilingRecordCatalogue) -> None:
        self._catalogue = catalogue


def _make_repos() -> tuple[
    _InMemoryWorkUnitRepository,
    _InMemoryCalculationRevisionRepository,
    _InMemoryFilingRecordRepository,
]:
    return (
        _InMemoryWorkUnitRepository(),
        _InMemoryCalculationRevisionRepository(),
        _InMemoryFilingRecordRepository(),
    )


def _seed_work_unit(
    wu_repo: _InMemoryWorkUnitRepository,
    *,
    bucket_id: str = "default",
    modelo: str = "303",
    filing_year: int = 2026,
    period: str = "Q1",
    revision_id: str = "2009-y-siguientes",
):
    return create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        repository=wu_repo,  # type: ignore[arg-type]
        clock=_T0,
    )


def test_two_calculates_under_one_work_unit_produce_two_revisions() -> None:
    """The toilet-break scenario. Operator calculates, walks away,
    comes back, calculates again with different inputs. Two
    ``CalculationRevision`` records exist; the work unit's
    ``current_calculation_revision_id`` advances to the second."""

    wu_repo, cr_repo, _ = _make_repos()
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T1,
    )

    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("2000"), "02": Decimal("500")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T2,
    )

    assert first.calculation_revision_id != second.calculation_revision_id

    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,  # type: ignore[arg-type]
    )
    assert len(revisions) == 2
    assert {r.calculation_revision_id for r in revisions} == {
        first.calculation_revision_id,
        second.calculation_revision_id,
    }
    assert all(r.state is CalculationRevisionState.DRAFT for r in revisions)

    # Current pointer follows most-recent calculate.
    refreshed_work_unit = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,  # type: ignore[arg-type]
    )
    assert refreshed_work_unit.current_calculation_revision_id == second.calculation_revision_id
    assert refreshed_work_unit.filed_calculation_revision_id is None
    assert refreshed_work_unit.current_filing_record_id is None


def test_calculate_is_idempotent_on_identical_inputs() -> None:
    """Re-running calculate with identical inputs / outputs returns
    the existing revision (content-addressed id collides) without
    creating a duplicate."""

    wu_repo, cr_repo, _ = _make_repos()
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T1,
    )
    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T2,
    )
    assert first.calculation_revision_id == second.calculation_revision_id
    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,  # type: ignore[arg-type]
    )
    assert len(revisions) == 1


def test_mark_verified_complete_requires_draft_state() -> None:
    """A revision in any state other than DRAFT cannot be marked
    verified-complete."""

    wu_repo, cr_repo, _ = _make_repos()
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T1,
    )
    verified = mark_revision_verified_complete(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T2,
    )
    assert verified.state is CalculationRevisionState.VERIFIED_COMPLETE

    # Second attempt against the now-verified revision must fail.
    with pytest.raises(CalculationRevisionStateError):
        mark_revision_verified_complete(
            revision.calculation_revision_id,
            actor="operator-A",
            calculation_repository=cr_repo,  # type: ignore[arg-type]
            clock=_T3,
        )


def test_file_requires_verified_complete_state() -> None:
    """A draft revision cannot be filed; only verified-complete
    revisions are eligible."""

    wu_repo, cr_repo, fr_repo = _make_repos()
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T1,
    )
    with pytest.raises(CalculationRevisionStateError):
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            work_unit_repository=wu_repo,  # type: ignore[arg-type]
            calculation_repository=cr_repo,  # type: ignore[arg-type]
            filing_repository=fr_repo,  # type: ignore[arg-type]
            clock=_T2,
        )


def test_file_creates_filing_record_and_advances_pointers() -> None:
    """The happy-path file flow: calculate → mark verified-complete
    → file. After file: a FilingRecord exists, the revision is in
    FILED state, the work unit's filed_calculation_revision_id and
    current_filing_record_id pointers point at the new IDs, and
    filing-record current_for(...) resolves to the new record."""

    wu_repo, cr_repo, fr_repo = _make_repos()
    work_unit = _seed_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T2,
    )
    filing = file_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        notes="Q1 IVA",
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        filing_repository=fr_repo,  # type: ignore[arg-type]
        clock=_T3,
    )

    assert filing.status is FilingRecordStatus.CURRENT
    assert filing.aeat_accepted is False
    assert filing.notes == "Q1 IVA"
    assert filing.filed_by == "operator-A"
    assert filing.calculation_revision_id == revision.calculation_revision_id

    refreshed_revision = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,  # type: ignore[arg-type]
    )
    assert refreshed_revision.state is CalculationRevisionState.FILED
    assert refreshed_revision.filed_at == _T3
    assert refreshed_revision.filed_by == "operator-A"

    refreshed_wu = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,  # type: ignore[arg-type]
    )
    assert refreshed_wu.filed_calculation_revision_id == revision.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == filing.filing_record_id

    # The filing-record catalogue's current_for query resolves to
    # the new record — this is the canonical "which revision is THE
    # Q1 filed answer?" lookup that downstream consumers
    # (aggregation, amendments) use.
    catalogue = fr_repo.load()
    current = catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    assert current is not None
    assert current.filing_record_id == filing.filing_record_id


def test_filing_record_supersession_preserves_audit_history() -> None:
    """Re-filing a later verified revision supersedes the prior
    filing. The prior filing record moves to SUPERSEDED with the
    supersession metadata captured; the prior calculation revision
    moves from FILED to FILED_SUPERSEDED. The new filing becomes
    CURRENT. ``history_for(...)`` returns both records in
    filed_at order."""

    wu_repo, cr_repo, fr_repo = _make_repos()
    work_unit = _seed_work_unit(wu_repo)

    # First filing: revision-1, filed at T3.
    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T2,
    )
    filing_one = file_modelo_revision(
        revision_one.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        filing_repository=fr_repo,  # type: ignore[arg-type]
        clock=_T3,
    )

    # Second filing: revision-2 with corrected inputs, filed at T5.
    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1200"), "02": Decimal("100")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T4,
    )
    mark_revision_verified_complete(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T4,
    )
    filing_two = file_modelo_revision(
        revision_two.calculation_revision_id,
        actor="operator-A",
        notes="corrected after audit",
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        filing_repository=fr_repo,  # type: ignore[arg-type]
        clock=_T5,
    )

    # New filing is current.
    assert filing_two.status is FilingRecordStatus.CURRENT
    refreshed_revision_two = get_calculation_revision(
        revision_two.calculation_revision_id,
        calculation_repository=cr_repo,  # type: ignore[arg-type]
    )
    assert refreshed_revision_two.state is CalculationRevisionState.FILED

    # Prior filing is superseded; prior revision moved to FILED_SUPERSEDED.
    refreshed_filing_one = get_filing_record(
        filing_one.filing_record_id,
        filing_repository=fr_repo,  # type: ignore[arg-type]
    )
    assert refreshed_filing_one.status is FilingRecordStatus.SUPERSEDED
    assert refreshed_filing_one.superseded_at == _T5
    assert refreshed_filing_one.superseded_by_filing_record_id == filing_two.filing_record_id

    refreshed_revision_one = get_calculation_revision(
        revision_one.calculation_revision_id,
        calculation_repository=cr_repo,  # type: ignore[arg-type]
    )
    assert refreshed_revision_one.state is CalculationRevisionState.FILED_SUPERSEDED
    assert refreshed_revision_one.superseded_at == _T5

    # current_for resolves to the new filing only.
    catalogue = fr_repo.load()
    current = catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    assert current is not None
    assert current.filing_record_id == filing_two.filing_record_id

    # history_for returns both records in filed_at order.
    history = catalogue.history_for(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    assert tuple(r.filing_record_id for r in history) == (
        filing_one.filing_record_id,
        filing_two.filing_record_id,
    )

    # Work-unit pointers point at the new filing.
    refreshed_wu = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,  # type: ignore[arg-type]
    )
    assert refreshed_wu.filed_calculation_revision_id == revision_two.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == filing_two.filing_record_id


def test_list_filing_records_excludes_superseded_by_default() -> None:
    """The default listing surfaces operator-visible state (current
    filings). Pass include_superseded=True to walk audit history."""

    wu_repo, cr_repo, fr_repo = _make_repos()
    work_unit = _seed_work_unit(wu_repo)

    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T2,
    )
    file_modelo_revision(
        revision_one.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        filing_repository=fr_repo,  # type: ignore[arg-type]
        clock=_T3,
    )

    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1200")},
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T4,
    )
    mark_revision_verified_complete(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        clock=_T4,
    )
    file_modelo_revision(
        revision_two.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,  # type: ignore[arg-type]
        calculation_repository=cr_repo,  # type: ignore[arg-type]
        filing_repository=fr_repo,  # type: ignore[arg-type]
        clock=_T5,
    )

    default_listing = list_filing_records(
        filing_repository=fr_repo,  # type: ignore[arg-type]
    )
    assert len(default_listing) == 1
    assert default_listing[0].status is FilingRecordStatus.CURRENT

    with_history = list_filing_records(
        include_superseded=True,
        filing_repository=fr_repo,  # type: ignore[arg-type]
    )
    assert len(with_history) == 2


def test_calculate_refused_on_discarded_work_unit() -> None:
    """A discarded work unit refuses further calculation. The
    operator must create a fresh work unit to continue."""

    from aeat.application.modelo import (
        WorkUnitMutationRefusedError,
        discard_work_unit,
    )

    wu_repo, cr_repo, _ = _make_repos()
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,  # type: ignore[arg-type]
        clock=_T1,
    )
    with pytest.raises(WorkUnitMutationRefusedError):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_values={"01": Decimal("1000")},
            work_unit_repository=wu_repo,  # type: ignore[arg-type]
            calculation_repository=cr_repo,  # type: ignore[arg-type]
            clock=_T2,
        )


def test_get_filing_record_raises_on_missing_id() -> None:
    _, _, fr_repo = _make_repos()
    with pytest.raises(FilingRecordNotFoundError):
        get_filing_record(
            "0" * 64,
            filing_repository=fr_repo,  # type: ignore[arg-type]
        )


def test_get_calculation_revision_raises_on_missing_id() -> None:
    _, cr_repo, _ = _make_repos()
    with pytest.raises(CalculationRevisionNotFoundError):
        get_calculation_revision(
            "0" * 64,
            calculation_repository=cr_repo,  # type: ignore[arg-type]
        )
