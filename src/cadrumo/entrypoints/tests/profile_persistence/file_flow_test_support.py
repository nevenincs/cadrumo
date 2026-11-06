"""Shared support for Modelo file-flow integration tests."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from cadrumo.adapters.persistence.profile.actividad_asset import ActividadAssetHistoryRepository
from cadrumo.adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.calculation_revision_override_migration import (
    migrate_stored_relation_overrides_to_binding_ids,
)
from cadrumo.adapters.persistence.profile.catalogue_reads import (
    InvoiceCatalogueReadAdapter,
    TransactionCatalogueReadAdapter,
)
from cadrumo.adapters.persistence.profile.credit_resolution_records import CreditResolutionRepositoryAdapter
from cadrumo.adapters.persistence.profile.foreign_assets import ForeignAssetRegisterRepository
from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.profile.invoice_source_resolver import InvoiceCatalogueSourceResolverAdapter
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.profile_path_values import ProfilePathValuesPersistenceAdapter
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_soportada_records import (
    RetencionSoportadaAbsenceRepositoryAdapter,
    RetencionSoportadaRecordRepositoryAdapter,
)
from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import (
    SEED_CLOCK,
    seed_clean_cross_period_sources,
)
from cadrumo.adapters.persistence.profile.tests.m130_source_support import (
    seed_m130_expense_transaction,
    seed_m130_income_transaction,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.profile.usage_ratios import load_usage_ratios
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    open_test_profile_session,
    seed_test_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.aggregation.percepciones_observations_repository import PercepcionObservationPorts
from cadrumo.application.aggregation.retencion_observations_repository import RetencionObservationPorts
from cadrumo.application.aggregation.retencion_soportada_repository import RetencionSoportadaPorts
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.application.invoices.source_resolver_ports import InvoiceSourceResolverPorts
from cadrumo.application.live.borrador_100 import Borrador100SnapshotRepository
from cadrumo.application.modelo.calculation_action_ports import CalculationActionPorts
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.filing_actions import (
    file_modelo_revision,
)
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import (
    create_work_unit,
)
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.modelo.workflow_gate import build_revision_workflow_engine, workflow_period_for_work_unit
from cadrumo.application.user_profile.profile_read_ports import ProfileReadPorts
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.application.workflow.engine import WorkflowEngine
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.config import Settings
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventObjectType as BucketEventObjectType
from cadrumo.domain.buckets.event import BucketEventType as BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from cadrumo.domain.deadlines.models import TaxpayerProfile
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.filing_record import ModeloRecord
from cadrumo.domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.usage_ratios.model import UsageRatioProfile
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_ports import build_borrador_100_snapshot_repository
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports, build_filing_action_ports
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from .secure_store_baseline import (
    SeededDurableProfile,
    provision_seeded_profile,
    reopened_seeded_profile,
)
from .verification_substance_support import workflow_profile as plain_workflow_profile

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _RelationOverrideMigration:
    """Adapt the persisted relation-override migration to its application port."""

    def migrate(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        *,
        operation: PinnedAuthorityOperation,
    ) -> None:
        migrate_stored_relation_overrides_to_binding_ids(repository, operation=operation)


@contextmanager
def calculation_ports_for_test(
    *,
    bucket_id: str,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
) -> Generator[CalculationActionPorts]:
    """Yield calculation ports for one bucket while retaining test repositories.

    The authority operation owns every capability in the yielded bundle.  The
    repository overrides are resolved before dependent lifecycle and invoice
    read/source ports are composed, so a test's injected repository remains the
    implementation used by every coupled path.
    """
    normalized_bucket_id = bucket_id.strip()
    with bundled_indexed_authority().operation() as operation:
        objects = secure_object_repository_for_bucket(normalized_bucket_id)

        def usage_ratio_profile_loader(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
            return load_usage_ratios(bucket_id=bucket_id, operation=operation, objects=objects)

        resolved_work_unit_repository = (
            work_unit_repository
            if work_unit_repository is not None
            else WorkUnitCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
        )
        resolved_calculation_repository = (
            calculation_repository
            if calculation_repository is not None
            else CalculationRevisionCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
        )
        resolved_filing_repository = (
            filing_repository
            if filing_repository is not None
            else ModeloRecordCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
        )
        resolved_bucket_event_repository = (
            bucket_event_repository
            if bucket_event_repository is not None
            else BucketEventHistoryRepository(objects=objects)
        )
        resolved_transaction_repository = (
            transaction_repository
            if transaction_repository is not None
            else TransactionCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
        )
        resolved_invoice_repository = (
            invoice_repository
            if invoice_repository is not None
            else InvoiceCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
        )
        resolved_iva_compensation_decision_repository = (
            iva_compensation_decision_repository
            if iva_compensation_decision_repository is not None
            else IvaWalletDecisionRepository(objects=objects)
        )
        profile_repository = ProfileRecordRepository.for_current_session(
            normalized_bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
        profile_path_values = ProfilePathValuesPersistenceAdapter(repository=profile_repository)
        yield CalculationActionPorts(
            operation=operation,
            work_unit_repository=resolved_work_unit_repository,
            work_lifecycle_ports=WorkLifecyclePorts(
                work_unit_repository=resolved_work_unit_repository,
                bucket_event_repository=resolved_bucket_event_repository,
            ),
            calculation_repository=resolved_calculation_repository,
            verification_repository=VerificationReportCatalogueRepository(
                bucket_id=normalized_bucket_id, objects=objects
            ),
            bucket_event_repository=resolved_bucket_event_repository,
            transaction_repository=resolved_transaction_repository,
            activity_asset_history_repository=ActividadAssetHistoryRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            usage_ratio_profile_loader=usage_ratio_profile_loader,
            profile_read_ports=ProfileReadPorts(path_values=profile_path_values),
            invoice_repository=resolved_invoice_repository,
            invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
                invoice_reader=InvoiceCatalogueReadAdapter(repository=resolved_invoice_repository),
                transaction_reader=TransactionCatalogueReadAdapter(repository=resolved_transaction_repository),
            ),
            filing_repository=resolved_filing_repository,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            bienes_inversion_repository=BienesInversionIvaRegisterRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            foreign_asset_register_repository=ForeignAssetRegisterRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            inventory_repository=InventoryLedgerRepository(objects=objects),
            observation_repository=CalculationObservationRepository(objects=objects),
            invoice_source_ports=InvoiceSourceResolverPorts(
                catalogue_reader=InvoiceCatalogueSourceResolverAdapter(repository=resolved_invoice_repository),
            ),
            percepciones_observation_ports=PercepcionObservationPorts(
                repository=PercepcionObservationRepositoryAdapter(objects=objects),
            ),
            iva_compensation_history_repository=IvaCompensationHistoryRepository(objects=objects),
            iva_compensation_decision_repository=resolved_iva_compensation_decision_repository,
            borrador_snapshot_repository=(
                borrador_snapshot_repository
                if borrador_snapshot_repository is not None
                else build_borrador_100_snapshot_repository(bucket_id=normalized_bucket_id)
            ),
            retencion_observation_ports=RetencionObservationPorts(
                repository=RetencionObservationRepositoryAdapter(objects=objects),
            ),
            retencion_soportada_ports=RetencionSoportadaPorts(
                repository=RetencionSoportadaRecordRepositoryAdapter(objects=objects),
                absences=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
            ),
            credit_resolution_reader=CreditResolutionRepositoryAdapter(objects=objects),
            relation_override_migration=_RelationOverrideMigration(),
        )


__all__ = [
    "DEFAULT_130_BASELINE_INPUTS",
    "DEFAULT_130_BINDING_VALUES",
    "M111_ACTIVITY_AMOUNT_CASILLA",
    "M111_ACTIVITY_COUNT_CASILLA",
    "M111_ACTIVITY_WITHHELD_CASILLA",
    "M111_EMPLOYMENT_WITHHELD_CASILLA",
    "M111_FORESTRY_WITHHELD_CASILLA",
    "M111_IMAGE_RIGHTS_WITHHELD_CASILLA",
    "M111_IMPUTED_INCOME_WITHHELD_CASILLA",
    "M111_PRIZE_WITHHELD_CASILLA",
    "M111_PROFESSIONAL_WITHHELD_CASILLA",
    "M111_TOTAL_WITHHELD_CASILLA",
    "M130_AGRARIAN_VOLUME_CASILLA",
    "M130_AGRARIAN_WITHHELD_CASILLA",
    "M130_CARRY_FORWARD_CASILLA",
    "M130_EXPENSE_CASILLA",
    "M130_HOME_DEDUCTION_CASILLA",
    "M130_INCOME_CASILLA",
    "M130_NET_RESULT_CASILLA",
    "M130_PRIOR_RETURN_RESULT_CASILLA",
    "M130_SALDO_NEGATIVO_CASILLA",
    "M130_WITHHELD_CASILLA",
    "M180_PERCEPTOR_BASE_CASILLA",
    "T0",
    "T1",
    "T2",
    "T3",
    "T4",
    "T5",
    "VERIFY_MODELO",
    "VERIFY_PERIOD",
    "VERIFY_REVISION",
    "VERIFY_YEAR",
    "FileFlowRuntime",
    "Repos",
    "WorkflowGate",
    "canonical_work_unit_period",
    "file_flow_repositories",
    "file_revision",
    "registry_required_manual_casillas",
    "seed_modelo_180_work_unit",
    "seed_modelo_193_work_unit",
    "seed_work_unit",
    "target_filing_records",
    "verify_revision",
    "workflow_gate",
    "workflow_profile",
]


_T0 = SEED_CLOCK
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 14, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_T5 = datetime(2026, 4, 17, 13, 0, 0, tzinfo=UTC)
FILE_FLOW_PROFILE_ID = "11111111-1111-4111-8111-111111111111"

_VERIFY_MODELO = "180"
_VERIFY_REVISION = "2023-y-siguientes"
_VERIFY_PERIOD = "0A"
_VERIFY_YEAR = 2024
_READY_PROFILE_FACTS = persona_facts_beneath(
    (
        UserProfileFact(path="identity.tax_id", value="X0001500M"),
        UserProfileFact(path="identity.name", value="Ready"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="activities.description", value="file-flow"),
        UserProfileFact(path="censo.activity_start_date", value=date(2000, 1, 1)),
        # Modelo 111 refuses a defaulted colegio-concertado declaration: the fichero
        # carries the row as filer data, so it must be stated rather than assumed.
        # False is the truthful value for this natural-person filer.
        UserProfileFact(path="withholding.colegio_concertado", value=False),
        # The flows file Modelo 180 and Modelo 349 for this operator, so it pays a rent
        # subject to retención and trades with other Member States as a ROI registrant.
        UserProfileFact(path="withholding.pays_rent_with_retencion", value=True),
        UserProfileFact(path="iva.does_intracomunitario", value=True),
        UserProfileFact(path="iva.roi_enrolled", value=True),
    )
)


def _registry_required_manual_casillas(*, modelo: str, filing_year: int, period: str) -> tuple[CasillaId, ...]:
    """Return the required manual casillas an operator supplies as scalar calculate inputs.

    A casilla that a repeated export record fills once per detail row is left
    out: calculate refuses it as a scalar input, and its values arrive on the
    detail rows. Modelo 180's required manual casillas are all such perceptor
    row fields, so it yields none.
    """
    revision = resolved_revision(modelo=modelo, filing_year=filing_year, period=period)
    row_field_casilla_ids = row_field_template_records_by_casilla(revision)
    return tuple(
        c.id
        for c in revision.casillas
        if c.required and c.input_kind == InputKind.MANUAL and c.id not in row_field_casilla_ids
    )


FileFlowRepos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]


def _seed_file_flow_profile_record(profile: TestRuntimeProfile) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=profile.bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
            context=profile_creation_context_for_test(),
        ),
    )


def file_flow_seeded_profile(tmp_path: Path) -> SeededDurableProfile:
    """Provision and seed the file-flow bucket once, for reuse across a module.

    Nothing process-global outlives this call; :func:`file_flow_repositories`
    and :func:`file_flow_runtime_value` re-enter the bucket for one test at a time.
    """
    return provision_seeded_profile(tmp_path, FILE_FLOW_PROFILE_ID, _seed_file_flow_profile_record)


def file_flow_repositories(shared: SeededDurableProfile) -> Iterator[Repos]:
    """Yield the five catalogue repositories over the module's encrypted store.

    The bucket is re-entered for this test and returned to its seeded rows. Tuple shape:
    ``(work_unit, calculation_revision, filing_record,
    verification_report, bucket_event_history)``."""

    with reopened_seeded_profile(shared) as profile:
        objects = profile.repository
        wu = WorkUnitCatalogueRepository(bucket_id=profile.bucket_id, objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        fr = ModeloRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, fr, vr, bv


@dataclass(frozen=True, slots=True)
class FileFlowFileFlowRuntime:
    """The live engine plus the repository bundle sharing it.

    Exposes the engine the repositories already use so a test can observe how
    many SQL transactions a composed write spans, which is the only way to tell
    a single unit of work from a sequence of independent saves.
    """

    engine: Engine
    repos: FileFlowRepos


def file_flow_runtime_value(shared: SeededDurableProfile) -> Iterator[FileFlowFileFlowRuntime]:
    """Yield the file-flow repository bundle alongside its live engine."""
    with reopened_seeded_profile(shared) as profile:
        objects = profile.repository
        yield FileFlowFileFlowRuntime(
            engine=objects.engine,
            repos=(
                WorkUnitCatalogueRepository(objects=objects),
                CalculationRevisionCatalogueRepository(objects=objects),
                ModeloRecordCatalogueRepository(objects=objects),
                VerificationReportCatalogueRepository(objects=objects),
                BucketEventHistoryRepository(objects=objects),
            ),
        )


def _seed_work_unit(
    wu_repo: WorkUnitCatalogueRepository,
    *,
    bucket_id: str = FILE_FLOW_PROFILE_ID,
    modelo: str = "130",
    filing_year: int = 2026,
    period: str = "1T",
    revision_id: str = "2019-y-siguientes",
) -> WorkUnit:
    """Default fixture: modelo 130 1T 2026 — autónomo IRPF quarterly,
    9 manual casillas + 10 formulas + 1 prior-filing binding.
    Registry-resolvable so the formula engine runs end-to-end."""

    with bundled_indexed_authority().operation() as operation:
        return create_work_unit(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, period),
            revision_id=revision_id,
            ports=WorkLifecyclePorts(
                work_unit_repository=wu_repo,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            operation=operation,
            clock=_T0,
        )


FILE_FLOW_DEFAULT_130_BINDING_VALUES = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
}


FILE_FLOW_M130_INCOME_CASILLA: CasillaId = validated_casilla_id("01")
_M130_EXPENSE_CASILLA: CasillaId = validated_casilla_id("02")
_M130_NET_RESULT_CASILLA: CasillaId = validated_casilla_id("03")
M130_PREVIOUS_PAYMENTS_CASILLA: CasillaId = validated_casilla_id("05")
FILE_FLOW_M130_WITHHELD_CASILLA: CasillaId = validated_casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
FILE_FLOW_M130_CARRY_FORWARD_CASILLA: CasillaId = validated_casilla_id("15")
FILE_FLOW_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
FILE_FLOW_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
FILE_FLOW_M130_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")
_M111_EMPLOYMENT_WITHHELD_CASILLA: CasillaId = validated_casilla_id("03")
_M111_PROFESSIONAL_WITHHELD_CASILLA: CasillaId = validated_casilla_id("06")
_M111_PRIZE_WITHHELD_CASILLA: CasillaId = validated_casilla_id("09")
_M111_IMAGE_RIGHTS_WITHHELD_CASILLA: CasillaId = validated_casilla_id("12")
_M111_FORESTRY_WITHHELD_CASILLA: CasillaId = validated_casilla_id("15")
_M111_IMPUTED_INCOME_WITHHELD_CASILLA: CasillaId = validated_casilla_id("18")
_M111_ACTIVITY_COUNT_CASILLA: CasillaId = validated_casilla_id("21")
_M111_ACTIVITY_AMOUNT_CASILLA: CasillaId = validated_casilla_id("24")
_M111_ACTIVITY_WITHHELD_CASILLA: CasillaId = validated_casilla_id("27")
_M111_TOTAL_WITHHELD_CASILLA: CasillaId = validated_casilla_id("29")
_M180_PERCEPTOR_BASE_CASILLA: CasillaId = validated_casilla_id("perc.base")

#: Operator-owned M130 inputs of the baseline scenario. Casillas 01 and 02 are
#: the ledger's: :func:`_seed_m130_activity` records the baseline income and
#: gastos as ledger rows instead.
_DEFAULT_130_BASELINE_INPUTS: dict[CasillaId, Decimal] = {
    M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
    FILE_FLOW_M130_WITHHELD_CASILLA: Decimal("0"),
    FILE_FLOW_M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    FILE_FLOW_M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}


_DEFAULT_130_BASELINE_INCOME = Decimal("10000")  # economic-activity gross income
_DEFAULT_130_BASELINE_EXPENSE = Decimal("3000")  # economic-activity gross expenses


def _m130_ledger_totals(work_unit: WorkUnit, *, through: date) -> tuple[Decimal, Decimal]:
    """Return the seeded activity income and gastos dated in the work unit's year up to ``through``."""
    with bundled_indexed_authority().operation(), open_test_profile_session(work_unit.bucket_id):
        transactions = TransactionCatalogueRepository(bucket_id=work_unit.bucket_id).load().transactions.values()
    totals = {"m130_oracle_income": Decimal("0"), "m130_oracle_expense": Decimal("0")}
    for transaction in transactions:
        kind = transaction.raw.raw_fields.get("source_kind")
        value_date = transaction.raw.value_date or transaction.raw.booked_date
        if kind in totals and value_date.year == work_unit.filing_year and value_date <= through:
            totals[kind] += transaction.raw.amount
    return totals["m130_oracle_income"], totals["m130_oracle_expense"]


def _seed_m130_activity(
    work_unit: WorkUnit,
    *,
    income: Decimal = Decimal("0"),
    expense: Decimal = Decimal("0"),
) -> None:
    """Make the ledger's year-to-date activity income and gastos read ``income`` and ``expense``.

    Modelo 130 casillas 01 and 02 are those year-to-date ledger totals, so the
    bucket calculation reads them from real ledger rows. The rows added here
    are dated inside the work unit's quarter and make up the difference from
    what the ledger already holds; a total cannot fall, as no row is removed.
    """
    quarter = int(work_unit.period.registry_token[0])
    row_date = date(work_unit.filing_year, 3 * (quarter - 1) + 1, 5)
    quarter_end = date(work_unit.filing_year, 3 * quarter, 28)
    held_income, held_expense = _m130_ledger_totals(work_unit, through=quarter_end)
    if income < held_income or expense < held_expense:
        raise AssertionError(f"the ledger already holds {held_income} income and {held_expense} gastos")
    source_key = f"{work_unit.period.registry_token}-{held_income}-{held_expense}"
    if income > held_income:
        seed_m130_income_transaction(
            amount=income - held_income,
            filing_year=work_unit.filing_year,
            source_key=source_key,
            value_date=row_date,
            bucket_id=work_unit.bucket_id,
        )
    if expense > held_expense:
        seed_m130_expense_transaction(
            amount=expense - held_expense,
            filing_year=work_unit.filing_year,
            source_key=source_key,
            value_date=row_date,
            bucket_id=work_unit.bucket_id,
        )


def workflow_profile() -> TaxpayerProfile:
    return plain_workflow_profile(activity_start_date=date(2000, 1, 1))


def _target_filing_records(
    records: tuple[object, ...],
    work_unit: WorkUnit,
) -> tuple[ModeloRecord, ...]:
    result: list[ModeloRecord] = []
    for record in records:
        if isinstance(record, ModeloRecord) and record.work_unit_id == work_unit.work_unit_id:
            result.append(record)
    return tuple(result)


def _canonical_work_unit_period(work_unit: WorkUnit) -> Period:
    return workflow_period_for_work_unit(work_unit)


@dataclass
class _WorkflowGate:
    engine: WorkflowEngine
    profile: TaxpayerProfile


def _workflow_gate(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    clock: datetime,
    operation: PinnedAuthorityOperation,
) -> _WorkflowGate:
    profile = workflow_profile()
    filing_ports = build_filing_action_ports(bucket_id=work_unit.bucket_id, operation=operation)
    return _WorkflowGate(
        profile=profile,
        engine=build_revision_workflow_engine(
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            draft_review_ports=filing_ports.draft_review_ports,
            workflow_gate_ports=filing_ports.workflow_gate_ports,
            revision=revision,
            work_unit=work_unit,
            profile=profile,
            actor="operator-A",
            clock=clock,
            settings=Settings(),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ),
    )


def file_flow_file_revision(
    calculation_revision_id: str,
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    actor: str = "operator-A",
    notes: str | None = None,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    clock: datetime,
):
    with bundled_indexed_authority().operation() as operation:
        seed_clean_cross_period_sources(
            work_unit,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            bucket_event_repository=bucket_event_repository,
            operation=operation,
        )
        gate = _workflow_gate(
            revision=revision,
            work_unit=work_unit,
            clock=clock,
            operation=operation,
        )
        filing_ports = replace(
            build_filing_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            bucket_event_repository=bucket_event_repository,
        )
        granting_reports = tuple(
            report
            for report in filing_ports.verification_repository.load().reports.values()
            if report.calculation_revision_id == calculation_revision_id and report.granted_verificado_completo
        )
        assert len(granting_reports) == 1, "filing test must use one actual granting verification report"
        return file_modelo_revision(
            calculation_revision_id,
            approved_verification_report_id=granting_reports[0].verification_report_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            ports=filing_ports,
            actor=actor,
            workflow_profile=gate.profile,
            notes=notes,
            workflow_engine=gate.engine,
            clock=clock,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).record


def file_flow_verify_revision(
    calculation_revision_id: str,
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    actor: str = "operator-A",
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    verification_repository: VerificationReportCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
    clock: datetime,
):
    with bundled_indexed_authority().operation() as operation:
        seed_clean_cross_period_sources(
            work_unit,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            filing_repository=filing_repository or ModeloRecordCatalogueRepository(),
            bucket_event_repository=bucket_event_repository,
            operation=operation,
        )
        gate = _workflow_gate(
            revision=revision,
            work_unit=work_unit,
            clock=clock,
            operation=operation,
        )
        verification_repositories = replace(
            build_test_verification_repository_bundle(),
            work_unit=work_unit_repository,
            calculation=calculation_repository,
            verification=verification_repository,
            bucket_event=bucket_event_repository,
            filing=filing_repository or ModeloRecordCatalogueRepository(),
        )
        return verify_modelo_revision_with_preconditions(
            calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=verification_repositories,
            actor=actor,
            workflow_profile=gate.profile,
            workflow_engine=gate.engine,
            clock=clock,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report


def calculate_baseline_130_revision(work_unit: WorkUnit) -> CalculationRevision:
    """Calculate the work unit's Modelo 130 revision from the default baseline inputs and bindings at T1."""
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
            binding_values=FILE_FLOW_DEFAULT_130_BINDING_VALUES,
            clock=_T1,
        ).revision


def _seed_modelo_180_work_unit(wu_repo: WorkUnitCatalogueRepository) -> WorkUnit:
    with bundled_indexed_authority().operation() as operation:
        return create_work_unit(
            bucket_id=FILE_FLOW_PROFILE_ID,
            modelo=_VERIFY_MODELO,
            filing_year=_VERIFY_YEAR,
            period=Period.from_year_and_code(_VERIFY_YEAR, _VERIFY_PERIOD),
            revision_id=_VERIFY_REVISION,
            ports=WorkLifecyclePorts(
                work_unit_repository=wu_repo,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            operation=operation,
            clock=_T0,
        )


def _seed_modelo_193_work_unit(wu_repo: WorkUnitCatalogueRepository):
    """Seed a Modelo 193 work unit, the fixture for a draft that omits a required scalar casilla.

    Modelo 193 declares a required scalar declarant casilla beside its
    perceptor row fields, so leaving it out is a missing-required refusal at
    verify. Modelo 180 cannot serve: every required manual casilla it declares
    is a perceptor-record row field, answered by the row source rather than
    by a scalar input.
    """
    return _seed_work_unit(wu_repo, modelo="193", filing_year=2024, period="0A", revision_id="2024")


DEFAULT_130_BASELINE_EXPENSE = _DEFAULT_130_BASELINE_EXPENSE
DEFAULT_130_BASELINE_INCOME = _DEFAULT_130_BASELINE_INCOME
DEFAULT_130_BASELINE_INPUTS = _DEFAULT_130_BASELINE_INPUTS
DEFAULT_130_BINDING_VALUES = FILE_FLOW_DEFAULT_130_BINDING_VALUES
M111_ACTIVITY_AMOUNT_CASILLA = _M111_ACTIVITY_AMOUNT_CASILLA
M111_ACTIVITY_COUNT_CASILLA = _M111_ACTIVITY_COUNT_CASILLA
M111_ACTIVITY_WITHHELD_CASILLA = _M111_ACTIVITY_WITHHELD_CASILLA
M111_EMPLOYMENT_WITHHELD_CASILLA = _M111_EMPLOYMENT_WITHHELD_CASILLA
M111_FORESTRY_WITHHELD_CASILLA = _M111_FORESTRY_WITHHELD_CASILLA
M111_IMAGE_RIGHTS_WITHHELD_CASILLA = _M111_IMAGE_RIGHTS_WITHHELD_CASILLA
M111_IMPUTED_INCOME_WITHHELD_CASILLA = _M111_IMPUTED_INCOME_WITHHELD_CASILLA
M111_PRIZE_WITHHELD_CASILLA = _M111_PRIZE_WITHHELD_CASILLA
M111_PROFESSIONAL_WITHHELD_CASILLA = _M111_PROFESSIONAL_WITHHELD_CASILLA
M111_TOTAL_WITHHELD_CASILLA = _M111_TOTAL_WITHHELD_CASILLA
M130_AGRARIAN_VOLUME_CASILLA = _M130_AGRARIAN_VOLUME_CASILLA
M130_AGRARIAN_WITHHELD_CASILLA = _M130_AGRARIAN_WITHHELD_CASILLA
M130_CARRY_FORWARD_CASILLA = FILE_FLOW_M130_CARRY_FORWARD_CASILLA
M130_EXPENSE_CASILLA = _M130_EXPENSE_CASILLA
M130_HOME_DEDUCTION_CASILLA = FILE_FLOW_M130_HOME_DEDUCTION_CASILLA
M130_INCOME_CASILLA = FILE_FLOW_M130_INCOME_CASILLA
M130_NET_RESULT_CASILLA = _M130_NET_RESULT_CASILLA
M130_PRIOR_RETURN_RESULT_CASILLA = FILE_FLOW_M130_PRIOR_RETURN_RESULT_CASILLA
M130_SALDO_NEGATIVO_CASILLA = FILE_FLOW_M130_SALDO_NEGATIVO_CASILLA
M130_WITHHELD_CASILLA = FILE_FLOW_M130_WITHHELD_CASILLA
M180_PERCEPTOR_BASE_CASILLA = _M180_PERCEPTOR_BASE_CASILLA
Repos = FileFlowRepos
T0 = _T0
T1 = _T1
T2 = _T2
T3 = _T3
T4 = _T4
T5 = _T5
VERIFY_MODELO = _VERIFY_MODELO
VERIFY_PERIOD = _VERIFY_PERIOD
VERIFY_REVISION = _VERIFY_REVISION
VERIFY_YEAR = _VERIFY_YEAR
WorkflowGate = _WorkflowGate
canonical_work_unit_period = _canonical_work_unit_period
file_revision = file_flow_file_revision
registry_required_manual_casillas = _registry_required_manual_casillas
seed_modelo_180_work_unit = _seed_modelo_180_work_unit
seed_m130_activity = _seed_m130_activity
seed_modelo_193_work_unit = _seed_modelo_193_work_unit
seed_work_unit = _seed_work_unit
target_filing_records = _target_filing_records
verify_revision = file_flow_verify_revision
workflow_gate = _workflow_gate
workflow_profile = workflow_profile
FileFlowRuntime = FileFlowFileFlowRuntime
