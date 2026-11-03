"""E2E vertical: general prorrata settles in the fourth quarter and folds into the Modelo 390 annual.

The prorrata share of the Modelo 303 to Modelo 390 chain: a seeded year drawn from the AEAT prorrata
general example, its definitive regularisation in 4T, and the tier screens over a register percentage.
The quarter chain itself is covered by ``test_e2e_ledger_m303_quarters_to_m390_annual``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
)
from cadrumo.application.modelo.calculation_note_gate import ModeloCalculationBlockedError
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.i18n.render import tr as render_tr
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.entrypoints.tests.profile_persistence.m303_annual_ledger_support import (
    _BUCKET_ID,
    _YEAR,
    PRORRATA_QUARTER_FACTS,
    persist_year_of_invoices,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.tests.env_scope import ready_clave_settings

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.modelo.tests.filed_observation_fixture import persist_filed_revision_observation
from .m303_m390_chain_support import (
    CASILLA_44,
    CASILLA_44_BINDING,
    CASILLA_45,
    DEDUCIBLE_TOTAL,
    FILE_AT,
    M390_DEDUCIBLE,
    M390_INTERIORES_CORRIENTES_CUOTA,
    M390_PRORRATA_REGULARIZACION,
    MANUAL_4T_CASILLA_45,
    MANUAL_4T_DEFINITIVE_DEDUCTION,
    MANUAL_EXCESO_DE_DEDUCCION,
    MANUAL_PRACTISED_DEDUCTIONS_1T_3T,
    MANUAL_YEAR_DEDUCTIONS,
    MANUAL_YEAR_INTERIORES_CORRIENTES_CUOTA,
    OPERATOR_SCOPE_PORTS,
    PRORRATA_VOLUMEN_CON_DERECHO,
    PRORRATA_VOLUMEN_TOTAL,
    QUARTER_ORDER,
    RESULTADO,
    SOPORTADO_INTERIORES,
    TAX_ID,
    TIER_SCREEN_REASONS,
    assert_form_states_no_figure,
    assert_verify_export_and_file_refused,
    bucket_id,
    calculate_and_file_m303_quarter,
    calculate_m303_quarter,
    calculate_m303_quarter_revision,
    calculate_m390_annual,
    save_general_prorrata_register,
    store_profile,
    tier_screen_reasons,
    verification_ports,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["bucket_id", "secure_objects"]


def test_general_prorrata_settles_in_the_fourth_quarter_and_folds_into_m390(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Ledger to M303 to M390 reproduces the AEAT manual's general prorrata regularisation.

    The first three quarters deduct at the provisional 73 %; the fourth quarter
    deducts its own cuotas at the definitive 56 % and regularises only the
    earlier quarters in casilla 44 (LIVA art. 105.Seis). The annual summary
    restates the settlement box and sums the per-period deductions.
    """
    store_profile(secure_objects)
    save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects,
        facts_by_period=PRORRATA_QUARTER_FACTS,
        received_rate_percent=Decimal("10"),
    )

    filed: dict[str, CalculationRevision] = {}
    for period in ("1T", "2T", "3T"):
        filed[period] = calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)
        casillas = filed[period].casilla_values
        assert Decimal(casillas[SOPORTADO_INTERIORES]) == MANUAL_PRACTISED_DEDUCTIONS_1T_3T[period]
        assert Decimal(casillas[CASILLA_44]) == Decimal("0.00")
    filed["4T"] = calculate_and_file_m303_quarter(
        secure_objects,
        period="4T",
        extra_casilla_inputs={
            PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"),
            PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00"),
        },
        operation=operation,
    )
    settlement = filed["4T"].casilla_values
    assert Decimal(settlement[SOPORTADO_INTERIORES]) == MANUAL_4T_DEFINITIVE_DEDUCTION
    assert Decimal(settlement[CASILLA_44]) == MANUAL_EXCESO_DE_DEDUCCION
    assert Decimal(settlement[CASILLA_45]) == MANUAL_4T_CASILLA_45

    year_deductions = sum((Decimal(filed[p].casilla_values[CASILLA_45]) for p in QUARTER_ORDER), Decimal("0"))
    assert year_deductions == MANUAL_YEAR_DEDUCTIONS

    annual = calculate_m390_annual(secure_objects, operation=operation)
    assert Decimal(annual.casilla_values[M390_PRORRATA_REGULARIZACION]) == MANUAL_EXCESO_DE_DEDUCCION
    assert Decimal(annual.casilla_values[M390_INTERIORES_CORRIENTES_CUOTA]) == (MANUAL_YEAR_INTERIORES_CORRIENTES_CUOTA)
    assert Decimal(annual.casilla_values[M390_DEDUCIBLE]) == MANUAL_YEAR_DEDUCTIONS


def test_settlement_quarter_without_filed_earlier_quarter_leaves_casilla_44_unresolved(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A missing first-quarter liquidation keeps the regularisation unresolved, never zero.

    The saved revision holds no figure for 44, nor for the deduction total [45]
    and the general-regime result [46] that sum it, and the unresolved-binding
    note refuses checking, exporting and recording the declaration.
    """
    store_profile(secure_objects)
    save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects,
        facts_by_period=PRORRATA_QUARTER_FACTS,
        received_rate_percent=Decimal("10"),
    )
    for period in ("2T", "3T"):
        calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)

    _work_unit, revision = calculate_m303_quarter_revision(
        secure_objects,
        period="4T",
        extra_casilla_inputs={
            PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"),
            PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00"),
        },
        operation=operation,
    )

    # The persisted unresolved-binding issue is what blocks verification and
    # filing of the box until a recalculation clears it.
    casilla_44_issues = tuple(
        issue
        for issue in revision.source_issues
        if issue.reason == "unresolved_binding" and issue.casilla_id == CASILLA_44
    )
    assert tuple(issue.message for issue in casilla_44_issues) == (
        render_tr("application.calculations.prorrata_regularizacion.unresolved.source_periods_missing", periods="1T"),
    )

    stored = CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(revision.calculation_revision_id)
    assert stored is not None
    observed = {observation.casilla_id for observation in stored.observations}
    for casilla_id in (CASILLA_44, CASILLA_45, DEDUCIBLE_TOTAL, RESULTADO):
        assert casilla_id not in stored.casilla_values
        assert casilla_id not in observed
    # The quarter's own deduction is still worked out at the definitive 56 %.
    assert Decimal(stored.casilla_values[SOPORTADO_INTERIORES]) == MANUAL_4T_DEFINITIVE_DEDUCTION
    assert_form_states_no_figure(secure_objects, (CASILLA_44, CASILLA_45), operation=operation)
    assert_verify_export_and_file_refused(secure_objects, revision, tmp_path, operation=operation)


def test_a_revision_saved_with_the_unresolved_44_as_zero_still_loads_unchanged(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A draft saved before unresolved bound boxes were left absent keeps its stored zero and still opens.

    Such a draft holds 44 as an ordinary zero beside its unresolved-binding
    note. Loading neither rejects nor rewrites it, its note still refuses the
    check, and the form still reads the box as not worked out.
    """
    store_profile(secure_objects)
    save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects,
        facts_by_period=PRORRATA_QUARTER_FACTS,
        received_rate_percent=Decimal("10"),
    )
    for period in ("2T", "3T"):
        calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)
    work_unit, current = calculate_m303_quarter_revision(
        secure_objects,
        period="4T",
        extra_casilla_inputs={
            PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"),
            PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00"),
        },
        operation=operation,
    )
    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period="4T")
    casilla_44 = next(casilla for casilla in snapshot.revision.casillas if casilla.id == CASILLA_44)
    stored_zero = current.model_copy(
        update={
            "casilla_values": {**current.casilla_values, CASILLA_44: Decimal("0.00")},
            "observations": (
                *current.observations,
                CasillaObservation(
                    casilla_id=CASILLA_44,
                    value=Decimal("0.00"),
                    legal_refs=casilla_44.legal_refs,
                    source_refs=casilla_44.source_refs,
                ),
            ),
        }
    )
    legacy = stored_zero.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(stored_zero)}
    )
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    catalogue = cr_repo.load()
    cr_repo.save(
        catalogue.model_copy(update={"revisions": {**catalogue.revisions, legacy.calculation_revision_id: legacy}})
    )
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    current_unit = wu_repo.load().get(work_unit.work_unit_id)
    assert current_unit is not None
    wu_repo.save(
        upsert_work_unit(
            wu_repo.load(),
            current_unit.model_copy(update={"current_calculation_revision_id": legacy.calculation_revision_id}),
        )
    )

    reloaded = CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(legacy.calculation_revision_id)
    assert reloaded is not None
    assert reloaded.casilla_values[CASILLA_44] == Decimal("0.00")
    assert reloaded.source_issues == current.source_issues
    assert_form_states_no_figure(secure_objects, (CASILLA_44,), operation=operation)
    with (
        bundled_indexed_authority().operation() as verify_operation,
        pytest.raises(ModeloCalculationBlockedError) as refusal,
    ):
        verify_modelo_revision_with_preconditions(
            legacy.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=verification_ports(
                operation=verify_operation,
                work_repo=wu_repo,
                calc_repo=CalculationRevisionCatalogueRepository(objects=secure_objects),
                filing_repo=ModeloRecordCatalogueRepository(objects=secure_objects),
                verification_repo=VerificationReportCatalogueRepository(objects=secure_objects),
                event_repo=BucketEventHistoryRepository(objects=secure_objects),
                tx_repo=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            ),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(TAX_ID),
            clock=FILE_AT,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=verify_operation,
        )
    assert (refusal.value.context or {})["reason"] == "unresolved_binding"


def test_a_register_prorrata_percentage_is_a_governed_source_and_raises_no_tier_divergence(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The register's provisional and definitive percentages apportion the deduction; no tier contests them.

    The percentage is read from the prorrata register and the 4T volumes are
    boxes no source resolves, so nothing holds a second value for any figure.
    The deductions still match the manual's printed figures, so the screen is
    silent on a calculation that did apply the register.
    """
    store_profile(secure_objects)
    save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects, facts_by_period=PRORRATA_QUARTER_FACTS, received_rate_percent=Decimal("10")
    )

    settled: BucketAggregationCalculationResult | None = None
    for period in QUARTER_ORDER:
        work_unit, result = calculate_m303_quarter(
            secure_objects,
            period=period,
            extra_casilla_inputs=(
                {PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"), PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00")}
                if period == "4T"
                else None
            ),
            operation=operation,
        )
        assert tier_screen_reasons(result) == set(), period
        expected = MANUAL_PRACTISED_DEDUCTIONS_1T_3T.get(period, MANUAL_4T_DEFINITIVE_DEDUCTION)
        assert Decimal(result.revision.casilla_values[SOPORTADO_INTERIORES]) == expected
        persist_filed_revision_observation(
            revision=result.revision,
            work_unit=work_unit,
            repository=CalculationObservationRepository(objects=secure_objects),
            captured_at=FILE_AT,
            result_disposition=ResultDisposition.INGRESO,
            iva_compensation_history_repository=IvaCompensationHistoryRepository(),
        )
        settled = result
    assert settled is not None
    assert Decimal(settled.revision.casilla_values[CASILLA_44]) == MANUAL_EXCESO_DE_DEDUCCION

    # The annual summary of a general-regime filer declares the simplified-regime
    # boxes, which their resolver settles as not applying rather than as zero.
    annual_bindings = published_authority_operation().snapshot("390", filing_year=_YEAR, period="0A").revision.bindings
    assert any(
        binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY for binding in annual_bindings
    )
    annual = calculate_m390_annual(secure_objects, operation=operation)
    assert {issue.reason for issue in annual.source_issues} & TIER_SCREEN_REASONS == set()
    assert Decimal(annual.casilla_values[M390_PRORRATA_REGULARIZACION]) == MANUAL_EXCESO_DE_DEDUCCION


def test_an_operator_value_over_an_unresolved_regularisation_raises_no_tier_divergence(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """With 1T unfiled the regularisation source states no value, so the operator's figure is a fill.

    The resolver leaves box 44 unresolved, the lower tier holds nothing, and the
    operator's value is used without a divergence being raised.
    """
    store_profile(secure_objects)
    save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects, facts_by_period=PRORRATA_QUARTER_FACTS, received_rate_percent=Decimal("10")
    )
    for period in ("2T", "3T"):
        calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)
    operator_value = Decimal("-150.00")

    _work_unit, result = calculate_m303_quarter(
        secure_objects,
        period="4T",
        extra_casilla_inputs={
            PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"),
            PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00"),
        },
        extra_binding_values={CASILLA_44_BINDING: operator_value},
        operation=operation,
    )

    assert tier_screen_reasons(result) == set()
    assert Decimal(result.revision.casilla_values[CASILLA_44]) == operator_value
