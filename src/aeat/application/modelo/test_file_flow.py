"""End-to-end tests for the modelo calculate / verify / file flow.

Every test in this module wires the full set of catalogue
repositories (work unit, calculation revision, filing record,
verification report, bucket-event history) over a fresh encrypted
SQLite database. No monkeypatches, no in-memory fakes, no stubs:
each ``save`` encrypts, each ``load`` decrypts, every domain write
also lands a bucket-scoped event row.

Coverage:

* Two ``calculate`` invocations under one work unit produce two
  distinct ``CalculationRevision`` records (the "toilet-break"
  scenario) and emit a ``modelo.calculation.created`` event each.
* ``mark_revision_verified_complete`` requires DRAFT state.
* ``verify_modelo_revision`` reads real registry truth and emits
  ``modelo.verification.passed`` / ``modelo.verification.refused``.
* ``file_modelo_revision`` requires VERIFIED_COMPLETE state and
  emits ``modelo.filed`` (plus ``modelo.filed_superseded`` when a
  prior filing exists).
* Filing advances the work unit's pointer fields atomically.
* Re-filing supersedes the prior filing record + revision without
  losing audit history.
* The filing-record catalogue ``current_for(...)`` /
  ``history_for(...)`` queries resolve the canonical answer and
  full audit chain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.application.modelo import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    FilingRecordNotFoundError,
    VerificationReportNotFoundError,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_verification_report,
    get_work_unit,
    list_calculation_revisions,
    list_filing_records,
    list_verification_reports,
    mark_revision_verified_complete,
    verify_modelo_revision,
)
from aeat.core.config import Settings
from aeat.domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from aeat.domain.calculations.registry import ValidatedRegistryAuthority
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._calculation_revision import CalculationRevisionState
from aeat.domain.modelos._filing_record import FilingRecordStatus
from aeat.domain.modelos._filing_repository import FilingRecordCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.modelos._verification_report import (
    VerificationCompletenessStatus,
    VerificationFindingKind,
    VerificationFindingSeverity,
)
from aeat.domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 15, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 1, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC)
_T5 = datetime(2026, 1, 16, 13, 0, 0, tzinfo=UTC)

_VERIFY_MODELO = "180"
_VERIFY_REVISION = "2023-y-siguientes"
_VERIFY_PERIOD = "0A"
_VERIFY_YEAR = 2024


def _registry_required_manual_casillas() -> tuple[str, ...]:
    """Return the required ``input_kind=manual`` casilla ids the verifier
    will demand for modelo 180 / 2024 / period 0A. Reads the real
    registry — no duplication of revision data in the test."""

    authority = ValidatedRegistryAuthority.load(Path("registry/aeat"), source_root=Path("."))
    snapshot = authority.snapshot(_VERIFY_MODELO, filing_year=_VERIFY_YEAR, period=_VERIFY_PERIOD)
    return tuple(str(c.id) for c in snapshot.revision.casillas if c.required and c.input_kind == "manual")


@pytest.fixture
def repos(tmp_path):
    """Yield the five catalogue repositories over an encrypted SQLite
    database. Tears down the master-key override on exit. Tuple shape:
    ``(work_unit, calculation_revision, filing_record,
    verification_report, bucket_event_history)``."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "modelo_flow.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        objects = SecureObjectRepository(engine=engine)
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        fr = FilingRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, fr, vr, bv
    finally:
        engine.dispose()
        override_master_key_provider(None)


def _seed_work_unit(
    wu_repo,
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
        repository=wu_repo,
        clock=_T0,
    )


def _seed_modelo_180_work_unit(wu_repo):
    return create_work_unit(
        bucket_id="default",
        modelo=_VERIFY_MODELO,
        filing_year=_VERIFY_YEAR,
        period=_VERIFY_PERIOD,
        revision_id=_VERIFY_REVISION,
        repository=wu_repo,
        clock=_T0,
    )


def test_two_calculates_under_one_work_unit_produce_two_revisions(repos) -> None:
    """The toilet-break scenario. Operator calculates, walks away,
    comes back, calculates again with different inputs. Two
    ``CalculationRevision`` records exist; the work unit's
    ``current_calculation_revision_id`` advances to the second."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("2000"), "02": Decimal("500")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert first.calculation_revision_id != second.calculation_revision_id

    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,
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
        repository=wu_repo,
    )
    assert refreshed_work_unit.current_calculation_revision_id == second.calculation_revision_id
    assert refreshed_work_unit.filed_calculation_revision_id is None
    assert refreshed_work_unit.current_filing_record_id is None


def test_calculate_is_idempotent_on_identical_inputs(repos) -> None:
    """Re-running calculate with identical inputs / outputs returns
    the existing revision (content-addressed id collides) without
    creating a duplicate."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    assert first.calculation_revision_id == second.calculation_revision_id
    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,
    )
    assert len(revisions) == 1


def test_mark_verified_complete_requires_draft_state(repos) -> None:
    """A revision in any state other than DRAFT cannot be marked
    verified-complete."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    verified = mark_revision_verified_complete(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    assert verified.state is CalculationRevisionState.VERIFIED_COMPLETE

    # Second attempt against the now-verified revision must fail.
    with pytest.raises(CalculationRevisionStateError, match=r"state|verified|already|complete"):
        mark_revision_verified_complete(
            revision.calculation_revision_id,
            actor="operator-A",
            calculation_repository=cr_repo,
            clock=_T3,
        )


def test_file_requires_verified_complete_state(repos) -> None:
    """A draft revision cannot be filed; only verified-complete
    revisions are eligible."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    with pytest.raises(CalculationRevisionStateError, match=r"state|verified|VERIFIED"):
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
        )


def test_file_creates_filing_record_and_advances_pointers(repos) -> None:
    """The happy-path file flow: calculate → mark verified-complete
    → file. After file: a FilingRecord exists, the revision is in
    FILED state, the work unit's filed_calculation_revision_id and
    current_filing_record_id pointers point at the new IDs, and
    filing-record current_for(...) resolves to the new record."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing = file_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        notes="Q1 IVA",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    assert filing.status is FilingRecordStatus.CURRENT
    assert filing.aeat_accepted is False
    assert filing.notes == "Q1 IVA"
    assert filing.filed_by == "operator-A"
    assert filing.calculation_revision_id == revision.calculation_revision_id

    refreshed_revision = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision.state is CalculationRevisionState.FILED
    assert refreshed_revision.filed_at == _T3
    assert refreshed_revision.filed_by == "operator-A"

    refreshed_wu = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,
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


def test_filing_record_supersession_preserves_audit_history(repos) -> None:
    """Re-filing a later verified revision supersedes the prior
    filing. The prior filing record moves to SUPERSEDED with the
    supersession metadata captured; the prior calculation revision
    moves from FILED to FILED_SUPERSEDED. The new filing becomes
    CURRENT. ``history_for(...)`` returns both records in
    filed_at order."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    # First filing: revision-1, filed at T3.
    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing_one = file_modelo_revision(
        revision_one.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    # Second filing: revision-2 with corrected inputs, filed at T5.
    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1200"), "02": Decimal("100")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    mark_revision_verified_complete(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T4,
    )
    filing_two = file_modelo_revision(
        revision_two.calculation_revision_id,
        actor="operator-A",
        notes="corrected after audit",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T5,
    )

    # New filing is current.
    assert filing_two.status is FilingRecordStatus.CURRENT
    refreshed_revision_two = get_calculation_revision(
        revision_two.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision_two.state is CalculationRevisionState.FILED

    # Prior filing is superseded; prior revision moved to FILED_SUPERSEDED.
    refreshed_filing_one = get_filing_record(
        filing_one.filing_record_id,
        filing_repository=fr_repo,
    )
    assert refreshed_filing_one.status is FilingRecordStatus.SUPERSEDED
    assert refreshed_filing_one.superseded_at == _T5
    assert refreshed_filing_one.superseded_by_filing_record_id == filing_two.filing_record_id

    refreshed_revision_one = get_calculation_revision(
        revision_one.calculation_revision_id,
        calculation_repository=cr_repo,
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
        repository=wu_repo,
    )
    assert refreshed_wu.filed_calculation_revision_id == revision_two.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == filing_two.filing_record_id


def test_list_filing_records_excludes_superseded_by_default(repos) -> None:
    """The default listing surfaces operator-visible state (current
    filings). Pass include_superseded=True to walk audit history."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    file_modelo_revision(
        revision_one.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"01": Decimal("1200")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    mark_revision_verified_complete(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T4,
    )
    file_modelo_revision(
        revision_two.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T5,
    )

    default_listing = list_filing_records(
        filing_repository=fr_repo,
    )
    assert len(default_listing) == 1
    assert default_listing[0].status is FilingRecordStatus.CURRENT

    with_history = list_filing_records(
        include_superseded=True,
        filing_repository=fr_repo,
    )
    assert len(with_history) == 2


def test_calculate_refused_on_discarded_work_unit(repos) -> None:
    """A discarded work unit refuses further calculation. The
    operator must create a fresh work unit to continue."""

    from aeat.application.modelo import (
        WorkUnitMutationRefusedError,
        discard_work_unit,
    )

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        clock=_T1,
    )
    with pytest.raises(WorkUnitMutationRefusedError, match=r"discard|state|DISCARDED|work_unit"):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_values={"01": Decimal("1000")},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
        )


def test_get_filing_record_raises_on_missing_id(repos) -> None:
    _, _, fr_repo, _, _ = repos
    with pytest.raises(FilingRecordNotFoundError, match=r"filing|record|not|found"):
        get_filing_record(
            "0" * 64,
            filing_repository=fr_repo,
        )


def test_get_calculation_revision_raises_on_missing_id(repos) -> None:
    _, cr_repo, _, _, _ = repos
    with pytest.raises(CalculationRevisionNotFoundError, match=r"calculation|revision|not|found"):
        get_calculation_revision(
            "0" * 64,
            calculation_repository=cr_repo,
        )


# ---------------------------------------------------------------------------
# verify_modelo_revision — real-registry, encrypted-SQL end-to-end coverage.
# Inputs are drawn from registry ground truth (modelo 180, revision
# ``2023-y-siguientes``, period ``0A``).
# ---------------------------------------------------------------------------


def test_verify_grants_when_all_required_casillas_present_real_registry(
    repos,
) -> None:
    """Real e2e: registry resolves modelo 180 (2024, 0A); every required
    manual casilla is supplied; the verifier persists a granted report
    in encrypted storage; the calculation revision transitions
    DRAFT → VERIFIED_COMPLETE. No mocks, no in-memory fakes — the
    SQL repository encrypts on save and decrypts on load."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    assert required, "registry must declare at least one required manual casilla"

    work_unit = _seed_modelo_180_work_unit(wu_repo)
    casilla_values = {cid: Decimal("1") for cid in required}
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values=casilla_values,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verified_complete is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    assert report.findings == ()
    assert set(report.resolved_casillas) == set(required)
    assert report.missing_required_casillas == ()

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.VERIFIED_COMPLETE
    assert refreshed.verified_at == _T2
    assert refreshed.verified_by == "operator-A"

    # Round-trip through encrypted storage.
    persisted = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert persisted.granted_verified_complete is True
    assert persisted.completeness_status is VerificationCompletenessStatus.COMPLETE


def test_verify_refuses_when_required_casilla_missing_real_registry(
    repos,
) -> None:
    """Real e2e: omit one required casilla; the verifier emits a
    BLOCKING ``MISSING_REQUIRED_CASILLA`` finding for it; the
    revision stays DRAFT; the refused report is still persisted so
    the audit trail records the refusal."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    assert len(required) >= 2

    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values=supplied,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verified_complete is False
    assert report.completeness_status is VerificationCompletenessStatus.INCOMPLETE
    assert any(
        f.kind is VerificationFindingKind.MISSING_REQUIRED_CASILLA
        and f.severity is VerificationFindingSeverity.BLOCKING
        and f.casilla_id == omitted
        for f in report.findings
    )
    assert omitted in report.missing_required_casillas

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.DRAFT

    persisted = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert persisted.granted_verified_complete is False


def test_verify_emits_blocking_rule_when_registry_unresolved_real_registry(
    repos,
) -> None:
    """Real e2e: a work unit anchored to a year that predates modelo
    180's earliest revision (``valid_from=2019``) cannot resolve a
    registry snapshot. The verifier surfaces a BLOCKING_RULE finding
    and refuses the transition. The revision stays DRAFT."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo=_VERIFY_MODELO,
        filing_year=2010,
        period=_VERIFY_PERIOD,
        revision_id=_VERIFY_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={"perc.base": Decimal("1")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verified_complete is False
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    assert any(f.kind is VerificationFindingKind.BLOCKING_RULE for f in report.findings)

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.DRAFT


def test_verify_rejects_non_draft_revision_real_registry(repos) -> None:
    """Real e2e: a verified-complete revision cannot be re-verified.
    The operator must produce a fresh draft (which lands as DRAFT)
    to verify again."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={cid: Decimal("1") for cid in required},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    with pytest.raises(CalculationRevisionStateError, match=r"state|verify|verified|already"):
        verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=_T3,
        )


def test_list_and_get_verification_reports_real_registry(repos) -> None:
    """Real e2e: reports persist through the encrypted catalogue and
    are indexable by id and by calculation_revision_id."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_values={cid: Decimal("1") for cid in required},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    listed = list_verification_reports(
        calculation_revision_id=revision.calculation_revision_id,
        verification_repository=vr_repo,
    )
    assert tuple(r.verification_report_id for r in listed) == (report.verification_report_id,)

    fetched = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert fetched.verification_report_id == report.verification_report_id

    with pytest.raises(VerificationReportNotFoundError, match=r"verification|report|not|found"):
        get_verification_report(
            "0" * 64,
            verification_repository=vr_repo,
        )


# ---------------------------------------------------------------------------
# bucket-event emission — modelo.calculation.created /
# modelo.verification.{passed,refused} / modelo.filed /
# modelo.filed_superseded.
#
# Every domain write that lands above must also append a row to the
# bucket-event-history catalogue. These tests exercise the encrypted
# round-trip on the bucket-event catalogue itself: emit, save, load,
# query.
# ---------------------------------------------------------------------------


def test_calculate_emits_modelo_calculation_created_event(repos) -> None:
    """calculate_modelo_revision appends a ``modelo.calculation.created``
    event with the new revision id as object_id and the work unit's
    (modelo, year, period) carried in the payload."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    catalogue = bv_repo.load()
    events = catalogue.for_bucket(work_unit.bucket_id)
    assert len(events) == 1
    event = events[0]
    assert event.event_type is BucketEventType.MODELO_CALCULATION_CREATED
    assert event.object_type is BucketEventObjectType.CALCULATION_REVISION
    assert event.object_id == revision.calculation_revision_id
    assert event.actor == "operator-A"
    assert event.occurred_at == _T1
    assert event.payload["work_unit_id"] == work_unit.work_unit_id
    assert event.payload["modelo"] == str(work_unit.modelo)
    assert event.payload["filing_year"] == str(work_unit.filing_year)
    assert event.payload["period"] == work_unit.period


def test_verify_emits_passed_event_on_success(repos) -> None:
    """verify_modelo_revision emits ``modelo.verification.passed``
    when the verifier grants verified-complete; the event id matches
    the persisted verification report."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_values={cid: Decimal("1") for cid in required},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    catalogue = bv_repo.load()
    verification_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(
            BucketEventType.MODELO_VERIFICATION_PASSED,
            BucketEventType.MODELO_VERIFICATION_REFUSED,
        ),
    )
    assert len(verification_events) == 1
    event = verification_events[0]
    assert event.event_type is BucketEventType.MODELO_VERIFICATION_PASSED
    assert event.object_type is BucketEventObjectType.VERIFICATION_REPORT
    assert event.object_id == report.verification_report_id
    assert event.payload["calculation_revision_id"] == revision.calculation_revision_id
    assert event.payload["completeness_status"] == "complete"


def test_verify_emits_refused_event_on_missing_casilla(repos) -> None:
    """verify_modelo_revision emits ``modelo.verification.refused``
    when a required casilla is missing; the calculation revision
    stays DRAFT and the refusal lands in the bucket event log."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_values=supplied,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    assert report.granted_verified_complete is False

    catalogue = bv_repo.load()
    refused = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_VERIFICATION_REFUSED,),
    )
    assert len(refused) == 1
    event = refused[0]
    assert event.event_type is BucketEventType.MODELO_VERIFICATION_REFUSED
    assert event.payload["completeness_status"] == "incomplete"
    assert int(event.payload["missing_required_count"]) >= 1
    assert omitted not in event.payload  # omitted casilla id stays in the report, not the event payload


def test_file_emits_modelo_filed_event(repos) -> None:
    """file_modelo_revision appends a ``modelo.filed`` event
    referencing the new filing record id and carrying the modelo /
    year / period plus the underlying revision id."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing = file_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    catalogue = bv_repo.load()
    filed_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )
    assert len(filed_events) == 1
    event = filed_events[0]
    assert event.object_id == filing.filing_record_id
    assert event.payload["calculation_revision_id"] == revision.calculation_revision_id
    assert event.payload["modelo"] == str(work_unit.modelo)
    # No prior filing was superseded — payload carries empty string.
    assert event.payload["supersedes_filing_record_id"] == ""


def test_file_supersession_emits_both_filed_and_superseded_events(repos) -> None:
    """A second filing supersedes the prior one. The bucket-event
    log carries one ``modelo.filed_superseded`` event for the prior
    record (object_id = prior filing record id) and one new
    ``modelo.filed`` event for the new record (with the prior id in
    the ``supersedes_filing_record_id`` payload key)."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_values={"01": Decimal("1000")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verified_complete(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing_one = file_modelo_revision(
        revision_one.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_values={"01": Decimal("1200"), "02": Decimal("100")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    mark_revision_verified_complete(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T4,
    )
    filing_two = file_modelo_revision(
        revision_two.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T5,
    )

    catalogue = bv_repo.load()
    superseded_events = catalogue.for_object(
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=filing_one.filing_record_id,
    )
    types = tuple(e.event_type for e in superseded_events)
    assert BucketEventType.MODELO_FILED in types
    assert BucketEventType.MODELO_FILED_SUPERSEDED in types

    # The new filing.filed event references the prior record id.
    new_filed_events = catalogue.for_object(
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=filing_two.filing_record_id,
    )
    assert len(new_filed_events) == 1
    assert new_filed_events[0].event_type is BucketEventType.MODELO_FILED
    assert new_filed_events[0].payload["supersedes_filing_record_id"] == filing_one.filing_record_id

    # Whole chain in chronological order for the bucket:
    # calc1, filed1, calc2, superseded1+filed2.
    all_events = catalogue.for_bucket(work_unit.bucket_id)
    type_chain = tuple(e.event_type for e in all_events)
    assert type_chain == (
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_FILED,
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_FILED_SUPERSEDED,
        BucketEventType.MODELO_FILED,
    )
