"""The row mutations of the ledger run alike on every frontend, and each says how it is put back.

The production registry, its real access resolvers and the real executors run
over a stored profile. Archive, stash, restore, exclude, split, attach and
detach resolve to one policy for the command line, the terminal interface and
MCP, and settle with the same result. None of these deletes anything: what the
mutation replaced stays stored, and the result names the registered operations
that return it. What an agent's execution records carries its own session
label; a person's carries the label the request typed.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.ledger.attachment_mutation_operation import (
    LedgerAttachmentOperationResult,
    LedgerAttachRequest,
    LedgerDetachRequest,
)
from ...application.ledger.lifecycle_contracts import LedgerLifecycleMutationRequest, LedgerLifecycleOperationResult
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.split_operation import (
    LedgerSplitChildRequest,
    LedgerSplitOperationResult,
    LedgerSplitRequest,
)
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, SessionKind
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.buckets.event import BucketEvent
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import (
    BusinessClassification,
    SplitRole,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...domain.transactions.models import Transaction
from ..ledger_action_composition import compose_ledger_action_ports
from . import registered_executor_case_support as conformance
from .ledger_attachment_operation_test_support import prepare_ledger_attachment_operation_conformance_case
from .ledger_lifecycle_operation_test_support import prepare_ledger_lifecycle_operation_conformance_case
from .test_operation_catalogue import _registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_MCP = OperationFrontendProjection.MCP
_OPENED = (
    "ledger.archive",
    "ledger.attach",
    "ledger.detach",
    "ledger.exclude",
    "ledger.restore",
    "ledger.split.manual",
    "ledger.stash",
)
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_AGENT_LABEL = f"agent:mcp.attended.{_SESSION_CLIENT}"
_ACTIVE = TransactionLifecycleState.ACTIVE
_STASHED = TransactionLifecycleState.STASHED
_ARCHIVED = TransactionLifecycleState.ARCHIVED
_FRONTENDS = pytest.mark.parametrize("frontend", [_MCP, _CLI, _TUI], ids=["mcp", "cli", "tui"])


def _recorded(frontend: OperationFrontendProjection, typed: str) -> str:
    """The label an execution admitted on ``frontend`` records when its request typed ``typed``."""
    return _AGENT_LABEL if frontend is _MCP else typed


def _session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id in _OPENED
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


def _ordinary_requests(profile_id: UUID) -> tuple[tuple[str, BaseModel], ...]:
    """One request of each opened operation, and both evidence axes of an attachment."""
    row = "a" * 12
    lifecycle = LedgerLifecycleMutationRequest(profile_id=profile_id, transaction_id=row, actor="typed", reason="why")
    return (
        ("ledger.archive", lifecycle),
        ("ledger.stash", lifecycle),
        ("ledger.restore", lifecycle),
        ("ledger.exclude", lifecycle),
        ("ledger.attach", LedgerAttachRequest(profile_id=profile_id, transaction_id=row, attachment_ids=("b" * 64,))),
        (
            "ledger.attach",
            LedgerAttachRequest(profile_id=profile_id, transaction_id=row, purchase_invoice_evidence_id="c" * 64),
        ),
        ("ledger.detach", LedgerDetachRequest(profile_id=profile_id, transaction_id=row, attachment_ids=("b" * 64,))),
        (
            "ledger.split.manual",
            LedgerSplitRequest(
                profile_id=profile_id,
                transaction_id=row,
                children=(
                    LedgerSplitChildRequest(amount="8", description="first part"),
                    LedgerSplitChildRequest(amount="12", description="second part"),
                ),
            ),
        ),
    )


def _context(
    registry: OperationRegistry,
    definition_id: str,
    *,
    frontend: OperationFrontendProjection,
    operation: PinnedAuthorityOperation,
    action: AccessAction = AccessAction.SUBMIT,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )


def test_no_request_of_the_opened_operations_carries_a_path_bytes_or_a_confirmation() -> None:
    """Every member is an identifier, typed text or a typed amount; none stands for a file or the person's consent."""
    registry = _registry()
    expected: dict[str, set[str]] = {
        "ledger.archive": {"profile_id", "transaction_id", "actor", "reason"},
        "ledger.stash": {"profile_id", "transaction_id", "actor", "reason"},
        "ledger.restore": {"profile_id", "transaction_id", "actor", "reason"},
        "ledger.exclude": {"profile_id", "transaction_id", "actor", "reason"},
        "ledger.attach": {"profile_id", "transaction_id", "purchase_invoice_evidence_id", "attachment_ids", "actor"},
        "ledger.detach": {"profile_id", "transaction_id", "attachment_ids", "actor"},
        "ledger.split.manual": {"profile_id", "transaction_id", "children", "reason", "actor"},
    }

    for definition_id in _OPENED:
        properties = registry.describe_public_definition(definition_id).request_json_schema["properties"]
        assert isinstance(properties, dict)
        assert set(properties) == expected[definition_id], definition_id


def test_the_real_resolvers_grant_every_frontend_the_same_policy(
    operation: PinnedAuthorityOperation,
) -> None:
    """Each row mutation resolves to one policy on the three frontends, at every access it is asked for."""
    registry = _registry()
    requests = _ordinary_requests(_PROFILE)

    assert {definition_id for definition_id, _payload in requests} == set(_OPENED)
    for definition_id, payload in requests:
        request = OperationRequest[BaseModel](
            definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
        )
        for action in (AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT):
            policies = set()
            for frontend in OperationFrontendProjection:
                access = resolve_operation_access(
                    registry=registry,
                    request=request,
                    context=_context(registry, definition_id, frontend=frontend, operation=operation, action=action),
                )
                assert access.request.frontend is frontend, (definition_id, frontend, action)
                assert access.request.profile_id == _PROFILE, (definition_id, frontend, action)
                assert access.request.period_independent, (definition_id, frontend, action)
                assert AccessAction.COMMIT in access.policy.actions, (definition_id, frontend, action)
                assert not access.policy.requires_human, (definition_id, frontend, action)
                policies.add(access.policy)
            assert len(policies) == 1, (definition_id, action)


@_FRONTENDS
def test_the_real_resolvers_refuse_a_row_of_another_profile_on_every_frontend(
    operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    """The grant above is a decision: the same resolvers refuse the same requests addressed elsewhere."""
    registry = _registry()

    for definition_id, payload in _ordinary_requests(_OTHER_PROFILE):
        request = OperationRequest[BaseModel](
            definition_id=definition_id, subject_ref=profile_operation_subject(str(_OTHER_PROFILE)), payload=payload
        )
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry,
                request=request,
                context=_context(registry, definition_id, frontend=frontend, operation=operation),
            )
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH, definition_id


def _run[ResultT: BaseModel](
    driver: conformance._ExecutionDriver,
    registry: OperationRegistry,
    *,
    definition_id: str,
    profile_id: UUID,
    payload: BaseModel,
    result_type: type[ResultT],
) -> ResultT:
    """Run one operation through the real supervisor and resolve its settled public result."""
    submitted, observed = asyncio.run(
        driver.run(definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload)
    )
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, definition_id
    assert observed.projection.effect is OperationEffect.UPDATED, definition_id
    return conformance._resolve_result_projection(
        driver,
        registry,
        definition_id=definition_id,
        operation_id=submitted.receipt.operation_id,
        terminal_revision=observed.projection.revision,
        projection_type=result_type,
    )


def _stored_row(profile_id: UUID, transaction_id: str, operation: PinnedAuthorityOperation) -> Transaction:
    ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
    stored = ports.transaction_repository.load().get(transaction_id)
    assert stored is not None
    return stored


def _events(profile_id: UUID, event_ids: tuple[str, ...]) -> tuple[BucketEvent, ...]:
    history = bucket_event_history_repository(bucket_id=str(profile_id)).load().events
    assert event_ids
    return tuple(history[event_id] for event_id in event_ids)


@_FRONTENDS
def test_each_lifecycle_mutation_records_the_session_and_is_put_back_by_the_operations_its_result_names(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """Stash, archive and exclude each keep the row; running what a result names returns the row to where it was."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_session_host(frontend)
    ) as (driver, registry, profile_id):
        case = prepare_ledger_lifecycle_operation_conformance_case("ledger.stash", profile_id, operation=operation)
        seeded = case.transaction_before
        assert seeded.lifecycle_state is _ACTIVE
        assert seeded.business_pct is None
        steps = (
            ("ledger.stash", _ACTIVE, _STASHED, ("ledger.restore",)),
            ("ledger.restore", _STASHED, _ACTIVE, ("ledger.stash",)),
            ("ledger.archive", _ACTIVE, _ARCHIVED, ("ledger.restore",)),
            ("ledger.restore", _ARCHIVED, _ACTIVE, ("ledger.archive",)),
        )

        for index, (definition_id, before, after, reversed_by) in enumerate(steps):
            typed = f"typed for step {index}"
            settled = _run(
                driver,
                registry,
                definition_id=definition_id,
                profile_id=profile_id,
                payload=LedgerLifecycleMutationRequest(
                    profile_id=profile_id,
                    transaction_id=case.transaction_id,
                    actor=typed,
                    reason=f"synthetic lifecycle step {index}",
                ),
                result_type=LedgerLifecycleOperationResult,
            )

            assert settled.result is not None, definition_id
            replaced = settled.result.replaced
            assert replaced.lifecycle_state is before, definition_id
            assert replaced.business_classification is seeded.business_classification, definition_id
            assert replaced.business_pct is None, definition_id
            assert replaced.classified_by == seeded.classified_by, definition_id
            assert replaced.reversed_by == reversed_by, definition_id
            stored = _stored_row(profile_id, case.transaction_id, operation)
            assert stored.lifecycle_state is after, definition_id
            assert stored.lifecycle_lineage[-1].previous_state is before, definition_id
            assert stored.lifecycle_lineage[-1].actor == _recorded(frontend, typed), definition_id
            (event,) = _events(profile_id, settled.result.bucket_event_ids)
            assert event.actor == _recorded(frontend, typed), definition_id

        returned = _stored_row(profile_id, case.transaction_id, operation)
        assert returned.lifecycle_state is seeded.lifecycle_state
        assert returned.business_classification is seeded.business_classification
        assert returned.raw == seeded.raw

        typed = "typed for the exclusion"
        excluded = _run(
            driver,
            registry,
            definition_id="ledger.exclude",
            profile_id=profile_id,
            payload=LedgerLifecycleMutationRequest(
                profile_id=profile_id, transaction_id=case.transaction_id, actor=typed, reason="synthetic exclusion"
            ),
            result_type=LedgerLifecycleOperationResult,
        )

        assert excluded.result is not None
        assert excluded.result.replaced.lifecycle_state is _ACTIVE
        assert excluded.result.replaced.business_classification is seeded.business_classification
        assert excluded.result.replaced.business_pct is None
        assert excluded.result.replaced.reversed_by == ("ledger.classify.single",)
        stored = _stored_row(profile_id, case.transaction_id, operation)
        assert stored.lifecycle_state is _ACTIVE
        assert stored.business_classification is BusinessClassification.REVIEWED_EXCLUDED
        (event,) = _events(profile_id, excluded.result.bucket_event_ids)
        assert event.actor == _recorded(frontend, typed)
        # The event keeps what the exclusion overwrote on the row.
        assert event.payload["previous_classification"] == seeded.business_classification.value
        assert event.payload["previous_business_pct"] == ""


@_FRONTENDS
def test_a_detachment_keeps_the_stored_attachment_and_attaching_it_again_puts_the_link_back(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """Attach and detach move one row's link to evidence already stored, and never the evidence."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_session_host(frontend)
    ) as (driver, registry, profile_id):
        case = prepare_ledger_attachment_operation_conformance_case("ledger.attach", profile_id, operation=operation)
        attachments = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation).attachment_store
        stored_bytes = attachments.read_bytes(case.attachment_id)
        assert stored_bytes
        linked = (case.attachment_id,)
        steps: tuple[tuple[str, BaseModel, str, tuple[str, ...]], ...] = (
            (
                "ledger.attach",
                LedgerAttachRequest(
                    profile_id=profile_id, transaction_id=case.transaction_id, attachment_ids=linked, actor="typed once"
                ),
                "typed once",
                linked,
            ),
            (
                "ledger.detach",
                LedgerDetachRequest(
                    profile_id=profile_id, transaction_id=case.transaction_id, attachment_ids=linked, actor="then typed"
                ),
                "then typed",
                (),
            ),
            (
                "ledger.attach",
                LedgerAttachRequest(
                    profile_id=profile_id, transaction_id=case.transaction_id, attachment_ids=linked, actor="last typed"
                ),
                "last typed",
                linked,
            ),
        )

        for definition_id, payload, typed, carried in steps:
            settled = _run(
                driver,
                registry,
                definition_id=definition_id,
                profile_id=profile_id,
                payload=payload,
                result_type=LedgerAttachmentOperationResult,
            )

            assert settled.outcome == "updated", definition_id
            assert settled.result is not None, definition_id
            assert settled.result.transaction.attachment_ids == carried, definition_id
            assert _stored_row(profile_id, case.transaction_id, operation).attachment_ids == carried, definition_id
            assert {event.actor for event in _events(profile_id, settled.result.bucket_event_ids)} == {
                _recorded(frontend, typed)
            }, definition_id
            # The link moved; the attachment and its bytes did not.
            assert attachments.read_bytes(case.attachment_id) == stored_bytes, definition_id


@_FRONTENDS
def test_a_split_records_the_session_keeps_its_parent_stored_and_is_not_undone_by_a_restore(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """The parent stays stored with what it carried, and the one operation that recombines it is the merge."""
    typed = "typed for the split"
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_session_host(frontend)
    ) as (driver, registry, profile_id):
        ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(profile_id),
                booked_date=date(2025, 1, 21),
                amount=Decimal("20.00"),
                direction=TransactionDirection.OUTGOING,
                description="synthetic row to split",
                business_classification=BusinessClassification.NOT_YET_PROCESSED,
                actor="synthetic-seed",
            ),
            ports=ports,
            occurred_at=now(),
        )
        parent_id = created.ref.transaction_id
        parent_before = _stored_row(profile_id, parent_id, operation)

        split = _run(
            driver,
            registry,
            definition_id="ledger.split.manual",
            profile_id=profile_id,
            payload=LedgerSplitRequest(
                profile_id=profile_id,
                transaction_id=parent_id,
                children=(
                    LedgerSplitChildRequest(amount="8", description="first part"),
                    LedgerSplitChildRequest(amount="12", description="second part"),
                ),
                reason="synthetic split",
                actor=typed,
            ),
            result_type=LedgerSplitOperationResult,
        )

        assert split.parent_transaction_id == parent_id
        assert split.parent_business_classification is parent_before.business_classification
        assert split.child_business_classification is BusinessClassification.NOT_YET_PROCESSED
        assert split.remerged_by == ("ledger.merge",)
        parent = _stored_row(profile_id, parent_id, operation)
        assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
        assert parent.raw == parent_before.raw
        assert parent.business_classification is parent_before.business_classification
        assert parent.lifecycle_lineage[-1].actor == _recorded(frontend, typed)
        (event,) = _events(profile_id, (split.bucket_event_id,))
        assert event.actor == _recorded(frontend, typed)
        for child_id in split.child_transaction_ids:
            child = _stored_row(profile_id, child_id, operation)
            assert child.lifecycle_state is _ACTIVE
            assert child.created_by == _recorded(frontend, typed)
            assert child.split_lineage is not None
            assert child.split_lineage.role is SplitRole.CHILD

        _submitted, refused = asyncio.run(
            driver.run(
                definition_id="ledger.restore",
                subject_ref=profile_operation_subject(str(profile_id)),
                payload=LedgerLifecycleMutationRequest(
                    profile_id=profile_id, transaction_id=parent_id, actor=typed, reason="synthetic restore of a parent"
                ),
            )
        )

        assert refused.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert refused.projection.effect is OperationEffect.NONE
        assert _stored_row(profile_id, parent_id, operation).lifecycle_state is TransactionLifecycleState.SPLIT
