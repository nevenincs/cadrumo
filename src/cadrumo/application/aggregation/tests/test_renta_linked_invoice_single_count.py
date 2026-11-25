"""A linked received invoice and its payment count once, in the Modelo 130 expense box and in the annual chain.

The ledger link stamps ``Transaction.invoice_id``. The expense is the payment row, read with
its invoice for its date and figures (LIRPF art. 28, RIRPF art. 30); the invoice is never a
second expense beside the row. Both resolvers read the link through the same reference.

Hand-worked figures. The inputs are assumed, since the totals alone fix them: the income is
typed as casilla 0171 (the income leg has its own worked examples), the 1.000,00 expense is a
received rent invoice of 1.000,00 base without IVA carrying a 15 % retencion (150,00)
withheld from its payment, so that the bank moved 850,00, and the 2.400,00 of other deductible expenses is one
row without an invoice.

    ingresos                                  12.000,00
    gastos: 2.400,00 + 1.000,00                3.400,00
    rendimiento previo                         8.600,00
    provision 5 % (dificil justificacion)        430,00
    rendimiento neto (0224)                    8.170,00
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.tests.modelo_100_registry_support import M100_NO_LET_PROPERTY_BINDINGS
from ....domain.calculations.registry.tests.scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import Transaction
from ...actividad_asset.history import ActivityAssetHistory
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryInvoiceCatalogueRepository,
    ledger_source_mesh_revision,
    m130_binding_id,
    resolve_m100,
    resolve_m130,
)
from .renta_ledger_support import ledger_expense_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = 2025
_CATEGORY = SpendingCategory.from_registry("arrendamiento_local")
_OTHER_CATEGORY = SpendingCategory.from_registry("asesoria_contable")
_BASE = Decimal("1000.00")
_NET = Decimal("850.00")
_OTHERS = Decimal("2400.00")


def _linked_expense() -> tuple[Transaction, Invoice]:
    bare = ledger_expense_transaction(
        "asesoria-retenida",
        amount=_NET,
        category=_CATEGORY,
        irpf_category="arrendamiento_local",
        booked_date=date(_YEAR, 2, 10),
        value_date=date(_YEAR, 2, 10),
        taxable_base=_BASE,
        iva_amount=Decimal("0.00"),
    )
    line = InvoiceLine(
        description="Asesoria",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.from_registry("RATE_0"),
        iva_amount=Decimal("0.00"),
    )
    invoice = Invoice.model_validate(
        {
            "bucket_id": BUCKET_ID,
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "ASE-RET-1",
            "issued_at": date(_YEAR, 2, 5),
            "counterparty_name": "Asesor Profesional",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": _BASE,
            "iva_total": Decimal("0.00"),
            "grand_total": _BASE,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "retention_rate": Decimal("0.15"),
            "retention_amount": Decimal("150.00"),
            "linked_transaction_ids": (bare.transaction_id,),
        }
    )
    return bare.model_copy(update={"invoice_id": invoice.invoice_id}), invoice


def _others() -> Transaction:
    return ledger_expense_transaction(
        "otros-gastos",
        amount=_OTHERS,
        category=_OTHER_CATEGORY,
        booked_date=date(_YEAR, 3, 3),
        value_date=date(_YEAR, 3, 3),
        taxable_base=_OTHERS,
        iva_amount=Decimal("0.00"),
    )


def _invoices(invoice: Invoice) -> InMemoryInvoiceCatalogueRepository:
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice,)))
    return repository


def _casilla(code: str) -> CasillaId:
    return validated_casilla_id(code, surface=code)


def test_the_expense_box_of_modelo_130_counts_the_linked_invoice_once() -> None:
    row, invoice = _linked_expense()

    resolution = resolve_m130(ActivityAssetHistory(), "4T", rows=(row, _others()), invoices=_invoices(invoice))

    assert (
        resolution.binding_values[m130_binding_id(ledger_source_mesh_revision("130", "2019-y-siguientes"))]
        == _BASE + _OTHERS
    )


def test_the_annual_chain_counts_the_linked_invoice_once_to_the_rendimiento_neto() -> None:
    row, invoice = _linked_expense()
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row, _others()), invoices=_invoices(invoice))
    revision = ledger_source_mesh_revision("100", str(_YEAR))
    expense_inputs = {
        _casilla(str(getattr(binding.provider, "target_casilla_id", None))): resolution.binding_values[binding.id]
        for binding in revision.bindings
        if str(binding.source) == "ledger_renta_gastos_estimacion_directa_aggregation"
        and binding.id in resolution.binding_values
    }
    assert sum(expense_inputs.values(), Decimal("0")) == _BASE + _OTHERS

    report = run_registry_calculation_scenario(
        RegistryCalculationScenario(
            id="m100-linked-invoice-single-count",
            modelo="100",
            revision=str(_YEAR),
            filing_year=_YEAR,
            period="0A",
            inputs={_casilla("0171"): Decimal("12000.00"), **expense_inputs},
            binding_values={
                "renta-profile-marriage-full-year": Decimal("0"),
                "renta-profile-marriage-month-start": Decimal("0"),
                "renta-profile-marriage-month-end": Decimal("0"),
                "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
                "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
                "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
                "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
                "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
                "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
                "renta-profile-declaration-type": Decimal("1"),
                "renta-profile-family-minor-children-in-unit": Decimal("0"),
                "renta-modelo-100-estimacion-directa-es-normal": Decimal("0"),
                "renta-profile-has-economic-activity": Decimal("1"),
                "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
                "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
                **M100_NO_LET_PROPERTY_BINDINGS,
                "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
                "renta-profile-estimacion-directa": Decimal("1"),
            },
            enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
            relation_values={
                "renta-modelo-130-pagos-fraccionados": Decimal("0"),
                "renta-modelo-131-pagos-fraccionados": Decimal("0"),
            },
            date_context={"filing_period": date(_YEAR, 12, 31)},
            date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 6, 15)},
            expected_outputs=(
                RegistryScenarioExpectedOutput(
                    target_casilla_id=_casilla("0224"),
                    value=Decimal("8170.00"),
                    legal_refs=(
                        "ley-35-2006:art-27",
                        "ley-35-2006:art-28",
                        "ley-35-2006:art-30",
                        "ley-35-2006:art-32",
                        "orden-hac-277-2026:art-3",
                    ),
                    source_refs=(
                        "aeat-dr-100-2025-dictionary",
                        "aeat-dr-100-2025-xsd",
                        "aeat-renta-2025-manual-parte1",
                        "boe-modelo-100-2025-form",
                    ),
                ),
            ),
            hand_typed_bound_casillas={
                _casilla("0171"): "income leg typed; its ledger binding has its own worked examples",
                **{
                    casilla: "resolved by the expense resolver and supplied as the scenario input"
                    for casilla in expense_inputs
                },
            },
        ),
    )

    assert_registry_scenario_matches(report)
    assert report.calculation.values[_casilla("0224")] == Decimal("8170.00")
