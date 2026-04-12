"""Shared helpers for the ``aeat workflow`` CLI sub-app.

Construction of the real :class:`aeat.workflow.WorkflowEngine`
requires wiring components that still live on sibling branches
(#43 status reader, #46 inbox, #8 cert auth). Until those land, the
command surface emits a typer-friendly error directing the user at
the missing sibling branch. The helpers are also the single seam
the CLI unit tests hook into via monkeypatched constructors, so no
``unittest.mock.patch`` is ever needed — tests substitute a real
engine instance by assigning ``_engine_factory``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date

import typer
from rich.console import Console
from rich.json import JSON

from aeat.config import load_settings
from aeat.deadlines import AutonomoProfile
from aeat.workflow import (
    WorkflowEngine,
    WorkflowError,
    WorkflowResult,
    save_run,
)

_CONSOLE = Console()

EngineFactory = Callable[[], WorkflowEngine]
"""Type alias for a zero-argument factory that returns a ``WorkflowEngine``."""

_engine_factory: EngineFactory | None = None
"""Module-level seam. Tests assign a real factory; production leaves it unset."""

_profile_factory: Callable[[], AutonomoProfile] | None = None
"""Module-level seam for the profile the CLI runs against."""


def set_test_hooks(
    *,
    engine_factory: EngineFactory,
    profile_factory: Callable[[], AutonomoProfile],
) -> None:
    """Install real factory functions (used by the CLI unit tests).

    Args:
        engine_factory: Callable returning a fully-wired
            :class:`WorkflowEngine`.
        profile_factory: Callable returning the
            :class:`AutonomoProfile` the CLI should run for.
    """
    global _engine_factory, _profile_factory
    _engine_factory = engine_factory
    _profile_factory = profile_factory


def clear_test_hooks() -> None:
    """Reset the module seams to their production defaults."""
    global _engine_factory, _profile_factory
    _engine_factory = None
    _profile_factory = None


def _build_engine() -> WorkflowEngine:
    """Return a :class:`WorkflowEngine` — test seam or production path."""
    if _engine_factory is not None:
        return _engine_factory()
    raise WorkflowError(
        "aeat workflow requires sibling-branch adapters for #43/#46/#8 which are not yet wired; "
        "use aeat.workflow.default_engine(...) in your own code or wait for the rebase."
    )


def _build_profile() -> AutonomoProfile:
    """Return the :class:`AutonomoProfile` — test seam or a placeholder."""
    if _profile_factory is not None:
        return _profile_factory()
    # Production callers need to provide a profile via settings (#38 will wire this
    # once the profile loader lands); until then we surface a clear WorkflowError.
    raise WorkflowError(
        "aeat workflow CLI needs a profile loader; inject one via set_test_hooks() "
        "or wait for the deadline-engine profile loader to land (TODO: wire via #38)."
    )


def _emit(result: WorkflowResult, *, as_json: bool) -> None:
    """Persist the run and print it in the requested format."""
    settings = load_settings()
    save_run(result, runs_dir=settings.aeat_workflow_runs_dir)
    payload = result.model_dump_json(indent=2)
    if as_json:
        typer.echo(payload)
        return
    _CONSOLE.print(JSON(payload))


def run_engine_next(
    *,
    dry_run: bool,
    override_confirmation: bool,
    sync_first: bool,
    as_json: bool,
    today: date | None = None,
) -> WorkflowResult:
    """Build, run, persist, and emit a ``run_next`` invocation."""
    try:
        engine = _build_engine()
        profile = _build_profile()
    except WorkflowError as exc:
        _CONSOLE.print(f"[red]refusing:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    result = asyncio.run(
        engine.run_next(
            profile,
            dry_run=dry_run,
            override_confirmation=override_confirmation,
            sync_first=sync_first,
            today=today,
        )
    )
    _emit(result, as_json=as_json)
    return result


def run_engine_for_period(
    *,
    modelo: str,
    period: str,
    dry_run: bool,
    override_confirmation: bool,
    sync_first: bool,
    as_json: bool,
    today: date | None = None,
) -> WorkflowResult:
    """Build, run, persist, and emit a ``run_for_period`` invocation."""
    try:
        engine = _build_engine()
        profile = _build_profile()
    except WorkflowError as exc:
        _CONSOLE.print(f"[red]refusing:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    result = asyncio.run(
        engine.run_for_period(
            profile,
            modelo,
            period,
            dry_run=dry_run,
            override_confirmation=override_confirmation,
            sync_first=sync_first,
            today=today,
        )
    )
    _emit(result, as_json=as_json)
    return result


__all__ = [
    "EngineFactory",
    "clear_test_hooks",
    "run_engine_for_period",
    "run_engine_next",
    "set_test_hooks",
]
