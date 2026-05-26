"""Tests for the workflow resumption action."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ...domain.deadlines import ModeloDeadline, ObligationStatus
from ...tests.secure_sql import isolated_runtime_profile
from . import (
    WorkflowAbortReason,
    WorkflowError,
    WorkflowResult,
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    WorkflowStage,
    WorkflowStep,
    find_latest_run_for_period,
    resume_modelo_workflow,
    save_run,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path):
        yield


_T = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)


def _obligation(modelo: str = "130", period: str = "2026Q1") -> ModeloDeadline:
    return ModeloDeadline(
        modelo=modelo,
        period=period,
        opens_on=date(2026, 4, 1),
        closes_on=date(2026, 4, 20),
        status=ObligationStatus.UPCOMING,
        applies_because="economic activity",
    )


def _aborted_result(
    *,
    run_id: str,
    reason: WorkflowAbortReason,
    obligation: ModeloDeadline | None,
) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=_T,
        ended_at=_T,
        success=False,
        summary="aborted",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=reason,
        obligation=obligation,
        steps=(step,),
        summary="aborted run for resume tests",
    )


def _done_result(run_id: str) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=_T,
        ended_at=_T,
        success=True,
        summary="done",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        obligation=_obligation(),
        steps=(step,),
        summary="done run",
    )


def test_resume_returns_context_for_resumable_aborted_run(tmp_path: Path) -> None:
    run_id = "a" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
    )
    context = resume_modelo_workflow(run_id)
    assert isinstance(context, WorkflowResumeContext)
    assert context.resumed_from_run_id == run_id
    assert context.modelo == "130"
    assert context.period == "2026Q1"
    assert context.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
    assert context.obligation.modelo == "130"


def test_resume_refuses_done_run(tmp_path: Path) -> None:
    run_id = "b" * 16
    save_run(_done_result(run_id))
    with pytest.raises(WorkflowResumeRefusedError, match=r"final_stage"):
        resume_modelo_workflow(run_id)


@pytest.mark.parametrize(
    "reason",
    [
        WorkflowAbortReason.NO_PENDING_OBLIGATION,
        WorkflowAbortReason.ALREADY_FILED,
        WorkflowAbortReason.USER_CANCELLED,
    ],
)
def test_resume_refuses_non_resumable_reasons(
    tmp_path: Path,
    reason: WorkflowAbortReason,
) -> None:
    run_id = "c" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=reason,
            obligation=_obligation() if reason is not WorkflowAbortReason.NO_PENDING_OBLIGATION else None,
        ),
    )
    with pytest.raises(WorkflowResumeRefusedError, match=r"terminal by design"):
        resume_modelo_workflow(run_id)


def test_resume_refuses_run_without_obligation(tmp_path: Path) -> None:
    run_id = "d" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=None,
        ),
    )
    with pytest.raises(WorkflowResumeRefusedError, match=r"obligation"):
        resume_modelo_workflow(run_id)


def test_resume_for_missing_run_id_surfaces_workflow_error(tmp_path: Path) -> None:
    with pytest.raises(WorkflowError, match=r"workflow run not found"):
        resume_modelo_workflow("missing-run-id-9")


def test_resume_context_run_id_satisfies_engine_resumed_from_contract(tmp_path: Path) -> None:
    """The resume action returns a ``resumed_from_run_id`` that matches the
    engine's ``run_for_period(resumed_from=...)`` boundary contract: a
    16-character lowercase hex string.

    Locks the end-to-end shape of the resume → engine linkage so the
    two halves stay compatible without requiring the full live
    composite engine to run inside the resume unit suite.
    """

    run_id = "0" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
    )
    context = resume_modelo_workflow(run_id)

    forwarded = context.resumed_from_run_id
    assert len(forwarded) == 16
    assert all(ch in "0123456789abcdef" for ch in forwarded)

    # A WorkflowResult constructed with the forwarded id round-trips
    # through the result-model validation that the engine emits at
    # the end of run_for_period — proves the producer/consumer contract.
    chained = WorkflowResult(
        run_id="b" * 16,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        obligation=_obligation(),
        steps=(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=_T,
                ended_at=_T,
                success=True,
                summary="resumed",
            ),
        ),
        summary="resumed completion",
        resumed_from=forwarded,
    )
    assert chained.resumed_from == run_id


def test_resume_for_unknown_run_id_is_indistinguishable_from_stale(tmp_path: Path) -> None:
    """A ``resumed_from`` run id that no longer resolves through the persistence
    layer surfaces as the same :class:`WorkflowError` the resume action raises
    for a never-saved run, locking the contract that stale and absent ids
    share one error path. The engine itself cannot verify existence; the
    upstream resume action is the gate."""

    with pytest.raises(WorkflowError, match=r"workflow run not found"):
        resume_modelo_workflow("c" * 16)


def test_resume_is_idempotent_for_a_persistently_aborted_run(tmp_path: Path) -> None:
    """Calling ``resume_modelo_workflow`` twice on the same aborted run
    returns equivalent contexts. The action is read-only over the prior
    record and does not mutate it, so repeated resume requests must
    produce the same ``(modelo, period, obligation, aborted_reason)``
    payload."""

    run_id = "f" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
    )
    first = resume_modelo_workflow(run_id)
    second = resume_modelo_workflow(run_id)
    assert first == second
    assert first.resumed_from_run_id == second.resumed_from_run_id == run_id


def test_find_latest_run_for_period_returns_newest_match(tmp_path: Path) -> None:
    """``find_latest_run_for_period`` resolves the newest persisted run for
    a ``(modelo, period)`` pair, so an operator who only knows the
    work unit's modelo and period can discover the run id without
    holding the 16-character hash by hand."""

    earlier = _aborted_result(
        run_id="a" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", "2026Q1"),
    ).model_copy(update={"started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC)})
    later = _aborted_result(
        run_id="b" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", "2026Q1"),
    ).model_copy(update={"started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC)})
    save_run(earlier)
    save_run(later)

    resolved = find_latest_run_for_period(modelo="130", period="2026Q1")
    assert resolved.run_id == later.run_id


def test_find_latest_run_for_period_ignores_other_periods(tmp_path: Path) -> None:
    """Only runs whose resolved obligation matches the requested
    ``(modelo, period)`` are considered."""

    save_run(
        _aborted_result(
            run_id="a" * 16,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation("303", "2026Q2"),
        ),
    )
    with pytest.raises(WorkflowError, match=r"no persisted workflow run"):
        find_latest_run_for_period(modelo="130", period="2026Q1")


def test_find_latest_run_for_period_resolves_id_for_resume(tmp_path: Path) -> None:
    """The run id resolved from a ``(modelo, period)`` pair feeds
    :func:`resume_modelo_workflow` directly — the discoverability
    path an operator holding only a work unit relies on."""

    run = _aborted_result(
        run_id="e" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", "2026Q1"),
    )
    save_run(run)

    resolved = find_latest_run_for_period(modelo="130", period="2026Q1")
    context = resume_modelo_workflow(resolved.run_id)
    assert context.resumed_from_run_id == run.run_id
    assert context.modelo == "130"
    assert context.period == "2026Q1"
