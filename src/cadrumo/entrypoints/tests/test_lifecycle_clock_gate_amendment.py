"""An amendment clock earlier than the baseline it supersedes is refused before anything persists."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.amendment_actions import amend_modelo_revision
from cadrumo.application.modelo.lifecycle_clock_gate import ModeloLifecycleClockPrecedesError
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventHistoryCatalogue
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from cadrumo.domain.modelos.filing_repository import upsert_filing_record
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition import build_amendment_action_ports, build_work_lifecycle_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "10000000-0000-4000-8000-000000000131"
_T0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
_INCOME: CasillaId = validated_casilla_id("01")
_EXPENSE: CasillaId = validated_casilla_id("02")
_FACTS = (
    UserProfileFact(path="identity.tax_id", value="X1234567L"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="amendment clock"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


@dataclass(frozen=True, slots=True)
class _Baseline:
    objects: SecureObjectRepository
    work_unit: WorkUnit
    record: ModeloRecord


@dataclass(frozen=True, slots=True)
class _Catalogues:
    """Every catalogue an amendment writes, each read back through its real repository loader."""

    revisions: CalculationRevisionCatalogue
    work_units: WorkUnitCatalogue
    records: ModeloRecordCatalogue
    events: BucketEventHistoryCatalogue


def _seed_confirmed_baseline(objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation) -> _Baseline:
    """Seed Modelo 130 1T 2026 created at ``_T0`` with an AEAT-confirmed filing at ``_T1``."""
    work_unit = create_work_unit(
        ports=build_work_lifecycle_ports(bucket_id=_BUCKET_ID),
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        clock=_T0,
        operation=operation,
    )
    casilla_values = {_INCOME: Decimal("1000"), _EXPENSE: Decimal("250")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_T1,
        updated_at=_T1,
        verified_at=_T1,
        verified_by="aeat-import",
        filed_at=_T1,
        filed_by="aeat-import",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), revision))
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit.work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="aeat-import",
        ),
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=_T1,
        filed_by="aeat-import",
        notes=None,
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUST2026130SYN001",
            imported_at=_T1,
        ),
    )
    filing_repository = ModeloRecordCatalogueRepository(objects=objects)
    filing_repository.save(upsert_filing_record(filing_repository.load(), record))
    return _Baseline(objects=objects, work_unit=work_unit, record=record)


@contextmanager
def _baseline(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Iterator[_Baseline]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="amendment clock") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_test_profile_record(
            create_user_profile_record(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=_FACTS,
                created_at=_T0,
                updated_at=_T0,
                context=profile_creation_context_for_test(),
            ),
        )
        yield _seed_confirmed_baseline(objects, operation=operation)


def _reload(baseline: _Baseline) -> _Catalogues:
    """Load every catalogue from storage; a record its own loader rejects raises here."""
    return _Catalogues(
        revisions=CalculationRevisionCatalogueRepository(objects=baseline.objects).load(),
        work_units=WorkUnitCatalogueRepository(objects=baseline.objects).load(),
        records=ModeloRecordCatalogueRepository(objects=baseline.objects).load(),
        events=BucketEventHistoryRepository(objects=baseline.objects).load(),
    )


def _amend(baseline: _Baseline, *, clock: datetime) -> ModeloRecord:
    with bundled_indexed_authority().operation() as operation:
        return amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_BUCKET_ID, operation=operation),
            from_filing_record_id=baseline.record.filing_record_id,
            overrides={_INCOME: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="synthetic under-reported turnover",
            actor="operator-A",
            clock=clock,
        )


def test_an_amend_clock_before_the_baseline_was_filed_is_refused_and_persists_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Superseding the baseline would otherwise save its ``superseded_at`` before its ``filed_at``."""
    early = _T1 - timedelta(microseconds=1)
    with _baseline(tmp_path, operation=operation) as baseline:
        before = _reload(baseline)

        with pytest.raises(ModeloLifecycleClockPrecedesError) as exc_info:
            _amend(baseline, clock=early)

        after = _reload(baseline)

    error = exc_info.value
    assert get_registered_error_code(error).code == "REFUSED_MODELO_LIFECYCLE_CLOCK_PRECEDES"
    context = error.context
    assert context is not None
    assert context["operation"] == "amend"
    assert context["subject"] == "filing_record.filed_at"
    assert context["record_id"] == baseline.record.filing_record_id
    assert after.revisions == before.revisions
    assert after.records == before.records
    assert after.work_units == before.work_units
    assert after.events == before.events
    stored = after.records.get(baseline.record.filing_record_id)
    assert stored is not None
    assert stored.status is ModeloRecordStatus.VIGENTE


def test_an_amend_clock_at_the_baseline_filing_persists_reloadable_catalogues(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The boundary clock is accepted and every catalogue the amendment writes reloads."""
    with _baseline(tmp_path, operation=operation) as baseline:
        new_filing = _amend(baseline, clock=_T1)

        reloaded = _reload(baseline)

    superseded = reloaded.records.get(baseline.record.filing_record_id)
    assert superseded is not None
    assert superseded.status is ModeloRecordStatus.SUPERSEDIDO
    assert superseded.superseded_at == _T1
    assert reloaded.records.get(new_filing.filing_record_id) is not None
    amendment = reloaded.revisions.get(new_filing.calculation_revision_id)
    assert amendment is not None
    assert amendment.state is CalculationRevisionState.PRESENTADO
    work_unit = reloaded.work_units.get(baseline.work_unit.work_unit_id)
    assert work_unit is not None
    assert work_unit.current_filing_record_id == new_filing.filing_record_id
    assert work_unit.updated_at == _T1
