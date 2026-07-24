"""Shared CLI error-emission boundary.

This module is the single funnel for translating exceptions raised
inside Typer callbacks into the structured CLI error contract — a
stable stderr payload (text or JSON) plus a stable :class:`~typer.Exit`
code drawn from :class:`ExitCode`.

Two narrow boundary exceptions wrap unexpected failures so they reach
:func:`render_error_text` and
:func:`render_error_json` with a predictable shape:

- :exc:`CliValidationBoundaryError` wraps a leaked
  :exc:`~pydantic.ValidationError`.
- :exc:`CliUnexpectedBoundaryError` wraps any
  other non-control-flow exception.

A third type, :exc:`CliRefusedBoundaryError`, is
reserved for refusals emitted in JSON mode whose payload is intentionally
stderr-only.

The :func:`command_error_boundary` decorator wraps a callback so that
:class:`CadrumoError` instances are emitted via
:func:`_emit_error_and_exit`.
:func:`decorate_typer_app` walks a
:class:`~typer.Typer` tree and applies the decorator to every registered command
and group callback (with an opt-out via ``skip_paths``).
:func:`error_boundary_under_test` toggles the
boundary off for tests that want to assert on the raised exception directly.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import io
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Never, Protocol, TypeGuard, cast

import click
import typer
from pydantic import ValidationError

from ...core import PRODUCT_IDENTITY, FormerProductStateError
from ...core.click_context import json_output_requested
from ...core.errors import (
    CadrumoError,
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)
from ...core.logging import get_logger
from ...core.redaction import redact_for_cli_output
from ...domain.user_profile import StoredProfileDriftError

_log = get_logger(__name__)

_UNDER_TEST: ContextVar[bool] = ContextVar("cadrumo_cli_error_boundary_under_test", default=False)
#: Dotted identifier of the command whose callback is currently executing,
#: set by :func:`command_error_boundary` at entry so the error spine's
#: ``command`` field can name the failing command (byte-identical to the
#: ``command=`` its success envelope would emit). ``None`` before any command
#: resolves — an argv parse failure — so the field is honestly null there.
_ACTIVE_COMMAND_ID: ContextVar[str | None] = ContextVar("cadrumo_cli_active_command_id", default=None)
_WRAPPED_CALLBACKS: dict[int, Callable[..., object]] = {}

#: Remedy offered when a REQUIRED dependency is missing at import time. A
#: required package is absent only when the installed distribution is
#: incomplete, so the honest fix is to reinstall it rather than to install an
#: extra (which would not carry the package) or to run ``config repair`` (which
#: diagnoses local profile state, never the Python environment).
_REINSTALL_SUGGESTION: str = f"pip install --force-reinstall {PRODUCT_IDENTITY.distribution}"


class _ReconfigurableTextIO(Protocol):
    """Structural type for a text stream that supports ``reconfigure``."""

    def reconfigure(self, *, encoding: str | None = None, errors: str | None = None) -> None:
        """Reconfigure the underlying text stream's encoding and error mode."""

    def write(self, s: str, /) -> int:
        """Write string ``s`` to the stream."""
        ...

    def flush(self) -> None:
        """Flush the write buffers of the stream."""
        ...


class CliValidationBoundaryError(CadrumoError):
    """Raised when a CLI callback leaks a :exc:`~pydantic.ValidationError`.

    The original exception is preserved on
    :attr:`CliValidationBoundaryError.original_exception` so
    downstream renderers and tests can inspect it without losing the
    typed pydantic detail.

    This class covers input-time validation failures (the operator passed
    an invalid argument or body).  It is distinct from
    :exc:`CliStoredDataValidationBoundaryError`,
    which handles schema drift on persisted records and legitimately suggests
    ``aeat config repair``.
    Suggesting ``aeat config repair`` here would be misleading: repair
    diagnoses local configuration state and cannot fix an application
    schema mismatch or an invalid CLI argument.

    Attributes:
        original_exception: The underlying :exc:`~pydantic.ValidationError`.
    """

    def __init__(self, error: ValidationError) -> None:
        """Wrap ``error`` in the structured CLI boundary contract.

        Args:
            error: The pydantic validation error raised inside the
                Typer callback.
        """
        super().__init__(
            translated_message="errors.refused.refused_cli_validation_boundary",
            context={},
            suggestion="aeat --help",
        )
        self.original_exception: ValidationError = error


class CliUnexpectedBoundaryError(CadrumoError):
    """Raised when a CLI callback leaks an unexpected exception.

    Used for any exception that is not :class:`CadrumoError`,
    :exc:`~pydantic.ValidationError`, or Typer/Click control flow. The
    original exception is preserved on
    :attr:`CliUnexpectedBoundaryError.original_exception`.

    Attributes:
        original_exception: The underlying exception raised by the
            callback.
    """

    def __init__(self, error: Exception) -> None:
        """Wrap ``error`` in the structured CLI boundary contract.

        Args:
            error: The unexpected exception raised inside the Typer
                callback.
        """
        # An unexpected exception here is almost always a code/environment
        # fault (an import error, a logic bug), NOT corrupted stored state.
        # Suggesting `config repair integrity` was misleading: it implies
        # storage corruption and points at a mutating repair that cannot fix a
        # code fault. Point instead at the read-only diagnostic log inspection,
        # where the actual traceback is echoed back — the honest recovery for an
        # internal error. (Mirrors the reasoning `CliValidationBoundaryError`
        # already applies to input-time failures.)
        super().__init__(
            translated_message="errors.internal.internal_cli_unexpected_boundary",
            context={
                "recovery": "aeat config repair logs",
            },
            suggestion="aeat config repair logs",
        )
        self.original_exception: Exception = error


class CliStoredDataValidationBoundaryError(CadrumoError):
    """Raised when a CLI callback loads stored profile data that fails validation.

    Distinct from
    :exc:`CliValidationBoundaryError` (which wraps
    input-time validation failures) so downstream handlers and tests can
    discriminate between malformed user input and drifted stored profile data.  The stored
    record was valid when it was written; schema evolution or an out-of-band
    edit caused the drift.

    The original exception is preserved on
    :attr:`CliStoredDataValidationBoundaryError.original_exception` so
    renderers and tests can inspect the typed pydantic detail.

    Attributes:
        original_exception: The underlying :exc:`~pydantic.ValidationError`
            raised while deserialising a stored record.
    """

    def __init__(self, error: ValidationError) -> None:
        """Wrap ``error`` in the stored-data validation boundary contract.

        Args:
            error: The pydantic validation error raised while loading a
                stored profile record.
        """
        super().__init__(
            translated_message="errors.storage.stored_data_validation_boundary",
            context={
                "recovery": "aeat config repair --help",
            },
            suggestion="aeat config repair --help",
        )
        self.original_exception: ValidationError = error


class CliCommandGroupUnavailableError(CadrumoError):
    """Raised when a command group cannot be imported and the cause is not an optional extra.

    A command group's module is imported lazily, the first time an operator
    dispatches into that subtree. When the import fails with a
    :exc:`ModuleNotFoundError` naming a package outside the
    :data:`~core.OPTIONAL_EXTRAS` registry, the missing package is a *required*
    dependency: the installation is incomplete, not merely un-extended.

    Degrading that case to an unavailable-command placeholder would turn a hard
    dependency failure into an invisible capability loss — the whole subtree
    would answer every invocation with a plausible refusal while naming no
    cause. This refusal names the module, the group it broke, and the
    reinstall remedy instead.

    Attributes:
        group: The command-group name whose subtree failed to load.
        module: The missing required module the import named.
    """

    def __init__(self, *, group: str, module: str) -> None:
        """Build the refusal for ``group`` failing on required ``module``.

        Args:
            group: The command-group name whose subtree failed to load.
            module: The dotted module name the failed import named.
        """
        super().__init__(
            translated_message="errors.fail.fail_cli_command_group_unavailable",
            context={"group": group, "module": module},
            suggestion=_REINSTALL_SUGGESTION,
        )
        self.group = group
        self.module = module


class CliRefusedBoundaryError(CadrumoError):
    """Raised when JSON-mode CLI must refuse a request with stderr-only output.

    Refusals are emitted as plain stderr text even in JSON mode because
    the structured payload contract intentionally does not expose them
    on stdout.
    """


def command_error_boundary[**P, R](callback: Callable[P, R]) -> Callable[P, R]:
    """Wrap ``callback`` so :class:`CadrumoError` emits the structured stderr form.

    The wrapper catches four exception families and routes them to
    :func:`_emit_error_and_exit`:

    - :exc:`StoredProfileDriftError` is
      wrapped in
      :exc:`CliStoredDataValidationBoundaryError`
      so operators see a repair-oriented message distinct from input-time
      validation failures. Checked before the broad
      :class:`CadrumoError` arm by typed exception, not field-path
      introspection.
    - :class:`CadrumoError` is forwarded verbatim.
    - :exc:`~pydantic.ValidationError` is wrapped in
      :exc:`CliValidationBoundaryError`.
    - Any other non-control-flow exception is wrapped in
      :exc:`CliUnexpectedBoundaryError`.

    Typer/Click control-flow exceptions (e.g. :exc:`~click.exceptions.Exit`,
    :exc:`~click.Abort`, :exc:`~typer.Exit`) propagate untouched so the
    framework can act on them. When
    :func:`error_boundary_under_test` is active
    the original exception is re-raised instead of being emitted.

    Calls are memoised by callback identity so wrapping the same
    callback twice returns the original wrapper.

    Args:
        callback: Typer callback to wrap.

    Returns:
        Wrapped callback with the original signature preserved.
    """
    existing = _WRAPPED_CALLBACKS.get(id(callback))
    if existing is not None and _is_memoised_wrapper(existing):
        # Safe: _WRAPPED_CALLBACKS stores only the _wrapped closure produced
        # by THIS function from a callback[P, R] argument. The memo key is
        # id(callback), which uniquely identifies the object at this call site.
        # Both the forward and reverse entries are written atomically at the end
        # of this function, so a hit guarantees the stored callable has exactly
        # the same ParamSpec P and return type R as callback. The widening to
        # Callable[..., object] in the dict value type is the only escape hatch;
        # it cannot be eliminated without making _WRAPPED_CALLBACKS generic over
        # P and R, which the stdlib dict does not support.
        # CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER (future: replace with generic ClassVar alias)
        return cast(Callable[P, R], existing)  # CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER

    @functools.wraps(callback)
    def _wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        token = _ACTIVE_COMMAND_ID.set(_resolve_active_command_id(*args, *kwargs.values()))
        try:
            return callback(*args, **kwargs)
        except Exception as error:
            # Typer/Click control flow (Exit, Abort, BadParameter) propagates
            # untouched so the framework can render it; the under-test override
            # re-raises the original so tests can assert on the typed exception.
            # Everything else routes through the ordered specificity dispatch.
            if _is_click_control_flow(error):
                raise
            if _UNDER_TEST.get():
                raise
            _emit_error_and_exit(_project_boundary_error(error, callback))
        finally:
            _ACTIVE_COMMAND_ID.reset(token)

    _WRAPPED_CALLBACKS[id(callback)] = _wrapped
    _WRAPPED_CALLBACKS[id(_wrapped)] = _wrapped
    return _wrapped


def decorate_typer_app(
    app: typer.Typer,
    *,
    skip_paths: Sequence[tuple[str, ...]] = (),
) -> None:
    """Apply :func:`command_error_boundary` across an entire Typer tree.

    Walks ``app`` recursively and wraps every command and group callback
    that is a plain function. Sub-apps are descended into.

    Args:
        app: Root or nested :class:`~typer.Typer` app to decorate.
        skip_paths: Fully-qualified command paths (as tuples of name
            segments) that must remain undecorated. Useful for callbacks
            that intentionally manage their own error reporting.
    """
    skip_set = set(skip_paths)
    _decorate_typer_node(app, prefix=(), skip_paths=skip_set)


def write_stderr(text: str, *, stream: io.TextIOBase | None = None) -> None:
    """Write ``text`` to stderr with UTF-8-safe fallback behaviour.

    On Windows consoles whose default encoding is cp1252, raw writes of
    non-ASCII characters raise ``UnicodeEncodeError``. This helper
    first attempts to reconfigure the stream to UTF-8 via
    :class:`_ReconfigurableTextIO`; on encoding
    failure it falls back to the underlying byte buffer with
    ``errors="replace"``, and finally to an ASCII-safe replacement string.

    Args:
        text: Text payload to emit.
        stream: Optional target stream to write to instead of
            :data:`~sys.stderr`. Primarily useful in tests.
    """
    target = sys.stderr if stream is None else stream
    redacted_text = redact_for_cli_output(text)
    if _supports_reconfigure(target):
        with contextlib.suppress(Exception):
            target.reconfigure(encoding="utf-8", errors="replace")
    try:
        target.write(redacted_text)
        target.flush()
        return
    except UnicodeEncodeError:
        buffer = getattr(target, "buffer", None)
        if buffer is not None:
            buffer.write(redacted_text.encode("utf-8", errors="replace"))
            with contextlib.suppress(Exception):
                buffer.flush()
            return
        target.write(redacted_text.encode("ascii", errors="replace").decode("ascii"))
        target.flush()


def active_profile_label_for_error() -> str | None:
    """Return the active-profile label for the error-document spine, best-effort.

    The error boundary is the one place that must never be disrupted by
    identity resolution: a failure resolving the active-profile label must
    not mask the original error being reported. Delegates to the CLI
    transport's :func:`_common._active_profile_label` (the same plaintext
    manifest-label read the success path uses, never the redacted UUID)
    and collapses any failure to ``None`` so the error still emits with a
    null identity anchor. The import is function-local to avoid a module
    cycle with :mod:`_common`, which imports this module.
    """
    try:
        from ._common import _active_profile_label

        return _active_profile_label()
    except Exception:  # identity resolution must never break error emit
        _log.debug("cli error boundary: active-profile label resolution failed", exc_info=True)
        return None


def _command_identifier_from_path(command_path: str) -> str | None:
    """Map a click ``command_path`` to the dotted envelope command identifier.

    The click command *path* uses the root prog token plus hyphenated CLI
    tokens (``aeat config repair reset-progress``); the envelope ``command``
    identifier uses dotted, underscored tokens (``config.repair.reset_progress``).
    Drop the root
    prog token, join the rest with ``.``, map ``-`` to ``_`` per token — the
    inverse of that convention, so a command's error envelope names it
    identically to the ``command=`` its success envelope emits, and the two can
    never disagree. ``None`` for the bare root (no subcommand).
    """
    segments = command_path.split()[1:]
    if not segments:
        return None
    return ".".join(segment.replace("-", "_") for segment in segments)


def _active_command_identifier() -> str | None:
    """Return the dotted identifier of the command currently executing, or ``None``.

    Read from the :data:`_ACTIVE_COMMAND_ID` context var, which
    :func:`command_error_boundary` sets from the executing command's injected
    :class:`click.Context` at callback entry (click's global context stack is
    not populated under the Typer/cached-tree invocation, so the injected ctx
    parameter is the reliable source). ``None`` when no command has resolved —
    an argv parse failure raised before any command callback runs.
    """
    return _ACTIVE_COMMAND_ID.get()


def _resolve_active_command_id(*values: object) -> str | None:
    """Return the dotted command identifier from the callback's injected Context.

    Name the executing command on the error spine: Typer injects the Context as
    a callback parameter, so scan the positional and keyword argument ``values``
    for the first with a string ``command_path`` and map it to the dotted
    envelope identifier (the global click context stack is not populated under
    this invocation). Duck-type on ``command_path`` rather than
    ``isinstance(click.Context)`` — the vendored Typer Context is not a
    guaranteed upstream subclass. ``None`` before any command resolves (an argv
    parse failure), so the spine's ``command`` field is honestly null there.
    """
    command_path = next(
        (path for value in values if isinstance(path := getattr(value, "command_path", None), str)),
        None,
    )
    return _command_identifier_from_path(command_path) if command_path is not None else None


def _emit_error_and_exit(error: CadrumoError) -> Never:
    """Render ``error`` to stderr and terminate with its registered exit code.

    Selects the JSON or text renderer based on whether the active
    callback opted into JSON output via
    :func:`json_output_requested`, writes the payload
    through :func:`write_stderr`, and raises
    :class:`~typer.Exit` with the category-mapped exit code. In JSON mode
    the shared-spine ``active_profile`` identity anchor and the dotted
    ``command`` identifier are resolved best-effort and injected into the
    error document.
    """
    code = get_registered_error_code(error)
    payload = (
        render_error_json(
            error,
            active_profile=active_profile_label_for_error(),
            command=_active_command_identifier(),
        )
        if json_output_requested()
        else render_error_text(error)
    )
    write_stderr(payload)
    raise typer.Exit(code=get_error_exit_code(code.category)) from error


@contextmanager
def error_boundary_under_test() -> Iterator[None]:
    """Temporarily force :func:`command_error_boundary` to re-raise originals.

    Tests that need to assert on the raised exception type rather than
    the rendered stderr payload should wrap their invocation in this
    context manager. The override is scoped to the active context via
    :class:`~contextvars.ContextVar`, so concurrent callbacks are
    unaffected.

    Yields:
        ``None``. The context's only purpose is the side effect on the internal
        flag.
    """
    token: Token[bool] = _UNDER_TEST.set(True)
    try:
        yield
    finally:
        _UNDER_TEST.reset(token)


def _decorate_typer_node(
    app: typer.Typer,
    *,
    prefix: tuple[str, ...],
    skip_paths: set[tuple[str, ...]],
) -> None:
    """Recursively decorate every command/group callback under ``app``."""
    registered_callback = app.registered_callback
    if (
        registered_callback is not None
        and _is_wrap_candidate(registered_callback.callback)
        and prefix not in skip_paths
    ):
        registered_callback.callback = command_error_boundary(registered_callback.callback)
    for command in app.registered_commands:
        name = command.name or _callback_name(command.callback)
        path = (*prefix, name)
        if _is_wrap_candidate(command.callback) and path not in skip_paths:
            command.callback = command_error_boundary(command.callback)
    for group in app.registered_groups:
        name = group.name or _callback_name(group.callback)
        path = (*prefix, name)
        if _is_wrap_candidate(group.callback) and path not in skip_paths:
            group.callback = command_error_boundary(group.callback)
        if group.typer_instance is not None:
            _decorate_typer_node(group.typer_instance, prefix=path, skip_paths=skip_paths)


def _callback_name(callback: Callable[..., object] | None) -> str:
    """Return a stable name for a Typer callback, even if it's a callable class."""
    if callback is None:
        return "<unknown>"
    if inspect.isfunction(callback):
        return callback.__name__
    return callback.__class__.__name__


def _is_memoised_wrapper(obj: object) -> TypeGuard[Callable[..., object]]:
    """Narrow ``obj`` to a callable produced by the command error boundary.

    The callable must have been produced by
    :func:`command_error_boundary`.

    A hit in ``_WRAPPED_CALLBACKS`` guarantees the stored value is the ``_wrapped``
    closure returned by this module; all such closures satisfy ``Callable[..., object]``.
    The full ``Callable[P, R]`` refinement is recovered at the call site via a
    documented cast (CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER).
    """
    return callable(obj)


def _is_wrap_candidate(callback: object) -> TypeGuard[Callable[..., object]]:
    """Narrow ``callback`` to a plain function suitable for wrapping."""
    return inspect.isfunction(callback)


def _supports_reconfigure(stream: object) -> TypeGuard[_ReconfigurableTextIO]:
    """Narrow ``stream`` to a text stream that exposes ``reconfigure``."""
    return hasattr(stream, "reconfigure")


def _unwrap_cadrumo_error(error: BaseException) -> CadrumoError | None:
    """Return the typed :class:`CadrumoError` wrapped inside ``error``, if any.

    A library boundary (notably SQLAlchemy) can catch an
    :class:`CadrumoError` raised inside its own machinery and
    re-raise it wrapped in a library-specific exception. The typed refusal is
    then reachable only through the ``orig`` attribute SQLAlchemy sets, or
    through the standard ``__cause__`` / ``__context__`` chain. This helper walks
    both so the refusal can be forwarded verbatim rather than mis-reported as an
    unexpected internal error.

    The walk is depth-bounded to avoid pathological cycles.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    depth = 0
    while current is not None and depth < 16:
        if isinstance(current, CadrumoError):
            return current
        if id(current) in seen:
            return None
        seen.add(id(current))
        depth += 1
        nxt = getattr(current, "orig", None)
        if not isinstance(nxt, BaseException):
            nxt = current.__cause__ or current.__context__
        current = nxt
    return None


# Typer vendors its own Click fork; ``typer.BadParameter`` and friends descend
# from ``typer._click.exceptions.ClickException`` rather than the upstream
# ``click.ClickException``. Derive the vendored base from ``typer.BadParameter``'s
# MRO so both hierarchies are recognised without a brittle private-module import.
_typer_click_exc_raw = next(base for base in typer.BadParameter.__mro__ if base.__name__ == "ClickException")
assert issubclass(_typer_click_exc_raw, BaseException)
_TYPER_CLICK_EXCEPTION: type[BaseException] = _typer_click_exc_raw
_CONTROL_FLOW_EXCEPTIONS: tuple[type[BaseException], ...] = (
    click.ClickException,
    click.exceptions.Exit,
    click.Abort,
    typer.Exit,
    _TYPER_CLICK_EXCEPTION,
)


def _is_click_control_flow(error: Exception) -> bool:
    """Return ``True`` when ``error`` is Typer/Click control flow, not a bug.

    Recognises :exc:`~click.ClickException`, :exc:`~click.exceptions.Exit`,
    :exc:`~click.Abort`, and :exc:`~typer.Exit`. Typer vendors its own Click
    fork (``typer._click.exceptions``), so ``typer.BadParameter`` raised by a
    ``_bad(...)`` refusal is NOT an instance of the upstream
    :exc:`~click.ClickException`; recognise the vendored hierarchy too so an
    instructive operator refusal is re-raised for Click/CliRunner to render
    rather than mis-classified as an unexpected internal error.
    """
    return isinstance(error, _CONTROL_FLOW_EXCEPTIONS)


_BoundaryProjection = Callable[[Exception, Callable[..., object]], CadrumoError]


def _project_stored_data_drift(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Discriminate stored-data drift from input-time validation failures.

    A schema mismatch on a persisted profile record and an invalid CLI argument
    both originate from a pydantic ``ValidationError`` but the operator-facing
    messages and recovery paths differ, so the drift is wrapped in the typed CLI
    boundary rather than emitted as the raw domain error code.
    """
    assert isinstance(error, StoredProfileDriftError)
    return CliStoredDataValidationBoundaryError(error.original_exception)


def _project_former_product_state(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Emit a former-product-state refusal as stderr-only output."""
    return CliRefusedBoundaryError(str(error), suggestion="aeat config repair --help")


def _project_cadrumo_error(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Forward a typed :class:`CadrumoError` verbatim."""
    assert isinstance(error, CadrumoError)
    return error


def _project_validation_error(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Log the pydantic detail, then wrap the input-time validation failure.

    The wrapped :class:`CliValidationBoundaryError` surfaces an operator-friendly
    refusal without the per-field error list, which is too noisy for an end-user
    but is exactly the diagnostic engineers need to triage a failing CLI surface
    or test fixture.
    """
    assert isinstance(error, ValidationError)
    _log.error(
        "command_error_boundary: pydantic ValidationError in %s: %s",
        getattr(callback, "__name__", repr(callback)),
        error.errors(),
    )
    return CliValidationBoundaryError(error)


#: Exception-family projections walked in DECLARATION ORDER by
#: :func:`_project_boundary_error` — order IS specificity, mirroring the former
#: ``except`` ladder exactly: the stored-drift and former-product refusals are
#: matched before the broad :class:`CadrumoError` arm, and
#: :exc:`~pydantic.ValidationError` before the unexpected fallback.
_ERROR_PROJECTIONS: tuple[tuple[type[Exception], _BoundaryProjection], ...] = (
    (StoredProfileDriftError, _project_stored_data_drift),
    (FormerProductStateError, _project_former_product_state),
    (CadrumoError, _project_cadrumo_error),
    (ValidationError, _project_validation_error),
)


def _project_unexpected(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Project an unexpected exception: unwrap a wrapped refusal, else internal error.

    SQLAlchemy wraps an exception raised inside bind-param processing (e.g.
    ``NoActiveBucketSessionError`` raised by an encrypted-column codec when no
    session is unlocked) into a ``StatementError``. The wrapped cause is a typed
    :class:`CadrumoError` carrying a clean operator refusal. Unwrap it and forward
    the refusal verbatim — otherwise the no-session refusal is mis-classified as
    an unexpected internal error and a full traceback is written to the log file,
    where ``aeat config repair logs`` later echoes it back at the operator as if
    it were a live crash.
    """
    wrapped = _unwrap_cadrumo_error(error)
    if wrapped is not None:
        return wrapped
    _log.error(
        "command_error_boundary: unexpected exception in %s",
        getattr(callback, "__name__", repr(callback)),
        exc_info=True,
    )
    return CliUnexpectedBoundaryError(error)


def _project_boundary_error(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Map a boundary exception to the :class:`CadrumoError` to emit.

    Walks :data:`_ERROR_PROJECTIONS` in declaration order (order = specificity),
    falling back to :func:`_project_unexpected`. Control-flow re-raise and the
    under-test re-raise are applied by the caller before this runs, so neither
    reaches the table.
    """
    for exc_type, project in _ERROR_PROJECTIONS:
        if isinstance(error, exc_type):
            return project(error, callback)
    return _project_unexpected(error, callback)


__all__ = [
    "CliCommandGroupUnavailableError",
    "CliRefusedBoundaryError",
    "CliStoredDataValidationBoundaryError",
    "CliValidationBoundaryError",
    "decorate_typer_app",
    "error_boundary_under_test",
    "write_stderr",
]
