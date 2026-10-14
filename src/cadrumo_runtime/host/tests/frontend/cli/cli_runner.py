"""Shared CLI test runner helpers."""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import cache
from typing import Protocol, Unpack, cast

import click
from click.testing import CliRunner, Result
from typer import Typer
from typer.main import get_command

from cadrumo.tests.cli_fixture_ports import ClickInvokeKwargs

_RUNNER = CliRunner()
_PUBLIC_CLI: ContextVar[Callable[..., Result] | None] = ContextVar("runtime-test-public-cli", default=None)


@cache
def cadrumo_click_command() -> click.Command:
    """Materialize the Typer app once for default-locale CLI tests."""

    from cadrumo.entrypoints.cli.main import cli_app

    app = cli_app()

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
def bind_profile_cli(invoker: ProfileCliInvoker) -> Generator[None]:
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


#: The refusal reason of a command that found no runtime to submit to.
_RUNTIME_UNAVAILABLE = "runtime_unavailable"

_OPERATOR_SCOPE: ContextVar[ExitStack | None] = ContextVar("cli-test-operator-scope", default=None)


@contextmanager
def operator_runtime_scope() -> Generator[None]:
    """Own, for one test phase, the runtime a live in-process profile session is joined to.

    Registering or unlocking a profile in a test leaves that profile's session
    live in the process, and commands once ran inside it. They now submit to
    the runtime, so a command refused for want of one joins that profile's
    runtime and binds it, as its operator would be admitted; the runtime is
    retired when the phase ends.
    """
    with ExitStack() as stack:
        token = _OPERATOR_SCOPE.set(stack)
        try:
            yield
        finally:
            _OPERATOR_SCOPE.reset(token)


def _join_live_session() -> ProfileCliInvoker | None:
    """Bind the live profile session's runtime inside the test's operator scope, if both exist."""
    scope = _OPERATOR_SCOPE.get()
    if scope is None:
        return None
    from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session

    session = current_active_bucket_session()
    if session is None:
        return None
    from .runtime_profile_backend import live_session_operator

    operator = live_session_operator(scope, session.bucket_id)
    if operator is not None:
        scope.enter_context(bind_profile_cli(operator))
    return operator


def invoke_cached_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the cached Cadrumo Click command, as the bound profile's operator when one is bound.

    With no profile bound, a command refused because no runtime is reachable,
    which therefore had no effect, is run again once as the operator of a
    profile session left live in the process, through
    :func:`operator_runtime_scope`. A test that already serves its profile from
    a runtime never reaches that path. See :func:`invoke_unbound_cli` for the
    invocation itself.
    """
    bound = _BOUND_PROFILE.get()
    if bound is not None:
        return bound.invoke(args, **kwargs)
    result = invoke_unbound_cli(args, **kwargs)
    if result.exit_code == 0 or _RUNTIME_UNAVAILABLE not in result.output:
        return result
    joined = _join_live_session()
    return result if joined is None else joined.invoke(args, **kwargs)


@contextmanager
def bind_public_cli_runner(runner: Callable[..., Result]) -> Generator[None]:
    """Bind the repository-root public AEAT invocation fixture for this test."""
    token = _PUBLIC_CLI.set(runner)
    try:
        yield
    finally:
        _PUBLIC_CLI.reset(token)


def invoke_unbound_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the cached Cadrumo Click command exactly as given.

    Typer's test runner rebuilds the full Click command tree on every
    invocation. The Cadrumo tree is large enough that repeated materialization
    dominates test runtime for default-locale CLI smoke tests.

    Only kwargs declared in :class:`ClickInvokeKwargs` are accepted; unknown
    kwargs are a static type error, catching accidental misuse at author time.
    """

    runner = _PUBLIC_CLI.get()
    if runner is None:
        raise RuntimeError("runtime host CLI tests require the injected run_cadrumo_cli fixture")
    return runner(args, **kwargs)


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
