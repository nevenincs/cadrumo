"""Terminal exception handling for the root ``cadrumo`` dispatch.

Typer's standalone ``main`` renders every :class:`~click.ClickException` (usage
errors, bad parameters, unknown options) as Rich text and lets unexpected
exceptions escape as raw Python tracebacks. Under ``--format json`` that
meant the shared-spine error document (``schema_version`` / ``command`` /
``status`` / ``error`` / ``notices``) never appeared on any parse-time
or crash failure — automation read prose, an empty stdout, or a traceback.

:func:`run_standalone_with_error_contract`
re-implements the standalone terminal handling around a non-standalone
dispatch:

- **Usage / Click errors** (either Click runtime's exception classes —
  Typer vendors its own fork under ``typer._click``): when the parse-time
  context chain (``exc.ctx``) or the raw argv requests JSON, the
  shared-spine error document is written to stderr; otherwise Typer's
  Rich rendering is preserved. The Click exit code (2 for usage errors)
  is preserved in both modes.
- **Unexpected exceptions**: wrapped in
  :class:`CliUnexpectedBoundaryError`
  (INTERNAL, exit 6) and rendered through the same JSON/text funnel —
  never a raw traceback.
- **Abort** keeps the interactive text rendering: it is an operator
  keypress, not a machine-readable failure.

Honest boundary: a failure inside this module's own emission path still
falls back to Typer's default behaviour, and an argv too malformed for
the flag probe (e.g. ``--format`` with no value) renders text.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from typing import TYPE_CHECKING, NoReturn

import click

if TYPE_CHECKING:
    from ._errors import CliRefusedBoundaryError

from ...core.click_context import argv_requests_json, context_chain_requests_json
from ...core.errors import (
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)

_ABORTED_EXIT_CODE = 1
_KEYBOARD_INTERRUPT_EXIT_CODE = 130

#: The raw argv slice of the active invocation, captured by
#: :func:`run_standalone_with_error_contract` so parse-time handling can read the
#: operator's ``--format`` and ``--language`` tokens even when no command context
#: resolved (a bad root option, a Choice failure whose ``BadParameter`` carries no
#: ``ctx``) and even under a test runner where ``sys.argv`` is the harness's own.
_INVOCATION_ARGV: ContextVar[tuple[str, ...] | None] = ContextVar("cadrumo_cli_invocation_argv", default=None)

_CHOICE_DETAIL_RE = re.compile(r"'([^']*)'\s+is not one of\s+(?P<accepted>.+?)\.?\s*$")
_NO_SUCH_COMMAND_RE = re.compile(r"No such command '([^']+)'")
_FIRST_QUOTED_RE = re.compile(r"'([^']+)'")


def _vendored_exceptions() -> tuple[type[BaseException], type[BaseException], type[BaseException]]:
    """Return (ClickException, UsageError, Abort) from Typer's vendored fork."""
    from typer._click import exceptions as ty_exceptions

    return ty_exceptions.ClickException, ty_exceptions.UsageError, ty_exceptions.Abort


def _invocation_argv() -> list[str]:
    """Return the active invocation's argv slice.

    Falls back to ``sys.argv[1:]`` when no invocation captured its argv (a
    direct call outside :func:`run_standalone_with_error_contract`).
    """
    captured = _INVOCATION_ARGV.get()
    return list(captured) if captured is not None else list(sys.argv[1:])


def _json_requested_for(exc: BaseException) -> bool:
    """Return whether the failed invocation asked for JSON output.

    Prefers the parse-time context the exception carries (``exc.ctx`` on
    usage errors — the live stack is already unwound by the time the
    terminal handler runs); falls back to the captured invocation argv for
    failures that carry no context (a Choice ``BadParameter`` with no ``ctx``,
    a bad root option, or a crash before dispatch).
    """
    ctx = getattr(exc, "ctx", None)
    if ctx is not None and context_chain_requests_json(ctx):
        return True
    return argv_requests_json(_invocation_argv())


def _parse_time_output_language() -> str:
    """Resolve the output language knowable at parse time.

    An explicit ``--language`` / ``--lang`` / ``--output-language`` token on the
    invocation is the most specific operator intent and wins; otherwise the i18n
    layer's own env-then-profile-then-default chain resolves the language. The
    argv token is honoured directly because the root callback's settings
    override is already torn down by the time this terminal handler runs, and a
    Choice ``BadParameter`` carries no context to walk.
    """
    from ...core.i18n import output_language
    from ._language_argv import language_from_argv

    explicit = language_from_argv(_invocation_argv())
    if explicit is not None:
        return explicit
    return output_language()


def _has_base(exc: BaseException, name: str) -> bool:
    """Return whether ``exc``'s class or any base is named ``name``.

    Matches by MRO class name so both Click runtimes (upstream ``click`` and
    Typer's vendored fork) are recognised without importing either exception
    module.
    """
    return any(base.__name__ == name for base in type(exc).__mro__)


def _parameter_hint(exc: BaseException) -> str | None:
    """Return the operator-facing parameter/option hint for ``exc``, if any."""
    param = getattr(exc, "param", None)
    ctx = getattr(exc, "ctx", None)
    if param is not None:
        try:
            hint = param.get_error_hint(ctx)
        except Exception:  # get_error_hint is best-effort structured detail
            hint = None
        if hint:
            return str(hint).strip("'")
    param_hint = getattr(exc, "param_hint", None)
    if param_hint:
        return str(param_hint).strip("'")
    return None


def _first_quoted(detail: str) -> str | None:
    """Return the first single-quoted token in ``detail``, if any."""
    match = _FIRST_QUOTED_RE.search(detail)
    return match.group(1) if match is not None else None


def _localise_parse_failure(exc: BaseException, detail: str, locale: str) -> tuple[str, dict[str, str]] | None:
    """Render a click parse failure as a localised message plus structured facts.

    Returns ``(message, context)`` for the click-generated argv-parse failures
    whose native message is English (missing argument, unknown option, an
    invalid Choice value, an unknown command), or ``None`` to preserve the
    exception's own message verbatim. A ``BadParameter`` raised by a command
    callback already carries a localised, purpose-built message (rendered by
    ``tr`` at the raise site), so only the click-internal structured patterns are
    re-keyed here — a generic value refusal is left untouched. The offending
    option/parameter, value, and accepted-value set ride in ``context`` so the
    refusal names the accepted set the CLI-boundary contract requires, and the
    message renders in the parse-time-resolved ``locale``.
    """
    for recognise in (
        _missing_argument_failure,
        _unknown_option_failure,
        _invalid_choice_failure,
        _unknown_command_failure,
    ):
        localised = recognise(exc, detail, locale)
        if localised is not None:
            return localised
    return None


def _missing_argument_failure(exc: BaseException, detail: str, locale: str) -> tuple[str, dict[str, str]] | None:
    """Recognise click's missing-argument failure."""
    from ...core.i18n import tr

    if not _has_base(exc, "MissingParameter"):
        return None
    parameter = _parameter_hint(exc) or _first_quoted(detail) or ""
    facts = _drop_empty({"parameter": parameter})
    return tr("cli.common.errors.parse_missing_argument", locale=locale, parameter=parameter), facts


def _unknown_option_failure(exc: BaseException, _detail: str, locale: str) -> tuple[str, dict[str, str]] | None:
    """Recognise an unknown or misused option, carrying click's own suggestions."""
    from ...core.i18n import tr

    option_name = getattr(exc, "option_name", None)
    if not option_name or not (_has_base(exc, "NoSuchOption") or _has_base(exc, "BadOptionUsage")):
        return None
    facts = {"option": str(option_name)}
    possibilities = getattr(exc, "possibilities", None)
    if possibilities:
        facts["suggestions"] = ", ".join(str(candidate) for candidate in possibilities)
    return tr("cli.common.errors.parse_unknown_option", locale=locale, option=facts["option"]), facts


def _invalid_choice_failure(exc: BaseException, detail: str, locale: str) -> tuple[str, dict[str, str]] | None:
    """Recognise an invalid Choice value, carrying the accepted set.

    The accepted set is what the CLI-boundary contract requires a refusal to
    name, so it is parsed out of click's own rendering rather than dropped.
    """
    from ...core.i18n import tr

    choice = _CHOICE_DETAIL_RE.search(detail)
    if choice is None:
        return None
    accepted = ", ".join(match.group(1) for match in _FIRST_QUOTED_RE.finditer(choice.group("accepted")))
    facts = _drop_empty({"value": choice.group(1), "accepted": accepted, "parameter": _parameter_hint(exc)})
    message = tr("cli.common.errors.parse_invalid_choice", locale=locale, value=choice.group(1), accepted=accepted)
    return message, facts


def _unknown_command_failure(_exc: BaseException, detail: str, locale: str) -> tuple[str, dict[str, str]] | None:
    """Recognise an unknown command name."""
    from ...core.i18n import tr

    unknown_command = _NO_SUCH_COMMAND_RE.search(detail)
    if unknown_command is None:
        return None
    command = unknown_command.group(1)
    return tr("cli.common.errors.parse_unknown_command", locale=locale, command=command), {"command": command}


def _drop_empty(facts: dict[str, str | None]) -> dict[str, str]:
    """Return ``facts`` with empty values removed."""
    return {key: value for key, value in facts.items() if value}


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
        from ._errors import active_profile_label_for_error, write_stderr

        boundary = _build_parse_time_refusal(exc)
        write_stderr(render_error_json(boundary, active_profile=active_profile_label_for_error()))
    else:
        _render_click_exception_text(exc)
    sys.exit(exit_code)


def _build_parse_time_refusal(exc: BaseException) -> CliRefusedBoundaryError:
    """Build the localised, structured refusal for a JSON-mode parse failure.

    A click-generated argv-parse failure (missing argument, unknown option,
    invalid Choice value, unknown command) is re-keyed to a localised refusal
    that carries the parse failure's structured facts (offending option/param,
    value, and — for a Choice — the accepted-value set) in ``context`` and
    renders in the parse-time-resolved output language. Any other click failure
    keeps its own message verbatim: a callback-raised ``BadParameter`` already
    carries a purpose-built localised message, so re-keying it would discard the
    more specific text.
    """
    from ._errors import CliRefusedBoundaryError

    format_message = getattr(exc, "format_message", None)
    detail = str(format_message()) if callable(format_message) else str(exc)
    localised = _localise_parse_failure(exc, detail, _parse_time_output_language())
    if localised is None:
        return CliRefusedBoundaryError(detail)
    message, context = localised
    return CliRefusedBoundaryError(message, context=context or None)


def _emit_crash(exc: Exception) -> NoReturn:
    """Emit a failure that escaped dispatch, preferring its own registered code.

    Most failures reaching here are genuine crashes and are wrapped in
    :class:`CliUnexpectedBoundaryError` (INTERNAL, exit 6). A typed
    :class:`~core.errors.CadrumoError` is different: it is an *expected*,
    already-classified refusal that simply had no callback boundary to catch it,
    because it was raised during command resolution rather than inside a command
    body (the lazy command-group loader is the canonical raiser). Flattening it
    would discard its registered category, its instructive message, and its
    remedy, and would report an operator-actionable condition as a program
    defect. Forward it verbatim instead, with its own exit code.
    """
    from ...core.logging import OPERATOR_DOCUMENT_LOG_EXTRA, get_logger
    from ._errors import CliUnexpectedBoundaryError, _unwrap_cadrumo_error, active_profile_label_for_error, write_stderr

    typed = _unwrap_cadrumo_error(exc)
    if typed is None:
        # The INTERNAL envelope this path renders tells the operator to consult
        # the diagnostic logs, so the traceback has to actually be in them;
        # without this the isolated-run log carried two DEBUG lines and nothing
        # else, and triage had to patch the emitter in-process to see the crash.
        # Logged only for the untyped case, mirroring the command boundary in
        # `_errors.py`: a typed CadrumoError is an expected, already-classified
        # refusal, and writing its traceback would make `aeat config repair
        # logs` echo an operator-actionable condition back as a live crash.
        #
        # The extra keeps the record off the stderr handler. This function is
        # about to write the JSON error document to that same stream, and the
        # record carries the raw exception and its frames — echoing it would
        # prepend an unredacted traceback to the translated document and break
        # any parser reading stderr for the document alone.
        get_logger(__name__).error(
            "cli terminal boundary: unexpected exception",
            exc_info=exc,
            extra={OPERATOR_DOCUMENT_LOG_EXTRA: True},
        )
    boundary = typed if typed is not None else CliUnexpectedBoundaryError(exc)
    code = get_registered_error_code(boundary)
    payload = (
        render_error_json(boundary, active_profile=active_profile_label_for_error())
        if _json_requested_for(exc)
        else render_error_text(boundary)
    )
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


def run_standalone_with_error_contract(
    dispatch: Callable[[], object],
    *,
    argv: Sequence[str] | None = None,
) -> NoReturn:
    """Run a non-standalone Click dispatch with JSON-aware terminal handling.

    ``dispatch`` must call the underlying ``main`` with
    ``standalone_mode=False`` so every failure propagates here instead of
    being rendered by Typer's text-only standalone handler. Mirrors the
    standalone exit semantics: a normal return exits 0, an explicit
    ``typer.Exit`` (surfaced as the non-standalone integer return) exits
    with its code, ``KeyboardInterrupt`` exits 130.

    ``argv`` is the raw invocation argv slice. It is captured for the duration
    of the dispatch so parse-time handling can read the operator's ``--format``
    and ``--language`` tokens even when the failure carries no command context;
    it defaults to ``sys.argv[1:]`` for a console launch.
    """
    captured = tuple(argv) if argv is not None else tuple(sys.argv[1:])
    token = _INVOCATION_ARGV.set(captured)
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
    finally:
        _INVOCATION_ARGV.reset(token)
    # Non-standalone dispatch RETURNS an explicit Exit's code as an int
    # (typer _main: `except Exit: ... return e.exit_code`); a successful
    # callback chain returns None. Mirror standalone exit semantics.
    sys.exit(result if isinstance(result, int) else 0)


__all__ = ["run_standalone_with_error_contract"]
