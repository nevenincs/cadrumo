"""Focused unit tests for invoices._importing private helpers.

Three private helpers gate the invoice import pipeline:

- ``_decode_invoice_payload(raw)`` — dispatches between JSON
  object, JSON array, and CSV based on the first non-whitespace
  character. Raises ``ValueError`` on malformed JSON shapes.
- ``_synthesise_single_line_if_needed(payload)`` — back-fills a
  single ``lines`` entry from the legacy ``base_total`` /
  ``iva_rate`` / ``iva_total`` flat shape. The IVA rate is mapped
  through ``_IVA_RATE_ALIASES`` so the wire string ``"21"``
  resolves to the substrate slot name ``RATE_21``.
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

from typing import cast

import pytest

from ....domain.invoices import InvoiceValidationError
from ....domain.iva import InvoiceKind
from .._importing import (
    _IVA_RATE_ALIASES,
    _coerce_kind,
    _decode_invoice_payload,
    _synthesise_single_line_if_needed,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# _decode_invoice_payload — dispatch contract
# ---------------------------------------------------------------------------


def test_decode_invoice_payload_decodes_single_json_object() -> None:
    raw = '{"invoice_id": "inv-1", "base_total": "100"}'

    result = _decode_invoice_payload(raw)

    assert len(result) == 1
    assert result[0].get("invoice_id") == "inv-1"


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

    result = _decode_invoice_payload(raw)

    assert len(result) == 1
    assert result[0].get("invoice_id") == "inv-1"


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


def test_decode_invoice_payload_decodes_csv_when_no_json_anchor() -> None:
    raw = "invoice_id,base_total\ninv-1,100\ninv-2,200\n"

    result = _decode_invoice_payload(raw)

    assert len(result) == 2
    assert result[0].get("invoice_id") == "inv-1"
    assert result[1].get("base_total") == "200"


def test_decode_invoice_payload_csv_returns_empty_tuple_for_header_only() -> None:
    """A CSV with only a header row produces no records."""
    raw = "invoice_id,base_total\n"

    result = _decode_invoice_payload(raw)

    assert result == ()


# ---------------------------------------------------------------------------
# _synthesise_single_line_if_needed — back-fill contract
# ---------------------------------------------------------------------------


def test_synthesise_single_line_returns_silently_when_lines_already_set() -> None:
    """When the payload already carries ``lines`` the helper is a
    no-op; pre-existing entries are not touched."""
    payload: dict[str, object] = {"lines": [{"description": "row"}]}

    _synthesise_single_line_if_needed(payload)

    assert payload["lines"] == [{"description": "row"}]


def test_synthesise_single_line_skips_when_base_total_missing() -> None:
    payload: dict[str, object] = {"iva_rate": "21"}

    _synthesise_single_line_if_needed(payload)

    assert "lines" not in payload


def test_synthesise_single_line_skips_when_iva_rate_missing() -> None:
    payload: dict[str, object] = {"base_total": "100"}

    _synthesise_single_line_if_needed(payload)

    assert "lines" not in payload


def test_synthesise_single_line_rejects_non_decimal_base_total_with_context() -> None:
    payload: dict[str, object] = {"base_total": "not-a-decimal", "iva_rate": "21"}

    with pytest.raises(InvoiceValidationError) as exc_info:
        _synthesise_single_line_if_needed(payload)

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_base_total"
    assert exc_info.value.context == {"base_total": "not-a-decimal"}


def test_synthesise_single_line_back_fills_with_substrate_slot_alias() -> None:
    """Wire rate ``"21"`` maps through ``_IVA_RATE_ALIASES`` to the
    substrate slot name ``"RATE_21"``."""
    payload: dict[str, object] = {"base_total": "100", "iva_rate": "21", "iva_total": "21"}

    _synthesise_single_line_if_needed(payload)

    assert "lines" in payload
    lines = payload["lines"]
    assert isinstance(lines, list)
    first_line = cast(dict[str, object], lines[0])
    assert first_line["iva_rate"] == "RATE_21"
    assert first_line["subtotal"] == "100"
    assert first_line["iva_amount"] == "21"


def test_synthesise_single_line_pops_top_level_iva_rate_after_projection() -> None:
    """After back-filling the line, the top-level ``iva_rate`` is
    removed so it does not double-flow into Invoice.model_validate."""
    payload: dict[str, object] = {"base_total": "100", "iva_rate": "21"}

    _synthesise_single_line_if_needed(payload)

    assert "iva_rate" not in payload


def test_synthesise_single_line_passes_through_unknown_rate_string_unchanged() -> None:
    """A rate string outside the alias table passes through verbatim
    (so substrate-slot names like ``"RATE_21"`` already in the
    payload survive the projection without double-aliasing)."""
    payload: dict[str, object] = {"base_total": "50", "iva_rate": "RATE_21"}

    _synthesise_single_line_if_needed(payload)

    lines = payload["lines"]
    assert isinstance(lines, list)
    first_line = cast(dict[str, object], lines[0])
    assert first_line["iva_rate"] == "RATE_21"


def test_synthesise_single_line_defaults_iva_amount_to_zero_when_absent() -> None:
    """When iva_total is absent the back-fill defaults the line's
    iva_amount to ``"0"`` rather than raising."""
    payload: dict[str, object] = {"base_total": "100", "iva_rate": "0"}

    _synthesise_single_line_if_needed(payload)

    lines = payload["lines"]
    assert isinstance(lines, list)
    first_line = cast(dict[str, object], lines[0])
    assert first_line["iva_amount"] == "0"


def test_iva_rate_alias_table_covers_every_canonical_substrate_slot() -> None:
    """The wire-to-substrate alias map mirrors the IvaRate substrate
    slot set used by invoice lines: every percentage maps to its
    canonical RATE_{n} slot."""
    assert _IVA_RATE_ALIASES == {
        "0": "RATE_0",
        "4": "RATE_4",
        "10": "RATE_10",
        "21": "RATE_21",
    }


# ---------------------------------------------------------------------------
# _coerce_kind — InvoiceKind dispatch
# ---------------------------------------------------------------------------


def test_coerce_kind_passes_invoice_kind_through_unchanged() -> None:
    """An already-typed :class:`InvoiceKind` member returns
    identically — the helper does not re-construct it."""
    assert _coerce_kind(InvoiceKind.ISSUED) is InvoiceKind.ISSUED
    assert _coerce_kind(InvoiceKind.RECEIVED) is InvoiceKind.RECEIVED


def test_coerce_kind_uppercases_lowercase_string() -> None:
    assert _coerce_kind("issued") is InvoiceKind.ISSUED
    assert _coerce_kind("received") is InvoiceKind.RECEIVED


def test_coerce_kind_strips_surrounding_whitespace() -> None:
    assert _coerce_kind("  issued  ") is InvoiceKind.ISSUED


def test_coerce_kind_handles_already_uppercase_string() -> None:
    assert _coerce_kind("ISSUED") is InvoiceKind.ISSUED


def test_coerce_kind_raises_on_unknown_string() -> None:
    """A string outside the invoice-kind contract raises the invoice error type."""
    with pytest.raises(InvoiceValidationError) as exc_info:
        _coerce_kind("not-a-kind")

    assert exc_info.value.translated_message == "application.invoices.importing.errors.invalid_kind"
    assert exc_info.value.context == {"kind": "not-a-kind"}
