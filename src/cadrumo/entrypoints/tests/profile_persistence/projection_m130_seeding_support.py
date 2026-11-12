"""Run the real Modelo 100 projection over one seeded Modelo 130 quarter, profile and payer records.

The quarter stores the four Modelo 130 boxes the projection reads. The profile
is a complete general-regime natural person whose IRPF income categories each
scenario chooses, because they decide whether a suffered-withholding class needs
payer evidence. Payer records are written through the production write port.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.aggregation.retencion_soportada_repository import record_retencion_soportada
from cadrumo.application.modelo.projection import (
    ModeloProjectNoM130RevisionsError,
    ModeloProjectNoM130UnitsError,
    ModeloProjectServiceResult,
    project_modelo_100_from_m130,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.operations.next_step import (
    OperationCalculateWorkStepV1,
    OperationCreateWorkStepV1,
    error_next_step,
)
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_work_lifecycle_ports,
)
from cadrumo.entrypoints.retencion_soportada_certificado_composition import (
    build_retencion_soportada_certificado_ports,
)

from .general_iva_profile_facts_support import general_iva_profile_facts

PROJECTION_YEAR = 2025
_T0 = datetime(2026, 2, 2, 9, 0, tzinfo=UTC)
_BUCKET_ID = "59659659-0596-4596-8596-596596596596"
_TAXPAYER_TAX_ID = "12345678Z"
_M130_REVISION_ID = "2019-y-siguientes"
ACTIVITY_ONLY = "actividad_economica"
"""Income categories that positively exclude every suffered-withholding credit class of Modelo 100."""

# The four Modelo 130 boxes the projection reads: cumulative ingresos, gastos and
# rendimiento neto, and the quarter's final result, which becomes casilla 0604.
M130_Q1_RESULTADO = Decimal("1200.00")
_M130_Q1_RESULT_BOX = validated_casilla_id("19", surface="projection seeding")
_M130_Q1_VALUES: dict[CasillaId, Decimal] = {
    validated_casilla_id("01", surface="projection seeding"): Decimal("10000.00"),
    validated_casilla_id("02", surface="projection seeding"): Decimal("4000.00"),
    validated_casilla_id("03", surface="projection seeding"): Decimal("6000.00"),
    _M130_Q1_RESULT_BOX: M130_Q1_RESULTADO,
}


class QuarterSeeding(StrEnum):
    """How much of the first Modelo 130 quarter a scenario stores."""

    CALCULATED = "calculated"
    #: Calculated, but without the final-result box, as a calculation stores one that could not work it out.
    WITHOUT_RESULT = "without_result"
    DRAFT_ONLY = "draft_only"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class PayerRecord:
    """One synthetic payer certificate: its payer and the retención it states."""

    payer_tax_id: str
    income_class: RetencionSoportadaClase
    retencion: Decimal


def _seed_profile(
    profile_id: str,
    *,
    income_categories: str,
    profile_facts: tuple[UserProfileFact, ...],
    states_region: bool,
) -> None:
    """Seed the complete profile; ``profile_facts`` replace a base fact of the same path.

    ``states_region`` is false for a profile whose tax residence never named a region.
    """
    scenario_paths = {fact.path for fact in profile_facts}
    if not states_region:
        scenario_paths.add("tax_residence.ccaa")
    base_facts = (
        *general_iva_profile_facts(tax_id=_TAXPAYER_TAX_ID, activity_start_date="2020-01-01"),
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value=income_categories),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="renta_filing.declaration_type", value="1"),
        UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 1, 1)),
    )
    # The base list repeats some paths; the last occurrence is the one the original seeding stored.
    latest_by_path = {fact.path: fact for fact in base_facts if fact.path not in scenario_paths}
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=profile_id,
            facts=(*latest_by_path.values(), *profile_facts),
            created_at=_T0,
            updated_at=_T0,
            context=profile_creation_context_for_test(),
        ),
    )


def _seed_first_quarter(
    profile: TestRuntimeProfile, operation: PinnedAuthorityOperation, *, seeding: QuarterSeeding
) -> None:
    """Store the Modelo 130 1T draft, and with a calculated seeding its revision carrying the boxes it holds."""
    if seeding is QuarterSeeding.NONE:
        return
    work_unit = create_work_unit(
        bucket_id=profile.bucket_id,
        modelo="130",
        filing_year=PROJECTION_YEAR,
        period=Period.from_year_and_code(PROJECTION_YEAR, "1T"),
        revision_id=_M130_REVISION_ID,
        ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
        clock=_T0,
        operation=operation,
    )
    if seeding is QuarterSeeding.DRAFT_ONLY:
        return
    held = {
        casilla_id: value
        for casilla_id, value in _M130_Q1_VALUES.items()
        if seeding is not QuarterSeeding.WITHOUT_RESULT or casilla_id != _M130_Q1_RESULT_BOX
    }
    inputs = {casilla_id: str(value) for casilla_id, value in held.items()}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=inputs,
            binding_overrides={},
            casilla_values=held,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values=held,
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=PROJECTION_YEAR,
            period="1T",
            casilla_values=held,
        ),
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
    repository.save(upsert_calculation_revision(repository.load(), revision))


def _seed_payer_records(
    profile: TestRuntimeProfile, records: tuple[PayerRecord, ...], operation: PinnedAuthorityOperation
) -> None:
    ports = build_retencion_soportada_certificado_ports(profile_id=UUID(profile.bucket_id), operation=operation)
    for index, item in enumerate(records):
        record = RetencionSoportadaRecord(
            ejercicio=PROJECTION_YEAR,
            payer_tax_id=item.payer_tax_id,
            payer_ref=ports.repository.payer_reference(item.payer_tax_id),
            income_class=item.income_class,
            importe_integro_dinerario=Decimal("20000.00"),
            valoracion_especie=Decimal("0.00"),
            retencion=item.retencion,
            ingreso_a_cuenta=Decimal("0.00"),
            ingreso_a_cuenta_repercutido=Decimal("0.00"),
            reducciones_aplicables=Decimal("0.00") if (item.income_class) is RetencionSoportadaClase.TRABAJO else None,
            gastos_deducibles=Decimal("0.00") if (item.income_class) is RetencionSoportadaClase.TRABAJO else None,
            origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
            evidence_fingerprint=ports.custody.ingest(
                source_path=Path("synthetic-certificate.pdf"),
                data=f"synthetic certificate {index + 1}".encode(),
                mime_type="application/pdf",
                captured_at=_T0,
            ),
            captured_at=_T0,
        )
        record_retencion_soportada(
            record,
            repository=ports.repository,
            authority=ports.authority,
            custody=ports.custody,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )


def run_projection(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    *,
    income_categories: str = ACTIVITY_ONLY,
    payer_records: tuple[PayerRecord, ...] = (),
    casilla_overrides: Mapping[str, str] | None = None,
    binding_overrides: Mapping[str, str] | None = None,
    profile_facts: tuple[UserProfileFact, ...] = (),
    ccaa: str | None = "madrid",
    states_region: bool = True,
    quarter: QuarterSeeding = QuarterSeeding.CALCULATED,
    year: int = PROJECTION_YEAR,
    ledger_rows: tuple[Transaction, ...] = (),
) -> ModeloProjectServiceResult:
    """Seed one isolated profile and return the real projection service's result for it.

    ``ccaa`` is the region the request names, or ``None`` to leave it to the
    profile; ``states_region`` is whether the profile's tax residence names one.
    ``year`` is the filing year the request asks for; the stored quarter is always
    the ``PROJECTION_YEAR`` one. ``ledger_rows`` are stored in the profile's ledger before projecting.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_profile(
            profile.bucket_id,
            income_categories=income_categories,
            profile_facts=profile_facts,
            states_region=states_region,
        )
        _seed_first_quarter(profile, operation, seeding=quarter)
        _seed_payer_records(profile, payer_records, operation)
        with bundled_indexed_authority().operation() as projection_operation:
            ports = build_calculation_action_ports(bucket_id=profile.bucket_id, operation=projection_operation)
            if ledger_rows:
                ledger = ports.transaction_repository
                if not isinstance(ledger, TransactionCatalogueRepository):
                    raise AssertionError("the calculation ports do not hold the profile's ledger repository")
                ledger.save(TransactionCatalogue.from_transactions(ledger_rows))
            return project_modelo_100_from_m130(
                year=year,
                ccaa=ccaa,
                bucket_id=profile.bucket_id,
                ports=ports,
                operation=projection_operation,
                casilla_overrides=dict(casilla_overrides) if casilla_overrides is not None else None,
                binding_overrides=dict(binding_overrides) if binding_overrides is not None else None,
            )


@dataclass(frozen=True, slots=True)
class FollowedProjectionSteps:
    """The steps the projection served at each stage, and the declaration the first one created."""

    create: OperationCreateWorkStepV1
    created_work_unit_id: str
    calculate: OperationCalculateWorkStepV1


def follow_projection_steps(tmp_path: Path, operation: PinnedAuthorityOperation) -> FollowedProjectionSteps:
    """Project a profile with no quarter, create the declaration the refusal's step names, and project again.

    The first refusal serves the step that creates the first quarter's declaration. The declaration is created
    from that step's address alone, through the production lifecycle, and the second refusal then serves the
    step that calculates the declaration just created.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_profile(profile.bucket_id, income_categories=ACTIVITY_ONLY, profile_facts=(), states_region=True)
        with bundled_indexed_authority().operation() as projection_operation:

            def project() -> None:
                project_modelo_100_from_m130(
                    year=PROJECTION_YEAR,
                    ccaa=None,
                    bucket_id=profile.bucket_id,
                    ports=build_calculation_action_ports(bucket_id=profile.bucket_id, operation=projection_operation),
                    operation=projection_operation,
                )

            try:
                project()
            except ModeloProjectNoM130UnitsError as no_quarter:
                create = error_next_step(no_quarter, OutputLanguage.EN)
            else:
                raise AssertionError("a profile with no quarterly declaration was projected")
            if not isinstance(create, OperationCreateWorkStepV1):
                raise AssertionError("the missing quarter did not serve a step that creates it")
            period = Period.from_year_and_code(create.filing_year, create.period_code)
            created = create_work_unit(
                bucket_id=profile.bucket_id,
                modelo=create.modelo,
                filing_year=create.filing_year,
                period=period,
                revision_id=str(
                    projection_operation.revision_for_context(
                        create.modelo, filing_year=create.filing_year, period=period.registry_token
                    ).id
                ),
                ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
                clock=_T0,
                operation=projection_operation,
            )
            try:
                project()
            except ModeloProjectNoM130RevisionsError as uncalculated:
                calculate = error_next_step(uncalculated, OutputLanguage.EN)
            else:
                raise AssertionError("an uncalculated quarter was projected")
            if not isinstance(calculate, OperationCalculateWorkStepV1):
                raise AssertionError("the uncalculated quarter did not serve a step that calculates it")
            return FollowedProjectionSteps(
                create=create, created_work_unit_id=created.work_unit_id, calculate=calculate
            )


__all__ = [
    "ACTIVITY_ONLY",
    "M130_Q1_RESULTADO",
    "PROJECTION_YEAR",
    "FollowedProjectionSteps",
    "PayerRecord",
    "QuarterSeeding",
    "follow_projection_steps",
    "run_projection",
]
