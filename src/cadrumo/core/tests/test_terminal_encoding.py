"""Tests for terminal-context encoding of operator-facing text."""

from __future__ import annotations

import io
import json

import pytest

from ..json_contract import emit_json_success
from ..output_rendering import render_command_output
from ..redaction.rules import redact_structured_for_cli_output
from ..terminal_encoding import encode_terminal_field, encode_terminal_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Built from code points so no invisible character is ever written into this source.
_ESC = chr(0x1B)
_BEL = chr(0x07)
_C1_CSI = chr(0x9B)
_RLO = chr(0x202E)
_PDF = chr(0x202C)

_CSI_CLEAR = f"{_ESC}[2J{_ESC}[H"
_OSC8_LINK = f"{_ESC}]8;;https://attacker.test/{_ESC}\\Pay here{_ESC}]8;;{_ESC}\\"
_OSC52_CLIPBOARD = f"{_ESC}]52;c;ZWNobyBwd25lZA=={_BEL}"
_C1_SEQUENCE = f"{_C1_CSI}31m"
_CARRIAGE_RETURN = "Refund 10.00\rRefund 9999.00"
_BIDI_OVERRIDE = f"Invoice {_RLO}gnp.exe{_PDF}"
_PAYLOADS = (_CSI_CLEAR, _OSC8_LINK, _OSC52_CLIPBOARD, _C1_SEQUENCE, _CARRIAGE_RETURN, _BIDI_OVERRIDE)

_UNSAFE = frozenset(
    [chr(code) for code in range(0x20) if chr(code) not in "\n\t"]
    + [chr(code) for code in range(0x7F, 0xA0)]
    + [chr(code) for code in (0x061C, 0x200E, 0x200F, 0x2028, 0x2029)]
    + [chr(code) for code in range(0x202A, 0x202F)]
    + [chr(code) for code in range(0x2066, 0x206A)],
)


def _assert_inert(text: str) -> None:
    assert not _UNSAFE.intersection(text)


@pytest.mark.parametrize("payload", _PAYLOADS)
def test_text_output_renders_terminal_controls_inert(payload: str) -> None:
    rendered = render_command_output(format_name="text", payload=None, lines=(f"row\t{payload}",))

    _assert_inert(rendered.text)
    assert rendered.text.startswith("row\t")


def test_text_output_escapes_visibly_and_keeps_printable_text() -> None:
    rendered = render_command_output(format_name="text", payload=None, lines=(_CSI_CLEAR + "ok", _CARRIAGE_RETURN))

    assert rendered.text == "\\u001b[2J\\u001b[Hok\nRefund 10.00\\rRefund 9999.00"


def test_text_output_keeps_deliberate_line_and_column_separators() -> None:
    rendered = render_command_output(format_name="text", payload=None, lines=("a\tb", "c\nd"))

    assert rendered.text == "a\tb\nc\nd"


def test_field_encoding_escapes_embedded_newline_and_tab() -> None:
    assert encode_terminal_field(f"line one\nforged\trow{_RLO}") == "line one\\nforged\\trow\\u202e"


def test_text_encoding_maps_every_unsafe_character_to_a_visible_escape() -> None:
    encoded = encode_terminal_text("".join(sorted(_UNSAFE)))

    _assert_inert(encoded)
    assert encoded.count("\\") == len(_UNSAFE)


@pytest.mark.parametrize("payload", (*_PAYLOADS, "embedded\nnewline"))
def test_json_output_remains_valid_escaped_and_lossless(payload: str) -> None:
    rendered = render_command_output(format_name="json", payload={"description": payload}, lines=())

    _assert_inert(rendered.text)
    assert "\n" not in rendered.text
    # Escaping is lossless: parsing yields exactly the redacted value.
    assert json.loads(rendered.text) == redact_structured_for_cli_output(
        {"description": payload},
        reveal_identifiers=False,
    )


@pytest.mark.parametrize("payload", _PAYLOADS)
def test_encoding_a_pretty_printed_json_document_keeps_it_valid_and_equal(payload: str) -> None:
    document = {"error": {"message": payload, "context": [payload, "Cafeteria Ñandú €"]}}

    encoded = encode_terminal_text(json.dumps(document, ensure_ascii=False, indent=2))

    _assert_inert(encoded)
    assert json.loads(encoded) == document


def test_plain_unicode_passes_through_unchanged() -> None:
    text = "Cafeteria Ñandú € — 12345678Z"

    assert encode_terminal_text(text) == text
    assert encode_terminal_field(text) == text


@pytest.mark.parametrize("payload", (_OSC52_CLIPBOARD, _C1_SEQUENCE, _BIDI_OVERRIDE))
def test_json_success_envelope_reaches_the_stream_inert(payload: str) -> None:
    stream = io.StringIO()

    emit_json_success("ledger.list", {"description": payload}, stream=stream)

    written = stream.getvalue()
    _assert_inert(written)
    assert json.loads(written)["result"] == {"description": payload}
