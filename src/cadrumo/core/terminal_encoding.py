r"""Terminal-context encoding for operator-facing text.

Confidentiality redaction decides which values an operator may see; this module
decides how any surviving text may reach a terminal. Imported narratives
(statement descriptions, invoice text, feed fields) are attacker influenced, so
ESC, C0/C1 controls (including the 8-bit CSI/OSC introducers), carriage
returns, DEL, Unicode line/paragraph separators and bidi formatting controls
are rendered as visible ``\u001b`` / ``\r`` / ``\u202e`` escapes instead of
being emitted raw. The terminal protocol parser therefore never sees them.

Every escape this module writes is also a valid JSON string escape, and a
serialized JSON document never contains a raw control outside its string
literals, so the same encoding applies to text and JSON output alike: a JSON
document passed through :func:`encode_terminal_text` parses to the same value.

Two functions express the two separator policies. :func:`encode_terminal_text`
keeps newline and tab, because rendered output uses them as deliberate line and
column separators. :func:`encode_terminal_field` escapes them too, for one
untrusted value interpolated into such a line, so an embedded newline cannot
forge an extra output row nor a tab shift columns.
"""

from __future__ import annotations

_C0_EXCEPT_SEPARATORS = (*range(0x00, 0x09), *range(0x0B, 0x20))
_DEL_AND_C1 = tuple(range(0x7F, 0xA0))
_LINE_AND_PARAGRAPH_SEPARATORS = (0x2028, 0x2029)
#: Unicode bidirectional formatting controls (marks, embeddings, overrides and
#: isolates) that can visually reorder terminal output.
_BIDI_CONTROLS = (0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A))

_NEWLINE = 0x0A
_TAB = 0x09
_CARRIAGE_RETURN = 0x0D


def _visible_escape(codepoint: int) -> str:
    if codepoint == _CARRIAGE_RETURN:
        return "\\r"
    return f"\\u{codepoint:04x}"


_TEXT_TABLE = {
    codepoint: _visible_escape(codepoint)
    for codepoint in (
        *_C0_EXCEPT_SEPARATORS,
        *_DEL_AND_C1,
        *_LINE_AND_PARAGRAPH_SEPARATORS,
        *_BIDI_CONTROLS,
    )
}
_FIELD_TABLE = {**_TEXT_TABLE, _NEWLINE: "\\n", _TAB: "\\t"}


def encode_terminal_text(text: str) -> str:
    r"""Return ``text`` with terminal controls visibly escaped, keeping ``\n`` and ``\t``."""
    return text.translate(_TEXT_TABLE)


def encode_terminal_field(value: str) -> str:
    r"""Return one untrusted value with every control, including ``\n`` and ``\t``, escaped."""
    return value.translate(_FIELD_TABLE)
