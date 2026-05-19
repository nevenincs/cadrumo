"""Tests for the workflow resumption action."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...domain.deadlines import ModeloDeadline, ObligationStatus
from . import (
    WorkflowAbortReason,
    WorkflowError,
    WorkflowResult,
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    WorkflowStage,
    WorkflowStep,
    resume_modelo_workflow,
    save_run,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'aeat.db'}")
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


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
