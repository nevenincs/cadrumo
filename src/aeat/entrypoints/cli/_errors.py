"""Shared CLI error-emission boundary.

This module is the single funnel for translating exceptions raised
inside Typer callbacks into the structured CLI error contract — a
stable stderr payload (text or JSON) plus a stable :class:`typer.Exit`
code drawn from :class:`aeat.entrypoints.cli._exit_codes.ExitCode`.

Two narrow boundary exceptions wrap unexpected failures so they reach
:func:`render_error_text` and :func:`render_error_json` with a
predictable shape:

- :exc:`CliValidationBoundaryError` wraps a leaked
  :exc:`pydantic.ValidationError`.
- :exc:`CliUnexpectedBoundaryError` wraps any other non-control-flow
  exception.

A third type, :exc:`CliRefusedBoundaryError`, is reserved for refusals
emitted in JSON mode whose payload is intentionally stderr-only.

The :func:`command_error_boundary` decorator wraps a callback so that
:class:`aeat.core.errors.AeatError` instances are emitted via
:func:`_emit_error_and_exit`. :func:`decorate_typer_app` walks a
:class:`typer.Typer` tree and applies the decorator to every registered
command and group callback (with an opt-out via ``skip_paths``).
:func:`error_boundary_under_test` toggles the boundary off for tests
that want to assert on the raised exception directly.
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

from ...core.errors import (
    AeatError,
    build_error_envelope,
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)
from ...core.logging import get_logger
from ...core.click_context import json_output_requested

_log = get_logger(__name__)

_UNDER_TEST: ContextVar[bool] = ContextVar("aeat_cli_error_boundary_under_test", default=False)
_WRAPPED_CALLBACKS: dict[int, Callable[..., object]] = {}


class _ReconfigurableTextIO(Protocol):
    """Structural type for a text stream that supports ``reconfigure``."""

    def reconfigure(self, *, encoding: str | None = None, errors: str | None = None) -> None:
        """Reconfigure the underlying text stream's encoding and error mode."""


class CliValidationBoundaryError(AeatError):
    """Raised when a CLI callback leaks a :exc:`pydantic.ValidationError`.

    The original exception is preserved on :attr:`original_exception` so
    downstream renderers and tests can inspect it without losing the
    typed pydantic detail.

    Attributes:
        original_exception: The underlying :exc:`pydantic.ValidationError`.
    """

    def __init__(self, error: ValidationError) -> None:
        """Wrap ``error`` in the structured CLI boundary contract.

        Args:
            error: The pydantic validation error raised inside the
                Typer callback.
        """

        super().__init__(
            "The command input failed validation. Run `aeat config repair` or reset the profile state.",
            context={
                "recovery": "aeat config repair",
            },
            suggestion="aeat config repair",
        )
        self.original_exception: ValidationError = error


class CliUnexpectedBoundaryError(AeatError):
    """Raised when a CLI callback leaks an unexpected exception.

    Used for any exception that is not :class:`AeatError`,
    :exc:`pydantic.ValidationError`, or Typer/Click control flow. The
    original exception is preserved on :attr:`original_exception`.

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

        # The recovery hint points at the engineer-surface diagnostic
        # report rather than `aeat config repair`. The repair family is
        # bootstrap-exempt but state-touching and may itself fail under
        # the same conditions that produced this unexpected exception
        # (disaster ADR Ruling 5: the welded-shut escape hatch retires).
        # The diagnostics surface dumps a structured report from a
        # process that never opens an encrypted session.
        super().__init__(
            "The command failed due to an unexpected internal error.",
            context={
                "recovery": "python -m aeat.diagnostics report",
            },
            suggestion="python -m aeat.diagnostics report",
        )
        self.original_exception: Exception = error


class CliRefusedBoundaryError(AeatError):
    """Raised when JSON-mode CLI must refuse a request with stderr-only output.

    Refusals are emitted as plain stderr text even in JSON mode because
    the structured payload contract intentionally does not expose them
    on stdout.
    """


def command_error_boundary[**P, R](callback: Callable[P, R]) -> Callable[P, R]:
    """Wrap ``callback`` so :class:`AeatError` emits the structured stderr form.

    The wrapper catches three exception families and routes them to
    :func:`_emit_error_and_exit`:

    - :class:`aeat.core.errors.AeatError` is forwarded verbatim.
    - :exc:`pydantic.ValidationError` is wrapped in
      :exc:`CliValidationBoundaryError`.
    - Any other non-control-flow exception is wrapped in
      :exc:`CliUnexpectedBoundaryError`.

    Typer/Click control-flow exceptions (e.g. :exc:`click.exceptions.Exit`,
    :exc:`click.Abort`, :exc:`typer.Exit`) propagate untouched so the
    framework can act on them. When :func:`error_boundary_under_test` is
    active the original exception is re-raised instead of being emitted.

    Calls are memoised by callback identity so wrapping the same
    callback twice returns the original wrapper.

    Args:
        callback: Typer callback to wrap.

    Returns:
        Wrapped callback with the original signature preserved.
    """

    existing = _WRAPPED_CALLBACKS.get(id(callback))
    if existing is not None:
        return cast(Callable[P, R], existing)

    @functools.wraps(callback)
    def _wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return callback(*args, **kwargs)
        except AeatError as error:
            if _UNDER_TEST.get():
                raise
            _emit_error_and_exit(error)
        except ValidationError as error:
            if _UNDER_TEST.get():
                raise
            _emit_error_and_exit(CliValidationBoundaryError(error))
        except Exception as error:
            if _is_click_control_flow(error):
                raise
            if _UNDER_TEST.get():
                raise
            # SQLAlchemy wraps an exception raised inside bind-param
            # processing (e.g. NoActiveBucketSessionError raised by an
            # encrypted-column codec when no session is unlocked) into
            # a StatementError. The wrapped cause is a typed AeatError
            # carrying a clean operator refusal. Unwrap it and forward
            # the refusal verbatim — otherwise the no-session refusal
            # is mis-classified as an unexpected internal error and a
            # full traceback is written to the log file, where
            # `aeat config repair logs` later echoes it back at the
            # operator as if it were a live crash.
            wrapped = _unwrap_aeat_error(error)
            if wrapped is not None:
                _emit_error_and_exit(wrapped)
            _log.error(
                "command_error_boundary: unexpected exception in %s",
                getattr(callback, "__name__", repr(callback)),
                exc_info=True,
            )
            _emit_error_and_exit(CliUnexpectedBoundaryError(error))

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
        app: Root or nested :class:`typer.Typer` app to decorate.
        skip_paths: Fully-qualified command paths (as tuples of name
            segments) that must remain undecorated. Useful for callbacks
            that intentionally manage their own error reporting.
    """

    skip_set = set(skip_paths)
    _decorate_typer_node(app, prefix=(), skip_paths=skip_set)


def write_stderr(text: str, *, stream: io.TextIOBase | None = None) -> None:
    """Write ``text`` to stderr with UTF-8-safe fallback behaviour.

    On Windows consoles whose default encoding is cp1252, raw writes of
    non-ASCII characters raise :exc:`UnicodeEncodeError`. This helper
    first attempts to reconfigure the stream to UTF-8 via
    :class:`_ReconfigurableTextIO`; on encoding failure it falls back to
    the underlying byte buffer with ``errors="replace"``, and finally to
    an ASCII-safe replacement string.

    Args:
        text: Text payload to emit.
        stream: Optional target stream to write to instead of
            :data:`sys.stderr`. Primarily useful in tests.
    """

    target = sys.stderr if stream is None else stream
    if _supports_reconfigure(target):
        with contextlib.suppress(Exception):
            target.reconfigure(encoding="utf-8", errors="replace")
    try:
        target.write(text)
        target.flush()
        return
    except UnicodeEncodeError:
        buffer = getattr(target, "buffer", None)
        if buffer is not None:
            buffer.write(text.encode("utf-8", errors="replace"))
            with contextlib.suppress(Exception):
                buffer.flush()
            return
        target.write(text.encode("ascii", errors="replace").decode("ascii"))
        target.flush()


def _emit_error_and_exit(error: AeatError) -> Never:
    """Render ``error`` to stderr and terminate with its registered exit code.

    Selects the JSON or text renderer based on whether the active
    callback opted into JSON output via :func:`json_output_requested`,
    writes the payload through :func:`write_stderr`, and raises
    :class:`typer.Exit` with the category-mapped exit code.
    """

    code = get_registered_error_code(error)
    payload = render_error_json(error) if json_output_requested() else render_error_text(error)
    write_stderr(payload)
    raise typer.Exit(code=get_error_exit_code(code.category)) from error


@contextmanager
def error_boundary_under_test() -> Iterator[None]:
    """Temporarily force :func:`command_error_boundary` to re-raise originals.

    Tests that need to assert on the raised exception type rather than
    the rendered stderr payload should wrap their invocation in this
    context manager. The override is scoped to the active context via
    :class:`contextvars.ContextVar`, so concurrent callbacks are
    unaffected.

    Yields:
        :data:`None`. The context's only purpose is the side effect on
        the internal flag.
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


def _is_wrap_candidate(callback: object) -> TypeGuard[Callable[..., object]]:
    """Narrow ``callback`` to a plain function suitable for wrapping."""

    return inspect.isfunction(callback)


def _supports_reconfigure(stream: object) -> TypeGuard[_ReconfigurableTextIO]:
    """Narrow ``stream`` to a text stream that exposes ``reconfigure``."""

    return hasattr(stream, "reconfigure")


def _unwrap_aeat_error(error: BaseException) -> AeatError | None:
    """Return the typed :class:`AeatError` wrapped inside ``error``, if any.

    A library boundary (notably SQLAlchemy) can catch an
    :class:`AeatError` raised inside its own machinery and re-raise it
    wrapped in a library-specific exception. The typed refusal is then
    reachable only through the ``orig`` attribute SQLAlchemy sets, or
    through the standard ``__cause__`` / ``__context__`` chain. This
    helper walks both so the refusal can be forwarded verbatim rather
    than mis-reported as an unexpected internal error.

    The walk is depth-bounded to avoid pathological cycles.
    """

    seen: set[int] = set()
    current: BaseException | None = error
    depth = 0
    while current is not None and depth < 16:
        if isinstance(current, AeatError):
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


def _is_click_control_flow(error: Exception) -> bool:
    """Return :data:`True` when ``error`` is Typer/Click control flow, not a bug.

    Recognises :exc:`click.ClickException`, :exc:`click.exceptions.Exit`,
    :exc:`click.Abort`, and :exc:`typer.Exit`.
    """

    return isinstance(error, (click.ClickException, click.exceptions.Exit, click.Abort, typer.Exit))


__all__ = [
    "CliRefusedBoundaryError",
    "build_error_envelope",
    "decorate_typer_app",
    "error_boundary_under_test",
    "json_output_requested",
    "write_stderr",
]
