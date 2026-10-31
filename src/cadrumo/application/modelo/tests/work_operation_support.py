"""Work-unit and phase-guard builders shared by the modelo work read-operation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from pydantic import BaseModel

from ....core.period import Period
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext

FIRST_QUARTER_PERIOD = Period.from_year_and_code(2026, "1T")


def first_quarter_unit(profile_id: UUID) -> WorkUnit:
    instant = datetime(2026, 3, 10, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id),
            modelo="303",
            filing_year=2026,
            period=FIRST_QUARTER_PERIOD,
            revision_id="2026-y-siguientes",
        ),
        bucket_id=str(profile_id),
        modelo="303",
        filing_year=2026,
        period=FIRST_QUARTER_PERIOD,
        revision_id="2026-y-siguientes",
        name="First quarter",
        created_at=instant,
        updated_at=instant,
    )


class GuardPhaseReachedError(Exception):
    pass


class GuardEvents:
    """Stop the executor at its first reported phase, after the guards ran."""

    def __init__(self) -> None:
        self.phases: list[str] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)
        raise GuardPhaseReachedError(phase)


def guarded_executor_context[Payload: BaseModel](
    request: OperationRequest[Payload],
    *,
    definition_id: str | None = None,
    subject_ref: str | None = None,
) -> tuple[OperationExecutorContext, GuardEvents]:
    events = GuardEvents()
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=definition_id if definition_id is not None else request.definition_id,
                    subject_ref=subject_ref if subject_ref is not None else request.subject_ref,
                ),
                events=events,
            ),
        ),
    )
    return context, events
