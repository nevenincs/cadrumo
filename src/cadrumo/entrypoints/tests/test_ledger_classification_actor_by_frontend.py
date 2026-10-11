"""An agent's classification, rule and ratio writes record its session's label.

The production registry and the real executors run over a stored profile with
a session host that answers for the frontend that admitted the invocation.
Each operation below records who acted, and for an execution admitted on the
MCP frontend that label is the session's, whatever the request carries. The
ratio verbs carry no label of their own, so the person's frontends record the
operator label there.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.ledger.bulk_classify_operation import LedgerBulkClassifyProjection
from ...application.ledger.ratios_contracts import LedgerRatiosSetProjection, LedgerRatiosUnsetProjection
from ...application.ledger.rule_contracts import LedgerRuleAddProjection, LedgerRuleApplyProjection
from ...application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ...application.operations.models import OperationIdentity
from ...application.operations.registry import OperationFrontendProjection
from ...application.user_profile.access_contracts import SessionKind
from ...core.operations import OperationTerminalCondition
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_CLI = OperationFrontendProjection.CLI
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_TYPED_ACTOR = "typed by the caller"
_AGENT_LABEL = f"agent:mcp.attended.{_SESSION_CLIENT}"
_PERSON_LABEL = "operator"
_FRONTENDS = pytest.mark.parametrize("frontend", [_MCP, _CLI], ids=["mcp", "cli"])


def _session_host(definition_id: str, frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation of ``definition_id`` it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == definition_id
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


def _run[ProjectionT: BaseModel](
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    *,
    definition_id: str,
    frontend: OperationFrontendProjection,
    projection_type: type[ProjectionT],
    adjust: Callable[[BaseModel], BaseModel] = lambda request: request,
) -> tuple[ProjectionT, tuple[BucketEvent, ...]]:
    """Run the seeded scenario of one operation as ``frontend`` and read what it left behind."""
    with (
        conformance._model_runtime_for(definition_id),
        conformance._runtime(
            tmp_path / "runtime",
            cleanup=conformance._CloseWitness(),
            execution_caller_reader=_session_host(definition_id, frontend),
        ) as (driver, registry, profile_id),
    ):
        definition = {item.definition_id: item for item in registry.definitions}[definition_id]
        submission = conformance._seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        submitted, observed = asyncio.run(
            driver.run(
                definition_id=definition_id,
                subject_ref=submission.subject_ref,
                payload=adjust(submission.payload),
            )
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        projection = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=projection_type,
        )
        events = tuple(bucket_event_history_repository(bucket_id=str(profile_id)).load().events.values())
        return projection, events


def _actors(events: tuple[BucketEvent, ...], event_type: BucketEventType) -> set[str]:
    return {event.actor for event in events if event.event_type is event_type}


def _typed(request: BaseModel) -> BaseModel:
    return request.model_copy(update={"actor": _TYPED_ACTOR})


@_FRONTENDS
def test_bulk_classification_records_the_session_label_for_an_agent(
    tmp_path: Path, operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    """Every classification event of the batch names the derived label, not the typed one."""
    projection, events = _run(
        tmp_path,
        operation,
        definition_id="ledger.classify.bulk",
        frontend=frontend,
        projection_type=LedgerBulkClassifyProjection,
        adjust=_typed,
    )

    assert projection.result is not None
    assert projection.result.bucket_event_ids
    by_id = {event.event_id: event for event in events}
    recorded = _AGENT_LABEL if frontend is _MCP else _TYPED_ACTOR
    assert {by_id[event_id].actor for event_id in projection.result.bucket_event_ids} == {recorded}


@_FRONTENDS
def test_rule_add_records_the_session_label_for_an_agent(
    tmp_path: Path, operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    """The stored rule names the derived label as its author, not the typed one."""
    projection, _events = _run(
        tmp_path,
        operation,
        definition_id="ledger.rule.add",
        frontend=frontend,
        projection_type=LedgerRuleAddProjection,
        adjust=_typed,
    )

    assert projection.rule is not None
    assert projection.rule.actor == (_AGENT_LABEL if frontend is _MCP else _TYPED_ACTOR)


@_FRONTENDS
def test_rule_apply_records_the_session_label_for_an_agent(
    tmp_path: Path, operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    """Each classification the run writes is attributed to the derived label, not the typed one."""
    projection, events = _run(
        tmp_path,
        operation,
        definition_id="ledger.rule.apply",
        frontend=frontend,
        projection_type=LedgerRuleApplyProjection,
        adjust=_typed,
    )

    assert projection.outcome == "applied"
    assert projection.bucket_event_count
    recorded = _AGENT_LABEL if frontend is _MCP else _TYPED_ACTOR
    assert _actors(events, BucketEventType.LEDGER_TRANSACTION_CLASSIFIED) == {recorded}


@_FRONTENDS
def test_ratio_set_records_the_session_label_for_an_agent(
    tmp_path: Path, operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    """The override's audit event names an agent's session, and the operator label stays the person's."""
    projection, events = _run(
        tmp_path,
        operation,
        definition_id="ledger.ratios.set",
        frontend=frontend,
        projection_type=LedgerRatiosSetProjection,
    )

    assert projection.ratio
    assert _actors(events, BucketEventType.LEDGER_RATIOS_SET) == {_AGENT_LABEL if frontend is _MCP else _PERSON_LABEL}


@_FRONTENDS
def test_ratio_unset_records_the_session_label_for_an_agent(
    tmp_path: Path, operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    """The clearance's audit event names an agent's session, and the operator label stays the person's."""
    projection, events = _run(
        tmp_path,
        operation,
        definition_id="ledger.ratios.unset",
        frontend=frontend,
        projection_type=LedgerRatiosUnsetProjection,
    )

    assert projection.outcome == "cleared"
    assert _actors(events, BucketEventType.LEDGER_RATIOS_UNSET) == {_AGENT_LABEL if frontend is _MCP else _PERSON_LABEL}
