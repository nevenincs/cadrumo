"""The composed journal hook refreshes the session's form only after an export that wrote has settled."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event

import pytest

from ...application.modelo.operation_shared import MODELO_EXPORT_OPERATION_DEFINITION_ID
from ...application.modelo.workbench_operations import MODELO_WORK_FORM_OPERATION_DEFINITION_ID
from ...application.operations.capabilities import OperationRequestStoragePolicy
from ...application.operations.models import OperationIdentity, OperationTerminalReceipt
from ...application.operations.persistence.events import OperationTerminalEvent
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.workbench_capture_memory import WorkbenchCaptureMemoryOwner
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ..operation_composition import _refreshing_form_after_export

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_STARTED = datetime.now(UTC)


def _snapshot(definition_id: str, lifecycle: OperationLifecycle, effect: OperationEffect) -> OperationPersistedSnapshot:
    terminal = lifecycle is OperationLifecycle.TERMINAL
    identity = OperationIdentity(operation_id="a" * 64, definition_id=definition_id, subject_ref="b" * 64)
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=_STARTED,
        result_ref="result:settled",
    )
    event = OperationTerminalEvent(
        identity=identity, revision=1, sequence=1, timestamp=_STARTED, code="operation.terminal", receipt=receipt
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest="c" * 64,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=1,
        lifecycle=lifecycle,
        terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
        effect=effect,
        started_at=_STARTED,
        updated_at=_STARTED,
        execution_deadline=_STARTED + timedelta(hours=1),
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1 if terminal else 0,
        events=(event,) if terminal else (),
        terminal_receipt=receipt if terminal else None,
    )


def _refreshes(snapshot: OperationPersistedSnapshot, *, awaited: bool) -> tuple[bool, list[OperationPersistedSnapshot]]:
    """Commit ``snapshot`` through the hook; answer whether the held form was refreshed and what the host was told."""
    owner = WorkbenchCaptureMemoryOwner()
    refreshed = Event()
    told: list[OperationPersistedSnapshot] = []
    owner.for_profile("profile").keep_form_refresh(refreshed.set)
    committed = _refreshing_form_after_export(told.append, owner)
    committed(snapshot)
    # A refresh runs on its own thread, started before the hook returns; without one nothing can set the event.
    ran = refreshed.wait(timeout=10) if awaited else refreshed.is_set()
    owner.close()
    return ran, told


def test_an_export_that_settled_having_written_refreshes_the_form() -> None:
    snapshot = _snapshot(MODELO_EXPORT_OPERATION_DEFINITION_ID, OperationLifecycle.TERMINAL, OperationEffect.UPDATED)
    ran, told = _refreshes(snapshot, awaited=True)

    assert told == [snapshot], "the host must still be told of every commit"
    assert ran


@pytest.mark.parametrize(
    ("definition_id", "lifecycle", "effect"),
    [
        (MODELO_EXPORT_OPERATION_DEFINITION_ID, OperationLifecycle.RUNNING, OperationEffect.NONE),
        (MODELO_EXPORT_OPERATION_DEFINITION_ID, OperationLifecycle.TERMINAL, OperationEffect.NONE),
        (MODELO_WORK_FORM_OPERATION_DEFINITION_ID, OperationLifecycle.TERMINAL, OperationEffect.UPDATED),
    ],
)
def test_no_other_commit_refreshes_the_form(
    definition_id: str, lifecycle: OperationLifecycle, effect: OperationEffect
) -> None:
    snapshot = _snapshot(definition_id, lifecycle, effect)
    ran, told = _refreshes(snapshot, awaited=False)

    assert told == [snapshot]
    assert not ran
