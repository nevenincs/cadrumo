"""Terminal exception handling for the root ``aeat`` dispatch.

Typer's standalone ``main`` renders every :class:`ClickException` (usage
errors, bad parameters, unknown options) as Rich text and lets unexpected
exceptions escape as raw Python tracebacks. Under ``--format json`` that
meant the shared-spine error document (``schema_version`` / ``command`` /
``status`` / ``error`` / ``notices``) mandated by the
cli-envelope-notice-standardisation ADR never appeared on any parse-time
or crash failure — automation read prose, an empty stdout, or a traceback.

:func:`run_standalone_with_error_contract` re-implements the standalone
terminal handling around a non-standalone dispatch:

- **Usage / Click errors** (either Click runtime's exception classes —
  Typer vendors its own fork under ``typer._click``): when the parse-time
  context chain (``exc.ctx``) or the raw argv requests JSON, the
  shared-spine error document is written to stderr; otherwise Typer's
  Rich rendering is preserved. The Click exit code (2 for usage errors)
  is preserved in both modes.
- **Unexpected exceptions**: wrapped in
  :class:`~aeat.entrypoints.cli._errors.CliUnexpectedBoundaryError`
  (INTERNAL, exit 6) and rendered through the same JSON/text funnel —
  never a raw traceback.
- **Abort** keeps the interactive text rendering: it is an operator
  keypress, not a machine-readable failure.

Honest boundary: a failure inside this module's own emission path still
falls back to Typer's default behaviour, and an argv too malformed for
the flag probe (e.g. ``--format`` with no value) renders text.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import NoReturn

import click

from ...core.click_context import argv_requests_json, context_chain_requests_json
from ...core.errors import (
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)

_ABORTED_EXIT_CODE = 1
_KEYBOARD_INTERRUPT_EXIT_CODE = 130


def _vendored_exceptions() -> tuple[type[BaseException], type[BaseException], type[BaseException]]:
    """Return (ClickException, UsageError, Abort) from Typer's vendored fork."""
    from typer._click import exceptions as ty_exceptions

    return ty_exceptions.ClickException, ty_exceptions.UsageError, ty_exceptions.Abort


def _json_requested_for(exc: BaseException) -> bool:
    """Return whether the failed invocation asked for JSON output.

    Prefers the parse-time context the exception carries (``exc.ctx`` on
    usage errors — the live stack is already unwound by the time the
    terminal handler runs); falls back to a raw argv probe for crashes
    that carry no context.
    """
    ctx = getattr(exc, "ctx", None)
    if ctx is not None and context_chain_requests_json(ctx):
        return True
    return argv_requests_json(sys.argv[1:])


def _render_click_exception_text(exc: BaseException) -> None:
    """Render ``exc`` the way Typer's standalone main would (Rich, else plain)."""
    try:
        from typer import rich_utils

        # The vendored fork's ClickException satisfies the structural
        # contract rich_format_error reads (message, ctx, format_message).
        rich_utils.rich_format_error(exc)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # reason: structural typing across the two Click runtimes (the vendored fork's ClickException is not an upstream click.ClickException instance)
    except Exception:  # pragma: no cover - rich unavailable or incompatible
        show = getattr(exc, "show", None)
        if callable(show):
            show()
        else:
            sys.stderr.write(str(exc) + "\n")


def _emit_click_exception(exc: BaseException) -> NoReturn:
    """Emit a Click/usage failure honouring the JSON error contract."""
    exit_code = int(getattr(exc, "exit_code", _ABORTED_EXIT_CODE))
    if _json_requested_for(exc):
        from ._errors import CliRefusedBoundaryError, write_stderr

        format_message = getattr(exc, "format_message", None)
        message = str(format_message()) if callable(format_message) else str(exc)
        boundary = CliRefusedBoundaryError(message)
        write_stderr(render_error_json(boundary))
    else:
        _render_click_exception_text(exc)
    sys.exit(exit_code)


def _emit_crash(exc: Exception) -> NoReturn:
    """Emit an unexpected failure as the structured crash boundary."""
    from ._errors import CliUnexpectedBoundaryError, write_stderr

    boundary = CliUnexpectedBoundaryError(exc)
    code = get_registered_error_code(boundary)
    payload = render_error_json(boundary) if _json_requested_for(exc) else render_error_text(boundary)
    write_stderr(payload)
    sys.exit(get_error_exit_code(code.category))


def _emit_abort() -> NoReturn:
    """Render the interactive abort the way Typer's standalone main would."""
    try:
        from typer import rich_utils

        rich_utils.rich_abort_error()
    except Exception:  # pragma: no cover - rich unavailable
        sys.stderr.write("Aborted.\n")
    sys.exit(_ABORTED_EXIT_CODE)


def run_standalone_with_error_contract(dispatch: Callable[[], object]) -> NoReturn:
    """Run a non-standalone Click dispatch with JSON-aware terminal handling.

    ``dispatch`` must call the underlying ``main`` with
    ``standalone_mode=False`` so every failure propagates here instead of
    being rendered by Typer's text-only standalone handler. Mirrors the
    standalone exit semantics: a normal return exits 0, an explicit
    ``typer.Exit`` (surfaced as the non-standalone integer return) exits
    with its code, ``KeyboardInterrupt`` exits 130.
    """
    vendored_click_exception, _vendored_usage, vendored_abort = _vendored_exceptions()
    try:
        result = dispatch()
    except (vendored_click_exception, click.ClickException) as exc:
        _emit_click_exception(exc)
    except (vendored_abort, click.Abort):
        _emit_abort()
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        sys.exit(_KEYBOARD_INTERRUPT_EXIT_CODE)
    except Exception as exc:
        _emit_crash(exc)
    # Non-standalone dispatch RETURNS an explicit Exit's code as an int
    # (typer _main: `except Exit: ... return e.exit_code`); a successful
    # callback chain returns None. Mirror standalone exit semantics.
    sys.exit(result if isinstance(result, int) else 0)


__all__ = ["run_standalone_with_error_contract"]
