"""Encoding and native-console contracts owned by the shared command client."""

from __future__ import annotations

import io

import pytest

from ..stdio import _set_windows_console_utf8, configure_stdio_for_utf8

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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
