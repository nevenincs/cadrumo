"""Tests for repository-backed Renta ledger expense aggregation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.profile.usage_ratios import save_usage_ratios
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.errors import (
    AggregationValidationError,
)
from cadrumo.application.aggregation.modelo_bindings_renta_expenses import (
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
)
from cadrumo.application.aggregation.renta_gasto_ledger import aggregate_renta_gasto_ledger_from_repositories
from cadrumo.application.aggregation.renta_ledger import (
    RentaLedgerAggregationIssueReason,
    RentaLedgerExpenseAggregation,
    aggregate_renta_ledger_expenses_from_repositories,
)
from cadrumo.application.aggregation.source_mesh import (
    CalculationSourceContext,
)
from cadrumo.core.aggregation import BindingAggregation, BindingAggregationOp
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.i18n.translatable import Translatable as tr
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.categories.profile import CategoryProfile
from cadrumo.domain.categories.proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    parse_http_url,
)
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.contribuyente.ccaa import CCAA
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.usage_ratios.model import UsageRatioProfile
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.tests.aeat_literal_fixtures import RENTA_REGIMEN_CITATION_URL_FIXTURE

SECURE_OBJECTS_BUCKET_ID = "78804f92-b6f7-4daf-9ddf-a8ce3829dbb1"

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=SECURE_OBJECTS_BUCKET_ID) as profile:
        yield profile.repository


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


def _m100_renta_expense_binding(binding_id: str, casilla_id: str) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider={
            "kind": "ledger_renta_gastos_estimacion_directa_aggregation",
            **{
                "modelo": "100",
                "period": "0A",
                "target_casilla_id": casilla_id,
                "fact": "deductible_amount_sum",
            },
        },
        value={"data_type": "money", "channel": "decimal"},
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
            _m100_renta_expense_binding("renta-ledger-expense-0186-deductible", "0186"),
            _m100_renta_expense_binding("renta-ledger-expense-0192-deductible", "0192"),
            _m100_renta_expense_binding("renta-ledger-expense-0199-deductible", "0199"),
            _m100_renta_expense_binding("renta-ledger-expense-0203-deductible", "0203"),
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
    category: SpendingCategory = SpendingCategory._from_registry("asesoria_fiscal"),
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
        iva_rate=IvaRate._from_registry("RATE_21"),
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
        category=SpendingCategory._from_registry("asesoria_fiscal"),
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

    assert binding_values["renta-ledger-expense-0199-deductible"] == Decimal("121.00")
    assert binding_values["renta-ledger-expense-0186-deductible"] == Decimal("0")
    assert binding_values["renta-ledger-expense-0192-deductible"] == Decimal("0")
    assert binding_values["renta-ledger-expense-0203-deductible"] == Decimal("0")


def test_renta_filing_aggregation_routes_office_software_and_marketing_to_m100_expenses(
    secure_objects: SecureObjectRepository,
) -> None:
    """Ordinary business operating costs must not disappear from M100."""
    transactions = (
        _transaction(
            "row-office",
            amount=Decimal("240.00"),
            category=SpendingCategory._from_registry("material_oficina"),
        ),
        _transaction(
            "row-software",
            amount=Decimal("360.00"),
            category=SpendingCategory._from_registry("software_suscripcion"),
        ),
        _transaction(
            "row-marketing",
            amount=Decimal("180.00"),
            category=SpendingCategory._from_registry("publicidad_marketing"),
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
    assert resolution.binding_values["renta-ledger-expense-0199-deductible"] == Decimal("780.00")


def test_renta_filing_aggregation_loads_usage_ratios_for_mobile_phone_expenses(
    secure_objects: SecureObjectRepository,
) -> None:
    """The live source resolver must consume persisted proportionality ratios."""
    phone = _transaction(
        "row-phone",
        amount=Decimal("121.00"),
        category=SpendingCategory._from_registry("telefonia_movil"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((phone,)),
    )
    InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory._from_registry("telefonia_movil"): Decimal("0.50")}),
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
    assert resolution.binding_values["renta-ledger-expense-0199-deductible"] == Decimal("60.50")
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
            category=SpendingCategory._from_registry("material_oficina"),
            booked_date=date(2025, 2, 3),
            value_date=date(2025, 2, 3),
            taxable_base=office_base,
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("147.00"),
        ),
        _transaction(
            "sofia-software",
            amount=Decimal("726.00"),
            category=SpendingCategory._from_registry("software_suscripcion"),
            booked_date=date(2025, 2, 4),
            value_date=date(2025, 2, 4),
            taxable_base=software_base,
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("126.00"),
        ),
        _transaction(
            "sofia-marketing",
            amount=Decimal("968.00"),
            category=SpendingCategory._from_registry("publicidad_marketing"),
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
            category=SpendingCategory._from_registry("material_oficina"),
            booked_date=date(2025, 1, 15),
            value_date=date(2025, 1, 15),
            taxable_base=bases[0],
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("147.00"),
        ),
        _transaction(
            "shared-software",
            amount=Decimal("726.00"),
            category=SpendingCategory._from_registry("software_suscripcion"),
            booked_date=date(2025, 2, 15),
            value_date=date(2025, 2, 15),
            taxable_base=bases[1],
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("126.00"),
        ),
        _transaction(
            "shared-marketing",
            amount=Decimal("968.00"),
            category=SpendingCategory._from_registry("publicidad_marketing"),
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
            kind=ProportionalityKind._from_registry(
                "fixed_percentage",
                requires_fixed_pct=True,
                is_full_deductible=False,
                is_usage_ratio=False,
                is_statutory_cap=False,
                is_non_deductible=False,
                requires_exclusive_use=False,
            ),
            fixed_pct=Decimal("0.50"),
            citations=(
                CategoryCitation(
                    source=CategoryCitationSource.MANUAL_RENTA,
                    reference="Manual práctico Renta 2025, regla de prueba territorial",
                    locator="test",
                    url=parse_http_url(RENTA_REGIMEN_CITATION_URL_FIXTURE),
                    quote=tr("Texto de prueba para override territorial."),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
            notes=tr("Override territorial de prueba."),
        ),
    )


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
        category=SpendingCategory._from_registry("gastos_bancarios"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    overrides = {
        CCAA.CANARIAS: {
            SpendingCategory._from_registry("gastos_bancarios"): _region_override_profile(
                SpendingCategory._from_registry("gastos_bancarios")
            )
        },
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
    assert matched.observations[0].proportionality_kind is ProportionalityKind._from_registry(
        "fixed_percentage",
        requires_fixed_pct=True,
        is_full_deductible=False,
        is_usage_ratio=False,
        is_statutory_cap=False,
        is_non_deductible=False,
        requires_exclusive_use=False,
    )
    assert matched.observations[0].deductible_amount == Decimal("50.0000")

    other_region = _run(_profile_with_ccaa("madrid"))
    assert other_region.issues == ()
    assert other_region.observations[0].proportionality_kind is not ProportionalityKind._from_registry(
        "fixed_percentage",
        requires_fixed_pct=True,
        is_full_deductible=False,
        is_usage_ratio=False,
        is_statutory_cap=False,
        is_non_deductible=False,
        requires_exclusive_use=False,
    )
    assert other_region.observations[0].deductible_amount == Decimal("100.00")
