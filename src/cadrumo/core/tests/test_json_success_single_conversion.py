"""The success envelope is converted to JSON shape once and written unchanged."""

from __future__ import annotations

import io
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from ..json_contract import emit_json_success
from ..output_rendering import jsonable_output_payload
from ..redaction.rules import redact_structured_for_cli_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Line(BaseModel):
    amount: Decimal
    booked: date


def _payload() -> dict[str, object]:
    return {
        "exponent_amount": Decimal("1E+2"),
        "booked": date(2025, 12, 31),
        "stamped": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "export": Path("exports") / "ledger.csv",
        "pair": ("B12345674", Decimal("0.10")),
        "tags": frozenset({"mixed"}),
        "lines": [_Line(amount=Decimal("12.50"), booked=date(2025, 3, 1))],
        "note": "invoice for B12345674 at https://example.org/private/path",
    }


def _converted_twice(payload: dict[str, object]) -> str:
    envelope = redact_structured_for_cli_output(
        {
            "schema_version": 1,
            "command": "app ledger list",
            "active_profile": "operator",
            "status": "ok",
            "result": jsonable_output_payload(payload),
            "notices": [],
        },
    )
    return json.dumps(jsonable_output_payload(envelope), ensure_ascii=False, indent=2, default=str) + "\n"


def test_the_emitted_envelope_equals_a_twice_converted_one() -> None:
    stream = io.StringIO()
    emit_json_success("app ledger list", _payload(), active_profile="operator", stream=stream)
    emitted = json.loads(stream.getvalue())
    expected = json.loads(_converted_twice(_payload()))

    assert emitted["result"] == expected["result"]
    assert emitted["result"]["exponent_amount"] == "100"
    assert emitted["result"]["lines"] == [{"amount": "12.50", "booked": "2025-03-01"}]
    assert "B12345674" not in stream.getvalue()


def test_the_emitted_bytes_are_the_twice_converted_bytes() -> None:
    stream = io.StringIO()
    emit_json_success("app ledger list", _payload(), active_profile="operator", stream=stream)
    emitted = json.loads(stream.getvalue())
    expected = _converted_twice(_payload())
    expected_document = json.loads(expected)
    expected_document["schema_version"] = emitted["schema_version"]
    expected_document["status"] = emitted["status"]

    assert stream.getvalue() == json.dumps(expected_document, ensure_ascii=False, indent=2) + "\n"
