"""End-to-end tests for the modelo external-filing amend path.

Every test wires the full set of catalogue repositories over a
fresh encrypted SQLite database and seeds a baseline filing record
that carries ``external_evidence`` — the gate the amend path
demands. The new revision lands as a complementaria amendment that
supersedes the baseline filing and emits a ``modelo.amended``
bucket event.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.application.modelo import (
    AmendmentEvidenceMissingError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    CalculationRevisionStateError,
    amend_modelo_revision,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_work_unit,
    mark_revision_verified_complete,
)
from aeat.core.config import Settings
from aeat.domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventType,
)
from aeat.domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from aeat.domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from aeat.domain.modelos._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingRecord,
    FilingRecordStatus,
    derive_filing_record_id,
)
from aeat.domain.modelos._filing_repository import (
    FilingRecordCatalogueRepository,
    upsert_filing_record,
)
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 15, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 1, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def repos(tmp_path):
    """Yield the five catalogue repositories over an encrypted SQLite db."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "modelo_amend_flow.db"
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


def _seed_work_unit(wu_repo):
    """Modelo 130 1T 2026 — registry-resolvable so the formula engine
    in ``calculate_modelo_revision`` has a snapshot to operate on."""

    return create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )


_DEFAULT_130_BINDING_VALUES = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
}


def _seed_external_baseline(repos_tuple, *, casilla_values):
    """Seed a CURRENT filing record carrying ``external_evidence`` plus
    its underlying calculation revision and work unit."""

    wu_repo, cr_repo, fr_repo, _, _ = repos_tuple
    work_unit = _seed_work_unit(wu_repo)

    inputs: dict[str, str] = {}
    overrides_map: dict[str, str] = {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot=inputs,
        binding_overrides=overrides_map,
        casilla_values=casilla_values,
    )
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_T1,
        filed_by="aeat-import",
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.FILED,
        inputs_snapshot=inputs,
        binding_overrides=overrides_map,
        casilla_values=casilla_values,
        created_at=_T1,
        updated_at=_T1,
        verified_at=_T1,
        verified_by="aeat-import",
        filed_at=_T1,
        filed_by="aeat-import",
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

    baseline_filing = FilingRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=_T1,
        filed_by="aeat-import",
        notes=None,
        aeat_accepted=True,
        status=FilingRecordStatus.CURRENT,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUST-2024-303-1T-ABC123",
            imported_at=_T1,
        ),
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), baseline_filing))

    return work_unit, revision, baseline_filing


def test_amend_refuses_without_external_evidence(repos) -> None:
    """A locally-filed return (no ``external_evidence``) cannot be amended."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
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
    locally_filed = file_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )
    assert locally_filed.external_evidence is None

    with pytest.raises(AmendmentEvidenceMissingError, match=r"external_evidence|imported|baseline"):
        amend_modelo_revision(
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={"01": Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )


def test_amend_refuses_when_baseline_already_superseded(repos) -> None:
    """A SUPERSEDED filing record cannot be amended."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(repos, casilla_values={"01": Decimal("1000")})
    fake_successor = "f" * 64
    fr_repo.save(
        upsert_filing_record(
            fr_repo.load(),
            baseline.model_copy(
                update={
                    "status": FilingRecordStatus.SUPERSEDED,
                    "superseded_at": _T3,
                    "superseded_by_filing_record_id": fake_successor,
                }
            ),
        )
    )

    with pytest.raises(AmendmentTargetStateError, match=r"status|CURRENT|superseded"):
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={"01": Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="late evidence",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )


def test_amend_creates_complementaria_filing_supersedes_baseline(repos) -> None:
    """Baseline carrying imported evidence → operator submits overrides
    → new revision (complementaria) + new filing record + supersedes
    baseline + emits ``modelo.amended`` event."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit, baseline_revision, baseline = _seed_external_baseline(
        repos,
        casilla_values={"01": Decimal("1000"), "02": Decimal("250")},
    )

    new_filing = amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={"01": Decimal("1100")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="under-reported turnover discovered in audit",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    assert new_filing.status is FilingRecordStatus.CURRENT
    assert new_filing.amends_filing_record_id == baseline.filing_record_id
    assert new_filing.external_evidence is None
    assert new_filing.filed_at == _T4
    assert new_filing.filed_by == "operator-A"

    refreshed_baseline = get_filing_record(baseline.filing_record_id, filing_repository=fr_repo)
    assert refreshed_baseline.status is FilingRecordStatus.SUPERSEDED
    assert refreshed_baseline.superseded_by_filing_record_id == new_filing.filing_record_id

    new_revision = get_calculation_revision(new_filing.calculation_revision_id, calculation_repository=cr_repo)
    assert new_revision.state is CalculationRevisionState.FILED
    assert new_revision.amendment_kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA
    assert new_revision.amends_filing_record_id == baseline.filing_record_id
    assert new_revision.amendment_reason == "under-reported turnover discovered in audit"
    assert new_revision.casilla_values["01"] == Decimal("1100")
    assert new_revision.casilla_values["02"] == baseline_revision.casilla_values["02"]

    refreshed_wu = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert refreshed_wu.filed_calculation_revision_id == new_filing.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == new_filing.filing_record_id

    catalogue = bv_repo.load()
    amended_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    assert len(amended_events) == 1
    event = amended_events[0]
    assert event.object_id == new_filing.filing_record_id
    assert event.payload["amends_filing_record_id"] == baseline.filing_record_id
    assert event.payload["amendment_kind"] == "complementaria"
    assert event.payload["override_count"] == "1"


def test_amend_refuses_no_op_overrides(repos) -> None:
    """Overrides identical to the baseline produce the same content-
    addressed revision id; the action refuses rather than persisting
    a no-op amendment."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(repos, casilla_values={"01": Decimal("1000")})

    with pytest.raises(CalculationRevisionStateError, match=r"already exists|no-op"):
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={"01": Decimal("1000")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="duplicate filing attempt",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )


def test_amend_refuses_overrides_with_casilla_ids_not_in_registry(repos) -> None:
    """An override targeting a casilla id the registry does not declare
    for the baseline's modelo / filing_year / period is refused. The
    corrected revision is the legal basis of the complementaria filing
    — fabricated casillas cannot be silently accepted."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(repos, casilla_values={"01": Decimal("1000")})

    with pytest.raises(AmendmentOverrideCasillaError, match=r"9999|not declared"):
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={"9999": Decimal("100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="fabricated casilla rejected",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
