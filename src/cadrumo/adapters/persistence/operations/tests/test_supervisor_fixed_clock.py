"""A registered operation's application work runs at the admitted fixed instant; the supervisor's stamps do not.

The test-host fixed clock lets the packaged window reproduce persona rows the
persona table computes under ``frozen_clock``. Its scope is the handler and
nothing around it: the journal, the subject lease that guards the operation and
the terminal receipt keep wall time, so lease expiry and journal ordering never
follow a past instant.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.workflow_gate import build_revision_deadline_window_checker
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import operation_conflict_scope_reference
from cadrumo.core.operations import OperationLifecycle
from cadrumo.core.period import Period
from cadrumo.core.time.clock import MADRID_TZ, frozen_clock, now, wall_now
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.irpf_income_categories import require_irpf_income_category
from cadrumo.domain.contribuyente.entity_type import require_entity_type
from cadrumo.domain.deadlines.engine import DeadlineEngine
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.deadlines.tests.effective_close_scan import obligation_with_a_shifted_close

from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    operation_repositories,
    operation_supervisor,
    supervisor_registry,
    supervisor_request,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_OPERATION_ID = "3" * 64


@dataclass
class _ClockObservingExecutor:
    """Records what its application work sees, and journals one phase from inside it."""

    answer: Callable[[], object] = lambda: None
    lease_probe: Callable[[], Awaitable[datetime | None]] | None = None
    observed_now: list[datetime] = field(default_factory=list)
    answers: list[object] = field(default_factory=list)
    lease_acquired_at: list[datetime | None] = field(default_factory=list)

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        self.observed_now.append(now())
        self.answers.append(self.answer())
        await context.events.phase("operation.phase.declared")
        if self.lease_probe is not None:
            self.lease_acquired_at.append(await self.lease_probe())
        return None


def _past_instant() -> datetime:
    """A whole-second instant well before today, derived from the wall clock rather than named."""
    return (wall_now() - timedelta(days=400)).replace(microsecond=0)


def _lease_probe(leases: OperationLeaseFilesystemRepository) -> Callable[[], Awaitable[datetime | None]]:
    scope_ref = operation_conflict_scope_reference(
        definition_id=supervisor_request().definition_id, subject_ref=supervisor_request().subject_ref
    )

    async def probe() -> datetime | None:
        inspection = await leases.inspect(scope_ref, _OPERATION_ID, observed_at=wall_now())
        return None if inspection.current is None else inspection.current.acquired_at

    return probe


def _settle_under_fixed_clock(
    tmp_path: Path,
    executor: _ClockObservingExecutor,
    instant: datetime,
    authority_operation: PinnedAuthorityOperation | None = None,
) -> OperationPersistedSnapshot:
    """Run one registered operation the way a fixed-clock profile worker composes its supervisor."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        executor.lease_probe = _lease_probe(leases)
        supervisor = operation_supervisor(
            registry=supervisor_registry(executor_type=_ClockObservingExecutor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            clock=wall_now,
            fixed_clock_instant=instant,
            authority_operation=authority_operation,
        )

        async def submit_and_settle() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(supervisor_request(), operation_id=_OPERATION_ID)
            return await run_to_settlement(supervisor, operation_id)

        return asyncio.run(submit_and_settle())


def test_application_work_reads_the_fixed_instant_while_every_supervisor_stamp_is_wall_time(tmp_path: Path) -> None:
    instant = _past_instant()
    executor = _ClockObservingExecutor()
    before = wall_now()

    terminal = _settle_under_fixed_clock(tmp_path, executor, instant)

    assert executor.observed_now == [instant]
    # The scope closed with the handler: this context reads the wall clock again.
    assert now() >= before
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_receipt is not None
    stamps = [
        terminal.started_at,
        terminal.updated_at,
        terminal.executor_entered_at,
        terminal.terminal_receipt.settled_at,
        *executor.lease_acquired_at,
        *(event.timestamp for event in terminal.events),
    ]
    assert executor.lease_acquired_at and all(stamp is not None for stamp in executor.lease_acquired_at)
    # Every journal, lease and receipt stamp, including the phase journaled from
    # inside the handler, is wall time, never the past instant.
    assert all(stamp is not None and stamp >= before for stamp in stamps)
    timestamps = [event.timestamp for event in terminal.events]
    assert timestamps == sorted(timestamps)


def _scan_profile() -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": IVARegime("GENERAL"),
            "has_employees": True,
            "pays_rent_with_retencion": True,
        },
    )


def _madrid_noon(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=MADRID_TZ).astimezone(UTC)


def _workflow_gate_answer(operation: PinnedAuthorityOperation, modelo: str, period: Period) -> Callable[[], bool]:
    """The workflow gate's filing-window answer on the Spanish civil date the seam reads, as the filing route asks it."""
    checker = build_revision_deadline_window_checker(
        profile=_scan_profile(), engine=DeadlineEngine(authority=operation)
    )

    def answer() -> bool:
        return checker.is_window_open(modelo, period, now().astimezone(MADRID_TZ).date())

    return answer


def test_the_workflow_gate_under_the_fixed_clock_answers_as_the_persona_table_does(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    scanned = obligation_with_a_shifted_close(_scan_profile(), operation=operation)
    obligation = scanned.obligation
    answer = _workflow_gate_answer(operation, obligation.modelo, obligation.period)
    instants = {
        "open": _madrid_noon(obligation.opens_on),
        "closed": _madrid_noon(obligation.adjusted_closes_on + timedelta(days=1)),
    }

    for name, instant in instants.items():
        # The persona table freezes the seam around the same work.
        with frozen_clock(instant):
            persona_table = answer()
        executor = _ClockObservingExecutor(answer=answer)

        _settle_under_fixed_clock(tmp_path / name, executor, instant, operation)

        assert executor.answers == [persona_table]
        assert persona_table is (name == "open")
