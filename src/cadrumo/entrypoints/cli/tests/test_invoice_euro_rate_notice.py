"""CLI presentation of the exact-profile invoice worker's euro-rate result."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
import typer

from ....adapters.outbound.fx.ecb_provider import EcbReferenceRateProvider
from ....adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ....application.invoices.catalogue_add_operation import (
    InvoiceAddResult,
)
from ....application.invoices.catalogue_creation import build_catalogue_invoice
from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ....core.json_contract import Notice
from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.invoices.models import Invoice
from ....domain.iva.classification import InvoiceKind
from ....tests.ecb_stub import ecb_csv_fetch
from .. import _ledger_business_invoice_cli as handler
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = UUID("50505050-5050-4505-8505-505050505050")
# Both provider paths are deterministic and network-free. The USD test transport
# explicitly reports no observations; the EUR case does not need a conversion.
_OPERATION_ID = "e" * 64
_RATELESS_PROVIDER = EcbReferenceRateProvider(fetch=ecb_csv_fetch({}))


def _invoice(currency: str, invoice_number: str) -> Invoice:
    provider = _RATELESS_PROVIDER if currency == "USD" else recorded_ecb_rate_provider()
    with bundled_indexed_authority().operation():
        return build_catalogue_invoice(
            bucket_id=str(_PROFILE),
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Proveedor Exterior SL",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            invoice_number=invoice_number,
            issued_at=date(2026, 3, 16),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("21"),
            currency=currency,
            rate_provider=provider,
        )


def _present_add_result(monkeypatch: pytest.MonkeyPatch, *, currency: str, invoice_number: str):
    invoice = _invoice(currency, invoice_number)
    added = InvoiceAddResult.created(
        _PROFILE,
        invoice=CatalogueInvoiceSnapshot.from_invoice(invoice),
        bucket_event_ids=("bucket-event",),
        euro_value_pending=invoice.euro_value_pending,
        simplificada_tax_id_advisory_required=False,
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=added,
        effect=OperationEffect.UPDATED,
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(handler, "_business_invoice_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(handler, "add_invoice_catalogue", lambda *_args, **_kwargs: (completion, added))
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: captured.update(kwargs))

    handler.invoice_add(
        cast(typer.Context, cast(object, None)),
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Exterior SL",
        invoice_number=invoice_number,
        invoice_date="2026-03-16",
        taxable_base="100.00",
        country_code="ES",
        iva_rate="21",
        currency=currency,
        counterparty_nif="A58818501",
    )
    return captured


def test_a_foreign_invoice_recorded_without_a_rate_warns_at_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI surfaces the worker's pending-euro-value result as a notice."""
    captured = _present_add_result(monkeypatch, currency="USD", invoice_number="FX-NO-RATE-001")

    assert captured["command"] == "ledger.invoice.add"
    notices = cast(list[Notice], captured["notices"])
    assert "ledger.invoice.euro_rate_unavailable" in {notice.code for notice in notices}


def test_a_euro_invoice_carries_no_rate_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI emits no missing-rate notice when the worker reports an EUR record."""
    captured = _present_add_result(monkeypatch, currency="EUR", invoice_number="FX-EURO-001")

    notices = cast(list[Notice], captured["notices"])
    assert "ledger.invoice.euro_rate_unavailable" not in {notice.code for notice in notices}
