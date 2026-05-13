"""Force the CLI's standard streams onto UTF-8.

Default Windows terminals expose stdout / stderr as cp1252; emoji
flag characters, CJK ideographs, the U+2192 right arrow used by the
review queue table, and the § sign used by some VAT-rate citations
all fall outside cp1252 and crash :func:`typer.echo` with
``UnicodeEncodeError``. Spanish accented characters (``á é í ó ú``,
``ñ``) survive the encoding boundary but Rich's legacy-Windows
renderer can still render them as mojibake (``?``) when the wide-
char boundary trips.

This module reconfigures :data:`sys.stdout` and :data:`sys.stderr`
to UTF-8 with ``errors="replace"`` so a non-encodable character
degrades to ``?`` rather than crashing the operator's command. It
is invoked at the top of :mod:`aeat.entrypoints.cli` before any
import that might emit through the central error / output drivers.

Streams that do not support :meth:`io.TextIOWrapper.reconfigure`
(captured streams, custom adapters, certain pipe wrappers) are
skipped silently — the alternative is crashing the CLI startup,
which is strictly worse than leaving the stream as-is.
"""

from __future__ import annotations

import sys
from typing import TextIO


def _reconfigure_stream(stream: TextIO | None) -> None:
    """Reconfigure ``stream`` to UTF-8 with ``errors="replace"`` if possible.

    Streams that don't expose ``reconfigure`` (e.g. test capture
    fixtures, custom wrappers, certain pipes) are left untouched.
    ``OSError`` and ``ValueError`` are the documented failure modes
    for streams that cannot be reconfigured at runtime; both are
    swallowed because crashing the CLI startup over an
    encoding-tuning step is the wrong trade-off.
    """

    if stream is None:
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        # Pipes, captured streams, and wrappers that decline mid-run
        # reconfiguration land here. Leaving the stream as-is is the
        # safest fallback.
        return


def configure_stdio_for_utf8() -> None:
    """Force ``sys.stdout`` and ``sys.stderr`` onto UTF-8 with replace.

    Idempotent — calling more than once is a no-op for already-
    UTF-8 streams.
    """

    _reconfigure_stream(sys.stdout)
    _reconfigure_stream(sys.stderr)


__all__ = ["configure_stdio_for_utf8"]
