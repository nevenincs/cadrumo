"""Tests for CLI disposition of invoice-link domain failures."""

from __future__ import annotations

import pytest

from ....core.i18n.render import tr
from .._ledger import invoice_link_error_bad_parameter

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_invoice_link_error_bad_parameter_uses_registered_message() -> None:
    error = invoice_link_error_bad_parameter()

    assert str(error) == tr("errors.error.error_financial_invoices_invoice_link")
    assert "transaction not found in catalogue" not in str(error)
