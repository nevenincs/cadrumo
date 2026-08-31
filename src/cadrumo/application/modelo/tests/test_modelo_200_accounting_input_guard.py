"""M200 refuses ledger-backed zero results without accounting-result input.

Modelo 200 currently derives base imponible from the operator's accounting
result casilla 00501, not from transaction-ledger taxable bases. These tests use
real repositories and the live calculate action to prove a legal-entity bucket
with business ledger rows cannot silently calculate a zero M200 merely because
00501 was omitted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import resolve_error_message
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ...tests import register_wizard_catalogue
from .._action_errors import ModeloAggregationBindingError
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


__all__ = ["register_wizard_catalogue"]

_BUCKET_ID = "2035baea-4afe-4fe3-b502-ff084fe79153"
_T0 = datetime(2026, 1, 14, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 14, 11, 0, tzinfo=UTC)
_M200 = "200"
_FILING_YEAR = 2025
_RESULTADO_CONTABLE: CasillaId = validated_casilla_id("00501", surface="_RESULTADO_CONTABLE")
_BASE_IMPONIBLE: CasillaId = validated_casilla_id("DP200014:00552", surface="_BASE_IMPONIBLE")
_CUOTA_EJERCICIO: CasillaId = validated_casilla_id("DP200014B:00599", surface="_CUOTA_EJERCICIO")


def _seed_m200_legal_entity_profile(objects: SecureObjectRepository) -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="Beatriz Test SL"),
            UserProfileFact(path="activities.description", value="software consultancy"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
            UserProfileFact(path="censo.activity_start_date", value="2024-01-01"),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"M200 ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(_FILING_YEAR, 6, 30),
                amount=amount,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "m200_accounting_reviewed",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": _T1,
            "classified_by": "manual",
        },
    )


def _seed_reviewed_business_ledger(tx_repo: TransactionCatalogueRepository) -> None:
    tx_repo.save(
        TransactionCatalogue.from_transactions(
            (
                _transaction(
                    "beatriz-income-100000",
                    direction=TransactionDirection.INCOMING,
                    amount=Decimal("121000.00"),
                    taxable_base=Decimal("100000.00"),
                    iva_amount=Decimal("21000.00"),
                ),
                _transaction(
                    "beatriz-expense-25000",
                    direction=TransactionDirection.OUTGOING,
                    amount=Decimal("30250.00"),
                    taxable_base=Decimal("25000.00"),
                    iva_amount=Decimal("5250.00"),
                ),
                _transaction(
                    "beatriz-expense-15000",
                    direction=TransactionDirection.OUTGOING,
                    amount=Decimal("18150.00"),
                    taxable_base=Decimal("15000.00"),
                    iva_amount=Decimal("3150.00"),
                ),
            ),
        ),
    )


def _create_m200_work_unit(work_unit_repository: WorkUnitCatalogueRepository):
    snapshot = bundled_authority().snapshot(
        _M200,
        filing_year=_FILING_YEAR,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M200,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=work_unit_repository,
        clock=_T0,
    )


def _calculate_m200(
    secure_objects: SecureObjectRepository,
    *,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
) -> tuple[BucketAggregationCalculationResult, CalculationRevisionCatalogueRepository]:
    _seed_m200_legal_entity_profile(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    _seed_reviewed_business_ledger(tx_repo)
    work_unit = _create_m200_work_unit(wu_repo)
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        actor="operator-Beatriz",
        casilla_inputs=casilla_inputs or {},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )
    return result, cr_repo


def test_m200_refuses_business_ledger_rows_without_accounting_result_input(
    secure_objects: SecureObjectRepository,
) -> None:
    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        _calculate_m200(secure_objects)

    error = exc_info.value
    message = resolve_error_message(error)
    assert "does not derive accounting profit from ledger transactions yet" in message
    assert "3 business ledger row(s)" in message
    assert error.context is not None
    assert error.context["required_casilla_id"] == _RESULTADO_CONTABLE
    assert error.context["ledger_transaction_count"] == 3
    failure = error.precondition_failure
    assert failure is not None
    assert failure.scenario_id == ("modelo.work.calculate.m200.accounting_result.ledger_rows_without_accounting_result")
    assert failure.verdict.no_recovery_outcome is not None


def test_m200_uses_explicit_accounting_result_even_when_reviewed_ledger_rows_exist(
    secure_objects: SecureObjectRepository,
) -> None:
    result, _cr_repo = _calculate_m200(
        secure_objects,
        casilla_inputs={_RESULTADO_CONTABLE: Decimal("60000.00")},
    )

    values = result.revision.casilla_values
    assert values[_BASE_IMPONIBLE] == Decimal("60000.00")
    # LIS DT 44a 2025 micro-empresa transitional scale: 50.000 x 21% + 10.000 x 22%
    # = 10.500 + 2.200 = 12.700.
    assert values[_CUOTA_EJERCICIO] == Decimal("12700.00")
    assert values[_CUOTA_EJERCICIO] != Decimal("0.00")
