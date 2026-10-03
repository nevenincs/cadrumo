"""Declared wizard facts use canonical validation, construction and no-op identity."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.iva.classification import InvoiceKind
from ..creation_wizard import create_invoice_via_wizard
from ._catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = "29292929-2929-4292-8292-292929292929"


def test_wizard_preserves_all_four_declared_facts_and_idempotent_noop(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    ports = in_memory_catalogue_creation_ports()
    with validating_governed_facts(authority_operation):

        def create():
            return create_invoice_via_wizard(
                bucket_id=_PROFILE,
                kind=InvoiceKind.RECEIVED,
                counterparty_nif="A58818501",
                counterparty_name="Synthetic supplier",
                invoice_number="WIZARD-R1",
                invoice_date="2026-05-01",
                taxable_base="100.00",
                iva_rate="21",
                currency="EUR",
                country_code="ES",
                invoice_class="RECTIFICATIVA",
                series="R",
                rectifies_invoice_number="ORIGINAL-1",
                recargo_amount="5.20",
                ports=ports,
                operation=authority_operation,
            )

        first, repeated = create(), create()
    invoice = first.invoice
    assert str(invoice.invoice_class) == "RECTIFICATIVA"
    assert invoice.series == "R" and invoice.rectifies_invoice_number == "ORIGINAL-1"
    assert invoice.recargo_amount == Decimal("5.20") and invoice.grand_total == Decimal("126.20")
    assert not first.already_existed and repeated.already_existed and repeated.invoice == invoice
    assert len(ports.invoice_repository.load()) == 1 and len(ports.event_repository.load().events) == 1


def test_wizard_accumulates_new_and_existing_field_refusals_before_write(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    ports = in_memory_catalogue_creation_ports()
    with validating_governed_facts(authority_operation), pytest.raises(InvoiceValidationError) as refused:
        create_invoice_via_wizard(
            bucket_id=_PROFILE,
            kind=InvoiceKind.RECEIVED,
            counterparty_nif="A58818501",
            counterparty_name="",
            invoice_number="WIZARD-BAD",
            invoice_date="2026-05-01",
            taxable_base="invalid",
            iva_rate="21",
            currency="EUR",
            country_code="ES",
            invoice_class="UNDECLARED",
            series=" ",
            rectifies_invoice_number=" ",
            recargo_amount="-5",
            ports=ports,
            operation=authority_operation,
        )
    assert refused.value.translated_message == "application.invoices.wizard.errors.field_errors"
    assert refused.value.context is not None
    field_names = refused.value.context["fields"]
    assert isinstance(field_names, str)
    fields = set(field_names.split(", "))
    assert fields == {
        "counterparty_name",
        "taxable_base",
        "invoice_class",
        "series",
        "rectifies_invoice_number",
        "recargo_amount",
    }
    assert len(ports.invoice_repository.load()) == 0 and not ports.event_repository.load().events
