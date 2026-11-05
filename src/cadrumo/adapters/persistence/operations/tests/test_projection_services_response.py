"""Public response, cancellation and caller-guard tests for the projection services."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import timedelta
from pathlib import Path
from typing import Self

import pytest
from pydantic import BaseModel, model_validator

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRefusalCode,
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationSuccessV1,
    OperationDetachRequestV1,
    OperationDetachSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalCode,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.interactions import (
    OperationResponseIntent,
)
from cadrumo.application.operations.models import (
    OperationTerminalReceipt,
)
from cadrumo.application.operations.projection_services import (
    BoundOperationSecureResponseAuthority,
    OperationCancellationService,
    OperationDetachService,
    OperationResponseAuthorityBroker,
    OperationResponseControlService,
    OperationResultProjectionService,
    UnavailableOperationSecureResponseAuthority,
)
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.core.operations import (
    OperationTerminalCondition,
)

from .projection_services_support import (
    DEFINITION_ID,
    INTERACTION_ID,
    NOW,
    OPERATION_ID,
    PROPOSAL,
    TOKEN,
    ProjectionResult,
    PublicProjectionResult,
    projection_services_lease,
    projection_services_pending,
    projection_services_registry,
    running_snapshot,
    terminal_snapshot,
    waiting_snapshot,
    write,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_response_control_requires_separately_bound_runtime_bearer(tmp_path: Path) -> None:
    root = tmp_path / "durable"
    registry = projection_services_registry()
    pending = projection_services_pending(registry)
    repository = OperationJournalRepository(storage_root=root)
    write(root, repository, waiting_snapshot(registry, pending))
    authority = BoundOperationSecureResponseAuthority.bind(
        operation_id=OPERATION_ID,
        interaction_id=INTERACTION_ID,
        revision=0,
        reviewed_proposal_digest=PROPOSAL,
        actor_ref="operator:reviewer",
        expires_at=pending.request.expires_at,
        intents=frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
        response_token=TOKEN,
        clock=lambda: NOW,
    )
    request = OperationResponseControlRequestV1(
        operation_id=OPERATION_ID,
        interaction_id=INTERACTION_ID,
        revision=0,
        actor_ref="operator:reviewer",
    )
    supervisor = OperationSupervisor(
        authority_operation=unread_authority_operation(),
        registry=registry,
        journal=repository,
        event_stream=repository,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=None,
        owner_id="5" * 64,
        lease_token_factory=lambda: "6" * 64,
        clock=lambda: NOW,
        lease_duration=timedelta(minutes=1),
    )
    service = OperationResponseControlService(
        reader=repository,
        registry=registry,
        authority=authority,
        supervisor=supervisor,
    )

    result = asyncio.run(service.inspect(request))
    authority.close()
    closed = asyncio.run(service.inspect(request))

    assert isinstance(result, OperationResponseControlSuccessV1)
    assert result.available and result.permitted_intents == frozenset({"apply", "reject"})
    assert closed.outcome == "refused"
    assert all(value == 0 for value in authority._token)
    assert TOKEN not in result.model_dump_json()


def test_response_authority_is_unavailable_after_process_restart(tmp_path: Path) -> None:
    root = tmp_path / "durable"
    registry = projection_services_registry()
    pending = projection_services_pending(registry)
    repository = OperationJournalRepository(storage_root=root)
    write(root, repository, waiting_snapshot(registry, pending))
    original_process = OperationResponseAuthorityBroker()
    capability = original_process.reserve(OPERATION_ID, "operator:reviewer")
    original_process.issue(pending, TOKEN)
    original_process.close()
    restarted_process = OperationResponseAuthorityBroker()
    request = OperationResponseControlRequestV1(
        operation_id=OPERATION_ID,
        interaction_id=INTERACTION_ID,
        revision=0,
        actor_ref="operator:reviewer",
    )
    authority = restarted_process.bind(request, pending, capability, clock=lambda: NOW)
    supervisor = OperationSupervisor(
        authority_operation=unread_authority_operation(),
        registry=registry,
        journal=repository,
        event_stream=repository,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=None,
        owner_id="7" * 64,
        lease_token_factory=lambda: "8" * 64,
        clock=lambda: NOW,
        lease_duration=timedelta(minutes=1),
    )
    service = OperationResponseControlService(
        reader=repository,
        registry=registry,
        authority=authority,
        supervisor=supervisor,
    )

    result = asyncio.run(service.inspect(request))

    assert result.outcome == "refused"
    assert result.code is OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE


@pytest.mark.parametrize("response_action", ["apply", "reject"])
def test_public_response_service_consumes_runtime_authority(tmp_path: Path, response_action: str) -> None:
    root = tmp_path / response_action
    registry = projection_services_registry()
    pending = projection_services_pending(registry)
    repository = OperationJournalRepository(storage_root=root)
    write(root, repository, waiting_snapshot(registry, pending))
    broker = OperationResponseAuthorityBroker()
    capability = broker.reserve(OPERATION_ID, "operator:reviewer")
    broker.issue(pending, TOKEN)
    control = OperationResponseControlRequestV1(
        operation_id=OPERATION_ID,
        interaction_id=INTERACTION_ID,
        revision=0,
        actor_ref="operator:reviewer",
    )
    actor_mismatch = control.model_copy(update={"actor_ref": "operator:intruder"})
    stale = control.model_copy(update={"revision": 1})
    forged = OperationResponseAuthorityBroker().reserve(OPERATION_ID, "operator:reviewer")
    assert isinstance(
        broker.bind(actor_mismatch, pending, capability, clock=lambda: NOW),
        UnavailableOperationSecureResponseAuthority,
    )
    assert isinstance(
        broker.bind(stale, pending, capability, clock=lambda: NOW), UnavailableOperationSecureResponseAuthority
    )
    assert isinstance(
        broker.bind(control, pending, forged, clock=lambda: NOW), UnavailableOperationSecureResponseAuthority
    )
    authority = broker.bind(control, pending, capability, clock=lambda: NOW)
    assert isinstance(
        broker.bind(control, pending, capability, clock=lambda: NOW), UnavailableOperationSecureResponseAuthority
    )
    supervisor = OperationSupervisor(
        authority_operation=unread_authority_operation(),
        registry=registry,
        journal=repository,
        event_stream=repository,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=None,
        owner_id="5" * 64,
        lease_token_factory=lambda: "6" * 64,
        clock=lambda: NOW,
        lease_duration=timedelta(minutes=1),
    )
    service = OperationResponseControlService(
        reader=repository,
        registry=registry,
        authority=authority,
        supervisor=supervisor,
    )

    if response_action == "apply":
        mutation = OperationResponseApplyRequestV1(**control.model_dump(), responded_at=NOW)
        result = asyncio.run(service.apply(mutation))
    else:
        mutation = OperationResponseRejectRequestV1(
            **control.model_dump(),
            responded_at=NOW,
            reason_code="operator.rejected",
        )
        result = asyncio.run(service.reject(mutation))

    assert isinstance(result, OperationResponseMutationSuccessV1)
    assert result.response_action == response_action
    consumed = asyncio.run(supervisor.inspect(OPERATION_ID)).consumed_interactions
    assert len(consumed) == 1 and consumed[0].intent.value == response_action


def test_cancellation_and_detach_delegate_to_real_supervisor_ports(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "durable"
        registry = projection_services_registry()
        repository = OperationJournalRepository(storage_root=root)
        leases = OperationLeaseFilesystemRepository(storage_root=root)
        write(root, repository, running_snapshot(registry))
        supervisor = OperationSupervisor(
            authority_operation=unread_authority_operation(),
            registry=registry,
            journal=repository,
            event_stream=repository,
            leases=leases,
            operands=operation_secure_reference_repository(objects=profile.repository),
            owner_id="5" * 64,
            lease_token_factory=lambda: "6" * 64,
            clock=lambda: NOW,
            lease_duration=timedelta(hours=1),
            cleanup_timeout=timedelta(minutes=5),
        )
        detach = asyncio.run(
            OperationDetachService(reader=repository, registry=registry, supervisor=supervisor).detach(
                OperationDetachRequestV1(operation_id=OPERATION_ID, expected_revision=0)
            )
        )
        cancelled = asyncio.run(
            OperationCancellationService(reader=repository, registry=registry, supervisor=supervisor).request(
                OperationCancellationRequestV1(operation_id=OPERATION_ID, expected_revision=0)
            )
        )
        stale = asyncio.run(
            OperationCancellationService(reader=repository, registry=registry, supervisor=supervisor).request(
                OperationCancellationRequestV1(operation_id=OPERATION_ID, expected_revision=0)
            )
        )
        journal_path = root / "operation-journals" / f"{OPERATION_ID}.json"
        settled_bytes = journal_path.read_bytes()
        with pytest.raises(ValueError, match="expected revision is stale"):
            asyncio.run(supervisor.request_cancel(OPERATION_ID, expected_revision=0))

        assert isinstance(detach, OperationDetachSuccessV1)
        assert isinstance(cancelled, OperationCancellationSuccessV1)
        assert isinstance(stale, OperationCancellationRefusalV1)
        assert stale.code is OperationCancellationRefusalCode.STALE_OPERATION_REVISION
        assert journal_path.read_bytes() == settled_bytes


_RESULT_PROJECTION_IDENTITY: ContextVar[str] = ContextVar("result_projection_identity", default="")


_RESULT_MODEL_HOOK: ContextVar[Callable[[], None] | None] = ContextVar("result_model_validation", default=None)


class HeldPublicProjectionResult(PublicProjectionResult):
    """Exercise both projector construction and registered public-model revalidation."""

    @model_validator(mode="after")
    def _hold_public_validation(self) -> Self:
        hook = _RESULT_MODEL_HOOK.get()
        if hook is not None:
            hook()
        return self


async def _await_result_stage[T](pending: asyncio.Task[T], entered: asyncio.Event) -> None:
    """Surface an on-loop regression without a blocking test fallback or wall-clock cutoff."""
    waiting = asyncio.create_task(entered.wait())
    try:
        await asyncio.wait((pending, waiting), return_when=asyncio.FIRST_COMPLETED)
        if not entered.is_set():
            pending.result()
            pytest.fail("the registered result stage did not enter its held body")
    finally:
        waiting.cancel()
        with suppress(asyncio.CancelledError):
            await waiting


@pytest.mark.parametrize("stage", ["projector", "validation"])
@pytest.mark.parametrize("cancel", [False, True])
def test_result_projection_yields_and_settles_inside_the_callers_guard(
    tmp_path: Path, stage: str, cancel: bool
) -> None:
    """Pure public transformation preserves context and cannot outlive the caller's authority guard."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:

        async def resolve() -> None:
            loop = asyncio.get_running_loop()
            loop_thread = threading.get_ident()
            entered, progressed = asyncio.Event(), asyncio.Event()
            resume = threading.Event()
            events: list[str] = []
            validations = 0

            def hold() -> None:
                assert threading.get_ident() != loop_thread
                assert _RESULT_PROJECTION_IDENTITY.get() == "original-result-context"
                loop.call_soon_threadsafe(entered.set)
                resume.wait()
                events.append("result-body-settled")

            def validate() -> None:
                nonlocal validations
                validations += 1
                assert threading.get_ident() != loop_thread
                assert _RESULT_PROJECTION_IDENTITY.get() == "original-result-context"
                if stage == "validation" and validations == 2:
                    hold()

            def project(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
                assert receipt.condition is OperationTerminalCondition.SUCCEEDED
                if stage == "projector":
                    hold()
                return HeldPublicProjectionResult(result_code=ProjectionResult.model_validate(result).result_code)

            root = tmp_path / "held-result-durable"
            registry = projection_services_registry(
                result_projector=project, result_schema_type=HeldPublicProjectionResult
            )
            repository = OperationJournalRepository(storage_root=root)
            operands = operation_secure_reference_repository(objects=profile.repository)
            result_ref = await operands.put(ProjectionResult(result_code="held.safe.result"), written_at=NOW)
            terminal = terminal_snapshot(registry, result_ref=result_ref)
            lease = projection_services_lease()
            observed = await OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=NOW)
            assert observed.current == lease
            await repository.create(running_snapshot(registry), lease=lease)
            await repository.commit_settlement(terminal, expected_revision=0, lease=lease)
            contract = registry.lookup_public_contract(DEFINITION_ID)
            assert contract.result_schema is not None
            request = OperationResultProjectionRequestV1(
                operation_id=OPERATION_ID,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            )
            service = OperationResultProjectionService(reader=repository, registry=registry, operands=operands)

            @asynccontextmanager
            async def caller_guard() -> AsyncGenerator[None]:
                events.append("authority-held")
                try:
                    yield
                finally:
                    events.append("authority-released")

            async def guarded_result() -> OperationResultProjectionSuccessV1[HeldPublicProjectionResult]:
                async with caller_guard():
                    result = await service.resolve(request, HeldPublicProjectionResult)
                    assert not isinstance(result, OperationResultProjectionRefusalV1)
                    assert isinstance(result, OperationResultProjectionSuccessV1)
                    return result

            async def control() -> None:
                assert entered.is_set() and not resume.is_set()
                progressed.set()

            identity = _RESULT_PROJECTION_IDENTITY.set("original-result-context")
            hook = _RESULT_MODEL_HOOK.set(validate)
            pending = asyncio.create_task(guarded_result())
            try:
                await _await_result_stage(pending, entered)
                await asyncio.create_task(control())
                assert progressed.is_set() and not pending.done()
                if cancel:
                    pending.cancel()
                    await asyncio.sleep(0)
                    pending.cancel()
                    await asyncio.sleep(0)
                    assert not pending.done() and events == ["authority-held"]
                resume.set()
                if cancel:
                    with pytest.raises(asyncio.CancelledError):
                        await pending
                else:
                    result = await pending
                    assert result.projection.result_code == "held.safe.result"
                    assert result.result_schema == contract.result_schema
                    assert result.definition_contract_digest == contract.definition_contract_digest
                assert validations >= 2
                assert events == ["authority-held", "result-body-settled", "authority-released"]
            finally:
                resume.set()
                _RESULT_MODEL_HOOK.reset(hook)
                _RESULT_PROJECTION_IDENTITY.reset(identity)
                if not pending.done():
                    with suppress(asyncio.CancelledError):
                        await pending

        asyncio.run(resolve())
