"""Modelo 390's simplified-regime boxes are reported unworked only for a filer the regime reaches.

Boxes 74 to 83 of every Modelo 390 carry the simplified regime's annual summary,
drawn from the filer's filed Modelo 303 for the fourth quarter. A filer whose
profile declares the general regime has nothing to put there (LIVA art. 122 Uno
reaches only filers who meet its requirements), so the calculation must not tell
them those printed boxes could not be worked out. A filer whose profile declares
the simplified regime and has no filed source is refused outright: the gap is
real and stays loud.

Real encrypted catalogues, real registry snapshot, the live calculation mesh.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.calculations.m303_regimen_simplificado_annual_summary import (
    M303RegimenSimplificadoAnnualSummaryHandoffError,
)
from cadrumo.application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "39000000-0000-4000-8000-000000000392"
_YEAR = 2025
_T0 = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
_SUMMARY = BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _seed_profile(*, iva_regime: str, composition: str, estimation_regime: str) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value=iva_regime),
                UserProfileFact(path="iva.m303_regime_composition", value=composition),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value=estimation_regime),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        )
    )


def _calculate_m390(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    work_units = WorkUnitCatalogueRepository(objects=secure_objects)
    calculations = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filings = ModeloRecordCatalogueRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot("390", filing_year=_YEAR, period="0A")
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="390",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=work_units,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            operation=operation,
            clock=_T0,
        )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=calculations,
        filing_repository=filings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        work_unit_repository=work_units,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values={},
            ports=ports,
            clock=_T1,
        )


def test_a_general_regime_filer_is_not_told_the_simplified_boxes_are_missing(
    secure_objects: SecureObjectRepository,
) -> None:
    _seed_profile(iva_regime="GENERAL", composition="general", estimation_regime="directa_normal")
    summary_bindings = {
        binding.id
        for binding in published_authority_operation().snapshot("390", filing_year=_YEAR, period="0A").revision.bindings
        if binding.source is _SUMMARY
    }
    assert len(summary_bindings) == 10, "Modelo 390 declares boxes 74 to 83 from the simplified summary"

    result = _calculate_m390(secure_objects)

    assert not [diagnostic for diagnostic in result.source_diagnostics if diagnostic.source_kind == _SUMMARY.value]
    assert not [issue for issue in result.revision.source_issues if issue.binding_source is _SUMMARY]
    assert result.revision.m303_regimen_simplificado_annual_summary_handoff is None


def test_a_simplified_regime_filer_without_its_filed_fourth_quarter_is_refused(
    secure_objects: SecureObjectRepository,
) -> None:
    """Teeth for the case above: when the regime does reach the filer, the absent source refuses the calculation."""
    _seed_profile(iva_regime="SIMPLIFICADO", composition="simplified", estimation_regime="objetiva")

    with pytest.raises(M303RegimenSimplificadoAnnualSummaryHandoffError):
        _calculate_m390(secure_objects)
