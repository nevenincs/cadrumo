"""Modelo 100 casilla 0599 takes the retención the taxpayer's issued invoices declare.

Casilla 0599 credits the retenciones and ingresos a cuenta borne on actividades
económicas (LIRPF art. 99; RIRPF arts. 95 and 108.4). The perceptor's own
issued invoice states the retención the client practised, so the ledger is the
value source. A figure reconstructed from invoice gross minus cash received is
not a recorded fact: it is reported with its count and amount and never added.
A row whose retención the substrate cannot determine is reported as unknown,
never as zero. Until the year that credits an invoice whose payment and accrual
fall in different ejercicios is grounded, the credit travels as advisory grade.

Every case runs through the production resolver against the Modelo 100 and
Modelo 130 revisions of the published authority, so the bindings under test are
the ones the registry declares, not fixture copies of them.

Every figure is invoice arithmetic hand-derived in the constants below. Two
rates are used because one rate cannot tell a per-invoice read from one rate
applied to a total: 1.000,00 at 15 % and 500,00 at 7 % give 150,00 and 35,00,
and no single rate over the 1.500,00 combined base reproduces 185,00.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.calculation_note_gate import gate_refuses
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceResolution
from .ledger_source_mesh_support import InMemoryTransactionCatalogueRepository
from .renta_income_aggregation_support import _catalogue_read_ports, _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "c4f1a2b3-5d6e-4f70-8a91-b2c3d4e5f607"
_YEAR = newest_authored_edition("100")
_ACTIVITY_DATE = date(_YEAR, 3, 10)

_M100_RETENCIONES_ACTIVIDADES_CASILLA: CasillaId = validated_casilla_id(
    "0599",
    surface="_M100_RETENCIONES_ACTIVIDADES_CASILLA",
)
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_DOMESTIC_GENERAL = IvaCategory("domestic_general")
_DOMESTIC_EXEMPT = IvaCategory("domestic_exempt")
_RENTA_INCOME = BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION

# Hand-derived: 1.000,00 base at the RIRPF art. 95.1 general 15 % leaves 150,00
# withheld; 1.000,00 + 210,00 IVA - 150,00 = 1.060,00 reaches the bank.
_PROFESIONAL_BASE = Decimal("1000.00")
_PROFESIONAL_RETENCION = Decimal("150.00")
_PROFESIONAL_CASH = Decimal("1060.00")
# Hand-derived: 500,00 base at the art. 95.1 new-professional 7 % leaves 35,00
# withheld; 500,00 + 105,00 IVA - 35,00 = 570,00 reaches the bank.
_REDUCED_BASE = Decimal("500.00")
_REDUCED_RETENCION = Decimal("35.00")
_REDUCED_CASH = Decimal("570.00")
# Hand-derived: 150,00 + 35,00.
_DECLARED_CREDIT = Decimal("185.00")

# Hand-derived inferred row: 2.000,00 base + 420,00 IVA = 2.420,00 invoiced, and
# 2.120,00 banked with no invoice to state the shortfall, so 300,00 is
# reconstructed. 300,00 is 15 % of the base, inside the supported rate.
_INFERRED_BASE = Decimal("2000.00")
_INFERRED_IVA = Decimal("420.00")
_INFERRED_CASH = Decimal("2120.00")
_INFERRED_RETENCION = Decimal("300.00")


def _transaction(
    *,
    provider_id: str,
    cash: Decimal,
    irpf_category: str | None = "actividad_economica",
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=_ACTIVITY_DATE,
        value_date=_ACTIVITY_DATE,
        amount=cash,
        currency="EUR",
        counterparty="Cliente SL",
        description="cobro factura",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": irpf_category,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _issued_invoice(
    *,
    number: str,
    base: Decimal,
    linked_transaction_id: str,
    retention_amount: Decimal,
    retention_rate: Decimal,
) -> Invoice:
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), _ACTIVITY_DATE)
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=base * rate,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": _ACTIVITY_DATE,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "bucket_id": _BUCKET,
            "base_total": base,
            "iva_total": line.iva_amount,
            "grand_total": base + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": _DOMESTIC_GENERAL,
            "retention_rate": retention_rate,
            "retention_amount": retention_amount,
            "linked_transaction_ids": (linked_transaction_id,),
        },
    )


def _declared_ledger(*extra: Transaction) -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    """Two issued invoices whose retención each invoice states, at 15 % and 7 %, plus ``extra`` rows."""
    profesional = _transaction(provider_id="cobro-15", cash=_PROFESIONAL_CASH)
    reduced = _transaction(provider_id="cobro-07", cash=_REDUCED_CASH)
    invoices = (
        _issued_invoice(
            number="F-001",
            base=_PROFESIONAL_BASE,
            linked_transaction_id=profesional.transaction_id,
            retention_amount=_PROFESIONAL_RETENCION,
            retention_rate=Decimal("0.15"),
        ),
        _issued_invoice(
            number="F-002",
            base=_REDUCED_BASE,
            linked_transaction_id=reduced.transaction_id,
            retention_amount=_REDUCED_RETENCION,
            retention_rate=Decimal("0.07"),
        ),
    )
    catalogue = TransactionCatalogue.from_transactions((profesional, reduced, *extra))
    for invoice, transaction in zip(invoices, (profesional, reduced), strict=True):
        catalogue = link_invoice(catalogue, transaction.transaction_id, invoice.invoice_id)
    return catalogue, build_invoice_catalogue(invoices)


def _resolve(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    revision: ModeloRevision,
    modelo: str = "100",
    period_code: str = "0A",
) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=_catalogue_read_ports(invoices=invoices, transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET,
            modelo=modelo,
            filing_year=_YEAR,
            period=_period(_YEAR, period_code),
            revision=revision,
        ),
    )


def _m100_revision() -> ModeloRevision:
    return published_snapshot("100", filing_year=_YEAR, period="0A").revision


def _casilla_0599_binding(revision: ModeloRevision) -> BindingId:
    """Return the binding the registry names for casilla 0599, asserting it is bound directly."""
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _M100_RETENCIONES_ACTIVIDADES_CASILLA)
    assert casilla.input_kind is InputKind.BOUND
    assert casilla.binding is not None
    return casilla.binding


def _credit_0599(resolution: CalculationSourceResolution, revision: ModeloRevision) -> Decimal:
    return resolution.binding_values[_casilla_0599_binding(revision)]


def _findings(resolution: CalculationSourceResolution, reason: str) -> list[CalculationSourceDiagnostic]:
    return [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == reason]


def test_declared_retenciones_at_two_rates_reach_casilla_0599() -> None:
    """Both invoices' stated retención enters 0599, each at its own rate: 150,00 + 35,00."""
    transactions, invoices = _declared_ledger()
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    assert not _findings(resolution, "inferred_retencion_excluded_from_credit")
    assert not _findings(resolution, "unresolved_retencion_substrate")


def test_the_0599_credit_is_advisory_grade() -> None:
    """A non-zero 0599 credit carries the advisory grade, which the filing gate does not refuse on.

    Advisory, not filing grade, because which ejercicio credits an invoice whose
    payment and accrual years differ is not yet grounded. The finding names the
    amount so the operator can check it against the payer's certificate.
    """
    transactions, invoices = _declared_ledger()

    resolution = _resolve(transactions, invoices, revision=_m100_revision())

    grade = _findings(resolution, "advisory_retencion_credit_grade")
    assert len(grade) == 1
    assert f"{_DECLARED_CREDIT} EUR is ADVISORY" in grade[0].message
    assert not gate_refuses(grade[0].reason, _RENTA_INCOME)


def test_an_inferred_row_raises_the_advisory_and_leaves_0599_unchanged() -> None:
    """A net-paid receipt with no invoice stating its retención is reported, not added.

    Its 300,00 is reconstructed from 2.420,00 invoiced minus 2.120,00 banked, so
    0599 stays at the declared 185,00 and the finding names one row and 300,00.
    """
    inferred = _transaction(
        provider_id="cobro-inferido",
        cash=_INFERRED_CASH,
        taxable_base=_INFERRED_BASE,
        iva_rate=Decimal("0.21"),
        iva_amount=_INFERRED_IVA,
    )
    transactions, invoices = _declared_ledger(inferred)
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    excluded = _findings(resolution, "inferred_retencion_excluded_from_credit")
    assert len(excluded) == 1
    assert excluded[0].message.startswith("1 issued-invoice row(s)")
    assert f"{_INFERRED_RETENCION} EUR" in excluded[0].message
    assert inferred.transaction_id in excluded[0].message
    assert not _findings(resolution, "unresolved_retencion_substrate")


@pytest.mark.parametrize(
    ("label", "cash", "taxable_base", "iva_category"),
    [
        # No base and no invoice: nothing determines the retención.
        ("no_substrate", Decimal("400.00"), None, None),
        # 2.000,00 exempt base banked as 1.000,00 would imply 50 % withheld,
        # above every supported activity rate, so the inference is refused.
        ("refused_above_supported_rate", Decimal("1000.00"), Decimal("2000.00"), _DOMESTIC_EXEMPT),
    ],
)
def test_an_undeterminable_retencion_is_unresolved_never_zero(
    label: str,
    cash: Decimal,
    taxable_base: Decimal | None,
    iva_category: IvaCategory | None,
) -> None:
    """A row whose retención is unknown is reported as unresolved and adds nothing to 0599."""
    unknown = _transaction(
        provider_id=f"cobro-{label}",
        cash=cash,
        taxable_base=taxable_base,
        iva_category=iva_category,
    )
    transactions, invoices = _declared_ledger(unknown)
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    unresolved = _findings(resolution, "unresolved_retencion_substrate")
    assert len(unresolved) == 1
    assert unresolved[0].message.startswith("1 issued-invoice row(s)")
    assert unknown.transaction_id in unresolved[0].message
    assert not _findings(resolution, "inferred_retencion_excluded_from_credit")


def test_employment_and_non_activity_rows_never_reach_0599() -> None:
    """A salary receipt and an uncategorised receipt add nothing and raise no retención finding."""
    employment = _transaction(provider_id="nomina", cash=Decimal("1800.00"), irpf_category="rendimientos_trabajo")
    uncategorised = _transaction(provider_id="sin-categoria", cash=Decimal("500.00"), irpf_category=None)
    transactions, invoices = _declared_ledger(employment, uncategorised)
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    assert not _findings(resolution, "inferred_retencion_excluded_from_credit")
    assert not _findings(resolution, "unresolved_retencion_substrate")


def test_the_unrouted_quantity_screen_is_silent_for_modelo_100() -> None:
    """The retención reaches 0599, so the screen that refuses an unrouted quantity stays silent.

    Teeth: the same rows against the published revision with the 0599 binding
    removed raise ``unrouted_declarable_quantity`` for the whole 185,00, and the
    calculation-note gate refuses on it.
    """
    transactions, invoices = _declared_ledger()
    revision = _m100_revision()

    assert not _findings(_resolve(transactions, invoices, revision=revision), "unrouted_declarable_quantity")

    binding_id = _casilla_0599_binding(revision)
    stripped = revision.model_copy(
        update={
            "bindings": tuple(binding for binding in revision.bindings if binding.id != binding_id),
            "casillas": tuple(
                casilla.model_copy(update={"input_kind": InputKind.MANUAL, "binding": None})
                if casilla.id == _M100_RETENCIONES_ACTIVIDADES_CASILLA
                else casilla
                for casilla in revision.casillas
            ),
        },
    )
    unrouted = _findings(_resolve(transactions, invoices, revision=stripped), "unrouted_declarable_quantity")
    assert len(unrouted) == 1
    assert f"{_DECLARED_CREDIT} EUR of 'declared_withheld_amount_sum'" in unrouted[0].message
    assert gate_refuses(unrouted[0].reason, _RENTA_INCOME)


def test_0599_agrees_with_the_fourth_quarter_modelo_130_casilla_06() -> None:
    """The annual credit equals the cumulative fourth-quarter Modelo 130 casilla 06 over the same ledger.

    Both are compared with the hand-derived 185,00 rather than with each other's
    output, and the inferred row is present so the comparison covers what both
    leave out as well as what both take.
    """
    inferred = _transaction(
        provider_id="cobro-inferido",
        cash=_INFERRED_CASH,
        taxable_base=_INFERRED_BASE,
        iva_rate=Decimal("0.21"),
        iva_amount=_INFERRED_IVA,
    )
    transactions, invoices = _declared_ledger(inferred)
    m100 = _m100_revision()

    annual = _resolve(transactions, invoices, revision=m100)
    fourth_quarter = _resolve(
        transactions,
        invoices,
        revision=published_snapshot("130", filing_year=_YEAR, period="4T").revision,
        modelo="130",
        period_code="4T",
    )

    assert _credit_0599(annual, m100) == _DECLARED_CREDIT
    assert fourth_quarter.bound_inputs_by_casilla_id[_M130_RETENCIONES_CASILLA] == _DECLARED_CREDIT
