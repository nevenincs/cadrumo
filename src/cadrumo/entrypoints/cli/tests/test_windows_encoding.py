"""Windows encoding regression tests for CLI stderr emission.

Pins the contract that
:func:`cadrumo.entrypoints.cli.errors.write_stderr` never raises when
the underlying stream uses the Windows default ``cp1252`` codec, even
when :func:`cadrumo.core.errors.render_error_text` produces non-ASCII
characters under the operator's configured language.

Also pins that :func:`cadrumo.entrypoints.cli._stdio.configure_stdio_for_utf8`
emits bytes that are valid UTF-8 regardless of the ambient console code
page, and that :func:`_set_windows_console_utf8` runs without error on
all platforms (including non-Windows where it is a no-op).
"""

from __future__ import annotations

import io

import pytest

from ....core.access_gate.errors import LiveSubmitForbiddenError
from ....core.errors.error_codes import render_error_text
from .._stdio import _set_windows_console_utf8, configure_stdio_for_utf8
from ..errors import write_stderr

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _output_language(language: str):
    """Pin ``cadrumo_output_language`` for the duration of a test.

    Delegates to the canonical Settings override API
    (:func:`cadrumo.core.config.override_settings`); the production
    locale resolver reads through ``load_settings`` so the ContextVar
    layer is reached.
    """
    from ....core.config import override_settings

    return override_settings(cadrumo_output_language=language)


_NON_ASCII_ERROR_CASES = (("es", "envío"), ("hu", "élő"))


def test_cp1252_stderr_path_does_not_raise_on_non_ascii_output() -> None:
    """``write_stderr`` survives a ``cp1252`` stream when emitting non-ASCII glyphs."""
    failures: list[str] = []
    for language, expected_fragment in _NON_ASCII_ERROR_CASES:
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

        with _output_language(language):
            write_stderr(render_error_text(LiveSubmitForbiddenError()), stream=stream)

        rendered = buffer.getvalue().decode("utf-8")
        if expected_fragment not in rendered:
            failures.append(f"{language}: missing {expected_fragment!r} in {rendered!r}")

    assert not failures, "\n".join(failures)


def test_write_stderr_redacts_sensitive_canaries() -> None:
    profile_id = "123e4567-e89b-12d3-a456-426614174000"
    stream = io.StringIO()

    write_stderr(f"profile={profile_id}", stream=stream)

    rendered = stream.getvalue()
    assert profile_id not in rendered
    assert "profile=<profile-id>" in rendered


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
