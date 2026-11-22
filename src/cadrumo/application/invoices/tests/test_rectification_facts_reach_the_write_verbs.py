"""The add and update verbs carry the rectification facts from their request to the record.

The facts are useless if the record can hold them and no verb can set them.
These tests take them through the two production write paths:

- ``ledger.invoice.add``'s own request, decoded from its wire JSON and built by
  the real :func:`build_invoice_from_add_request` the worker calls, so the
  request's stated tokens reach the invoice projected through fact 0141 on the
  invoice's own issue date;
- ``ledger.invoice.update``'s patch across the real serialisation round trip
  the operation performs, so a correction's facts survive transport and reach
  the corrected record.

The update half also proves the direction nobody would think to check: a fact
entered in error can be WITHDRAWN, not only replaced, because a person who
mistyped a cause must be able to take it back rather than being forced to state
a different wrong one.

Real-behaviour: real contracts, the real worker builder and the real lifecycle
correction over the published authority. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.rectification import missing_rectification_facts, required_rectification_facts
from ....domain.iva.schema import InvoiceKind
from ..catalogue_add_contracts import InvoiceAddRequest
from ..catalogue_add_operation import build_invoice_from_add_request, invoice_add_lease
from ..catalogue_lifecycle import CatalogueInvoicePatch
from ..catalogue_update_operation import InvoiceUpdatePatch
from .figures_preview_support import NoRate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE = "5a5a5a5a-5a5a-4a5a-8a5a-5a5a5a5a5a5a"
_YEAR = filing_year_envelope().horizon
_ISSUED_AT = date(_YEAR, 4, 15)
_RECEIVED_ON = _ISSUED_AT + timedelta(days=9)


def _served_tokens() -> tuple[str, str, str]:
    """A method, cause and direction fact 0141 declares for the issue date."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    return (
        str(catalogue.sustitucion_token),
        str(catalogue.error_fundado_de_derecho_cause_token),
        str(catalogue.aumento_token),
    )


def _add_request(**overrides: object) -> InvoiceAddRequest:
    """One received rectificativa add request, decoded from its own wire JSON.

    Decoded through ``model_validate_json`` rather than constructed, because
    what the worker receives is JSON: a field the request serialises but cannot
    read back would pass a constructor and fail the verb.
    """
    body: dict[str, object] = {
        "profile_id": _PROFILE,
        "kind": InvoiceKind.RECEIVED.value,
        "counterparty_name": "Proveedor SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "invoice_number": "2026/R-0001",
        "issued_at": _ISSUED_AT.isoformat(),
        "taxable_base": {"decimal": "1000.00"},
        "iva_rate": {"decimal": "21"},
        "currency": "EUR",
        "invoice_class": "RECTIFICATIVA",
        "series": "R",
        "rectifies_invoice_number": "2026/F-0001",
    }
    body.update(overrides)
    return InvoiceAddRequest.model_validate_json(json.dumps(body))


def _built(payload: InvoiceAddRequest, operation: PinnedAuthorityOperation):
    invoice, _advisory = build_invoice_from_add_request(
        payload=payload,
        business_premises_lease=invoice_add_lease(payload, authority_operation=operation),
        profile=_PROFILE,
        authority_operation=operation,
        rate_provider=NoRate(),
    )
    return invoice


def test_the_add_request_carries_every_fact_onto_the_record(operation: PinnedAuthorityOperation) -> None:
    """Each stated token reaches the invoice as the projected registry token it names."""
    method, cause, direction = _served_tokens()

    invoice = _built(
        _add_request(
            rectification_method=method,
            rectification_cause=cause,
            rectification_direction=direction,
            document_received_on=_RECEIVED_ON.isoformat(),
        ),
        operation,
    )

    assert str(invoice.rectification_method) == method
    assert str(invoice.rectification_cause) == cause
    assert str(invoice.rectification_direction) == direction
    assert invoice.document_received_on == _RECEIVED_ON
    assert missing_rectification_facts(invoice) == ()
    # The record stays a magnitude record: the direction, not a sign, is the sense.
    assert invoice.base_total == Decimal("1000.00")


def test_an_add_request_stating_no_fact_still_creates_the_rectificativa(
    operation: PinnedAuthorityOperation,
) -> None:
    """Nothing is defaulted on the way in; every fact the document lacks is reported absent."""
    invoice = _built(_add_request(), operation)

    assert invoice.rectification_method is None
    assert invoice.rectification_cause is None
    assert invoice.rectification_direction is None
    assert invoice.document_received_on is None
    assert missing_rectification_facts(invoice) == required_rectification_facts(InvoiceKind.RECEIVED)


def test_an_add_request_with_a_reception_date_on_an_issued_invoice_is_refused(
    operation: PinnedAuthorityOperation,
) -> None:
    """The write boundary's kind rule reaches the verb rather than the record alone."""
    with pytest.raises(Exception) as refusal:
        _built(
            _add_request(kind=InvoiceKind.ISSUED.value, document_received_on=_RECEIVED_ON.isoformat()),
            operation,
        )

    assert "only applies to a received invoice" in str(refusal.value)


def test_the_update_patch_carries_the_facts_across_its_wire_round_trip() -> None:
    """A correction's four facts survive serialisation with their field mask intact."""
    method, cause, direction = _served_tokens()
    patch = CatalogueInvoicePatch.model_validate(
        {
            "rectification_method": method,
            "rectification_cause": cause,
            "rectification_direction": direction,
            "document_received_on": _RECEIVED_ON,
        },
    )

    restored = InvoiceUpdatePatch.model_validate_json(InvoiceUpdatePatch.from_patch(patch).model_dump_json()).to_patch()

    assert restored.rectification_method == method
    assert restored.rectification_cause == cause
    assert restored.rectification_direction == direction
    assert restored.document_received_on == _RECEIVED_ON
    assert restored.model_fields_set == {
        "rectification_method",
        "rectification_cause",
        "rectification_direction",
        "document_received_on",
    }


def test_the_update_patch_can_withdraw_a_fact_entered_in_error() -> None:
    """An explicit ``None`` clears the fact, so a mistyped cause can be taken back.

    The field mask, not the value, carries the selection, which is why a
    cleared fact and an untouched one stay distinguishable across transport.
    """
    patch = CatalogueInvoicePatch.model_validate({"rectification_cause": None})

    restored = InvoiceUpdatePatch.model_validate_json(InvoiceUpdatePatch.from_patch(patch).model_dump_json()).to_patch()

    assert restored.rectification_cause is None
    assert restored.model_fields_set == {"rectification_cause"}
    # An untouched fact is NOT in the mask, so the correction leaves it alone.
    assert "rectification_method" not in restored.model_fields_set
