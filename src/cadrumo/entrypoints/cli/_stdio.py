"""Force the CLI's standard streams onto UTF-8, and its help/error rendering to plain text.

Default Windows terminals expose stdout / stderr as cp1252; emoji
flag characters, CJK ideographs, the U+2192 right arrow used by the
review queue table, and the § sign used by some IVA-rate citations
all fall outside cp1252 and crash :func:`~typer.echo` with
``UnicodeEncodeError``. Spanish accented characters (``á é í ó ú``,
``ñ``) survive the encoding boundary but Rich's legacy-Windows
renderer can still render them as mojibake (``?``) when the wide-
char boundary trips.

This module reconfigures :data:`~sys.stdout` and :data:`~sys.stderr`
to UTF-8 with ``errors="replace"`` so a non-encodable character
degrades to ``?`` rather than crashing the operator's command. It
is invoked at the top of the CLI package before any
import that might emit through the central error / output drivers.

Streams that do not support :meth:`~io.TextIOWrapper.reconfigure`
(captured streams, custom adapters, certain pipe wrappers) are
skipped silently — the alternative is crashing the CLI startup,
which is strictly worse than leaving the stream as-is.
"""

from __future__ import annotations

# LOGGING-STDLIB-RATIONALE-STDIO-PLATFORM-FALLBACK:
# stdlib logging used for debug-level platform diagnostic on Windows ctypes
# failure; core logging is unavailable at stream-bootstrap time.
import logging
import sys
from typing import TextIO

import typer
import typer.core


def disable_rich_cli_rendering() -> None:
    """Force Typer/Click's plain-text formatter for help, errors, and tracebacks.

    Rich's boxed help panels derive their width from the ``COLUMNS``
    environment variable or the detected terminal size, and both are
    unreliable across the CLI's real invocation surfaces: piped /
    redirected output, non-tty CI runners, and narrow terminals all
    make Rich pick a box width wider than what actually renders,
    wrapping the box-drawing border characters mid-line into unreadable
    output. Cadrumo's wizard verbs additionally expose long negatable
    flag pairs (``--iva-intracommunity-operations-exceed-50000-eur`` /
    ``--no-...``) that Rich's fixed-width options table ellipsises
    (``--address-postco…``) once its chosen width runs out, which a
    prior version of this module worked around by force-widening
    ``COLUMNS`` for help surfaces — masking the box-wrapping failure
    mode instead of removing it.

    ``typer.core.HAS_RICH`` is read live by every Typer/Click render
    call (help, parse errors, tracebacks) rather than captured once
    per ``Typer()`` instance, so flipping it here — before or after any
    of the project's ``Typer()`` apps are constructed — disables Rich
    rendering across the whole command tree from this single call.
    Click's plain formatter wraps prose to the real terminal width
    (capped at 80 columns) instead of truncating option names, so no
    width floor is needed for it.
    """
    typer.core.HAS_RICH = False


def _set_windows_console_utf8() -> None:
    """Switch the Windows console input/output code page to UTF-8 (65001).

    On Windows, the default console code page is cp850 or cp1252
    depending on locale.  When the CLI reconfigures its Python streams
    to UTF-8 via
    :func:`_reconfigure_stream` the bytes emitted
    are valid UTF-8, but the console *renders* them as the active code
    page, producing mojibake for Spanish accented characters
    (``ó`` → ``Ã³`` on cp1252).

    ``SetConsoleOutputCP(65001)`` and ``SetConsoleCP(65001)`` instruct
    the Windows console host to interpret bytes as UTF-8 instead.  The
    calls are best-effort: they succeed silently in a real console and
    are no-ops (return 0, which we ignore) in redirected / piped output
    where code-page switching has no effect.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        # The ``sys.platform != "win32"`` guard above narrows the platform, so
        # ``ctypes.windll`` resolves without a suppression.
        k32 = ctypes.windll.kernel32
        k32.SetConsoleOutputCP(65001)
        k32.SetConsoleCP(65001)
    except Exception as exc:
        # Best-effort: non-fatal when ctypes or windll is unavailable
        # (redirected / piped output where code-page switching is a
        # no-op). Surface the cause at debug level so diagnostic
        # captures see why the console code page was not switched —
        # silent ``pass`` would hide a real misconfiguration on
        # genuine Windows consoles where this is expected to work.
        _LOGGER.debug(
            "windows console UTF-8 switch skipped: %s: %s",
            type(exc).__name__,
            exc,
        )


# ``cadrumo.core.logging`` cannot be imported at this layer without
# pulling the project's configuration eagerly; this module runs at
# the top of CLI startup, before settings are loaded. The stdlib
# logger here defers handler routing until the central logging
# config attaches, at which point messages flow through the
# SecretScrubbingFilter and project handlers like any other.
_LOGGER = logging.getLogger(__name__)


def _reconfigure_stream(stream: TextIO | None) -> None:
    """Reconfigure ``stream`` to UTF-8 with ``errors="replace"`` if possible.

    Streams that don't expose ``reconfigure`` (test capture fixtures,
    custom wrappers, certain pipes) are left untouched. ``OSError``
    and ``ValueError`` are the documented failure modes when a
    stream declines mid-run reconfiguration. Either is logged at
    debug level so the swallow is observable in diagnostic captures;
    crashing the CLI startup over an encoding-tuning step is the
    wrong trade-off.
    """
    if stream is None:
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        _LOGGER.debug(
            "stdio reconfigure skipped: stream %r exposes no reconfigure() method",
            type(stream).__name__,
        )
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        _LOGGER.debug(
            "stdio reconfigure declined by stream %r: %s",
            type(stream).__name__,
            exc,
        )
        return


def configure_stdio_for_utf8(
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    """Force ``stdout`` and ``stderr`` onto UTF-8 with replace.

    Idempotent — calling more than once is a no-op for already-
    UTF-8 streams. Both arguments default to ``sys.stdout`` /
    ``sys.stderr`` so production startup keeps its zero-argument
    contract; tests that want to exercise the reconfiguration logic
    against a synthetic stream pass it in directly instead of
    monkeypatching ``sys``.
    """
    _set_windows_console_utf8()
    _reconfigure_stream(sys.stdout if stdout is None else stdout)
    _reconfigure_stream(sys.stderr if stderr is None else stderr)


__all__ = ["configure_stdio_for_utf8"]
