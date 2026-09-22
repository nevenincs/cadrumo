"""Installed withholding lookup accepts visible invoice numbers only when unambiguous."""

from __future__ import annotations

import pytest

from cadrumo.domain.invoices.models import InvoiceCatalogue
from cadrumo.entrypoints.tui.withholding.installed import _resolve_visible_invoice

from .test_screen import _invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def test_visible_invoice_number_selects_one_canonical_invoice() -> None:
    invoice = _invoice(number="TUI-VISIBLE-ONE", base="500.00", withholding="95.00")
    catalogue = InvoiceCatalogue.model_validate((invoice,))

    assert _resolve_visible_invoice(catalogue, invoice.invoice_number) == invoice
    assert _resolve_visible_invoice(catalogue, invoice.invoice_id[:16]) == invoice
    assert _resolve_visible_invoice(catalogue, "UNKNOWN") is None


def test_duplicate_visible_invoice_number_refuses_instead_of_choosing_a_liability() -> None:
    first = _invoice(number="TUI-VISIBLE-DUP", base="500.00", withholding="95.00")
    second = _invoice(number="TUI-VISIBLE-DUP", base="600.00", withholding="114.00")
    catalogue = InvoiceCatalogue.model_validate((first, second))

    assert first.invoice_id != second.invoice_id
    assert _resolve_visible_invoice(catalogue, "TUI-VISIBLE-DUP") is None
    assert _resolve_visible_invoice(catalogue, first.invoice_id) == first
