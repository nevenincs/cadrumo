"""An issued invoice's stated retención is the Modelo 130 casilla 06 credit.

APP-QA's first quarter in miniature: three Spanish invoices of 2000.00 base, 21 per
cent IVA and a stated 15 per cent retención of 300.00, each collected net at
2120.00, plus one 1500.00 intra-community service invoice with no retención. The
invoices come from the Libro de facturas, so none declares an IVA treatment. Each
cobro also carries the base and cuota the person typed on the movement. One link is
held on the movement alone, as a record written before both sides were kept
together.

Hand-derived oracle (AEAT Modelo 130 instructions, casilla 06; RIRPF art. 110.3.a):
300.00 x 3 = 900.00 of declared retención, and casilla 01 is 2000.00 x 3 + 1500.00
= 7500.00. Each retención is the invoice's own figure, never also inferred from the
net cobro, so the credit is not counted twice.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import LedgerWithholdingDerivation
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.ledger_renta_income_bindings import (
    ledger_renta_withholding_derivation_partition,
    resolve_ledger_renta_income_aggregation_binding_values,
)
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..renta_income_ledger import aggregate_renta_income_ledger
from .renta_income_aggregation_support import (
    m130_activity_category_matcher,
    m130_employment_category_matcher,
)
from .test_renta_income_actividad_contract import m130_2026_q1_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

BUCKET = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
_Q1 = Period.from_year_and_code(2026, "1T")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"

_BASE = Decimal("2000.00")
_CUOTA = Decimal("420.00")
_RETENCION = Decimal("300.00")
_NET_COBRO = Decimal("2120.00")
_INTRA_COMMUNITY_BASE = Decimal("1500.00")


def _cobro(provider_id: str, day: date, *, cash: Decimal, cuota: Decimal) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=day,
        value_date=day,
        amount=cash,
        currency="EUR",
        counterparty="Cliente",
        description=f"TRANSF RECIBIDA {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
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
            "irpf_category": "actividad_economica",
            "taxable_base": cash if cuota == 0 else _BASE,
            "iva_amount": cuota,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _invoice(
    number: str,
    day: date,
    *,
    base: Decimal,
    cuota: Decimal,
    retencion: Decimal | None,
    country: str,
    linked: tuple[str, ...],
) -> Invoice:
    rate = IvaRate.from_registry("RATE_21") if cuota else IvaRate.from_registry("RATE_0")
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=rate,
        iva_amount=cuota,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": day,
            "counterparty_name": f"Cliente {number}",
            "counterparty_tax_id": "B81000010" if country == "ES" else "DE123456788",
            "counterparty_country": country,
            "bucket_id": BUCKET,
            "base_total": base,
            "iva_total": cuota,
            "grand_total": base + cuota,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": None,
            "retention_rate": None if retencion is None else Decimal("0.15"),
            "retention_amount": retencion,
            "linked_transaction_ids": linked,
        },
    )


def _first_quarter() -> tuple[TransactionCatalogue, list[Invoice]]:
    dated = (
        ("2026-001", date(2026, 1, 15)),
        ("2026-003", date(2026, 2, 14)),
        ("2026-004", date(2026, 3, 14)),
    )
    cobros = [_cobro(number, day, cash=_NET_COBRO, cuota=_CUOTA) for number, day in dated]
    kunde = _cobro("2026-002", date(2026, 1, 31), cash=_INTRA_COMMUNITY_BASE, cuota=Decimal("0"))
    invoices = [
        _invoice(
            number,
            day,
            base=_BASE,
            cuota=_CUOTA,
            retencion=_RETENCION,
            country="ES",
            # The last invoice is linked from its movement alone.
            linked=() if number == "2026-004" else (cobro.transaction_id,),
        )
        for (number, day), cobro in zip(dated, cobros, strict=True)
    ]
    invoices.append(
        _invoice(
            "2026-002",
            date(2026, 1, 31),
            base=_INTRA_COMMUNITY_BASE,
            cuota=Decimal("0"),
            retencion=None,
            country="DE",
            linked=(kunde.transaction_id,),
        )
    )
    movements = [
        cobro.model_copy(update={"invoice_id": invoice.invoice_id})
        for cobro, invoice in zip((*cobros, kunde), invoices, strict=True)
    ]
    return TransactionCatalogue.from_transactions(movements), invoices


def test_stated_retenciones_reach_casilla_06_with_no_iva_treatment_and_either_side_links() -> None:
    transactions, invoices = _first_quarter()

    aggregation = aggregate_renta_income_ledger(
        transactions,
        build_invoice_catalogue(invoices),
        bucket_id=BUCKET,
        period=_Q1,
        modelo="130",
        target_casilla_id=_M130_INGRESOS_CASILLA,
        activity_category_matcher=m130_activity_category_matcher,
        employment_category_matcher=m130_employment_category_matcher,
    )
    revision = m130_2026_q1_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    partition = ledger_renta_withholding_derivation_partition(revision, aggregation.observations)

    assert resolved[_M130_RETENCIONES_BINDING] == Decimal("900.00")
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("7500.00")
    assert partition.inferred_observations == ()
    assert partition.unresolved_observations == ()
    assert sorted(
        (observation.withheld_amount, observation.withheld_derivation) for observation in aggregation.observations
    ) == sorted(
        [
            (Decimal("0"), LedgerWithholdingDerivation.NONE_WITHHELD),
            *[(_RETENCION, LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE)] * 3,
        ]
    )
