"""Each ledger write that records who acted records the session for an agent, on every frontend alike otherwise.

The production registry and the real executors run over a stored profile with
a session host that answers for the frontend that admitted the invocation.
Each operation below runs its seeded scenario on the command line, the
terminal interface and MCP. It settles the same on all three, and every event
it stores names the party who acted: the session's label for an execution
admitted on MCP, whatever the request typed, and for a person's frontend the
label the request typed or, where the request carries none, the operation's
own label for a person.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest

from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ...application.operations.models import OperationIdentity
from ...application.operations.registry import OperationFrontendProjection
from ...application.user_profile.access_contracts import SessionKind
from ...core.operations import OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_TYPED_ACTOR = "typed by the caller"
_AGENT_LABEL = f"agent:mcp.attended.{_SESSION_CLIENT}"
_FRONTENDS = pytest.mark.parametrize("frontend", sorted(OperationFrontendProjection))

_TYPED = "the label the request typed"
_WRITES: tuple[tuple[str, str], ...] = (
    ("ledger.add", _TYPED),
    ("ledger.update", _TYPED),
    ("ledger.classify.single", _TYPED),
    ("ledger.allocate", _TYPED),
    ("ledger.merge", _TYPED),
    ("ledger.remove", _TYPED),
    ("ledger.reset", _TYPED),
    ("ledger.export", _TYPED),
    ("ledger.evidence.add", "cli"),
    ("ledger.evidence.remove", "cli"),
)
"""Each write with what a person's frontend records for it."""


def _session_host(definition_id: str, frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation of ``definition_id`` it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == definition_id
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


@pytest.mark.parametrize(("definition_id", "a_person_records"), _WRITES, ids=[name for name, _ in _WRITES])
@_FRONTENDS
def test_a_ledger_write_records_the_session_label_for_an_agent_and_the_persons_label_otherwise(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    definition_id: str,
    a_person_records: str,
    frontend: OperationFrontendProjection,
) -> None:
    with (
        conformance._model_runtime_for(definition_id),
        conformance._runtime(
            tmp_path / definition_id,
            cleanup=conformance._CloseWitness(),
            execution_caller_reader=_session_host(definition_id, frontend),
        ) as (driver, registry, profile_id),
    ):
        definition = {item.definition_id: item for item in registry.definitions}[definition_id]
        submission = conformance._seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        payload = submission.payload
        carries_a_typed_label = "actor" in type(payload).model_fields
        assert carries_a_typed_label is (a_person_records == _TYPED)
        if carries_a_typed_label:
            payload = payload.model_copy(update={"actor": _TYPED_ACTOR})
        if "dry_run" in type(payload).model_fields:
            # A preview stores nothing, and what is under test is what the write stores.
            payload = payload.model_copy(update={"dry_run": False})
        history = bucket_event_history_repository(bucket_id=str(profile_id))
        before = set(history.load().events) if history.exists() else set()

        _submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=submission.subject_ref, payload=payload)
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        stored = [event for event_id, event in history.load().events.items() if event_id not in before]
        assert stored
        if frontend is _MCP:
            recorded = _AGENT_LABEL
        elif a_person_records == _TYPED:
            recorded = _TYPED_ACTOR
        else:
            recorded = a_person_records
        assert {event.actor for event in stored} == {recorded}
