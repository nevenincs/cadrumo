"""Resolve one screened invoice line to its Modelo 303 binding values."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import Invoice
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..modelo_bindings_invoice_iva import invoice_line_iva_observation

_DEVENGO_2024_Q1 = date(2024, 3, 15)


def resolved_for(
    invoice: Invoice,
    *,
    operation: PinnedAuthorityOperation,
    devengo_date: date = _DEVENGO_2024_Q1,
) -> dict[str, Decimal]:
    """Project the invoice's single line the way the screen does, then resolve."""
    line = invoice.lines[0]
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    assert base_amount_eur is not None
    assert iva_amount_eur is not None
    observation = invoice_line_iva_observation(
        invoice=invoice,
        line=line,
        line_index=0,
        devengo_date=devengo_date,
        recargo_amount=Decimal("0"),
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
        operation=operation,
    )
    if observation is None:
        return {}
    revision = published_snapshot("303", filing_year=2024, period="1T").revision
    return {
        str(k): v
        for k, v in resolve_iva_ledger_binding_values(
            revision,
            (observation,),
            operation=operation,
        ).items()
    }
