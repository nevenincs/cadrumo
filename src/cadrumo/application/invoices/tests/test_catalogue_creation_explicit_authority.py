"""The catalogue writer resolves every governed fact under the operation it is handed.

``build_catalogue_invoice`` takes a pinned authority operation, so the facts
it reads belong to that generation, not to whatever scope the calling thread
happens to hold. Each test here leases without scoping its own context, so a
read that fell back to an ambient scope refuses instead of passing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import IntracomOperationType
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from ....domain.iva.classification import InvoiceKind
from ...exchange_rate_provider import exchange_rate_provider
from ..catalogue_creation import build_catalogue_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_operator_asserted_facts_resolve_under_the_explicit_operation() -> None:
    with private_authority_lease() as operation:
        invoice = build_catalogue_invoice(
            bucket_id=None,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Papeleria Sol SL",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            invoice_number="EXPLICIT-2026-001",
            issued_at=date(2026, 3, 15),
            operation_date=date(2026, 3, 14),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("21"),
            currency="EUR",
            rate_provider=exchange_rate_provider(),
            operation=operation,
        )

    assert invoice.operation_date == date(2026, 3, 14)
    assert invoice.operation_date_role is not None
    assert invoice.grand_total == Decimal("121.00")


def test_the_modelo_349_clave_rule_resolves_under_the_explicit_operation() -> None:
    """An intra-community supply's clave is checked against the handed generation's rule."""
    with private_authority_lease() as operation:
        invoice = build_catalogue_invoice(
            bucket_id=None,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Cliente Intracomunitario GmbH",
            counterparty_tax_id="DE123456789",
            counterparty_country="DE",
            invoice_number="EXPLICIT-2026-002",
            issued_at=date(2026, 3, 15),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0"),
            operation_type=IntracomOperationType.E,
            currency="EUR",
            rate_provider=exchange_rate_provider(),
            operation=operation,
        )

    assert invoice.operation_type is IntracomOperationType.E
