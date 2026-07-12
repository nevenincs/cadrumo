"""Focused unit tests for invoices._importing private helpers.

Three private helpers gate the invoice import pipeline:

- ``_decode_invoice_payload(raw)`` — dispatches between JSON
  object and JSON array based on the first non-whitespace character.
  Raises ``InvoiceValidationError`` on malformed or non-JSON shapes.
- ``_reject_top_level_iva_rate(payload)`` — refuses invoice-level
  ``iva_rate`` values so imported invoices must carry IVA rates on
  each line item.
- ``_coerce_kind(kind)`` — accepts either an already-typed
  :class:`InvoiceKind` member or a string that uppercases to a
  valid member.

Previously exercised only indirectly through
``parse_invoice_payload`` integration tests. A regression in
``_decode_invoice_payload``'s dispatch (e.g. treating a leading
whitespace JSON object as CSV) would silently route well-formed
JSON imports through the CSV reader and produce empty results.

Tests pin each branch's typed output; assertions are
structural / dispatch-contract assertions, not calculation
tautologies.
"""

from __future__ import annotations

import pytest

from ....domain.invoices import InvoiceValidationError
from ....domain.iva import InvoiceKind
from .._importing import (
    _coerce_kind,
    _decode_invoice_payload,
    _reject_top_level_iva_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# _decode_invoice_payload — dispatch contract
# ---------------------------------------------------------------------------


def test_decode_invoice_payload_decodes_single_json_object() -> None:
    raw = '{"invoice_id": "inv-1", "base_total": "100"}'

    (item,) = _decode_invoice_payload(raw)

    assert item.get("invoice_id") == "inv-1"


def test_decode_invoice_payload_decodes_json_array_of_objects() -> None:
    raw = '[{"invoice_id": "inv-1"}, {"invoice_id": "inv-2"}]'

    result = _decode_invoice_payload(raw)

    assert len(result) == 2
    assert [item.get("invoice_id") for item in result] == ["inv-1", "inv-2"]


def test_decode_invoice_payload_handles_leading_whitespace_before_json() -> None:
    """The dispatch keys on ``raw.lstrip()``'s first character so a
    leading newline / indent does not misroute a JSON payload to
    CSV."""
    raw = '\n  {"invoice_id": "inv-1"}'

    (item,) = _decode_invoice_payload(raw)

    assert item.get("invoice_id") == "inv-1"


def test_decode_invoice_payload_rejects_json_with_scalar_top_level() -> None:
    """A JSON top-level decoded as a non-Mapping / non-list shape is
    rejected. The dispatch keys on the first non-whitespace byte
    (``{`` or ``[``); only those branches reach the JSON decoder.
    A top-level number that starts with ``[`` would be a list-of-
    scalars — also rejected by the all-Mapping invariant."""
    with pytest.raises(InvoiceValidationError) as exc_info:
        _decode_invoice_payload("[1, 2, 3]")
    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_json_shape"
    assert exc_info.value.context == {"payload_type": "list"}


def test_decode_invoice_payload_rejects_json_list_of_non_objects() -> None:
    """A list with at least one non-mapping element is rejected so
    the import pipeline cannot silently swallow a malformed entry."""
    with pytest.raises(InvoiceValidationError) as exc_info:
        _decode_invoice_payload('[{"invoice_id": "inv-1"}, "not-an-object"]')
    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_json_shape"
    assert exc_info.value.context == {"payload_type": "list"}


def test_decode_invoice_payload_rejects_malformed_json_with_context() -> None:
    with pytest.raises(InvoiceValidationError) as exc_info:
        _decode_invoice_payload('{"invoice_id": "inv-1"')

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_json"
    assert exc_info.value.context == {"line": "1", "column": "23"}


def test_decode_invoice_payload_rejects_csv_when_no_json_anchor() -> None:
    raw = "invoice_id,base_total\ninv-1,100\ninv-2,200\n"

    with pytest.raises(InvoiceValidationError) as exc_info:
        _decode_invoice_payload(raw)

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_json_shape"
    assert exc_info.value.context == {"payload_type": "csv"}


def test_decode_invoice_payload_rejects_header_only_csv() -> None:
    raw = "invoice_id,base_total\n"

    with pytest.raises(InvoiceValidationError) as exc_info:
        _decode_invoice_payload(raw)

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_json_shape"
    assert exc_info.value.context == {"payload_type": "csv"}


# ---------------------------------------------------------------------------
# _reject_top_level_iva_rate — line-level import contract
# ---------------------------------------------------------------------------


def test_reject_top_level_iva_rate_allows_line_level_payload() -> None:
    payload: dict[str, object] = {"lines": [{"description": "row"}]}

    _reject_top_level_iva_rate(payload)

    assert payload["lines"] == [{"description": "row"}]


def test_reject_top_level_iva_rate_refuses_flat_payload() -> None:
    payload: dict[str, object] = {"base_total": "100", "iva_rate": "21"}

    with pytest.raises(InvoiceValidationError) as exc_info:
        _reject_top_level_iva_rate(payload)

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_json_shape"
    assert exc_info.value.context == {"payload_type": "top-level-iva-rate"}


def test_reject_top_level_iva_rate_refuses_mixed_payload() -> None:
    payload: dict[str, object] = {"lines": [{"description": "row"}], "iva_rate": "RATE_21"}

    with pytest.raises(InvoiceValidationError) as exc_info:
        _reject_top_level_iva_rate(payload)

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_json_shape"
    assert exc_info.value.context == {"payload_type": "top-level-iva-rate"}


# ---------------------------------------------------------------------------
# _coerce_kind — InvoiceKind dispatch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_kind", "expected"),
    [
        pytest.param(InvoiceKind.ISSUED, InvoiceKind.ISSUED, id="typed-issued"),
        pytest.param(InvoiceKind.RECEIVED, InvoiceKind.RECEIVED, id="typed-received"),
        pytest.param("issued", InvoiceKind.ISSUED, id="lowercase-issued"),
        pytest.param("received", InvoiceKind.RECEIVED, id="lowercase-received"),
        pytest.param("  issued  ", InvoiceKind.ISSUED, id="whitespace-issued"),
        pytest.param("ISSUED", InvoiceKind.ISSUED, id="uppercase-issued"),
    ],
)
def test_coerce_kind_accepts_valid_invoice_kind_inputs(
    raw_kind: InvoiceKind | str,
    expected: InvoiceKind,
) -> None:
    """An already-typed :class:`InvoiceKind` member returns
    identically — the helper does not re-construct it."""
    assert _coerce_kind(raw_kind) is expected


def test_coerce_kind_raises_on_unknown_string() -> None:
    """A string outside the invoice-kind contract raises the invoice error type."""
    with pytest.raises(InvoiceValidationError) as exc_info:
        _coerce_kind("not-a-kind")

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_kind"
    assert exc_info.value.context == {"kind": "not-a-kind"}
