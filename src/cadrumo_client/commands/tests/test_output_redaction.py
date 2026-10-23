"""Command stderr carries only redacted text on every encoding route."""

from __future__ import annotations

import io
from typing import BinaryIO, override

import pytest

from ..output import write_stderr

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_IBAN = "ES9121000418450200051332"
_NIF = "12345678Z"
_BEARER_VALUE = "abcdefghijklmnop0123"
_LINE = f"Revisión: cuenta {_IBAN}, titular {_NIF}, Bearer {_BEARER_VALUE}"


class _AsciiOnlyStream(io.StringIO):
    """A console that cannot encode non-ASCII text, as a legacy code page refuses it."""

    @override
    def write(self, s: str, /) -> int:
        s.encode("ascii")
        return super().write(s)


class _AsciiOnlyStreamWithBuffer(_AsciiOnlyStream):
    def __init__(self) -> None:
        super().__init__()
        self.raw = io.BytesIO()

    @property
    @override
    def buffer(self) -> BinaryIO:
        return self.raw


def _assert_redacted(written: str) -> None:
    assert "cuenta sha256:" in written
    assert _IBAN not in written
    assert _NIF not in written
    assert _BEARER_VALUE not in written


def test_a_writable_stream_receives_the_redacted_line() -> None:
    stream = io.StringIO()
    write_stderr(_LINE, stream=stream)
    _assert_redacted(stream.getvalue())


def test_the_utf8_buffer_fallback_receives_the_redacted_line() -> None:
    stream = _AsciiOnlyStreamWithBuffer()
    write_stderr(_LINE, stream=stream)
    assert stream.getvalue() == ""
    _assert_redacted(stream.raw.getvalue().decode("utf-8"))


def test_the_ascii_replacement_fallback_receives_the_redacted_line() -> None:
    stream = _AsciiOnlyStream()
    write_stderr(_LINE, stream=stream)
    written = stream.getvalue()
    assert written.startswith("Revisi?n:")
    _assert_redacted(written)
