"""Shared helpers for the ``aeat workflow`` CLI sub-app.

Production wiring composes the on-main deadline engine, filing runtime
schema provider, and dry-run-safe submission engine helper into a real
:class:`aeat.workflow.WorkflowEngine`. Tests can still override the
construction seam by assigning ``_engine_factory`` / ``_profile_factory``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date

import typer
from rich.console import Console
from rich.json import JSON

from ...config import load_settings
from ...deadlines import AutonomoProfile
from ...filing.runtime import build_runtime_schema_provider
from ...workflow import (
    DeadlineEngineAdapter,
    FilingDraftBuilderAdapter,
    SubmissionEngineAdapter,
    WorkflowEngine,
    WorkflowError,
    WorkflowResult,
    default_engine,
    save_run,
)
from ..deadlines._helpers import build_engine as build_deadline_engine
from ..deadlines._helpers import load_profile, resolve_profile_path
from ..submission._helpers import build_engine as build_submission_engine

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
    deadline_engine = build_deadline_engine()
    submission_engine = build_submission_engine()
    return default_engine(
        deadline_engine=DeadlineEngineAdapter(deadline_engine),
        filing_draft_builder=FilingDraftBuilderAdapter(schema_provider=build_runtime_schema_provider()),
        submission_engine=SubmissionEngineAdapter(submission_engine),
    )


def _build_profile() -> AutonomoProfile:
    """Return the :class:`AutonomoProfile` — test seam or configured default."""
    if _profile_factory is not None:
        return _profile_factory()
    try:
        return load_profile(resolve_profile_path(None))
    except Exception as exc:
        raise WorkflowError(str(exc)) from exc


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
