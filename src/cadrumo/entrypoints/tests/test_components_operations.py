"""Real supervisor and encrypted journal over a controlled external role wire.

The wire fixture replaces the native role's downloads, not the application,
supervisor, protocol parser, review or custody. Native engine tests separately
prove actual archive installation and drift; this file downloads nothing.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from typing import override
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ...adapters.outbound.components import client as components_client
from ...adapters.outbound.components.client import (
    ComponentsCancellation,
    ComponentsEventSink,
    ComponentsLaunch,
    ComponentsRequest,
    launch_components_role,
    run_components_role,
)
from ...adapters.outbound.components.protocol import ComponentsCommand, ComponentsNoticeCode, ComponentsResultLine
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_SETUP_DEFINITION_ID,
    COMPONENTS_STATUS_DEFINITION_ID,
    COMPONENTS_VERIFY_DEFINITION_ID,
    ProvisionMutationRequest,
    ProvisionReadRequest,
    ProvisionResult,
    ProvisionReviewedOperand,
    resolve_components_access,
)
from ...application.dependency_contracts import DependencyItemKind
from ...application.operations.access_resolution import OperationAccessContext
from ...application.operations.error_detail import OperationErrorDetailV1
from ...application.operations.interactions import (
    OperationApplyResponse,
    OperationPendingInteraction,
    OperationRejectResponse,
    OperationReviewClaimAttribution,
)
from ...application.operations.models import OperationRequest
from ...application.operations.persistence.events import OperationNoticeEvent, OperationProgressEvent
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.operations.persistence.leases import OperationOwnerLease
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures
from ...core.errors.error_codes import resolve_error_message
from ...core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n.render import lookup_translation
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.components_role_replay import ReplayLaunch, transcript_lines
from .. import components_operation_composition as composition

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_BEARER = "b" * 64


class _HandleClosingLaunch(ReplayLaunch):
    """Match native handle ownership: end releases the handle used by wait."""

    @override
    def wait(self, timeout: float) -> int | None:
        if self.ended:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        return super().wait(timeout)

    @override
    def end(self) -> None:
        super().end()
        self.standard_input.close()


class _WireRole:
    """Speak the role wire on real pipes, recording requests independently."""

    def __init__(
        self,
        outcome: str = "completed",
        *,
        lose_apply_result: bool = False,
        fail_cleanup: bool = False,
    ) -> None:
        self.outcome = outcome
        self.lose_apply_result = lose_apply_result
        self.result_lost = Event()
        self.unresponsive_started = Event()
        self.cleanup_allowed = Event()
        self.cleanup_attempts = 0
        self.fail_cleanup = fail_cleanup
        self.arguments: list[tuple[str, ...]] = []
        self.timeouts: list[float | None] = []
        self.launches: list[ReplayLaunch] = []
        records = [json.loads(line) for line in transcript_lines("setup_browser_completed")]
        self.plan = next(record for record in records if record["type"] == "review")
        self.completed = records

    def __call__(
        self, image: Path, arguments: Sequence[str], environment: Mapping[str, str], root: Path
    ) -> ComponentsLaunch:
        del image, environment, root
        self.arguments.append(tuple(arguments))
        command = arguments[2]
        if command == "plan":
            records = [
                {"type": "started", "protocol": 1, "command": "plan"},
                {
                    "type": "result",
                    "command": "plan",
                    "outcome": "ok",
                    "plan": self.plan["plan"],
                    "plan_digest": self.plan["plan_digest"],
                },
            ]
            status = 0
        elif command == "setup":
            if self.outcome in {"silent", "foreign_silent"}:
                started = self.unresponsive_started
                foreign = self.outcome == "foreign_silent"
                role = self

                class UnresponsiveLaunch(_HandleClosingLaunch):
                    @override
                    def end(self) -> None:
                        role.cleanup_attempts += 1
                        if role.fail_cleanup and not role.cleanup_allowed.is_set():
                            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
                        super().end()

                    @override
                    def _write(self) -> None:
                        try:
                            self._writer.write(b'{"type":"started","protocol":1,"command":"setup"}\n')
                            if foreign:
                                self._writer.write(
                                    json.dumps(
                                        {
                                            "type": "notice",
                                            "notice_code": "following",
                                            "subject_code": "browser",
                                            "plan_digest": "d" * 64,
                                        }
                                    ).encode()
                                    + b"\n"
                                )
                            started.set()
                            self._release.wait()
                        finally:
                            self._writer.close()
                            self._done.set()

                launch = UnresponsiveLaunch((), 1)
                self.launches.append(launch)
                return launch
            records = [record for record in self.completed if record["type"] != "review"]
            if self.outcome == "plan_changed":
                records = [
                    records[0],
                    {
                        "type": "result",
                        "command": "setup",
                        "outcome": "plan_changed",
                        "plan": self.plan["plan"],
                        "plan_digest": "d" * 64,
                    },
                ]
            elif self.outcome == "lost":
                records = records[:1]
            elif self.outcome == "foreign_follow":
                records.insert(
                    1,
                    {
                        "type": "notice",
                        "notice_code": "following",
                        "subject_code": "browser",
                        "plan_digest": "d" * 64,
                    },
                )
            elif self.outcome == "refused":
                records = [
                    records[0],
                    {
                        "type": "result",
                        "command": "setup",
                        "outcome": "refused",
                        "item_id": "browser",
                        "items": ["browser"],
                        "failure_category": "offline",
                        "rows": [{"item_id": "browser", "mode": "quick", "state": "absent"}],
                    },
                ]
            status = 0 if self.outcome in {"completed", "foreign_follow"} else 1
        else:
            records = [json.loads(line) for line in transcript_lines("status_quick")]
            if "--full" in arguments:
                for record in records:
                    if "mode" in record:
                        record["mode"] = "full"
                    for row in record.get("rows", []):
                        row["mode"] = "full"
            status = 0
        launch = _HandleClosingLaunch(tuple(json.dumps(record).encode() + b"\n" for record in records), status)
        self.launches.append(launch)
        return launch


def _bind_wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, role: _WireRole) -> None:
    image = tmp_path / "external-role.exe"
    image.write_bytes(b"fixture")

    def run(
        request: ComponentsRequest,
        *,
        on_event: ComponentsEventSink | None = None,
        cancellation: ComponentsCancellation | None = None,
        timeout: float | None = None,
    ) -> ComponentsResultLine:
        role.timeouts.append(timeout)
        result = run_components_role(
            request, on_event=on_event, cancellation=cancellation, timeout=timeout, image=image, launcher=role
        )
        if request.command is ComponentsCommand.SETUP and role.lose_apply_result:
            role.result_lost.set()
            raise asyncio.CancelledError("external role result lost with its owner")
        return result

    monkeypatch.setattr(composition, "run_components_role", run)


def _owner(
    root: Path,
    objects: SecureObjectRepository,
    authority: PinnedAuthorityOperation,
    *,
    clock: Callable[[], datetime] = now,
    owner_id: str = "1" * 64,
    token: str = "2" * 64,
    journal: OperationJournalRepository | None = None,
) -> OperationSupervisor:
    group = composition.build_components_operations()
    registry = OperationRegistry(definitions=group.definitions, public_registrations=group.registrations)
    journal = OperationJournalRepository(storage_root=root) if journal is None else journal
    return OperationSupervisor(
        registry=registry,
        authority_operation=authority,
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(objects=objects),
        owner_id=owner_id,
        lease_token_factory=lambda: token,
        clock=clock,
        lease_duration=timedelta(minutes=1),
        execution_timeout=timedelta(minutes=2),
        cleanup_timeout=timedelta(minutes=1),
        response_token_factory=lambda: _BEARER,
    )


async def _claim_review(
    owner: OperationSupervisor, pending: OperationPendingInteraction
) -> OperationPendingInteraction:
    """Supply trusted attribution at the supervisor seam, not native admission."""
    session_id = uuid4()
    claim = OperationReviewClaimAttribution(
        actor_ref=f"session:{session_id}",
        connection_id=uuid4(),
        session_id=session_id,
        profile_id=uuid4(),
        runtime_boot_id=uuid4(),
        authority_generation="a" * 64,
        frontend="cli",
        source_ref="login:verified",
        claimed_at=now(),
        displayed_revision=pending.request.revision,
        reviewed_document_digest="d" * 64,
    )
    return await owner.claim_review(pending, claim)


@pytest.mark.parametrize(
    ("intent", "outcome", "effect", "condition"),
    [
        ("apply", "completed", OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED),
        ("reject", "completed", OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED),
        ("apply", "plan_changed", OperationEffect.NONE, OperationTerminalCondition.REFUSED),
        ("apply", "lost", OperationEffect.UNKNOWN, OperationTerminalCondition.REFUSED),
        ("apply", "foreign_follow", OperationEffect.UNKNOWN, OperationTerminalCondition.REFUSED),
        ("apply", "foreign_silent", OperationEffect.UNKNOWN, OperationTerminalCondition.REFUSED),
        ("apply", "silent", OperationEffect.UNKNOWN, OperationTerminalCondition.REFUSED),
        ("apply", "refused", OperationEffect.NONE, OperationTerminalCondition.REFUSED),
    ],
)
def test_setup_reviews_the_role_digest_once_and_accounts_for_the_actual_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    intent: str,
    outcome: str,
    effect: OperationEffect,
    condition: OperationTerminalCondition,
) -> None:
    role = _WireRole(outcome)
    _bind_wire(monkeypatch, tmp_path, role)
    if outcome in {"silent", "foreign_silent"}:
        monkeypatch.setattr(components_client, "_CANCEL_GRACE_S", 0.0)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        owner = _owner(tmp_path / "operations", profile.repository, authority_operation)
        operands = operation_secure_reference_repository(objects=profile.repository)

        async def scenario() -> None:
            operation = await owner.submit(
                OperationRequest(
                    definition_id=COMPONENTS_SETUP_DEFINITION_ID,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload=ProvisionMutationRequest(),
                )
            )
            waiting = await run_to_settlement(owner, operation)
            assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert waiting.effect is OperationEffect.NONE
            pending = waiting.pending_interaction
            assert pending is not None
            reviewed = await operands.resolve(pending.reviewed_proposal_digest, ProvisionReviewedOperand)
            assert reviewed.plan_digest == role.plan["plan_digest"]
            assert pending.proposed_effect_digest == reviewed.plan_digest
            pending = await _claim_review(owner, pending)
            assert pending.review_claim is not None
            common = dict(
                interaction_id=pending.request.interaction_id,
                operation_id=operation,
                revision=pending.request.revision,
                continuation_digest=pending.request.continuation_digest,
                reviewed_proposal_digest=pending.reviewed_proposal_digest,
                actor_ref=pending.review_claim.actor_ref,
                responded_at=now(),
            )
            # Visible checkpoint coordinates do not confer response authority.
            forged = OperationRejectResponse.model_validate({**common, "response_token": "c" * 64})
            with pytest.raises(ValueError):
                await owner.respond(forged)
            if intent == "apply":
                response = OperationApplyResponse.model_validate(
                    {
                        **common,
                        "response_token": _BEARER,
                        "baseline_digest": reviewed.plan_digest,
                        "proposed_effect_digest": reviewed.plan_digest,
                    }
                )
            else:
                response = OperationRejectResponse.model_validate({**common, "response_token": _BEARER})
            await owner.respond(response)
            if outcome == "silent":
                assert await asyncio.to_thread(role.unresponsive_started.wait, 120)
                await owner.request_cancel(operation)
            terminal = await owner.await_terminal(operation)
            assert terminal.effect is effect
            assert terminal.terminal_receipt is not None
            assert terminal.terminal_receipt.condition is condition
            if outcome in {"foreign_follow", "foreign_silent"}:
                reference = terminal.terminal_receipt.error_detail_ref
                assert reference is not None
                detail = await operands.resolve(reference, OperationErrorDetailV1)
                assert detail.context_mapping()["outcome"] == "followed_plan_mismatch"
                assert detail.context_mapping()["new_setup_required"] == "true"
                assert detail.message_key == "cli.config.provision.outcome.followed_plan_mismatch"
                recorded = detail.recorded_error()
                assert recorded is not None
                assert resolve_error_message(recorded, locale="en") == (
                    "Another setup is using a different approved plan. The outcome is uncertain. "
                    "Start a new setup and review its plan."
                )
            if outcome == "refused":
                reference = terminal.terminal_receipt.error_detail_ref
                assert reference is not None
                detail = await operands.resolve(reference, OperationErrorDetailV1)
                facts = detail.context_mapping()
                assert facts["failure_category"] == "offline"
                assert facts["item_id"] == "browser"
                assert "browser" in facts["items"]
                assert "browser" in facts["rows"] and "absent" in facts["rows"]
            assert len(terminal.consumed_interactions) == 1
            assert [arguments[2] for arguments in role.arguments] == (
                ["plan", "setup"] if intent == "apply" else ["plan"]
            )
            if intent == "apply":
                assert role.arguments[1][-2:] == ("--approve", reviewed.plan_digest)
            else:
                assert terminal.terminal_receipt.result_ref is not None
                assert (
                    await operands.resolve(terminal.terminal_receipt.result_ref, ProvisionResult)
                ).outcome.value == "rejected"
            assert all(launch.ended and launch.input_closed for launch in role.launches)
            await owner.shutdown()

        asyncio.run(scenario())


def test_setup_consumed_without_verified_claim_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    role = _WireRole()
    _bind_wire(monkeypatch, tmp_path, role)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        owner = _owner(tmp_path / "operations", profile.repository, authority_operation)

        async def scenario() -> None:
            operation = await owner.submit(
                OperationRequest(
                    definition_id=COMPONENTS_SETUP_DEFINITION_ID,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload=ProvisionMutationRequest(),
                )
            )
            waiting = await run_to_settlement(owner, operation)
            pending = waiting.pending_interaction
            assert pending is not None
            assert pending.baseline_digest is not None and pending.proposed_effect_digest is not None
            await owner.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation,
                    revision=pending.request.revision,
                    response_token=_BEARER,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:unverified",
                    responded_at=now(),
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            terminal = await owner.await_terminal(operation)
            assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
            assert terminal.effect is OperationEffect.NONE
            assert [arguments[2] for arguments in role.arguments] == ["plan"]
            await owner.shutdown()

        asyncio.run(scenario())


@pytest.mark.parametrize("intent", ["apply", "reject"])
def test_claimed_setup_review_consumes_exact_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    intent: str,
) -> None:
    # Runtime admission is tested at the host boundary; this fixture supplies
    # an already verified attribution to exercise the real supervisor seam.
    role = _WireRole()
    _bind_wire(monkeypatch, tmp_path, role)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        owner = _owner(tmp_path / "operations", profile.repository, authority_operation)
        operands = operation_secure_reference_repository(objects=profile.repository)

        async def scenario() -> None:
            operation = await owner.submit(
                OperationRequest(
                    definition_id=COMPONENTS_SETUP_DEFINITION_ID,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload=ProvisionMutationRequest(),
                )
            )
            waiting = await run_to_settlement(owner, operation)
            pending = waiting.pending_interaction
            assert pending is not None
            reviewed = await operands.resolve(pending.reviewed_proposal_digest, ProvisionReviewedOperand)
            session_id = uuid4()
            claim = OperationReviewClaimAttribution(
                actor_ref=f"session:{session_id}",
                connection_id=uuid4(),
                session_id=session_id,
                profile_id=uuid4(),
                runtime_boot_id=uuid4(),
                authority_generation="a" * 64,
                frontend="tui",
                source_ref="login:verified",
                claimed_at=now(),
                displayed_revision=pending.request.revision,
                reviewed_document_digest="d" * 64,
            )
            successor = await owner.claim_review(pending, claim)
            assert successor.request.revision == pending.request.revision + 1
            assert successor.reviewed_proposal_digest == pending.reviewed_proposal_digest
            assert successor.request.continuation_digest == pending.request.continuation_digest
            common = dict(
                interaction_id=successor.request.interaction_id,
                operation_id=operation,
                revision=successor.request.revision,
                response_token=_BEARER,
                continuation_digest=successor.request.continuation_digest,
                reviewed_proposal_digest=successor.reviewed_proposal_digest,
                actor_ref=claim.actor_ref,
                responded_at=now(),
            )
            foreign = OperationRejectResponse.model_validate({**common, "actor_ref": "operator:foreign"})
            with pytest.raises(ValueError, match="claimant"):
                successor.consume(foreign)
            if intent == "apply":
                response = OperationApplyResponse.model_validate(
                    {
                        **common,
                        "baseline_digest": reviewed.plan_digest,
                        "proposed_effect_digest": reviewed.plan_digest,
                    }
                )
            else:
                response = OperationRejectResponse.model_validate(common)
            await owner.respond(response)
            terminal = await owner.await_terminal(operation)
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is (OperationEffect.UPDATED if intent == "apply" else OperationEffect.NONE)
            assert len(terminal.consumed_interactions) == 1
            assert terminal.consumed_interactions[0].checkpoint.review_claim == claim
            assert [arguments[2] for arguments in role.arguments] == (
                ["plan", "setup"] if intent == "apply" else ["plan"]
            )
            if intent == "apply":
                assert role.arguments[1][-2:] == ("--approve", reviewed.plan_digest)
            await owner.shutdown()

        asyncio.run(scenario())


@pytest.mark.parametrize(
    ("definition_id", "full"),
    [(COMPONENTS_STATUS_DEFINITION_ID, False), (COMPONENTS_VERIFY_DEFINITION_ID, True)],
)
def test_read_admission_ids_preserve_status_argv_and_check_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    definition_id: str,
    full: bool,
) -> None:
    role = _WireRole()
    _bind_wire(monkeypatch, tmp_path, role)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        owner = _owner(tmp_path / "operations", profile.repository, authority_operation)

        async def scenario() -> None:
            operation = await owner.submit(
                OperationRequest(
                    definition_id=definition_id,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload=ProvisionReadRequest(items=(DependencyItemKind.LOCAL_AI,)),
                )
            )
            terminal = await run_to_settlement(owner, operation)
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert role.arguments == [
                ("--role", "components", "status", "--item", "local_ai", *(("--full",) if full else ()))
            ]
            assert terminal.terminal_receipt is not None and terminal.terminal_receipt.result_ref is not None
            result = await operation_secure_reference_repository(objects=profile.repository).resolve(
                terminal.terminal_receipt.result_ref,
                ProvisionResult,
            )
            assert {row.mode.value for row in result.rows} == {"full" if full else "quick"}
            assert terminal.effect is OperationEffect.NONE
            assert role.timeouts == [None if full else 30.0]
            await owner.shutdown()

        asyncio.run(scenario())


@pytest.mark.parametrize(
    "action", [AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESPOND]
)
def test_mcp_may_start_and_observe_setup_but_never_answer_its_review(action: AccessAction) -> None:
    group = composition.build_components_operations()
    registry = OperationRegistry(definitions=group.definitions, public_registrations=group.registrations)
    context = OperationAccessContext(
        profile_id=uuid4(),
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
        contract=registry.lookup_public_contract(COMPONENTS_SETUP_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )
    request = OperationRequest[BaseModel](
        definition_id=COMPONENTS_SETUP_DEFINITION_ID,
        subject_ref=COMPONENTS_OPERATION_SUBJECT,
        payload=ProvisionMutationRequest(),
    )
    if action is AccessAction.RESPOND:
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_components_access(request, context)
        assert refused.value.reason is AccessDenialCode.PERSON_ACT_REQUIRED
    else:
        assert resolve_components_access(request, context).policy.requires_human is False


def test_python_mutations_cannot_name_local_ai() -> None:
    with pytest.raises(ValidationError):
        ProvisionMutationRequest.model_validate({"items": (DependencyItemKind.LOCAL_AI,)})


def test_cancellation_is_idempotent_and_does_not_wait_for_a_blocked_input_sender() -> None:
    cancellation = ComponentsCancellation()
    sending, release, completed = Event(), Event(), Event()
    deliveries: list[bool] = []

    def blocked_sender() -> None:
        deliveries.append(True)
        sending.set()
        try:
            assert release.wait(120)
        finally:
            completed.set()

    cancellation.attach_sender(blocked_sender)
    try:
        cancellation.cancel()
        assert sending.wait(120)
        deadline = cancellation.deadline
        for _ in range(100):
            cancellation.cancel()
        assert cancellation.deadline == deadline
        assert deliveries == [True]
    finally:
        release.set()
        assert completed.wait(120)


def test_foreign_follow_cleanup_failure_retains_launch_and_prevents_terminal_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    role = _WireRole("foreign_silent", fail_cleanup=True)
    _bind_wire(monkeypatch, tmp_path, role)
    monkeypatch.setattr(components_client, "_CANCEL_GRACE_S", 0.0)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        owner = _owner(tmp_path / "operations", profile.repository, authority_operation)

        async def scenario() -> None:
            operation = await owner.submit(
                OperationRequest(
                    definition_id=COMPONENTS_SETUP_DEFINITION_ID,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload=ProvisionMutationRequest(),
                )
            )
            waiting = await run_to_settlement(owner, operation)
            pending = waiting.pending_interaction
            assert pending is not None
            pending = await _claim_review(owner, pending)
            assert pending.review_claim is not None
            assert pending.baseline_digest is not None and pending.proposed_effect_digest is not None
            await owner.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation,
                    revision=pending.request.revision,
                    response_token=_BEARER,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref=pending.review_claim.actor_ref,
                    responded_at=now(),
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            try:
                with pytest.raises(AsyncResourceCleanupError) as failed:
                    await owner._continuation_tasks[operation]
                assert role.cleanup_attempts >= 2
                snapshot = await owner.inspect(operation)
                assert snapshot.effect is OperationEffect.UNKNOWN
                assert snapshot.terminal_receipt is None
                assert snapshot.lifecycle is not OperationLifecycle.TERMINAL
                assert not role.launches[-1].ended
                retained = {
                    id(resource) for error in async_cleanup_failures(failed.value) for resource in error.resources
                }
                assert retained
                assert retained.intersection(id(resource) for resource in owner._resources[operation])
                # Release is supported by the canonical cleanup error. This
                # does not erase the supervisor's cached failed cleanup task.
                role.cleanup_allowed.set()
                await failed.value.retry_cleanup()
                assert role.launches[-1].ended
                with pytest.raises(AsyncResourceCleanupError):
                    await owner._cleanup_tasks[operation]
                assert (await owner.inspect(operation)).terminal_receipt is None
            finally:
                role.cleanup_allowed.set()
                for resource in owner._resources.get(operation, ()):
                    await resource.close()
                await owner.shutdown()

        asyncio.run(scenario())


@pytest.mark.parametrize("cooperative", [True, False])
def test_real_contained_process_cancellation_reaps_before_releasing_wait_handles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cooperative: bool,
) -> None:
    cancellation = ComponentsCancellation()
    script = (
        "import json,sys,threading\n"
        "print(json.dumps({'type':'started','protocol':1,'command':'verify'}),flush=True)\n"
        "print(json.dumps({'type':'phase','phase_code':'dependencies.setup.browser.verify',"
        "'item_id':'browser','step':'verify'}),flush=True)\n"
    )
    if cooperative:
        script += (
            "answer=json.loads(sys.stdin.buffer.readline())\n"
            "assert answer == {'type':'cancel'}\n"
            "print(json.dumps({'type':'result','command':'verify','outcome':'cancelled',"
            "'failure_category':'cancelled'}),flush=True)\n"
            "sys.exit(1)\n"
        )
    else:
        script += "threading.Event().wait()\n"
        monkeypatch.setattr(components_client, "_CANCEL_GRACE_S", 0.0)

    def launcher(image: Path, arguments: Sequence[str], environment: Mapping[str, str], root: Path) -> ComponentsLaunch:
        del image, arguments
        return launch_components_role(Path(sys.executable), ("-I", "-S", "-u", "-c", script), environment, root)

    with isolated_runtime_profile(tmp_path=tmp_path):

        def run() -> ComponentsResultLine:
            return run_components_role(
                ComponentsRequest(ComponentsCommand.VERIFY),
                cancellation=cancellation,
                on_event=lambda event: cancellation.cancel(),
                image=Path(sys.executable),
                launcher=launcher,
            )

        if cooperative:
            assert run().outcome.value == "cancelled"
        else:
            with pytest.raises(RefusalError) as caught:
                run()
            assert caught.value.reason is RefusalCode.TIMEOUT


@pytest.mark.parametrize("retained_effect", [OperationEffect.UNKNOWN, OperationEffect.UPDATED])
def test_recovery_preserves_effect_and_never_replays_an_apply_whose_result_was_lost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    retained_effect: OperationEffect,
) -> None:
    role = _WireRole(lose_apply_result=retained_effect is OperationEffect.UNKNOWN)
    _bind_wire(monkeypatch, tmp_path, role)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        started = now()
        root = tmp_path / "operations"

        class CrashAfterUpdatedJournal(OperationJournalRepository):
            @override
            async def commit(
                self, snapshot: OperationPersistedSnapshot, *, expected_revision: int, lease: OperationOwnerLease
            ) -> None:
                await super().commit(snapshot, expected_revision=expected_revision, lease=lease)
                if snapshot.effect is OperationEffect.UPDATED:
                    role.result_lost.set()
                    raise asyncio.CancelledError("owner lost after durable UPDATED before result")

        journal = CrashAfterUpdatedJournal(storage_root=root) if retained_effect is OperationEffect.UPDATED else None
        owner = _owner(root, profile.repository, authority_operation, clock=lambda: started, journal=journal)

        async def scenario() -> None:
            operation = await owner.submit(
                OperationRequest(
                    definition_id=COMPONENTS_SETUP_DEFINITION_ID,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload=ProvisionMutationRequest(),
                )
            )
            waiting = await run_to_settlement(owner, operation)
            pending = waiting.pending_interaction
            assert pending is not None
            pending = await _claim_review(owner, pending)
            assert pending.review_claim is not None
            assert pending.baseline_digest is not None and pending.proposed_effect_digest is not None
            await owner.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation,
                    revision=pending.request.revision,
                    response_token=_BEARER,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref=pending.review_claim.actor_ref,
                    responded_at=now(),
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            # The external fixture signals only after the real client has
            # closed the role and lost its result. No elapsed-time race.
            assert await asyncio.to_thread(role.result_lost.wait, 120)
            with pytest.raises(asyncio.CancelledError):
                await owner._continuation_tasks[operation]
            uncertain = await owner.inspect(operation)
            assert uncertain.lifecycle is OperationLifecycle.RUNNING
            assert uncertain.effect is retained_effect
            await owner.shutdown()
            recovery = _owner(
                root,
                profile.repository,
                authority_operation,
                clock=lambda: started + timedelta(seconds=90),
                owner_id="3" * 64,
                token="4" * 64,
            )
            await recovery.reconcile(operation)
            terminal = await recovery.await_terminal(operation)
            assert terminal.effect is retained_effect
            assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
            assert [arguments[2] for arguments in role.arguments] == ["plan", "setup"]
            assert len(terminal.consumed_interactions) == 1
            await recovery.shutdown()

        asyncio.run(scenario())


class _CancellingRole(_WireRole):
    """Wait on the actual input cancel line before returning a safe acknowledgement."""

    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.cancel_seen = Event()

    @override
    def __call__(
        self, image: Path, arguments: Sequence[str], environment: Mapping[str, str], root: Path
    ) -> ComponentsLaunch:
        del image, environment, root
        self.arguments.append(tuple(arguments))
        started, cancel_seen = self.started, self.cancel_seen

        class Launch(_HandleClosingLaunch):
            @override
            def _write(self) -> None:
                try:
                    lines = [
                        {"type": "started", "command": "status", "protocol": 1},
                        {
                            "type": "phase",
                            "phase_code": "dependencies.setup.browser.verify",
                            "item_id": "browser",
                            "step": "verify",
                        },
                        *[
                            {
                                "type": "progress",
                                "subject_code": "browser",
                                "unit_code": "bytes",
                                "completed": 1,
                                "total": 100,
                            }
                        ]
                        * 100,
                    ]
                    for line in lines:
                        self._writer.write(json.dumps(line).encode() + b"\n")
                    started.set()
                    if self._input.answered.wait(120) and b'{"type":"cancel"}' in self.written:
                        cancel_seen.set()
                        self._writer.write(b'{"type":"notice","notice_code":"cancel_requested"}\n')
                        self._writer.write(
                            b'{"type":"result","command":"status","outcome":"cancelled","failure_category":"cancelled"}\n'
                        )
                finally:
                    self._writer.close()
                    self._done.set()

        launch = Launch((), 1)
        self.launches.append(launch)
        return launch


class _ProgressJournal(OperationJournalRepository):
    """Signal only after the real journal commits the role's first progress."""

    def __init__(self, root: Path) -> None:
        super().__init__(storage_root=root)
        self.progress_committed = asyncio.Event()

    @override
    async def commit(
        self, snapshot: OperationPersistedSnapshot, *, expected_revision: int, lease: OperationOwnerLease
    ) -> None:
        await super().commit(snapshot, expected_revision=expected_revision, lease=lease)
        if any(isinstance(event, OperationProgressEvent) for event in snapshot.events):
            self.progress_committed.set()


def test_cancellation_reaches_the_role_and_settles_only_after_its_safe_acknowledgement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    role = _CancellingRole()
    _bind_wire(monkeypatch, tmp_path, role)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "operations"
        journal = _ProgressJournal(root)
        owner = _owner(root, profile.repository, authority_operation, journal=journal)

        async def scenario() -> None:
            operation = await owner.submit(
                OperationRequest(
                    definition_id=COMPONENTS_VERIFY_DEFINITION_ID,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload=ProvisionReadRequest(items=(DependencyItemKind.BROWSER,)),
                )
            )
            await owner.start(operation)
            assert await asyncio.to_thread(role.started.wait, 120)
            await journal.progress_committed.wait()
            await owner.request_cancel(operation)
            terminal = await owner.await_terminal(operation)
            assert role.cancel_seen.is_set()
            assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED
            assert terminal.effect is OperationEffect.NONE
            assert all(launch.ended and launch.input_closed for launch in role.launches)
            replay = await OperationJournalRepository(storage_root=root).read_after(operation, 0, limit=256)
            progress = [event for event in replay.events if isinstance(event, OperationProgressEvent)]
            assert len(progress) == 1
            assert (progress[0].completed, progress[0].total) == (1, 100)
            assert any(
                isinstance(event, OperationNoticeEvent) and event.notice_code == "dependencies.setup.cancel_requested"
                for event in replay.events
            )
            await owner.shutdown()

        asyncio.run(scenario())


def test_every_role_notice_relays_a_translated_operation_notice() -> None:
    assert set(composition._NOTICE_LOCALE_KEYS) == set(ComponentsNoticeCode)
    for key in composition._NOTICE_LOCALE_KEYS.values():
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            assert lookup_translation(key, locale=locale) is not None, (key, locale)
