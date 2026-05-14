"""Tests for the per-work-unit history assembler."""

from __future__ import annotations

import re
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
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    assemble_work_unit_history,
    calculate_modelo_revision,
    create_work_unit,
    discard_work_unit,
    file_modelo_revision,
    import_external_filing_evidence,
    verify_modelo_revision,
)
from aeat.core.config import Settings
from aeat.core.errors import ErrorCategory, build_error_envelope, get_registered_error_code
from aeat.core.paths import PROJECT_ROOT
from aeat.domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
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
from aeat.domain.modelos._codes import ModeloCode
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
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from aeat.domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)
from aeat.domain.modelos._work_unit import WorkUnit, derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_census_foundation_callers_do_not_reintroduce_local_modelo_branches() -> None:
    scoped_files = (
        PROJECT_ROOT / "src" / "aeat" / "application" / "modelo" / "_actions.py",
        PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_modelo.py",
    )
    forbidden_patterns = (
        r"_CENSUS_MODEL",
        r"modelo(?:_code)?\s*={2}\s*[\"']03[67][\"']",
        r"\{[\"']036[\"']\s*,\s*[\"']037[\"']\}",
        r"frozenset\(\([\"']036[\"']\s*,\s*[\"']037[\"']\)\)",
    )
    offenders: list[str] = []
    for path in scoped_files:
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if re.search(pattern, text):
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: {pattern}")

    assert offenders == []


def test_work_unit_mutation_refusal_has_registered_error_code() -> None:
    error = WorkUnitMutationRefusedError("historical census metadata")
    code = get_registered_error_code(error)
    envelope = build_error_envelope(error)

    assert code.code == "ERROR_MODELO_WORK_UNIT_MUTATION_REFUSED"
    assert code.category is ErrorCategory.ERROR
    assert envelope.code == "ERROR_MODELO_WORK_UNIT_MUTATION_REFUSED"


def _seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    modelo: str,
    period: str,
    revision_id: str,
) -> WorkUnit:
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="default",
            modelo=modelo,
            filing_year=2025,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id="default",
        modelo=ModeloCode(modelo),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-2025-{period}",
        created_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    repository.save(upsert_work_unit(repository.load(), work_unit))
    return work_unit


@pytest.fixture
def repos(tmp_path: Path):
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "history.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        objects = SecureObjectRepository(engine=engine)
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            FilingRecordCatalogueRepository(objects=objects),
            VerificationReportCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )
    finally:
        engine.dispose()
        override_master_key_provider(None)


def test_history_for_missing_work_unit_raises(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError):
        assemble_work_unit_history(
            "no-such-work-unit",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
        )


def test_history_for_freshly_created_work_unit_is_empty(repos) -> None:
    """``create_work_unit`` does not emit a bucket event today, so the
    history of a freshly-created work unit is empty. This test pins
    that contract: the assembler returns an empty stream rather than
    fabricating a synthesized creation row."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )

    history = assemble_work_unit_history(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )

    assert history.bucket_id == "default"
    assert history.work_unit_id == work_unit.work_unit_id
    assert history.events == ()


def test_create_census_036_work_unit_routes_through_foundation_service(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="036",
        filing_year=2025,
        period="modificacion",
        revision_id="2025-02-03-y-siguientes",
        repository=wu_repo,
        clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )

    history = assemble_work_unit_history(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )

    assert str(work_unit.modelo) == "036"
    assert work_unit.period == "modificacion"
    assert history.events == ()


def test_census_036_imported_filing_surfaces_in_work_unit_history(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 12, 5, tzinfo=UTC)

    work_unit = create_work_unit(
        bucket_id="census-s1493-import",
        modelo="036",
        filing_year=2025,
        period="baja",
        revision_id="2025-02-03-y-siguientes",
        repository=wu_repo,
        clock=t0,
    )
    filing = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"decl.event-kind": Decimal("1")},
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="REG-036-BAJA",
        actor="aeat-import",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=t1,
    )
    history = assemble_work_unit_history(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )
    refreshed_work_unit = wu_repo.load().get(work_unit.work_unit_id)
    imported_revision = cr_repo.load().get(filing.calculation_revision_id)

    assert str(work_unit.modelo) == "036"
    assert work_unit.period == "baja"
    assert filing.status is FilingRecordStatus.CURRENT
    assert filing.aeat_accepted is True
    assert filing.external_evidence is not None
    assert filing.external_evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER
    assert filing.external_evidence.reference_id == "REG-036-BAJA"
    assert refreshed_work_unit is not None
    assert refreshed_work_unit.current_calculation_revision_id == filing.calculation_revision_id
    assert refreshed_work_unit.current_filing_record_id == filing.filing_record_id
    assert imported_revision is not None
    assert imported_revision.state is CalculationRevisionState.FILED
    assert [event.event_type for event in history.events] == [BucketEventType.MODELO_FILING_IMPORTED]
    assert {event.payload["modelo"] for event in history.events} == {"036"}
    assert {event.payload["filing_year"] for event in history.events} == {"2025"}
    assert {event.payload["period"] for event in history.events} == {"baja"}
    assert {event.payload["evidence_kind"] for event in history.events} == {"aeat_csv_register"}
    assert {event.payload["evidence_reference_id"] for event in history.events} == {"REG-036-BAJA"}


def test_create_census_036_work_unit_rejects_non_event_period(repos) -> None:
    wu_repo, *_ = repos

    with pytest.raises(WorkUnitMutationRefusedError, match="census event periods"):
        create_work_unit(
            bucket_id="default",
            modelo="036",
            filing_year=2025,
            period="1T",
            revision_id="2025-02-03-y-siguientes",
            repository=wu_repo,
            clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )

    assert tuple(wu_repo.load().values()) == ()


def test_create_census_037_work_unit_is_refused_as_historical_metadata(repos) -> None:
    wu_repo, *_ = repos

    with pytest.raises(WorkUnitMutationRefusedError, match="historical census metadata"):
        create_work_unit(
            bucket_id="default",
            modelo="037",
            filing_year=2025,
            period="alta",
            revision_id="historical",
            repository=wu_repo,
            clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )

    assert tuple(wu_repo.load().values()) == ()


def test_seeded_census_037_work_unit_cannot_reach_calculation_registry(repos) -> None:
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="037",
        period="alta",
        revision_id="historical",
    )

    with pytest.raises(WorkUnitMutationRefusedError, match="historical census metadata"):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator@example.test",
            casilla_inputs={},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )

    assert tuple(cr_repo.load().values()) == ()


def test_seeded_census_037_work_unit_cannot_import_external_filing(repos) -> None:
    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="037",
        period="alta",
        revision_id="historical",
    )

    with pytest.raises(WorkUnitMutationRefusedError, match="historical census metadata"):
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"decl.event-kind": Decimal("1")},
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="REG-037",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )

    assert tuple(cr_repo.load().values()) == ()
    assert tuple(fr_repo.load().values()) == ()


def test_seeded_census_037_work_unit_cannot_verify_revision(repos) -> None:
    wu_repo, cr_repo, _fr_repo, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="037",
        period="alta",
        revision_id="historical",
    )
    calculation_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={"decl.event-kind": Decimal("1")},
    )
    cr_repo.save(
        upsert_calculation_revision(
            cr_repo.load(),
            CalculationRevision(
                calculation_revision_id=calculation_id,
                work_unit_id=work_unit.work_unit_id,
                state=CalculationRevisionState.DRAFT,
                casilla_values={"decl.event-kind": Decimal("1")},
                created_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
            ),
        )
    )

    with pytest.raises(WorkUnitMutationRefusedError, match="historical census metadata"):
        verify_modelo_revision(
            calculation_id,
            actor="operator@example.test",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )

    assert tuple(vr_repo.load().values()) == ()


def test_seeded_census_037_work_unit_cannot_file_verified_revision(repos) -> None:
    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="037",
        period="alta",
        revision_id="historical",
    )
    calculation_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={"decl.event-kind": Decimal("1")},
    )
    cr_repo.save(
        upsert_calculation_revision(
            cr_repo.load(),
            CalculationRevision(
                calculation_revision_id=calculation_id,
                work_unit_id=work_unit.work_unit_id,
                state=CalculationRevisionState.VERIFIED_COMPLETE,
                casilla_values={"decl.event-kind": Decimal("1")},
                created_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
                verified_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
                verified_by="operator@example.test",
            ),
        )
    )

    with pytest.raises(WorkUnitMutationRefusedError, match="historical census metadata"):
        file_modelo_revision(
            calculation_id,
            actor="operator@example.test",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )

    assert tuple(fr_repo.load().values()) == ()


def test_seeded_census_037_work_unit_cannot_amend_external_baseline(repos) -> None:
    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="037",
        period="alta",
        revision_id="historical",
    )
    calculation_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={"decl.event-kind": Decimal("1")},
    )
    filed_at = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=calculation_id,
        filed_at=filed_at,
        filed_by="aeat-import",
    )
    cr_repo.save(
        upsert_calculation_revision(
            cr_repo.load(),
            CalculationRevision(
                calculation_revision_id=calculation_id,
                work_unit_id=work_unit.work_unit_id,
                state=CalculationRevisionState.FILED,
                casilla_values={"decl.event-kind": Decimal("1")},
                created_at=filed_at,
                updated_at=filed_at,
                verified_at=filed_at,
                verified_by="aeat-import",
                filed_at=filed_at,
                filed_by="aeat-import",
            ),
        )
    )
    fr_repo.save(
        upsert_filing_record(
            fr_repo.load(),
            FilingRecord(
                filing_record_id=filing_id,
                work_unit_id=work_unit.work_unit_id,
                calculation_revision_id=calculation_id,
                bucket_id=work_unit.bucket_id,
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period,
                filed_at=filed_at,
                filed_by="aeat-import",
                aeat_accepted=True,
                status=FilingRecordStatus.CURRENT,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                    reference_id="REG-037",
                    imported_at=filed_at,
                ),
            ),
        )
    )

    with pytest.raises(WorkUnitMutationRefusedError, match="historical census metadata"):
        amend_modelo_revision(
            from_filing_record_id=filing_id,
            overrides={},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="external correction",
            actor="operator@example.test",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=datetime(2026, 1, 15, 13, 0, tzinfo=UTC),
        )

    assert len(fr_repo.load().records) == 1


def test_history_records_discard_event(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=t0,
    )
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator@example.test",
        reason="superseded by a fresh draft",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t1,
    )

    history = assemble_work_unit_history(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )

    assert len(history.events) == 1
    event = history.events[0]
    assert event.object_type is BucketEventObjectType.WORK_UNIT
    assert event.object_id == work_unit.work_unit_id
    assert event.event_type is BucketEventType.MODELO_WORK_UNIT_DISCARDED
    assert event.occurred_at == t1
    assert event.actor == "operator@example.test"


def test_history_excludes_events_from_other_work_units(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)

    target = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=t0,
    )
    other = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="2T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=t0,
    )
    # Discard *only* the unrelated work unit so it emits an event.
    discard_work_unit(
        other.work_unit_id,
        actor="other-operator",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t1,
    )

    history = assemble_work_unit_history(
        target.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )

    # The target was never discarded -> the other unit's event must
    # not leak into its history.
    assert history.events == ()
