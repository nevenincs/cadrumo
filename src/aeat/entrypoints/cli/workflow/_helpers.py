"""Shared helpers for the ``aeat workflow`` CLI sub-app.

Production wiring composes the deadline engine, filing runtime schema
provider, and read-only submission preflight helper into a real
:class:`aeat.application.workflow.WorkflowEngine`. Tests override the
construction seam by assigning :data:`_engine_factory` and
:data:`_profile_factory` via :func:`set_test_hooks`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date

from rich.console import Console
from rich.json import JSON

from ....application.filing.runtime import build_runtime_schema_provider
from ....application.workflow import (
    DeadlineEngineAdapter,
    FilingDraftBuilderAdapter,
    SubmissionEngineAdapter,
    WorkflowEngine,
    WorkflowError,
    WorkflowResult,
    default_engine,
    save_run,
)
from ....core.config import load_settings
from ....domain.deadlines import AutonomoProfile
from .._errors import json_output_requested
from .._schemas import emit_json_success
from ..deadlines._helpers import build_engine as build_deadline_engine
from ..deadlines._helpers import load_profile, resolve_profile_path
from ..submission._helpers import build_engine as build_submission_engine

_CONSOLE = Console()

EngineFactory = Callable[[], WorkflowEngine]
"""Type alias for a zero-argument factory returning a
:class:`aeat.application.workflow.WorkflowEngine`."""

_engine_factory: EngineFactory | None = None
"""Construction seam for the engine factory; production leaves it ``None``
so :func:`_build_engine` falls back to :func:`aeat.application.workflow.default_engine`."""

_profile_factory: Callable[[], AutonomoProfile] | None = None
"""Construction seam for the
:class:`aeat.domain.deadlines.AutonomoProfile` the CLI runs against."""


def set_test_hooks(
    *,
    engine_factory: EngineFactory,
    profile_factory: Callable[[], AutonomoProfile],
) -> None:
    """Install real factory functions used by the CLI unit tests.

    Args:
        engine_factory: Callable returning a fully-wired
            :class:`aeat.application.workflow.WorkflowEngine`.
        profile_factory: Callable returning the
            :class:`aeat.domain.deadlines.AutonomoProfile` the CLI should
            run for.
    """
    global _engine_factory, _profile_factory
    _engine_factory = engine_factory
    _profile_factory = profile_factory


def clear_test_hooks() -> None:
    """Reset :data:`_engine_factory` and :data:`_profile_factory` to ``None``.

    Restores the production fallback path on :func:`_build_engine` and
    :func:`_build_profile`.
    """
    global _engine_factory, _profile_factory
    _engine_factory = None
    _profile_factory = None


def _build_engine() -> WorkflowEngine:
    """Return a :class:`aeat.application.workflow.WorkflowEngine`.

    Uses :data:`_engine_factory` when set; otherwise composes a default
    engine via :func:`aeat.application.workflow.default_engine` against the
    deadline-engine, runtime filing schema, and submission-preflight
    helpers.
    """
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
    """Return the :class:`aeat.domain.deadlines.AutonomoProfile`.

    Uses :data:`_profile_factory` when set; otherwise loads the default
    profile via :func:`aeat.entrypoints.cli.deadlines._helpers.load_profile`
    and wraps any failure in :exc:`aeat.application.workflow.WorkflowError`.
    """
    if _profile_factory is not None:
        return _profile_factory()
    try:
        return load_profile(resolve_profile_path(None))
    except Exception as exc:
        raise WorkflowError(str(exc)) from exc


def _emit(result: WorkflowResult, *, as_json: bool, command: str) -> None:
    """Persist ``result`` and render it in the requested output format.

    Args:
        result: The workflow run to persist and emit.
        as_json: When ``True`` (or when JSON output was requested via
            :func:`aeat.entrypoints.cli._errors.json_output_requested`),
            emit a structured JSON envelope on stdout. Otherwise render the
            run as Rich-formatted JSON.
        command: Logical command name used in the JSON envelope.
    """
    settings = load_settings()
    save_run(result, runs_dir=settings.aeat_workflow_runs_dir)
    payload = result.model_dump_json(indent=2)
    if as_json or json_output_requested():
        emit_json_success(command, result)
        return
    _CONSOLE.print(JSON(payload))


def run_engine_next(
    *,
    sync_first: bool,
    as_json: bool,
    today: date | None = None,
) -> WorkflowResult:
    """Build, run, persist, and emit a ``run_next`` invocation.

    Args:
        sync_first: Whether the self-healing sync stage runs before the
            deadline stage.
        as_json: Forwarded to :func:`_emit`.
        today: Optional override for the workflow's reference date.

    Returns:
        The :class:`aeat.application.workflow.WorkflowResult` that was
        persisted.
    """
    engine = _build_engine()
    profile = _build_profile()
    result = asyncio.run(
        engine.run_next(
            profile,
            sync_first=sync_first,
            today=today,
        )
    )
    _emit(result, as_json=as_json, command="workflow next")
    return result


def run_engine_for_period(
    *,
    modelo: str,
    period: str,
    sync_first: bool,
    as_json: bool,
    today: date | None = None,
) -> WorkflowResult:
    """Build, run, persist, and emit a ``run_for_period`` invocation.

    Args:
        modelo: Target modelo identifier (e.g. ``"130"``).
        period: Target period identifier (e.g. ``"2026Q1"``).
        sync_first: Whether the self-healing sync stage runs before the
            deadline stage.
        as_json: Forwarded to :func:`_emit`.
        today: Optional override for the workflow's reference date.

    Returns:
        The :class:`aeat.application.workflow.WorkflowResult` that was
        persisted.
    """
    engine = _build_engine()
    profile = _build_profile()
    result = asyncio.run(
        engine.run_for_period(
            profile,
            modelo,
            period,
            sync_first=sync_first,
            today=today,
        )
    )
    _emit(result, as_json=as_json, command="workflow run")
    return result


__all__ = [
    "clear_test_hooks",
    "run_engine_for_period",
    "run_engine_next",
    "set_test_hooks",
]
