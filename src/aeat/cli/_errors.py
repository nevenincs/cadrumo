"""Shared CLI error-emission boundary."""

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

from ..errors import (
    AeatError,
    build_error_envelope,
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)
from ._context import json_output_requested

_UNDER_TEST: ContextVar[bool] = ContextVar("aeat_cli_error_boundary_under_test", default=False)
_WRAPPED_CALLBACKS: dict[int, Callable[..., object]] = {}


class _ReconfigurableTextIO(Protocol):
    """Text stream that supports runtime encoding reconfiguration."""

    def reconfigure(self, *, encoding: str | None = None, errors: str | None = None) -> None:
        """Reconfigure the underlying text stream."""


class CliValidationBoundaryError(AeatError):
    """Raised when a CLI callback leaks a Pydantic validation failure."""

    def __init__(self, error: ValidationError) -> None:
        """Wrap ``error`` in the structured CLI boundary contract."""

        super().__init__(
            "The command input failed validation.",
            context={
                "error_type": type(error).__name__,
                "detail": str(error),
            },
        )
        self.original_exception: ValidationError = error


class CliUnexpectedBoundaryError(AeatError):
    """Raised when a CLI callback leaks an unexpected exception."""

    def __init__(self, error: Exception) -> None:
        """Wrap ``error`` in the structured CLI boundary contract."""

        super().__init__(
            "The command failed due to an unexpected internal error.",
            context={
                "error_type": type(error).__name__,
                "detail": str(error) or type(error).__name__,
            },
        )
        self.original_exception: Exception = error


class CliRefusedBoundaryError(AeatError):
    """Raised when CLI JSON mode must refuse a request with stderr-only output."""


def command_error_boundary[**P, R](callback: Callable[P, R]) -> Callable[P, R]:
    """Wrap ``callback`` so :class:`AeatError` emits the structured stderr form.

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
            _emit_error_and_exit(CliUnexpectedBoundaryError(error))

    _WRAPPED_CALLBACKS[id(callback)] = _wrapped
    _WRAPPED_CALLBACKS[id(_wrapped)] = _wrapped
    return _wrapped


def decorate_typer_app(
    app: typer.Typer,
    *,
    skip_paths: Sequence[tuple[str, ...]] = (),
) -> None:
    """Apply the error boundary to every registered Typer callback.

    Args:
        app: Root or nested Typer app.
        skip_paths: Fully-qualified command paths that must remain untouched.
    """

    skip_set = set(skip_paths)
    _decorate_typer_node(app, prefix=(), skip_paths=skip_set)


def write_stderr(text: str, *, stream: io.TextIOBase | None = None) -> None:
    """Write ``text`` to stderr with UTF-8-safe fallback behaviour."""

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
    """Render ``error`` to stderr and terminate with the stable exit code."""

    code = get_registered_error_code(error)
    payload = render_error_json(error) if json_output_requested() else render_error_text(error)
    write_stderr(payload)
    raise typer.Exit(code=get_error_exit_code(code.category)) from error


@contextmanager
def error_boundary_under_test() -> Iterator[None]:
    """Temporarily force the boundary to re-raise the original exception."""

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
    if callback is None:
        return "<unknown>"
    if inspect.isfunction(callback):
        return callback.__name__
    return callback.__class__.__name__


def _is_wrap_candidate(callback: object) -> TypeGuard[Callable[..., object]]:
    return inspect.isfunction(callback)


def _supports_reconfigure(stream: object) -> TypeGuard[_ReconfigurableTextIO]:
    return hasattr(stream, "reconfigure")


def _is_click_control_flow(error: Exception) -> bool:
    """Return ``True`` when ``error`` is Typer/Click control flow, not a bug."""

    return isinstance(error, (click.ClickException, click.exceptions.Exit, click.Abort, typer.Exit))


__all__ = [
    "CliRefusedBoundaryError",
    "build_error_envelope",
    "command_error_boundary",
    "decorate_typer_app",
    "error_boundary_under_test",
    "json_output_requested",
    "write_stderr",
]
