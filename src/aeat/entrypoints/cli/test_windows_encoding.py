"""Windows encoding regression tests for CLI stderr emission.

Pins the contract that
:func:`aeat.entrypoints.cli._errors.write_stderr` never raises when
the underlying stream uses the Windows default ``cp1252`` codec, even
when :func:`aeat.core.errors.render_error_text` produces non-ASCII
characters under the operator's configured language.

Also pins that :func:`aeat.entrypoints.cli._stdio.configure_stdio_for_utf8`
emits bytes that are valid UTF-8 regardless of the ambient console code
page, and that :func:`_set_windows_console_utf8` runs without error on
all platforms (including non-Windows where it is a no-op).
"""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from ...core.access_gate import LiveSubmitForbiddenError
from ...core.errors import render_error_text
from ._errors import write_stderr
from ._stdio import _set_windows_console_utf8, configure_stdio_for_utf8

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@contextmanager
def _output_language(language: str) -> Iterator[None]:
    """Temporarily override ``AEAT_OUTPUT_LANGUAGE`` for the duration of a test."""
    previous = os.environ.get("AEAT_OUTPUT_LANGUAGE")
    os.environ["AEAT_OUTPUT_LANGUAGE"] = language
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("AEAT_OUTPUT_LANGUAGE", None)
        else:
            os.environ["AEAT_OUTPUT_LANGUAGE"] = previous


@pytest.mark.parametrize(
    ("language", "expected_fragment"),
    [
        ("es", "envío"),
        ("hu", "élő"),
    ],
)
def test_cp1252_stderr_path_does_not_raise_on_non_ascii_output(
    language: str,
    expected_fragment: str,
) -> None:
    """``write_stderr`` survives a ``cp1252`` stream when emitting non-ASCII glyphs."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

    with _output_language(language):
        write_stderr(render_error_text(LiveSubmitForbiddenError()), stream=stream)

    rendered = buffer.getvalue().decode("utf-8")
    assert expected_fragment in rendered


def test_set_windows_console_utf8_does_not_raise() -> None:
    """``_set_windows_console_utf8`` must not raise on any platform.

    On non-Windows it returns immediately (no-op).  On Windows it calls
    ``SetConsoleOutputCP(65001)``; in a redirected / piped subprocess
    (as in CI) the API call is silently ignored.  Either way the
    function must never propagate an exception.
    """
    _set_windows_console_utf8()  # must not raise


def test_configure_stdio_for_utf8_streams_emit_valid_utf8() -> None:
    """Streams reconfigured by ``configure_stdio_for_utf8`` must produce valid UTF-8.

    Regression for the mojibake bug where Spanish accented characters
    (e.g. ``ó``) were mis-rendered by a Windows console whose code page
    was cp850/cp1252.  The fix is that ``configure_stdio_for_utf8`` sets
    the Windows console code page to 65001 (UTF-8) via
    ``SetConsoleOutputCP`` *before* reconfiguring the Python streams.
    This test exercises the stream-level side: bytes written to a
    reconfigured stream are decodable as UTF-8.
    """
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="replace")
    configure_stdio_for_utf8(stderr=stream)

    spanish_text = "La vinculación no está configurada"
    stream.write(spanish_text)
    stream.flush()

    rendered = buffer.getvalue().decode("utf-8")
    assert "vinculaci" in rendered
    # Confirm no cp1252 double-encoding artifacts (Ã³ for ó, etc.)
    assert "\xc3\xb3" not in rendered  # literal two-byte sequence in str would be double-encode
    assert "Ã" not in rendered
