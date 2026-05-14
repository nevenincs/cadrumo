"""End-to-end tests for the external-filing import path.

The import path is the production source of ``FilingRecord``
records that carry ``external_evidence``. Operators (or import
adapters: justificante PDF reader, AEAT CSV register importer,
AEAT live capture) call ``import_external_filing_evidence`` with
the casilla values they read from the official receipt, plus a
reference id pointing at the evidence source. The amend path then
consumes these records as its baseline.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
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
    ExternalFilingImportError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    calculate_modelo_revision,
    create_work_unit,
    discard_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_work_unit,
    import_external_filing_evidence,
    mark_revision_verified_complete,
)
from aeat.core.config import Settings
from aeat.domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from aeat.domain.deadlines import AutonomoProfile, IVARegime
from aeat.domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
)
from aeat.domain.modelos._calculation_revision import (
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
)
from aeat.domain.modelos._filing_record import (
    ExternalEvidenceKind,
    FilingRecordStatus,
)
from aeat.domain.modelos._filing_repository import (
    FilingRecordCatalogueRepository,
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
_T5 = datetime(2026, 1, 16, 13, 0, 0, tzinfo=UTC)
_WORKFLOW_TODAY = date(2026, 4, 10)
_WORKFLOW_PROFILE = AutonomoProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)


@pytest.fixture
def repos(tmp_path):
    """Yield the five catalogue repositories over an encrypted SQLite db."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "modelo_import_flow.db"
    env_values = {
        "AEAT_DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "AEAT_AUTH_PROVIDER": "clave_movil",
        "AEAT_CLAVE_MOVIL_DNI_NIE": "12345678Z",
    }
    previous_env = {key: os.environ.get(key) for key in env_values}
    os.environ.update(env_values)
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
        for key, previous in previous_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        override_master_key_provider(None)


def _seed_work_unit(wu_repo):
    """Modelo 130 1T 2026 — registry-resolvable for the
    ``calculate_modelo_revision`` formula-engine path used by the
    locally-filed regression test."""

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


def test_import_persists_filing_with_external_evidence(repos) -> None:
    """The happy path: importer supplies casilla values + evidence
    reference. The action persists a FILED revision, a CURRENT
    filing record with ``external_evidence`` populated, advances
    work-unit pointers, and emits ``modelo.filing.imported``."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    filing = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1500"), "02": Decimal("300")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-2026-303-Q1-OPERATOR1",
        actor="aeat-import",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    assert filing.status is FilingRecordStatus.CURRENT
    assert filing.aeat_accepted is True
    assert filing.external_evidence is not None
    assert filing.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert filing.external_evidence.reference_id == "JUST-2026-303-Q1-OPERATOR1"
    assert filing.external_evidence.imported_at == _T1
    assert filing.amends_filing_record_id is None
    assert filing.filed_at == _T1

    revision = get_calculation_revision(filing.calculation_revision_id, calculation_repository=cr_repo)
    assert revision.state is CalculationRevisionState.FILED
    assert revision.casilla_values["01"] == Decimal("1500")
    assert revision.casilla_values["02"] == Decimal("300")
    assert revision.amendment_kind is None  # import is not an amendment

    refreshed_wu = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert refreshed_wu.filed_calculation_revision_id == filing.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == filing.filing_record_id

    catalogue = bv_repo.load()
    events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_IMPORTED,),
    )
    assert len(events) == 1
    event = events[0]
    assert event.object_type is BucketEventObjectType.FILING_RECORD
    assert event.object_id == filing.filing_record_id
    assert event.payload["evidence_kind"] == "aeat_justificante_pdf"
    assert event.payload["evidence_reference_id"] == "JUST-2026-303-Q1-OPERATOR1"
    assert event.payload["supersedes_filing_record_id"] == ""
    assert event.payload["casilla_count"] == "2"


def test_import_supersedes_prior_current_filing(repos) -> None:
    """A second import for the same (bucket, modelo, year, period)
    supersedes the prior current filing. The supersession metadata
    is captured; the new filing's bucket-event references the prior
    via ``supersedes_filing_record_id``."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1500")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-FIRST",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    second = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1600")},
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="CSV-SECOND",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    refreshed_first = get_filing_record(first.filing_record_id, filing_repository=fr_repo)
    assert refreshed_first.status is FilingRecordStatus.SUPERSEDED
    assert refreshed_first.superseded_by_filing_record_id == second.filing_record_id

    refreshed_first_revision = get_calculation_revision(first.calculation_revision_id, calculation_repository=cr_repo)
    assert refreshed_first_revision.state is CalculationRevisionState.FILED_SUPERSEDED

    assert second.status is FilingRecordStatus.CURRENT
    assert second.external_evidence is not None
    assert second.external_evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER

    catalogue = bv_repo.load()
    imports = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_IMPORTED,),
    )
    assert len(imports) == 2
    assert imports[0].payload["supersedes_filing_record_id"] == ""
    assert imports[1].payload["supersedes_filing_record_id"] == first.filing_record_id


def test_import_then_amend_unlocks_amendment_path(repos) -> None:
    """The import path produces a baseline the amend path accepts.
    This is the canonical production flow for correcting an
    externally-filed return: import official evidence, then amend
    locally with the corrected casilla values."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    imported = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1500"), "02": Decimal("300")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-BASELINE",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    assert imported.external_evidence is not None

    amended = amend_modelo_revision(
        from_filing_record_id=imported.filing_record_id,
        overrides={"01": Decimal("1650")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="under-reported revenue discovered in subsequent audit",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert amended.amends_filing_record_id == imported.filing_record_id
    refreshed_baseline = get_filing_record(imported.filing_record_id, filing_repository=fr_repo)
    assert refreshed_baseline.status is FilingRecordStatus.SUPERSEDED
    assert refreshed_baseline.superseded_by_filing_record_id == amended.filing_record_id

    # Chronological event chain: import → amend.
    catalogue = bv_repo.load()
    chain = tuple(e.event_type for e in catalogue.for_bucket(work_unit.bucket_id))
    assert chain == (
        BucketEventType.MODELO_FILING_IMPORTED,
        BucketEventType.MODELO_AMENDED,
    )


def test_import_refuses_casilla_ids_not_in_registry(repos) -> None:
    """The import path refuses casilla ids the registry does not
    declare for the work unit's modelo / filing_year / period.
    Imported baselines are the legal source of truth for amend
    paths — fabricated casilla ids cannot be silently accepted."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalFilingImportError, match=r"9999|not declared"):
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"9999": Decimal("100")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-FABRICATED",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_import_refuses_empty_casilla_values(repos) -> None:
    """The import path requires at least one casilla value — a
    zero-value mapping doesn't represent any real receipt."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalFilingImportError, match=r"empty|casilla"):
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-WHATEVER",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_import_refuses_empty_evidence_reference(repos) -> None:
    """The import path requires a non-empty evidence reference id —
    without it the baseline can't be traced back to the receipt."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalFilingImportError, match=r"evidence_reference_id|non-empty"):
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="   ",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_import_refuses_discarded_work_unit(repos) -> None:
    """A discarded work unit cannot accept new imports."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        clock=_T1,
    )

    with pytest.raises(WorkUnitMutationRefusedError, match=r"discard|state|DISCARDED"):
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-LATE",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
        )


def test_import_refuses_unknown_work_unit(repos) -> None:
    """A work_unit_id absent from the catalogue is rejected."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError):
        import_external_filing_evidence(
            work_unit_id="0" * 64,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-WHATEVER",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_amend_locally_filed_still_refused_after_import_path_exists(repos) -> None:
    """Adding the import path does NOT loosen the amend evidence
    gate — a locally-filed record still has no ``external_evidence``
    and the amend path still refuses it."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={"01": Decimal("1500")},
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
        workflow_profile=_WORKFLOW_PROFILE,
        workflow_today=_WORKFLOW_TODAY,
        clock=_T3,
    )
    assert locally_filed.external_evidence is None

    with pytest.raises(AmendmentEvidenceMissingError, match=r"external_evidence|imported|baseline"):
        amend_modelo_revision(
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={"01": Decimal("1700")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="needed to amend",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
