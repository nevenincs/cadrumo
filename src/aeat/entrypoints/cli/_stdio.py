"""Force the CLI's standard streams onto UTF-8.

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
is invoked at the top of :mod:`~aeat.entrypoints.cli` before any
import that might emit through the central error / output drivers.

Streams that do not support :meth:`~io.TextIOWrapper.reconfigure`
(captured streams, custom adapters, certain pipe wrappers) are
skipped silently — the alternative is crashing the CLI startup,
which is strictly worse than leaving the stream as-is.
"""

from __future__ import annotations

import contextlib

# LOGGING-STDLIB-RATIONALE-STDIO-PLATFORM-FALLBACK:
# stdlib logging used for debug-level platform diagnostic on Windows ctypes
# failure; core logging is unavailable at stream-bootstrap time.
import logging
import os
import shutil
import sys
from collections.abc import Iterator
from typing import Final, TextIO

from ...core.external_constants import COLUMNS_ENV_VAR

# Minimum render width for the help surface. The wizard `profile
# create` / `edit` verbs expose ~40 flags, including long negatable
# boolean flag pairs that carry both `--x` and `--no-x` in one
# options-column cell. Rich's help formatter ellipsises a flag name
# (`--address-postco…`) when the console is too narrow to fit it,
# and piped / redirected output defaults to an 80-column console.
# Bumping the width floor for help rendering keeps full flag names
# readable. The widening is scoped to `--help` invocations only, so
# ordinary command output keeps the real terminal width.
#
# The floor must clear the widest flag-pair cell: the longest pair
# (`--iva-intracommunity-operations-exceed-50000-eur/--no-...`) runs
# to ~100 chars, and Rich splits the table width between the options
# and help columns — a 200-column floor still ellipsised three pairs,
# whereas 240 fits every flag name in full.
_MIN_HELP_RENDER_COLUMNS = 240

#: Environment variable key Rich uses to determine console column width.
_COLUMNS_ENV_VAR: Final[str] = COLUMNS_ENV_VAR

#: argv tokens that request the help surface.
_HELP_TOKENS = frozenset({"--help", "-h"})


def _help_surface_requested() -> bool:
    """Return whether the current invocation renders a ``--help`` surface."""
    return any(token in _HELP_TOKENS for token in sys.argv[1:])


@contextlib.contextmanager
def _ensure_help_render_width() -> Iterator[None]:
    """Context manager that widens the console width floor for ``--help`` surfaces.

    Rich (used by Typer for ``--help``) derives its console width from
    the ``COLUMNS`` environment variable, falling back to the terminal
    size. When output is piped the fallback is 80 columns, which
    ellipsises long option names in the wizard help tables. This sets
    ``COLUMNS`` to
    :data:`~aeat.entrypoints.cli._stdio._MIN_HELP_RENDER_COLUMNS` only when a help
    surface is being rendered and the resolved width is below the
    floor, so ordinary command output and genuinely wide terminals
    keep their real width.

    The mutation is scoped to the ``with`` block: the original value of
    ``COLUMNS`` (or its absence) is restored on exit so the environment
    mutation does not leak into sibling processes or tests.

    Tests that exercise the decision branches scope ``sys.argv`` and
    ``os.environ[COLUMNS]`` via the centralized backend helpers in
    :mod:`~aeat.tests.env_scope` (``scoped_sys_argv`` /
    ``scoped_env_var``) rather than rebinding process state directly.
    Rich reads the env var from the live environment at render time,
    so a DI-seam that bypassed the os.environ write would misrepresent
    the production contract.
    """
    _original = os.environ.get(_COLUMNS_ENV_VAR)

    if not _help_surface_requested():
        yield
        return

    resolved = _original
    if resolved is not None:
        try:
            current = int(resolved)
        except ValueError:
            current = 0
        if current >= _MIN_HELP_RENDER_COLUMNS:
            yield
            return
    else:
        current = shutil.get_terminal_size(fallback=(80, 24)).columns
        if current >= _MIN_HELP_RENDER_COLUMNS:
            yield
            return

    os.environ[_COLUMNS_ENV_VAR] = str(_MIN_HELP_RENDER_COLUMNS)
    try:
        yield
    finally:
        if _original is None:
            os.environ.pop(_COLUMNS_ENV_VAR, None)
        else:
            os.environ[_COLUMNS_ENV_VAR] = _original


def _set_windows_console_utf8() -> None:
    """Switch the Windows console input/output code page to UTF-8 (65001).

    On Windows, the default console code page is cp850 or cp1252
    depending on locale.  When the CLI reconfigures its Python streams
    to UTF-8 via
    :func:`~aeat.entrypoints.cli._stdio._reconfigure_stream` the bytes emitted
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

        # TYPE-IGNORE-RATIONALE-PLATFORM-WINDOWS-CTYPES:
        # ctypes.windll is Windows-only and absent from cross-platform stubs.
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
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


# ``aeat.core.logging`` cannot be imported at this layer without
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
    with _ensure_help_render_width():
        _reconfigure_stream(sys.stdout if stdout is None else stdout)
        _reconfigure_stream(sys.stderr if stderr is None else stderr)


__all__ = ["configure_stdio_for_utf8"]
