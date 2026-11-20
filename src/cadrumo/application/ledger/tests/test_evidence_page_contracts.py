"""A structured e-invoice fact states one value of the kind its served key declares."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....application.operations.public_scalar import PublicDecimal
from ..evidence_page_contracts import (
    EVIDENCE_STRUCTURED_FACT_KEYS,
    EVIDENCE_STRUCTURED_LINE_KEYS,
    EVIDENCE_STRUCTURED_VALUE_KINDS,
    EvidenceStructuredFactV1,
    EvidenceStructuredValueKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FACT = "application.ledger.evidence.structured.fact."
_LINE = "application.ledger.evidence.structured.line."
_TWENTY_ONE = PublicDecimal(decimal="21")


def test_every_declared_kind_names_a_served_key() -> None:
    served = {key for _field, key in (*EVIDENCE_STRUCTURED_FACT_KEYS, *EVIDENCE_STRUCTURED_LINE_KEYS)}

    assert set(EVIDENCE_STRUCTURED_VALUE_KINDS) <= served


def test_a_date_is_carried_as_a_calendar_date() -> None:
    fact = EvidenceStructuredFactV1(
        label_key=_FACT + "invoice_date", value_kind=EvidenceStructuredValueKind.DATE, iso_date=date(2024, 11, 15)
    )

    assert fact.model_dump(mode="json")["iso_date"] == "2024-11-15"


def test_a_rate_is_a_percentage_figure_and_a_quantity_a_plain_one() -> None:
    EvidenceStructuredFactV1(
        label_key=_LINE + "iva_rate", value_kind=EvidenceStructuredValueKind.RATE_PERCENT, number=_TWENTY_ONE
    )
    EvidenceStructuredFactV1(
        label_key=_LINE + "quantity", value_kind=EvidenceStructuredValueKind.QUANTITY, number=_TWENTY_ONE
    )


@pytest.mark.parametrize(
    "fields",
    [
        # no value at all
        {"label_key": _FACT + "invoice_number", "value_kind": EvidenceStructuredValueKind.TEXT},
        # two values
        {
            "label_key": _FACT + "invoice_number",
            "value_kind": EvidenceStructuredValueKind.TEXT,
            "text": "A-1",
            "number": _TWENTY_ONE,
        },
        # a kind whose member is not the one carried
        {"label_key": _FACT + "grand_total", "value_kind": EvidenceStructuredValueKind.AMOUNT, "text": "121,00"},
        {"label_key": _FACT + "invoice_date", "value_kind": EvidenceStructuredValueKind.DATE, "text": "2024-11-15"},
        # a kind the served key does not declare
        {
            "label_key": _FACT + "grand_total",
            "value_kind": EvidenceStructuredValueKind.RATE_PERCENT,
            "number": _TWENTY_ONE,
        },
        {"label_key": _FACT + "supplier_name", "value_kind": EvidenceStructuredValueKind.AMOUNT, "number": _TWENTY_ONE},
        # a key the read does not serve
        {"label_key": _FACT + "unknown", "value_kind": EvidenceStructuredValueKind.TEXT, "text": "x"},
    ],
    ids=["none", "two", "amount-as-text", "date-as-text", "wrong-numeric-kind", "name-as-amount", "unserved-key"],
)
def test_a_fact_that_contradicts_its_kind_or_its_key_is_refused(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EvidenceStructuredFactV1.model_validate(fields)


def test_a_figure_the_record_states_unreadably_may_still_be_served_as_its_text() -> None:
    fact = EvidenceStructuredFactV1(
        label_key=_FACT + "invoice_date", value_kind=EvidenceStructuredValueKind.TEXT, text="15/11/24"
    )

    assert fact.text == "15/11/24"
