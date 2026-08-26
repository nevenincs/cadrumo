"""Sofia's M100/2025 annual expense inspection must survive work creation.

This regression exercises the live application path that was blocked before any
Modelo 100 calculation could run: work-unit creation for revision 2025, followed
by the bucket-aggregation calculate that fills source-owned annual expense
casillas from real ledger transactions.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.ids import BindingId

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.categories import SpendingCategory
from ....domain.invoices import InvoiceCatalogue
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from .._work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "76634915-7e84-4db9-9c06-0c67ad5a164d"
_YEAR = 2025
_ANNUAL_PERIOD = "0A"
_REVISION_ID = "2025"
_T0 = datetime(2026, 6, 29, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 6, 29, 11, 0, tzinfo=UTC)

_M100_SS_CASILLA: CasillaId = validated_casilla_id("0186", surface="_M100_SS_CASILLA")
_M100_OTHER_EXPENSES_CASILLA: CasillaId = validated_casilla_id(
    "0199",
    surface="_M100_OTHER_EXPENSES_CASILLA",
)
_M100_2024_NEGATIVE_GENERAL_BASE_CARRY_CASILLA: CasillaId = validated_casilla_id(
    "1391",
    surface="_M100_2024_NEGATIVE_GENERAL_BASE_CARRY_CASILLA",
)
_ESTIMACION_DIRECTA_NORMAL_BINDING: BindingId = "renta-2025-modelo-100-estimacion-directa-es-normal"
_M100_SS_BINDING: BindingId = "renta-2025-ledger-expense-0186-deductible"
_M100_OTHER_EXPENSES_BINDING: BindingId = "renta-2025-ledger-expense-0199-deductible"

_AUTO_RESOLVED_SOURCES = frozenset(
    {
        "profile",
        "relation_prefill",
        "ledger_renta_gastos_estimacion_directa_aggregation",
        "ledger_renta_income_aggregation",
        "ledger_iva_aggregation",
        "ledger_oss_aggregation",
        "collectible_invoice",
        "payable_invoice",
    },
)


def _seed_sofia_profile(objects: SecureObjectRepository) -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Sofia"),
            UserProfileFact(path="identity.surnames", value="Expense Inspector"),
            UserProfileFact(path="activities.description", value="professional services"),
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
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="M"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _raw_transaction(provider_id: str, *, value_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=value_date,
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty="Sofia counterparty",
        description=f"Sofia M100 inspection row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="4" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_T0,
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _expense_transaction(
    provider_id: str,
    *,
    category: SpendingCategory,
    value_date: date,
    gross_amount: Decimal,
    taxable_base: Decimal,
    iva_rate: Decimal,
    iva_amount: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, value_date=value_date, amount=gross_amount),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": category.value,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _seed_sofia_ledger(objects: SecureObjectRepository) -> tuple[Transaction, ...]:
    transactions = (
        _expense_transaction(
            "sofia-autonomos-ss",
            category=SpendingCategory.CUOTAS_AUTONOMOS_SS,
            value_date=date(_YEAR, 2, 15),
            gross_amount=Decimal("340.00"),
            taxable_base=Decimal("340.00"),
            iva_rate=Decimal("0"),
            iva_amount=Decimal("0"),
        ),
        _expense_transaction(
            "sofia-advisory-taxable-base",
            category=SpendingCategory.ASESORIA_FISCAL,
            value_date=date(_YEAR, 2, 20),
            gross_amount=Decimal("6776.00"),
            taxable_base=Decimal("5600.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("1176.00"),
        ),
    )
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions(transactions),
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(InvoiceCatalogue())
    return transactions


def _seed_prior_year_m100_zero_carry(objects: SecureObjectRepository) -> None:
    CalculationObservationRepository(objects=objects).save(
        CalculationObservationRepository(objects=objects).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=2024,
                period=_ANNUAL_PERIOD,
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=2024,
                    period=_ANNUAL_PERIOD,
                    casilla_values={_M100_2024_NEGATIVE_GENERAL_BASE_CARRY_CASILLA: Decimal("0")},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )


def _m100_caller_zero_bindings() -> dict[BindingId, Decimal]:
    snapshot = bundled_authority().snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    values = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if str(binding.source) not in _AUTO_RESOLVED_SOURCES
    }
    values[_ESTIMACION_DIRECTA_NORMAL_BINDING] = Decimal("1")
    return values


def test_sofia_m100_2025_work_create_and_calculate_exposes_0186_and_0199(
    secure_objects: SecureObjectRepository,
) -> None:
    """Work create must not treat the M100 modalidad selector as export layout."""
    _seed_sofia_profile(secure_objects)
    transactions = _seed_sofia_ledger(secure_objects)
    _seed_prior_year_m100_zero_carry(secure_objects)

    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    # This was Sofia's blocker: resolving/creating M100/2025 work raised the
    # internal export-selector projection error before a calculation existed.
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        revision_id=_REVISION_ID,
        repository=wu_repo,
        clock=_T0,
    )

    snapshot = bundled_authority().snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    binding_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    assert str(binding_by_id[_M100_SS_BINDING].source) == "ledger_renta_gastos_estimacion_directa_aggregation"
    assert (
        str(binding_by_id[_M100_OTHER_EXPENSES_BINDING].source) == "ledger_renta_gastos_estimacion_directa_aggregation"
    )

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        actor="operator-sofia",
        binding_values=_m100_caller_zero_bindings(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert isinstance(result, BucketAggregationCalculationResult)
    values = result.revision.casilla_values
    assert Decimal(values[_M100_SS_CASILLA]) == Decimal("340.00")
    assert Decimal(values[_M100_OTHER_EXPENSES_CASILLA]) == Decimal("5600.00")
    assert Decimal(values[_M100_SS_CASILLA]) + Decimal(values[_M100_OTHER_EXPENSES_CASILLA]) == Decimal("5940.00")
    assert set(result.revision.source_transaction_ids) >= {transaction.transaction_id for transaction in transactions}
    assert not any(
        diagnostic.source_kind == "ledger_renta_gastos_estimacion_directa_aggregation"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
