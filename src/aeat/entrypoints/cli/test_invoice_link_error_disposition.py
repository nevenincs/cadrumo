"""Tests for CLI disposition of invoice-link domain failures."""

from __future__ import annotations

import pytest

from aeat.core.i18n import tr
from aeat.entrypoints.cli._ledger import _invoice_link_error_bad_parameter

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_invoice_link_error_bad_parameter_uses_registered_message() -> None:
    error = _invoice_link_error_bad_parameter()

    assert str(error) == tr("errors.error.error_financial_invoices_invoice_link")
    assert "transaction not found in catalogue" not in str(error)
