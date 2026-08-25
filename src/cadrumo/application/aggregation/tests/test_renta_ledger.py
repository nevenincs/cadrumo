"""Tests for repository-backed Renta ledger expense aggregation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from ._secure_objects_fixtures import SECURE_OBJECTS_BUCKET_ID, secure_objects

__all__ = ["secure_objects"]

from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.profile.usage_ratios import save_usage_ratios
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, ProrrataProvisionalProvenance, ProrrataRegisterRegime, validated_casilla_id
from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ....core.i18n import Translatable as tr
from ....domain.categories import (
    CategoryCitation,
    CategoryCitationSource,
    CategoryProfile,
    ProportionalityKind,
    ProportionalityRule,
    SpendingCategory,
    parse_http_url,
)
from ....domain.contribuyente import CCAA
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind
from ....domain.prorrata_register import ProrrataRegisterEntry
from ....domain.renta import RentaExpenseDirection
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
from ....domain.usage_ratios import UsageRatioProfile
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import RENTA_REGIMEN_CITATION_URL_FIXTURE
from ....tests.secure_sql import isolated_two_bucket_runtime
from .. import (
    AggregationValidationError,
    CalculationSourceContext,
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    RentaLedgerAggregationIssueReason,
    RentaLedgerExpenseAggregation,
    aggregate_renta_ledger_expenses,
    aggregate_renta_ledger_expenses_from_repositories,
)
from .._renta_gasto_ledger import aggregate_renta_gasto_ledger_from_repositories
from ._renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m100_renta_expense_binding(binding_id: str, casilla_id: str) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=binding_id,
        source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        selector={
            "modelo": "100",
            "period": "0A",
            "target_casilla_id": casilla_id,
            "fact": "deductible_amount_sum",
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-35-2006:art-28", "ley-35-2006:art-30"),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )


def _m100_2025_renta_expense_revision() -> ModeloRevision:
    return ModeloRevision(
        id="2025",
        localization_key="test.schema.revision.2025.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2025,), periods=("0A",)),
        legal_refs=("ley-35-2006:art-28", "ley-35-2006:art-30"),
        source_refs=("aeat-renta-2025-manual-parte1",),
        bindings=(
            _m100_renta_expense_binding("renta-2025-ledger-expense-0186-deductible", "0186"),
            _m100_renta_expense_binding("renta-2025-ledger-expense-0192-deductible", "0192"),
            _m100_renta_expense_binding("renta-2025-ledger-expense-0199-deductible", "0199"),
            _m100_renta_expense_binding("renta-2025-ledger-expense-0203-deductible", "0203"),
        ),
    )


_ANNUAL_2025 = _period(2025, "0A")
_Q1_2025 = _period(2025, "1T")
_M100_ASESORIA_CASILLA: CasillaId = validated_casilla_id("0199", surface="_M100_ASESORIA_CASILLA")
_M100_GASTOS_FINANCIEROS_CASILLA: CasillaId = validated_casilla_id(
    "0203",
    surface="_M100_GASTOS_FINANCIEROS_CASILLA",
)
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2025, 4, 5),
    value_date: date | None = date(2025, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Proveedor SL",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _transaction(
    provider_id: str,
    *,
    amount: Decimal = Decimal("121.00"),
    category: SpendingCategory = SpendingCategory.ASESORIA_FISCAL,
    purchase_invoice_evidence_id: str | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    booked_date: date = date(2025, 4, 5),
    value_date: date | None = date(2025, 4, 5),
    currency: str = "EUR",
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": purchase_invoice_evidence_id,
            "category_id": category.value,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _invoice(
    tx_id: str,
    *,
    bucket_id: str = SECURE_OBJECTS_BUCKET_ID,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    issued_at: date = date(2025, 4, 1),
    grand_total: Decimal = Decimal("121.00"),
    linked_transaction_ids: tuple[str, ...] | None = None,
) -> Invoice:
    base_total = grand_total - Decimal("21.00")
    line = InvoiceLine(
        description="Asesoria fiscal",
        quantity=Decimal("1"),
        unit_price=base_total,
        subtotal=base_total,
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": kind,
            "invoice_number": f"INV-{tx_id[:8]}",
            "issued_at": issued_at,
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": base_total,
            "iva_total": Decimal("21.00"),
            "grand_total": grand_total,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids if linked_transaction_ids is not None else (tx_id,),
        },
    )


def test_repository_backed_aggregation_loads_persisted_catalogues_and_emits_casilla_values(
    secure_objects: SecureObjectRepository,
) -> None:
    initial = _transaction("row-linked")
    invoice = _invoice(initial.transaction_id)
    linked = _transaction("row-linked", purchase_invoice_evidence_id=invoice.invoice_id)
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((linked,)))
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.casilla_values == {_M100_ASESORIA_CASILLA: invoice.base_total}
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.transaction_id == linked.transaction_id
    assert observation.invoice_id == invoice.invoice_id
    assert observation.filing_date == date(2025, 4, 1)
    assert observation.taxable_base == Decimal("100.00")
    assert observation.iva_amount == Decimal("21.00")
    assert observation.deductible_amount == invoice.base_total
    assert result.casilla_aggregation.provenance[0].transaction_ids == (linked.transaction_id,)


def test_repository_backed_aggregation_binds_default_invoice_repository_to_requested_bucket(
    secure_objects: SecureObjectRepository,
) -> None:
    initial = _transaction("row-default-invoice-repository")
    invoice = _invoice(initial.transaction_id)
    linked = _transaction(
        "row-default-invoice-repository",
        purchase_invoice_evidence_id=invoice.invoice_id,
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((linked,)),
    )
    InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        InvoiceCatalogue.from_invoices((invoice,)),
    )

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.observations[0].invoice_id == invoice.invoice_id
    assert result.casilla_values == {_M100_ASESORIA_CASILLA: invoice.base_total}


def test_renta_filing_aggregation_resolves_registry_bound_inputs(secure_objects: SecureObjectRepository) -> None:
    """The LedgerRentaGastosEstimacionDirectaAggregationSourceResolver resolves modelo-100 renta-expense
    ledger bindings from repository-backed transactions, keyed by binding id."""
    transaction = _transaction(
        "row-cli-renta",
        amount=Decimal("121.00"),
        category=SpendingCategory.ASESORIA_FISCAL,
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))
    invoice_repo.save(InvoiceCatalogue())

    revision = _m100_2025_renta_expense_revision()
    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    ).resolve(
        CalculationSourceContext(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )
    binding_values = resolution.binding_values

    assert binding_values["renta-2025-ledger-expense-0199-deductible"] == Decimal("121.00")
    assert binding_values["renta-2025-ledger-expense-0186-deductible"] == Decimal("0")
    assert binding_values["renta-2025-ledger-expense-0192-deductible"] == Decimal("0")
    assert binding_values["renta-2025-ledger-expense-0203-deductible"] == Decimal("0")


def test_renta_filing_aggregation_routes_office_software_and_marketing_to_m100_expenses(
    secure_objects: SecureObjectRepository,
) -> None:
    """Ordinary business operating costs must not disappear from M100."""
    transactions = (
        _transaction(
            "row-office",
            amount=Decimal("240.00"),
            category=SpendingCategory.MATERIAL_OFICINA,
        ),
        _transaction(
            "row-software",
            amount=Decimal("360.00"),
            category=SpendingCategory.SOFTWARE_SUSCRIPCION,
        ),
        _transaction(
            "row-marketing",
            amount=Decimal("180.00"),
            category=SpendingCategory.PUBLICIDAD_MARKETING,
        ),
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))
    invoice_repo.save(InvoiceCatalogue())

    revision = _m100_2025_renta_expense_revision()
    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    ).resolve(
        CalculationSourceContext(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )

    assert resolution.diagnostics == ()
    assert resolution.binding_values["renta-2025-ledger-expense-0199-deductible"] == Decimal("780.00")


def test_renta_filing_aggregation_loads_usage_ratios_for_mobile_phone_expenses(
    secure_objects: SecureObjectRepository,
) -> None:
    """The live source resolver must consume persisted proportionality ratios."""
    phone = _transaction(
        "row-phone",
        amount=Decimal("121.00"),
        category=SpendingCategory.TELEFONIA_MOVIL,
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((phone,)),
    )
    InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.50")}),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        objects=secure_objects,
    )

    revision = _m100_2025_renta_expense_revision()
    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    ).resolve(
        CalculationSourceContext(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )

    assert resolution.diagnostics == ()
    assert resolution.binding_values["renta-2025-ledger-expense-0199-deductible"] == Decimal("60.50")
    assert resolution.source_transaction_ids == (phone.transaction_id,)


def test_m100_expense_aggregation_uses_taxable_base_for_iva_bearing_business_expenses(
    secure_objects: SecureObjectRepository,
) -> None:
    """Sofia's ordinary IVA-bearing expenses feed M100 by base, not cash gross."""
    office_base, software_base, marketing_base = Decimal("700.00"), Decimal("600.00"), Decimal("800.00")
    transactions = (
        _transaction(
            "sofia-office",
            amount=Decimal("847.00"),
            category=SpendingCategory.MATERIAL_OFICINA,
            booked_date=date(2025, 2, 3),
            value_date=date(2025, 2, 3),
            taxable_base=office_base,
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("147.00"),
        ),
        _transaction(
            "sofia-software",
            amount=Decimal("726.00"),
            category=SpendingCategory.SOFTWARE_SUSCRIPCION,
            booked_date=date(2025, 2, 4),
            value_date=date(2025, 2, 4),
            taxable_base=software_base,
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("126.00"),
        ),
        _transaction(
            "sofia-marketing",
            amount=Decimal("968.00"),
            category=SpendingCategory.PUBLICIDAD_MARKETING,
            booked_date=date(2025, 2, 5),
            value_date=date(2025, 2, 5),
            taxable_base=marketing_base,
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("168.00"),
        ),
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))
    InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    expected_taxable_base = office_base + software_base + marketing_base
    gross_cash = sum((transaction.raw.amount for transaction in transactions), Decimal("0"))
    assert result.issues == ()
    assert result.casilla_values[_M100_ASESORIA_CASILLA] == expected_taxable_base
    assert result.casilla_values[_M100_ASESORIA_CASILLA] != gross_cash


def test_m100_and_m130_expense_aggregations_reconcile_on_taxable_base_for_same_ledger_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """The annual M100 expense basis matches M130's taxable-base gasto basis."""
    bases = (Decimal("700.00"), Decimal("600.00"), Decimal("800.00"))
    transactions = (
        _transaction(
            "shared-office",
            amount=Decimal("847.00"),
            category=SpendingCategory.MATERIAL_OFICINA,
            booked_date=date(2025, 1, 15),
            value_date=date(2025, 1, 15),
            taxable_base=bases[0],
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("147.00"),
        ),
        _transaction(
            "shared-software",
            amount=Decimal("726.00"),
            category=SpendingCategory.SOFTWARE_SUSCRIPCION,
            booked_date=date(2025, 2, 15),
            value_date=date(2025, 2, 15),
            taxable_base=bases[1],
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("126.00"),
        ),
        _transaction(
            "shared-marketing",
            amount=Decimal("968.00"),
            category=SpendingCategory.PUBLICIDAD_MARKETING,
            booked_date=date(2025, 3, 15),
            value_date=date(2025, 3, 15),
            taxable_base=bases[2],
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("168.00"),
        ),
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))
    InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())

    m100_result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )
    m130_result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    expected_taxable_base = sum(bases, Decimal("0"))
    gross_cash = sum((transaction.raw.amount for transaction in transactions), Decimal("0"))
    m100_value = m100_result.casilla_values[_M100_ASESORIA_CASILLA]
    m130_value = m130_result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA]

    assert m100_result.issues == ()
    assert m130_result.issues == ()
    assert m100_value == expected_taxable_base
    assert m130_value == expected_taxable_base
    assert m100_value == m130_value
    assert m100_value != gross_cash


def test_repository_backed_aggregation_rejects_transaction_repository_bucket_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    repo = TransactionCatalogueRepository(bucket_id="other", objects=secure_objects)

    with pytest.raises(AggregationValidationError, match="bucket"):
        aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=repo,
            invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
            profile_year=2025,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )


def test_repository_backed_aggregation_rejects_invoice_repository_bucket_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id="other", objects=secure_objects)

    with pytest.raises(AggregationValidationError, match="invoice_bucket_mismatch"):
        aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            profile_year=2025,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )


def test_repository_backed_aggregation_rejects_unbound_invoice_repository(
    secure_objects: SecureObjectRepository,
) -> None:
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)

    with pytest.raises(AggregationValidationError, match="invoice_bucket_mismatch"):
        aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            profile_year=2025,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )


def test_mixed_business_percentage_scales_transaction_only_expenses() -> None:
    mixed = _transaction(
        "row-mixed",
        amount=Decimal("200.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.25"),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((mixed,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.casilla_values == {_M100_GASTOS_FINANCIEROS_CASILLA: Decimal("50.0000")}
    assert result.observations[0].gross_amount == Decimal("50.0000")
    assert result.observations[0].deductible_amount == Decimal("50.0000")


def test_archived_and_stashed_transactions_do_not_feed_renta_expense_aggregation() -> None:
    active = _transaction(
        "row-active",
        amount=Decimal("100.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
    )
    archived = _transaction(
        "row-archived",
        amount=Decimal("500.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    stashed = _transaction(
        "row-stashed",
        amount=Decimal("700.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        lifecycle_state=TransactionLifecycleState.STASHED,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((active, archived, stashed)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert [observation.transaction_id for observation in result.observations] == [active.transaction_id]
    assert result.casilla_values == {_M100_GASTOS_FINANCIEROS_CASILLA: Decimal("100.00")}


def test_manual_transaction_tax_fields_feed_renta_observation_without_invoice_catalogue() -> None:
    manual = _transaction(
        "manual-tax-fields",
        amount=Decimal("121.00"),
        category=SpendingCategory.ASESORIA_FISCAL,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((manual,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.observations[0].taxable_base == Decimal("100.00")
    assert result.observations[0].iva_amount == Decimal("21.00")
    assert result.observations[0].deductible_amount == Decimal("100.00")
    assert result.casilla_values == {_M100_ASESORIA_CASILLA: Decimal("100.00")}


def test_usage_ratio_phone_requires_ratio_before_routing_to_other_expenses() -> None:
    phone = _transaction(
        "phone",
        category=SpendingCategory.TELEFONIA_MOVIL,
    )

    missing_ratio = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((phone,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert missing_ratio.observations == ()
    assert missing_ratio.issues[0].reason is RentaLedgerAggregationIssueReason.INELIGIBLE_DEDUCTIBILITY
    assert "missing usage ratio" in missing_ratio.issues[0].detail

    with_ratio = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((phone,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        usage_ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.25")},
    )

    assert with_ratio.issues == ()
    assert with_ratio.observations[0].deductible_amount == Decimal("30.2500")
    assert with_ratio.casilla_values == {_M100_ASESORIA_CASILLA: Decimal("30.2500")}


def test_linked_invoice_issue_date_controls_period_filtering() -> None:
    initial = _transaction("row-outside")
    invoice = _invoice(initial.transaction_id, issued_at=date(2024, 12, 31))
    linked = _transaction("row-outside", purchase_invoice_evidence_id=invoice.invoice_id)

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((linked,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert result.issues[0].transaction_id == linked.transaction_id


def test_repository_backed_aggregation_admits_a_transaction_whose_invoice_date_is_in_window_but_own_date_is_not(
    secure_objects: SecureObjectRepository,
) -> None:
    """Regression test: a transaction whose OWN filing date falls outside the
    requested annual window but whose LINKED INVOICE's issue date falls inside it must not
    be silently dropped before the classifier ever runs.

    ``aggregate_renta_ledger_expenses_from_repositories`` used to pre-filter the loaded
    catalogue via ``TransactionCatalogueRepository.load_for_date_range``, keyed ONLY on the
    transaction's own ``value_date``/``booked_date`` (the same field the plaintext date
    index stores). But the aggregation's own ``OUTSIDE_PERIOD`` classification uses
    ``RentaDeductibleExpenseFact.filing_date``, which PREFERS the linked invoice's
    ``issue_date`` over the transaction's own date (see
    ``domain.renta.RentaDeductibleExpenseFact.filing_date``). When a transaction's own date
    fell OUTSIDE the requested window but its invoice's issue date fell INSIDE it, the
    pre-filter excluded the row from the loaded catalogue before the aggregation ever ran --
    so instead of correctly admitting the expense (by invoice date), it silently disappeared
    with NO observation and NO issue at all. Reverting the pre-filter to a full
    ``repository.load()`` (mirroring ``_iva_ledger`` / ``_renta_income_ledger`` /
    ``_renta_gasto_ledger`` / ``_impatriado_income_ledger``) closes the gap: the classifier
    now sees every row and correctly admits this one by its invoice-issue-date filing_date.
    """
    # Transaction's own date (2024-12-15) is OUTSIDE the 2025 annual window; a
    # pre-filtering repository read would have excluded it before the
    # aggregation ever ran. Its linked invoice's issue date (2025-01-10) is
    # INSIDE the window -- by the aggregation's own filing_date rule this
    # expense must be admitted as a real observation, not silently dropped.
    own_date_outside_invoice_date_inside = _transaction(
        "row-own-date-outside",
        booked_date=date(2024, 12, 15),
        value_date=date(2024, 12, 15),
    )
    invoice = _invoice(
        own_date_outside_invoice_date_inside.transaction_id,
        issued_at=date(2025, 1, 10),
    )
    linked = _transaction(
        "row-own-date-outside",
        booked_date=date(2024, 12, 15),
        value_date=date(2024, 12, 15),
        purchase_invoice_evidence_id=invoice.invoice_id,
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((linked,)))
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert len(result.observations) == 1
    assert result.observations[0].transaction_id == linked.transaction_id
    assert result.issues == ()


def test_repository_backed_aggregation_reports_out_of_period_catalogue_transactions_across_years(
    secure_objects: SecureObjectRepository,
) -> None:
    """A catalogue transaction from a different year must surface as an OUTSIDE_PERIOD issue.

    Regression test: the repository-backed entry point must NOT pre-filter the
    loaded catalogue by date range for a multi-year catalogue. ``OUTSIDE_PERIOD`` is a genuine
    no-silent-under-declaration-class diagnostic -- an operator running a 10-year ledger history
    against the 2025 annual window needs to see that a 2023-dated catalogue transaction exists
    and was excluded, not have it silently vanish before the classifier ever runs (mirroring
    ``test_iva_ledger.py::test_repository_backed_projection_reports_out_of_period_catalogue_transactions``).
    """
    in_year = _transaction("row-in-2025", booked_date=date(2025, 4, 5), value_date=date(2025, 4, 5))
    out_of_year = _transaction("row-in-2023", booked_date=date(2023, 6, 10), value_date=date(2023, 6, 10))
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((in_year, out_of_year)))

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert {o.transaction_id for o in result.observations} == {in_year.transaction_id}
    assert len(result.issues) == 1
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert result.issues[0].transaction_id == out_of_year.transaction_id


def test_multi_transaction_invoice_link_is_excluded_from_first_slice() -> None:
    first = _transaction("row-partial-a")
    second = _transaction("row-partial-b", amount=Decimal("60.50"))
    invoice = _invoice(first.transaction_id, linked_transaction_ids=(first.transaction_id, second.transaction_id))
    linked = _transaction("row-partial-a", purchase_invoice_evidence_id=invoice.invoice_id)

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((linked,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert (
        result.issues[0].reason
        is RentaLedgerAggregationIssueReason.PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE
    )


def test_purchase_invoice_evidence_from_other_bucket_is_reported_as_issue() -> None:
    initial = _transaction("row-cross-bucket")
    invoice = _invoice(initial.transaction_id, bucket_id="other")
    linked = _transaction("row-cross-bucket", purchase_invoice_evidence_id=invoice.invoice_id)

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((linked,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH
    assert result.issues[0].purchase_invoice_evidence_id == invoice.invoice_id


def test_linked_incoming_refund_becomes_negative_binding_value() -> None:
    initial = _transaction(
        "row-refund",
        amount=Decimal("121.00"),
        direction=TransactionDirection.INCOMING,
    )
    invoice = _invoice(initial.transaction_id)
    refund = _transaction(
        "row-refund",
        amount=Decimal("121.00"),
        purchase_invoice_evidence_id=invoice.invoice_id,
        direction=TransactionDirection.INCOMING,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((refund,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.observations[0].direction is RentaExpenseDirection.REFUND
    assert result.casilla_values == {_M100_ASESORIA_CASILLA: -invoice.base_total}


def test_transaction_only_renta_expense_buckets_on_value_date_caja_basis() -> None:
    """Document the CAJA-only basis for a transaction-only (un-invoiced) expense.

    For a Renta expense with no linked invoice, the first-slice ``filing_date``
    falls back to ``operation_date`` = ``value_date or booked_date`` — a CASH
    (caja) basis. There is no accrual/devengo basis selector.

    This pins the current behaviour as the regression anchor for a future
    devengo addition: the row whose VALUE_DATE lands in the tax year is
    aggregated; the mirror row whose value_date is outside (but booked_date
    inside) is excluded. A devengo basis would invert both outcomes.

    Note ``test_linked_invoice_issue_date_controls_period_filtering`` covers the
    *linked-invoice* branch, where the invoice issue date (not the payment date)
    drives period selection — that is invoice-date provenance, NOT an accrual
    basis selector. This test covers the un-invoiced branch where caja governs.
    """
    # value_date in-year (caja), booked_date in the prior year (devengo would differ).
    caja_in_year = _transaction(
        "row-caja-in-year",
        amount=Decimal("100.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        booked_date=date(2024, 12, 31),
        value_date=date(2025, 1, 2),
        purchase_invoice_evidence_id=None,
    )
    # value_date in the prior year (caja), booked_date in-year (devengo would include).
    caja_out_of_year = _transaction(
        "row-caja-out-of-year",
        amount=Decimal("100.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        booked_date=date(2025, 1, 2),
        value_date=date(2024, 12, 31),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((caja_in_year, caja_out_of_year)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    # Caja basis: only the row whose VALUE_DATE is in-year is aggregated, and the
    # observation's filing_date is that value_date (operation_date fallback).
    assert [observation.transaction_id for observation in result.observations] == [caja_in_year.transaction_id]
    assert result.observations[0].filing_date == date(2025, 1, 2)
    assert result.casilla_values == {_M100_GASTOS_FINANCIEROS_CASILLA: Decimal("100.00")}
    # The mirror row is excluded keyed on value_date — a devengo basis
    # (booked_date 2025-01-02) would instead have INCLUDED it.
    assert [issue.transaction_id for issue in result.issues] == [caja_out_of_year.transaction_id]
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert "2024-12-31" in result.issues[0].detail


def test_non_eur_transaction_is_reported_as_issue_before_fact_creation() -> None:
    usd_expense = _transaction(
        "row-usd",
        category=SpendingCategory.GASTOS_BANCARIOS,
        purchase_invoice_evidence_id=None,
        currency="USD",
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((usd_expense,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY


def test_zero_business_amount_is_reported_as_invalid_fact_issue() -> None:
    zero_business = _transaction(
        "row-zero-business",
        amount=Decimal("200.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0"),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((zero_business,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT


# ---------------------------------------------------------------------------
# Territorial-regime region-scoped deductibility (region-Renta D1/D2/D4)
# ---------------------------------------------------------------------------


def _region_override_profile(category: SpendingCategory) -> CategoryProfile:
    """A SYNTHETIC per-comunidad override profile for wiring tests only.

    Fixed 50% deductibility, distinct from the GASTOS_BANCARIOS state profile
    (full deductible), so a selection is observable. This is a test double for
    the SELECTION MECHANISM, never a real territorial-regime figure.
    """
    return CategoryProfile(
        category=category,
        display_label=tr("Override territorial de prueba"),
        proportionality=ProportionalityRule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            fixed_pct=Decimal("0.50"),
            citations=(
                CategoryCitation(
                    source=CategoryCitationSource.MANUAL_RENTA,
                    reference="Regla de prueba territorial",
                    locator="test",
                    url=parse_http_url(RENTA_REGIMEN_CITATION_URL_FIXTURE),
                    quote=tr("Texto de prueba para override territorial."),
                ),
            ),
            notes=tr("Override territorial de prueba."),
        ),
    )


def test_non_regional_category_profile_preserves_result_across_region() -> None:
    """With the empty override layer, the residence CCAA is inert.

    A category with no territorial-regime override produces byte-identical
    observations whether the residence comunidad is declared or not.
    """
    row = _transaction("row-region-inert", amount=Decimal("100.00"), category=SpendingCategory.GASTOS_BANCARIOS)
    catalogue = TransactionCatalogue.from_transactions((row,))

    without_region = aggregate_renta_ledger_expenses(
        catalogue, InvoiceCatalogue(), bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_ANNUAL_2025, profile_year=2025
    )
    with_region = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        residence_ccaa=CCAA.MADRID,
    )

    assert with_region.observations == without_region.observations
    assert with_region.casilla_values == without_region.casilla_values
    assert with_region.issues == without_region.issues == ()


def test_region_override_selected_when_residence_matches() -> None:
    """A declared residence with a territorial override selects the override.

    The synthetic 50% override for the residence comunidad halves the deductible
    versus the full-deductible state profile, proving selection by CCAA.
    """
    row = _transaction("row-region-hit", amount=Decimal("100.00"), category=SpendingCategory.GASTOS_BANCARIOS)
    overrides = {
        CCAA.CANARIAS: {SpendingCategory.GASTOS_BANCARIOS: _region_override_profile(SpendingCategory.GASTOS_BANCARIOS)}
    }

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((row,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        residence_ccaa=CCAA.CANARIAS,
        region_category_overrides=overrides,
    )

    assert result.issues == ()
    assert result.observations[0].proportionality_kind is ProportionalityKind.FIXED_PERCENTAGE
    assert result.observations[0].deductible_amount == Decimal("50.0000")


def test_region_override_undeclared_residence_fails_closed() -> None:
    """A category carrying an override with no declared residence fails closed."""
    row = _transaction("row-region-undeclared", amount=Decimal("100.00"), category=SpendingCategory.GASTOS_BANCARIOS)
    overrides = {
        CCAA.CANARIAS: {SpendingCategory.GASTOS_BANCARIOS: _region_override_profile(SpendingCategory.GASTOS_BANCARIOS)}
    }

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((row,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        residence_ccaa=None,
        region_category_overrides=overrides,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.REGION_UNDECLARED_FOR_OVERRIDE


# ---------------------------------------------------------------------------
# Residence CCAA derived from the active profile at the repository boundary.
# ---------------------------------------------------------------------------


def _profile_with_ccaa(ccaa_value: str | None) -> UserProfileRecord:
    """A user profile carrying an optional ``tax_residence.ccaa`` fact."""
    facts = (UserProfileFact(path="identity.tax_id", value="X1234567L"),)
    if ccaa_value is not None:
        facts = (*facts, UserProfileFact(path="tax_residence.ccaa", value=ccaa_value))
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=facts,
    )


def test_repository_wrapper_residence_ccaa_is_byte_identical_while_override_empty(
    secure_objects: SecureObjectRepository,
) -> None:
    """Deriving residence CCAA from the profile changes nothing without overrides.

    With the registry override layer empty, aggregating through the repository
    wrapper with a profile declaring ``tax_residence.ccaa = madrid`` produces
    casilla totals and observations byte-identical to the no-residence case.
    """
    invoice = _invoice(_transaction("row-region-wrapper-inert").transaction_id)
    linked = _transaction("row-region-wrapper-inert", purchase_invoice_evidence_id=invoice.invoice_id)
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((linked,)),
    )
    InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        InvoiceCatalogue.from_invoices((invoice,)),
    )

    def _run(profile_record: UserProfileRecord | None) -> RentaLedgerExpenseAggregation:
        return aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
            profile_year=2025,
            profile_record=profile_record,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )

    with_madrid = _run(_profile_with_ccaa("madrid"))
    without_region = _run(_profile_with_ccaa(None))

    assert with_madrid.casilla_values == without_region.casilla_values
    assert with_madrid.observations == without_region.observations
    assert with_madrid.issues == without_region.issues == ()


def test_repository_wrapper_threads_profile_residence_into_region_override_selection(
    secure_objects: SecureObjectRepository,
) -> None:
    """The residence CCAA derived from the profile reaches override selection.

    A GASTOS_BANCARIOS row with a synthetic Canarias override: a profile declaring
    ``tax_residence.ccaa = canarias`` selects the override THROUGH the repository
    wrapper (deductible halved), proving the residence derived from the profile
    flows end-to-end; a Madrid profile falls through to state law, proving the
    derived residence is the actual selector and is not silently dropped.
    """
    row = _transaction(
        "row-region-wrapper-hit",
        amount=Decimal("100.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    overrides = {
        CCAA.CANARIAS: {SpendingCategory.GASTOS_BANCARIOS: _region_override_profile(SpendingCategory.GASTOS_BANCARIOS)},
    }

    def _run(profile_record: UserProfileRecord | None) -> RentaLedgerExpenseAggregation:
        return aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
            profile_year=2025,
            profile_record=profile_record,
            region_category_overrides=overrides,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )

    matched = _run(_profile_with_ccaa("canarias"))
    assert matched.issues == ()
    assert matched.observations[0].proportionality_kind is ProportionalityKind.FIXED_PERCENTAGE
    assert matched.observations[0].deductible_amount == Decimal("50.0000")

    other_region = _run(_profile_with_ccaa("madrid"))
    assert other_region.issues == ()
    assert other_region.observations[0].proportionality_kind is not ProportionalityKind.FIXED_PERCENTAGE
    assert other_region.observations[0].deductible_amount == Decimal("100.00")


# ---------------------------------------------------------------------------
# IVA-deduction ratio derived from the profile's ``iva.regime`` fact and the
# bucket's ProrrataRegister, driven through the real repository path.
# ---------------------------------------------------------------------------


def _profile_with_iva_regime(*iva_facts: UserProfileFact) -> UserProfileRecord:
    """Build a user-profile record from explicitly supplied IVA facts."""
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="33333333-3333-4333-8333-333333333333",
        facts=(UserProfileFact(path="identity.tax_id", value="X1234567L"), *iva_facts),
    )


def test_repository_wrapper_exento_iva_regime_joins_the_full_iva_to_deductible_cost(
    secure_objects: SecureObjectRepository,
) -> None:
    """A wholly ``EXENTO`` taxpayer's non-deductible input IVA joins the IRPF cost, end to end.

    Same medico radiologo figures the domain-level unit test
    (``domain.renta.tests.test_ledger_expenses.test_wholly_exempt_activity_joins_the_full_iva_amount_to_the_deductible_cost``)
    grounds against the AEAT Manual practico de Renta 2024, Parte 1, Capitulo 7:
    base 8.000,00 EUR, IVA soportado 1.600,00 EUR, gross 9.600,00 EUR. LIVA
    art. 20.Uno.3.º gives the activity NO right to deduct any of its input IVA
    (art. 94.Uno a contrario), so the whole cuota becomes IRPF-deductible cost.
    Drives the real repository path -- a transaction carrying its own
    taxable_base/iva_amount and a profile declaring ``iva.regime = EXENTO`` --
    never a hand-built :class:`RentaDeductibilityContext`.
    """
    row = _transaction(
        "row-exento",
        amount=Decimal("9600.00"),
        category=SpendingCategory.MATERIAL_OFICINA,
        taxable_base=Decimal("8000.00"),
        iva_amount=Decimal("1600.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )

    def _run(profile_record: UserProfileRecord | None) -> RentaLedgerExpenseAggregation:
        return aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
            profile_year=2025,
            profile_record=profile_record,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )

    exento = _run(
        _profile_with_iva_regime(
            UserProfileFact(path="iva.regime", value="EXENTO"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    assert exento.issues == ()
    assert exento.observations[0].deductible_amount == Decimal("9600.00")
    assert exento.observations[0].non_deductible_amount == Decimal("0.00")
    assert exento.casilla_values[_M100_ASESORIA_CASILLA] == Decimal("9600.00")

    # Without the EXENTO fact the historic base-only behaviour stands: only the
    # net-of-IVA base is deductible, proving the ratio is the actual selector
    # and not silently ignored.
    general = _run(_profile_with_iva_regime())
    assert general.issues == ()
    assert general.observations[0].deductible_amount == Decimal("8000.00")


def test_repository_wrapper_general_prorrata_register_joins_the_non_deductible_share(
    secure_objects: SecureObjectRepository,
) -> None:
    """A GENERAL-prorrata register entry joins the non-recoverable IVA share, end to end.

    Same 70% figures the domain-level unit test
    (``test_prorrata_rationed_activity_joins_only_the_non_deductible_iva_share``)
    grounds against LIVA art. 104.Uno: base 1.000,00 EUR, IVA soportado 210,00
    EUR, gross 1.210,00 EUR, of which 30% of the cuota (63,00 EUR) has no right
    to deduct. Seeds a real :class:`~domain.prorrata_register.ProrrataRegister`
    entry rather than a hand-built context, exercising the same
    ``resolve_provisional`` resolution the M303 side already applies
    (``application.aggregation._iva_ledger._active_prorrata_apportionment``), so
    the two filings stay consistent for the same ejercicio.
    """
    row = _transaction(
        "row-prorrata",
        amount=Decimal("1210.00"),
        category=SpendingCategory.MATERIAL_OFICINA,
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(
            ejercicio=2025,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("70"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        ),
    )

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("1063.00")
    assert result.observations[0].non_deductible_amount == Decimal("147.00")


def test_repository_wrapper_ninguna_prorrata_regime_is_byte_identical_to_absent_entry(
    secure_objects: SecureObjectRepository,
) -> None:
    """A ``NINGUNA`` regime entry (full deduction rights) changes nothing.

    ``NINGUNA`` means the taxpayer performs only con-derecho operations, so no
    percentage apportions the cuotas (LIVA art. 94 stands unmodified) -- the
    fold-in must fall through to the historic base-only behaviour exactly as if
    no register entry existed at all.
    """
    row = _transaction(
        "row-ninguna",
        amount=Decimal("1210.00"),
        category=SpendingCategory.MATERIAL_OFICINA,
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(ejercicio=2025, regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None),
    )

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("1000.00")
    assert result.observations[0].non_deductible_amount == Decimal("210.00")


def test_repository_wrapper_uses_the_explicit_secondary_prorrata_store_while_primary_is_active(
    tmp_path: Path,
) -> None:
    """The M100 IVA ratio follows the injected secondary register, never the active primary bucket."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        row = _transaction(
            "secondary-prorrata",
            amount=Decimal("1210.00"),
            category=SpendingCategory.MATERIAL_OFICINA,
            taxable_base=Decimal("1000.00"),
            iva_amount=Decimal("210.00"),
        )
        primary_prorrata_repository = ProrrataRegisterRepository(
            bucket_id=runtime.primary.bucket_id,
            objects=runtime.primary.repository,
        )
        with runtime.switch_to_secondary():
            transaction_repository = TransactionCatalogueRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            invoice_repository = InvoiceCatalogueRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            secondary_prorrata_repository = ProrrataRegisterRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            transaction_repository.save(TransactionCatalogue.from_transactions((row,)))
            secondary_prorrata_repository.upsert_entry(
                ProrrataRegisterEntry(
                    ejercicio=2025,
                    regime=ProrrataRegisterRegime.GENERAL,
                    especial_transition=None,
                    provisional_percentage=Decimal("80"),
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                )
            )

            result = aggregate_renta_ledger_expenses_from_repositories(
                bucket_id=runtime.secondary.bucket_id,
                period=_ANNUAL_2025,
                transaction_repository=transaction_repository,
                invoice_repository=invoice_repository,
                profile_year=2025,
                profile_record=_profile_with_iva_regime(),
                prorrata_register_repository=secondary_prorrata_repository,
            )

        assert primary_prorrata_repository.load().entries == ()

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("1042.00")
    assert result.observations[0].non_deductible_amount == Decimal("168.00")


def test_repository_wrapper_refuses_an_implicit_prorrata_repository() -> None:
    """No public Renta repository path can silently recreate a register store."""
    with pytest.raises(TypeError, match="prorrata_register_repository"):
        cast(Any, aggregate_renta_ledger_expenses_from_repositories)(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=None,
            invoice_repository=None,
        )
