"""A verify or file clock earlier than the records it rewrites is refused before anything persists."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.lifecycle_clock_gate import ModeloLifecycleClockPrecedesError
from cadrumo.application.modelo.verification_actions import verify_modelo_revision
from cadrumo.application.modelo.work_lifecycle import create_work_unit, discard_work_unit, rename_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventHistoryCatalogue
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from cadrumo.domain.modelos.filing_record import ModeloRecordCatalogue
from cadrumo.domain.modelos.verification_report import VerificationReport, VerificationReportCatalogue
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports, build_filing_action_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000124"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_Q2_2025 = Period.from_year_and_code(2025, "2T")


@dataclass(frozen=True, slots=True)
class _Bucket:
    objects: SecureObjectRepository
    work_unit: WorkUnit


@dataclass(frozen=True, slots=True)
class _Catalogues:
    """Every catalogue verify and file write, each read back through its real repository loader."""

    revisions: CalculationRevisionCatalogue
    reports: VerificationReportCatalogue
    work_units: WorkUnitCatalogue
    records: ModeloRecordCatalogue
    events: BucketEventHistoryCatalogue


def _seed_ready_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="capital income payer"),
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
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=profile_creation_context_for_test(),
        ),
    )


@contextmanager
def _bucket(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Iterator[_Bucket]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="lifecycle clock") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(objects)
        snapshot = published_authority_operation().snapshot("123", filing_year=2025, period="2T")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="123",
            filing_year=2025,
            period=_Q2_2025,
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=_T0,
            operation=operation,
        )
        yield _Bucket(objects=objects, work_unit=work_unit)


def _calculate(bucket: _Bucket) -> CalculationRevisionId:
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=bucket.objects),
        invoice_repository=InvoiceCatalogueRepository(objects=bucket.objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects),
        work_unit_repository=WorkUnitCatalogueRepository(objects=bucket.objects),
    ) as ports:
        result = calculate_modelo_work_revision(
            work_unit_id=bucket.work_unit.work_unit_id,
            actor="test",
            inputs=WorkCalculateInputBundle.build(
                casilla_inputs={},
                binding_values={},
                enum_binding_values={},
                relation_values={},
                detail_rows=(),
                borrador_snapshot_id=None,
            ),
            ports=ports,
        )
    return result.revision.calculation_revision_id


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime("GENERAL"),
        activity_start_date=date(2020, 1, 1),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _verify(
    revision_id: CalculationRevisionId, *, clock: datetime, operation: PinnedAuthorityOperation
) -> VerificationReport:
    return verify_modelo_revision(
        revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        operator_scope_ports=build_operator_scope_ports(),
        actor="test",
        workflow_profile=_workflow_profile(),
        verification_repositories=build_test_verification_repository_bundle(),
        clock=clock,
        operation=operation,
    )


def _file(revision_id: CalculationRevisionId, *, clock: datetime, operation: PinnedAuthorityOperation) -> None:
    file_modelo_revision(
        revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        operator_scope_ports=build_operator_scope_ports(),
        ports=build_filing_action_ports(bucket_id=_BUCKET_ID),
        actor="test",
        workflow_profile=_workflow_profile(),
        clock=clock,
        operation=operation,
    )


def _reload(bucket: _Bucket) -> _Catalogues:
    """Load every catalogue from storage; a record its own loader rejects raises here."""
    return _Catalogues(
        revisions=CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load(),
        reports=VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load(),
        work_units=WorkUnitCatalogueRepository(objects=bucket.objects).load(),
        records=ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load(),
        events=BucketEventHistoryRepository(objects=bucket.objects).load(),
    )


def _revision_created_at(bucket: _Bucket, revision_id: CalculationRevisionId) -> datetime:
    revision = _reload(bucket).revisions.get(revision_id)
    assert revision is not None
    return revision.created_at


def _assert_clock_refusal(
    error: ModeloLifecycleClockPrecedesError,
    *,
    operation: str,
    clock: datetime,
    subject: str = "calculation_revision.created_at",
) -> None:
    assert get_registered_error_code(error).code == "REFUSED_MODELO_LIFECYCLE_CLOCK_PRECEDES"
    context = error.context
    assert context is not None
    assert context["operation"] == operation
    assert context["clock"] == clock.isoformat()
    assert context["subject"] == subject


def test_a_verify_clock_before_the_revision_was_created_is_refused_and_persists_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The draft would otherwise be granted and saved with ``updated_at`` before ``created_at``."""
    with _bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate(bucket)
        before = _reload(bucket)
        early = _revision_created_at(bucket, revision_id) - timedelta(microseconds=1)

        with pytest.raises(ModeloLifecycleClockPrecedesError) as exc_info:
            _verify(revision_id, clock=early, operation=operation)

        after = _reload(bucket)

    _assert_clock_refusal(exc_info.value, operation="verify", clock=early)
    revision = after.revisions.get(revision_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR
    assert revision.verified_at is None
    assert after.revisions == before.revisions
    assert dict(after.reports.reports) == {}
    assert after.work_units == before.work_units
    assert after.events == before.events


@pytest.mark.parametrize(
    "offset",
    [timedelta(0), timedelta(microseconds=1), timedelta(days=30)],
    ids=["at-created-at", "one-microsecond-later", "thirty-days-later"],
)
def test_every_catalogue_a_granted_verify_writes_reloads_through_its_loader(
    tmp_path: Path, offset: timedelta, *, operation: PinnedAuthorityOperation
) -> None:
    """A clock at or after ``created_at`` persists records that every repository loader accepts."""
    with _bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate(bucket)
        clock = _revision_created_at(bucket, revision_id) + offset

        report = _verify(revision_id, clock=clock, operation=operation)

        reloaded = _reload(bucket)

    assert report.granted_verificado_completo is True
    revision = reloaded.revisions.get(revision_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert revision.verified_at == clock
    assert revision.updated_at == clock
    assert revision.updated_at >= revision.created_at
    assert set(reloaded.reports.reports) == {report.verification_report_id}
    assert reloaded.reports.reports[report.verification_report_id].run_at == clock
    work_unit = reloaded.work_units.get(bucket.work_unit.work_unit_id)
    assert work_unit is not None
    assert work_unit.updated_at >= work_unit.created_at


def test_a_file_clock_before_the_revision_was_created_is_refused_and_persists_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A verified revision is not filed under a clock that would stamp it before its creation."""
    with _bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate(bucket)
        created_at = _revision_created_at(bucket, revision_id)
        _verify(revision_id, clock=created_at, operation=operation)
        before = _reload(bucket)
        early = created_at - timedelta(microseconds=1)

        with pytest.raises(ModeloLifecycleClockPrecedesError) as exc_info:
            _file(revision_id, clock=early, operation=operation)

        after = _reload(bucket)

    _assert_clock_refusal(exc_info.value, operation="file", clock=early)
    revision = after.revisions.get(revision_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert revision.filed_at is None
    assert after.revisions == before.revisions
    assert dict(after.records.records) == {}
    assert after.work_units == before.work_units
    assert after.events == before.events


def _lifecycle_ports(bucket: _Bucket) -> WorkLifecyclePorts:
    return WorkLifecyclePorts(
        work_unit_repository=WorkUnitCatalogueRepository(objects=bucket.objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=bucket.objects),
    )


def _calculate_at(bucket: _Bucket, *, clock: datetime, operation: PinnedAuthorityOperation) -> CalculationRevisionId:
    revision = calculate_modelo_revision(
        bucket.work_unit.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
        actor="test",
        casilla_inputs={},
        clock=clock,
    )
    return revision.calculation_revision_id


def test_a_calculate_clock_before_the_work_unit_was_created_is_refused_and_persists_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The advanced current pointer would otherwise stamp the work unit before its creation."""
    early = _T0 - timedelta(microseconds=1)
    with _bucket(tmp_path, operation=operation) as bucket:
        before = _reload(bucket)

        with pytest.raises(ModeloLifecycleClockPrecedesError) as exc_info:
            _calculate_at(bucket, clock=early, operation=operation)

        after = _reload(bucket)

    _assert_clock_refusal(exc_info.value, operation="calculate", clock=early, subject="work_unit.created_at")
    assert dict(after.revisions.revisions) == {}
    assert after.work_units == before.work_units
    assert after.events == before.events


def test_a_calculate_clock_at_work_unit_creation_persists_reloadable_catalogues(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The boundary clock is accepted and the pointer advance reloads."""
    with _bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate_at(bucket, clock=_T0, operation=operation)

        reloaded = _reload(bucket)

    revision = reloaded.revisions.get(revision_id)
    assert revision is not None
    assert revision.created_at == _T0
    work_unit = reloaded.work_units.get(bucket.work_unit.work_unit_id)
    assert work_unit is not None
    assert work_unit.current_calculation_revision_id == revision_id
    assert work_unit.updated_at == _T0


def test_a_rename_clock_before_the_work_unit_was_created_is_refused_and_persists_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A rename would otherwise save ``updated_at`` before ``created_at``."""
    early = _T0 - timedelta(microseconds=1)
    with _bucket(tmp_path, operation=operation) as bucket:
        before = _reload(bucket)

        with pytest.raises(ModeloLifecycleClockPrecedesError) as exc_info:
            rename_work_unit(
                bucket.work_unit.work_unit_id, "renamed", actor="test", ports=_lifecycle_ports(bucket), clock=early
            )

        after = _reload(bucket)

    _assert_clock_refusal(exc_info.value, operation="rename", clock=early, subject="work_unit.created_at")
    assert after.work_units == before.work_units
    assert after.events == before.events


def test_a_rename_clock_at_work_unit_creation_persists_a_reloadable_catalogue(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The boundary clock is accepted and the renamed unit reloads."""
    with _bucket(tmp_path, operation=operation) as bucket:
        rename_work_unit(
            bucket.work_unit.work_unit_id, "renamed", actor="test", ports=_lifecycle_ports(bucket), clock=_T0
        )

        reloaded = _reload(bucket)

    work_unit = reloaded.work_units.get(bucket.work_unit.work_unit_id)
    assert work_unit is not None
    assert work_unit.name == "renamed"
    assert work_unit.updated_at == _T0


def test_a_discard_clock_before_the_work_unit_was_created_is_refused_and_persists_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A discard would otherwise save ``discarded_at`` and ``updated_at`` before ``created_at``."""
    early = _T0 - timedelta(microseconds=1)
    with _bucket(tmp_path, operation=operation) as bucket:
        before = _reload(bucket)

        with pytest.raises(ModeloLifecycleClockPrecedesError) as exc_info:
            discard_work_unit(bucket.work_unit.work_unit_id, actor="test", ports=_lifecycle_ports(bucket), clock=early)

        after = _reload(bucket)

    _assert_clock_refusal(exc_info.value, operation="discard", clock=early, subject="work_unit.created_at")
    work_unit = after.work_units.get(bucket.work_unit.work_unit_id)
    assert work_unit is not None
    assert work_unit.state is WorkUnitState.BORRADOR
    assert after.work_units == before.work_units
    assert after.events == before.events


def test_a_discard_clock_at_work_unit_creation_persists_a_reloadable_catalogue(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The boundary clock is accepted and the discarded unit reloads."""
    with _bucket(tmp_path, operation=operation) as bucket:
        discard_work_unit(bucket.work_unit.work_unit_id, actor="test", ports=_lifecycle_ports(bucket), clock=_T0)

        reloaded = _reload(bucket)

    work_unit = reloaded.work_units.get(bucket.work_unit.work_unit_id)
    assert work_unit is not None
    assert work_unit.state is WorkUnitState.DESCARTADO
    assert work_unit.discarded_at == _T0
