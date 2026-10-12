"""Shared CLI test runner helpers."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from functools import cache
from typing import NotRequired, Protocol, Unpack, cast

import click
from click.testing import CliRunner, Result
from typer import Typer
from typer.main import get_command
from typing_extensions import TypedDict

_RUNNER = CliRunner()


class ClickInvokeKwargs(TypedDict, total=False):
    """Typed surface for ``CliRunner.invoke`` keyword arguments.

    Covers the kwargs that Cadrumo tests legitimately pass.  Any kwarg
    not listed here is a caller mistake and will be caught by the
    type-checker.
    """

    env: NotRequired[Mapping[str, str | None] | None]
    color: NotRequired[bool]
    catch_exceptions: NotRequired[bool]
    input: NotRequired[str | bytes | None]
    obj: NotRequired[object]


@cache
def cadrumo_click_command() -> click.Command:
    """Materialize the Typer app once for default-locale CLI tests."""

    from ..main import app

    # Typer vendors its own Click fork, so typer.main.get_command is typed to
    # return typer._click.core.Command; it is the same object family at runtime
    # as the upstream click.Command the CliRunner consumes. The cast bridges the
    # static vendored/upstream duality only.
    return cast(click.Command, get_command(app))


@cache
def click_command_for_typer_app(typer_app: Typer) -> click.Command:
    """Materialize any Typer app once for direct app-surface tests."""

    return cast(click.Command, get_command(typer_app))


def invoke_typer_app(
    typer_app: Typer,
    args: Sequence[str],
    **kwargs: Unpack[ClickInvokeKwargs],
) -> Result:
    """Invoke a Typer app through the shared cached Click runner."""

    return _RUNNER.invoke(click_command_for_typer_app(typer_app), list(args), **kwargs)


def invoke_uncached_typer_app(
    typer_app: Typer,
    args: Sequence[str],
    **kwargs: Unpack[ClickInvokeKwargs],
) -> Result:
    """Invoke a Typer app without reusing a cached command tree."""

    return _RUNNER.invoke(cast(click.Command, get_command(typer_app)), list(args), **kwargs)


class ProfileCliInvoker(Protocol):
    """A test-owned profile whose joined runtime admits the commands a test runs."""

    def invoke(self, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        """Run one command as the profile's operator."""
        ...


_BOUND_PROFILE: ContextVar[ProfileCliInvoker | None] = ContextVar("cli-test-bound-profile", default=None)


@contextmanager
def bind_profile_cli(invoker: ProfileCliInvoker) -> Iterator[None]:
    """Run every :func:`invoke_cached_cli` call as ``invoker``'s operator until the scope ends.

    A fixture that registers a profile and joins its runtime binds it, so a
    test runs its commands the way that profile's operator would, exactly as
    the session that registration left live in the test process once did.
    """
    token = _BOUND_PROFILE.set(invoker)
    try:
        yield
    finally:
        _BOUND_PROFILE.reset(token)


def invoke_cached_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the cached Cadrumo Click command, as the bound profile's operator when one is bound.

    See :func:`invoke_unbound_cli` for the invocation itself.
    """
    bound = _BOUND_PROFILE.get()
    return invoke_unbound_cli(args, **kwargs) if bound is None else bound.invoke(args, **kwargs)


def invoke_unbound_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the cached Cadrumo Click command exactly as given.

    Typer's test runner rebuilds the full Click command tree on every
    invocation. The Cadrumo tree is large enough that repeated materialization
    dominates test runtime for default-locale CLI smoke tests.

    Only kwargs declared in :class:`ClickInvokeKwargs` are accepted; unknown
    kwargs are a static type error, catching accidental misuse at author time.
    """

    return _RUNNER.invoke(cadrumo_click_command(), list(args), **kwargs)


def semantic_cli_output(result: Result) -> str:
    """Return CLI output without terminal styling for semantic assertions.

    Typer forces terminal styling when GitHub Actions is detected, even when
    Click's test runner is invoked with ``color=False``.  Removing ANSI styling
    keeps option names and prose intact without changing the production CLI's
    colour behaviour.
    """

    return semantic_cli_text(result.output)


def semantic_cli_text(text: str) -> str:
    """Return one CLI stream without terminal styling.

    Sequence capture reads stdout and stderr independently, whereas
    :func:`semantic_cli_output` consumes Click's combined
    :class:`~click.testing.Result.output`.  This string-level authority keeps
    both callers on the same presentation-only ANSI removal.
    """

    return click.unstyle(text)
