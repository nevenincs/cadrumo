"""Shared profile seeders and the export operator fixture for the modelo export verb tests."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.filing_report_support import seed_filing_gate_report
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import set_active_test_profile_facts
from cadrumo.application.modelo.calculation_screen import calculation_screen_stamp
from cadrumo.application.modelo.tests.registry_revision import active_registry_revision_id
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    revision_before_first_declaring,
)
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.calculation_screen_stamp import CalculationScreenStamp
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.user_profile.values import UserProfileFact

from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder


@pytest.fixture(autouse=True)
def export_operator(seed_profile: ProfileSeeder) -> None:
    """Register one password-custodied profile whose joined runtime admits every export command.

    The command line submits export through the runtime, so the revisions each
    test plants in this profile's encrypted catalogues are read by the same
    registered operation an operator's export reaches.
    """
    seed_profile(label="export operator", facts={})


def invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def calculated_screen_stamp(
    *, modelo: str, filing_year: int, period: str, operation: PinnedAuthorityOperation
) -> CalculationScreenStamp:
    """Return the stamp a calculation of this target persists; a seeded revision stands in for that calculation."""
    snapshot = operation.snapshot(
        modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.CALCULATION
    )
    return calculation_screen_stamp(snapshot, operation=operation)


def seed_work_unit_only(
    *, modelo: str = "130", filing_year: int = 2026, period: str = "1T", operation: PinnedAuthorityOperation
) -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = active_registry_revision_id(
        modelo=modelo, filing_year=filing_year, period=period, operation=operation
    )
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def seed_work_unit_with_draft_revision(*, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    work_unit_id = seed_work_unit_only(operation=operation)
    now = datetime.now(UTC)
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="130",
            revision_id=active_registry_revision_id(modelo="130", filing_year=2026, period="1T", operation=operation),
            modelo_year=2026,
            period="1T",
        ),
        state=CalculationRevisionState.BORRADOR,
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    if revision.verified_at is not None:
        seed_filing_gate_report(revision, VerificationReportCatalogueRepository())
    return work_unit_id, calculation_revision_id


def seed_verified_revision_without_inputs(
    *, modelo: str, filing_year: int, period: str, operation: PinnedAuthorityOperation
) -> tuple[str, str]:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = active_registry_revision_id(
        modelo=modelo, filing_year=filing_year, period=period, operation=operation
    )
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
    )
    screen_stamp = calculated_screen_stamp(modelo=modelo, filing_year=filing_year, period=period, operation=operation)
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
        screen_stamp=screen_stamp,
    )
    # The seeded revision stands in for a calculation, which makes it the work unit's current one.
    work_unit = work_unit.model_copy(update={"current_calculation_revision_id": calculation_revision_id})
    WorkUnitCatalogueRepository().save(upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit))
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=modelo,
            revision_id=revision_id,
            modelo_year=filing_year,
            period=period,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
        screen_stamp=screen_stamp,
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    if revision.verified_at is not None:
        seed_filing_gate_report(revision, VerificationReportCatalogueRepository())
    return work_unit_id, calculation_revision_id


M111_CASILLA_03: CasillaId = validated_casilla_id("03", surface="modelo 111 export test casilla")
M111_CASILLA_06: CasillaId = validated_casilla_id("06", surface="modelo 111 export test casilla")
M111_CASILLA_09: CasillaId = validated_casilla_id("09", surface="modelo 111 export test casilla")
M111_CASILLA_12: CasillaId = validated_casilla_id("12", surface="modelo 111 export test casilla")
M111_CASILLA_15: CasillaId = validated_casilla_id("15", surface="modelo 111 export test casilla")
M111_CASILLA_18: CasillaId = validated_casilla_id("18", surface="modelo 111 export test casilla")
M111_CASILLA_21: CasillaId = validated_casilla_id("21", surface="modelo 111 export test casilla")
M111_CASILLA_24: CasillaId = validated_casilla_id("24", surface="modelo 111 export test casilla")
M111_CASILLA_27: CasillaId = validated_casilla_id("27", surface="modelo 111 export test casilla")
M111_CASILLA_29: CasillaId = validated_casilla_id("29", surface="modelo 111 export test casilla")
M202_CASILLA_01: CasillaId = validated_casilla_id("01", surface="modelo 202 export test casilla")
M202_2023_2024_PRIOR_PAYMENTS_BINDING = "modelo-202-pagos-fraccionados-anteriores"
M202_INCN_PRIOR_12_MONTHS_BINDING = "modelo-202-incn-prior-12-months"
M202_CUOTA_BASE_BINDING = "modelo-202-cuota-base-ejercicio-anterior"
# The last exercise of the Modelo 202 revision the registry authors right before the
# first one that declares the B2 tramo casilla 67; the exportable fixture revision
# below is seeded for its first period.
PRE_B2 = revision_before_first_declaring("202", "67")
assert PRE_B2.valid_to is not None
PRE_B2_LAST_EXERCISE = PRE_B2.valid_to.year

MODELO_111_INPUTS: dict[CasillaId, str] = {
    M111_CASILLA_03: "180.25",
    M111_CASILLA_06: "12.10",
    M111_CASILLA_09: "300.00",
    M111_CASILLA_12: "14.40",
    M111_CASILLA_15: "25.00",
    M111_CASILLA_18: "0.50",
    M111_CASILLA_21: "7.00",
    M111_CASILLA_24: "8.00",
    M111_CASILLA_27: "9.00",
    M111_CASILLA_29: "40.00",
}


def set_export_profile_name() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Export Test"),
            UserProfileFact(path="activities.description", value="Consulting"),
            # Modelo 111 declares whether the withholder is a colegio
            # concertado in its own header field; the producer refuses an
            # undeclared value rather than assume one.
            UserProfileFact(path="withholding.colegio_concertado", value=False),
        ),
    )


def set_emilio_legal_entity_export_profile(
    *,
    activity_start_date: date | None = None,
    constitution_date: date | None = None,
    without: Collection[str] = (),
) -> None:
    activity_start = (
        (UserProfileFact(path="censo.activity_start_date", value=activity_start_date.isoformat()),)
        if activity_start_date is not None
        else ()
    )
    # A calendar ejercicio: the declaración censal's closing day and month, and the constitution date.
    periodo_impositivo = (
        (
            UserProfileFact(path="taxpayer_type.cierre_ejercicio_dia", value=31),
            UserProfileFact(path="taxpayer_type.cierre_ejercicio_mes", value=12),
            UserProfileFact(path="taxpayer_type.fecha_constitucion", value=constitution_date.isoformat()),
        )
        if constitution_date is not None
        else ()
    )
    set_active_test_profile_facts(
        persona_facts_beneath(
            (
                *activity_start,
                *periodo_impositivo,
                UserProfileFact(path="identity.tax_id", value="B00015016"),
                UserProfileFact(path="identity.name", value="Emilio"),
                UserProfileFact(path="identity.surnames", value="Corporate Persona"),
                UserProfileFact(path="identity.legal_name", value="Emilio Consulting Sociedad Limitada"),
                UserProfileFact(path="activities.description", value="Consulting"),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
                UserProfileFact(path="withholding.has_employees", value=True),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value=""),
                UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="500000"),
            ),
            persona_id="sociedad-limitada",
            without=without,
        ),
    )


def clear_export_profile_surnames() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.surnames", value=None),
            UserProfileFact(path="activities.description", value="Consulting"),
            UserProfileFact(path="withholding.colegio_concertado", value=False),
        ),
    )


def seed_modelo_111_revisions(
    *,
    states: tuple[CalculationRevisionState, ...],
    current_index: int | None = None,
    filed_index: int | None = None,
    filing_year: int = 2026,
    period: str = "1T",
    operation: PinnedAuthorityOperation,
) -> tuple[str, tuple[str, ...]]:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    registry_revision_id = active_registry_revision_id(
        modelo="111", filing_year=filing_year, period=period, operation=operation
    )
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="111",
        filing_year=filing_year,
        period=filing_period,
        revision_id=registry_revision_id,
    )
    now = datetime.now(UTC)
    revision_ids: list[str] = []
    revisions: list[CalculationRevision] = []
    screen_stamp = calculated_screen_stamp(modelo="111", filing_year=filing_year, period=period, operation=operation)
    for index, state_value in enumerate(states):
        inputs = {**MODELO_111_INPUTS, M111_CASILLA_03: f"{180 + index}.25"}
        calculation_revision_id = derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id=inputs,
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
            screen_stamp=screen_stamp,
        )
        revision_ids.append(calculation_revision_id)
        revisions.append(
            CalculationRevision(
                calculation_revision_id=calculation_revision_id,
                work_unit_id=work_unit_id,
                registry_snapshot_ref=RegistrySnapshotRef(
                    modelo="111",
                    revision_id=registry_revision_id,
                    modelo_year=filing_year,
                    period=period,
                ),
                state=state_value,
                input_values_by_casilla_id=inputs,
                created_at=now,
                updated_at=now,
                verified_at=now
                if state_value in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}
                else None,
                verified_by="operator"
                if state_value in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}
                else None,
                filed_at=now if state_value is CalculationRevisionState.PRESENTADO else None,
                filed_by="operator" if state_value is CalculationRevisionState.PRESENTADO else None,
                filing_instance_evidence=None,
                source_provenance=(),
                screen_stamp=screen_stamp,
            ),
        )

    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("111"),
        filing_year=filing_year,
        period=filing_period,
        revision_id=registry_revision_id,
        name=f"111-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
        current_calculation_revision_id=revision_ids[current_index] if current_index is not None else None,
        filed_calculation_revision_id=revision_ids[filed_index] if filed_index is not None else None,
    )
    wu_repo = WorkUnitCatalogueRepository()
    wu_repo.save(upsert_work_unit(wu_repo.load(), work_unit))
    cr_repo = CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    for revision in revisions:
        catalogue = upsert_calculation_revision(catalogue, revision)
    cr_repo.save(catalogue)
    reports = VerificationReportCatalogueRepository()
    for revision in revisions:
        if revision.verified_at is not None:
            seed_filing_gate_report(revision, reports)
    return work_unit_id, tuple(revision_ids)


def seed_exportable_modelo_202_pre_b2_revision(*, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """Persist a verified-complete pre-B2 M202 1P revision with the 2023-2024 binding channel."""

    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = active_registry_revision_id(
        modelo="202", filing_year=PRE_B2_LAST_EXERCISE, period="1P", operation=operation
    )
    filing_period = Period.from_year_and_code(PRE_B2_LAST_EXERCISE, "1P")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="202",
        filing_year=PRE_B2_LAST_EXERCISE,
        period=filing_period,
        revision_id=revision_id,
    )
    inputs = {M202_CASILLA_01: "0"}
    # Every supported year requires the prior-twelve-month turnover, recorded as the Emilio
    # export profile declares it, and the art. 40.2 base, recorded as the zero instalment's.
    binding_overrides = {
        M202_2023_2024_PRIOR_PAYMENTS_BINDING: "0",
        M202_INCN_PRIOR_12_MONTHS_BINDING: "500000",
        M202_CUOTA_BASE_BINDING: "0",
    }
    casilla_values = {M202_CASILLA_01: Decimal("0")}
    screen_stamp = calculated_screen_stamp(
        modelo="202", filing_year=PRE_B2_LAST_EXERCISE, period="1P", operation=operation
    )
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
        screen_stamp=screen_stamp,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("202"),
        filing_year=PRE_B2_LAST_EXERCISE,
        period=filing_period,
        revision_id=revision_id,
        name=f"202-{PRE_B2_LAST_EXERCISE}-1P",
        created_at=now,
        updated_at=now,
        current_calculation_revision_id=calculation_revision_id,
    )
    WorkUnitCatalogueRepository().save(upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit))
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="202",
            revision_id=revision_id,
            modelo_year=PRE_B2_LAST_EXERCISE,
            period="1P",
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id=inputs,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo="202",
            filing_year=PRE_B2_LAST_EXERCISE,
            period="1P",
            casilla_values=casilla_values,
        ),
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="Emilio",
        filing_instance_evidence=None,
        source_provenance=(),
        screen_stamp=screen_stamp,
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    if revision.verified_at is not None:
        seed_filing_gate_report(revision, VerificationReportCatalogueRepository())
    return work_unit_id, calculation_revision_id
