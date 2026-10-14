"""Lazy canonical operation composition within one immutable profile worker.

The worker serves its channels before any of this composition exists. The
production registry, its handlers and the pinned tax authority are imported
and built the first time an operation needs them, never to admit a worker or a
sign-in, so the modules below stay off the worker's startup path and every
heavier dependency is imported inside the method that first uses it.

Core types: :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import AbstractContextManager, ExitStack, asynccontextmanager, contextmanager
from datetime import timedelta
from math import isfinite
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from ...adapters.persistence.storage.errors import RepositoryError
from ...application.operations.drain import OperationDrainResult
from ...application.operations.errors import OperationSubjectBusyError, OperationUnsettledError
from ...application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from ...application.operations.models import (
    OperationId,
    OperationIdentity,
    OperationRequest,
    OperationStoredInvocation,
    new_operation_id,
)
from ...application.operations.secret_submission import OperationSecretRequirement, zeroize_secret_buffer
from ...application.runtime.operation_access import OperationManagementRequest, operation_management_action
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...core.async_cleanup import await_cancellation_complete
from ...core.config import override_settings
from ...core.errors.hierarchy import CadrumoError
from ...core.logging import get_logger
from ...core.operations import OperationDurability, OperationLifecycle
from ...core.request_faults import registered_error_fault, request_faults
from ...core.startup_phase_log import startup_phase
from ...core.time.clock import now

if TYPE_CHECKING:
    from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
    from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
    from ...application.operations.composition import OperationComposedServices, OperationSubmission
    from ...application.operations.execution_actor import OperationExecutionCaller
    from ...application.operations.registry import (
        OperationFrontendProjection,
        OperationPublicDefinitionContractV1,
        OperationPublicDefinitionDescriptionV1,
        OperationRegistry,
    )
    from ...application.operations.supervisor import OperationSupervisor
    from ...application.runtime.worker_authorization import WorkerAuthorityRequest
    from ...application.user_profile.automation_enrollment import AutomationInventory
    from ...application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
    from ...application.workbench_generation_contracts import WorkbenchGenerationV1
    from ...application.workbench_generation_operation import WorkbenchGenerationOperationRequest
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from ...domain.deadlines.models import TaxpayerProfile
    from .automation_execution import WorkerAutomationAdministration
    from .operation_authority import ProfileWorkerOperationAuthority

_PROJECTION_DOCUMENT = TypeAdapter(dict[str, JsonValue])
#: How often, at most, a used profile looks for operations whose owner lapsed.
_LAPSE_CHECK_SECONDS = 30.0
_log = get_logger(__name__)
_PRIVATE_RESULT_RELEASE_ACTIONS = frozenset({AccessAction.RESULT, AccessAction.REVIEW})


@contextmanager
def _refusing_what_its_readers_refuse() -> Generator[None]:
    """Answer whatever refuses a caller's document while it is read as an invalid request that says why.

    Every frontend is told what the validator said, as the command line shows
    it. A validator can also refuse with a registered error the model does not
    wrap: that is the same refusal, with the error's code and message, and it
    must not end the worker that every session of the profile shares.
    """
    try:
        yield
    except ValidationError as refused:
        faults = request_faults(refused)
        raise AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=faults) from None
    except (AutomationCustodyError, ProfileAccessRefusedError):
        raise
    except CadrumoError as refused:
        faults = (registered_error_fault(refused),)
        raise AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=faults) from None
    except (ValueError, TypeError, RecursionError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None


class ProfileWorkerOperationHost:
    """Own the existing services and publication lease, never a second dispatcher."""

    def __init__(self, custody: ProfileWorkerCustody, *, authorization: WorkerAuthorizationClient) -> None:
        """Defer publication and backend loading until a governed capability needs it."""
        self.custody = custody
        self._lifetime = ExitStack()
        self._authority: PinnedAuthorityOperation | None = None
        self._services: OperationComposedServices | None = None
        self._client = authorization
        self._execution: ProfileWorkerOperationAuthority | None = None
        self._closed = False
        self._drain_result: OperationDrainResult | None = None
        self._output_tasks: dict[asyncio.Task[object], OperationId] = {}
        self._submissions: dict[OperationId, tuple[UUID, OperationSubmission]] = {}
        self._inventory_lock = asyncio.Lock()
        self._inventory_verified = False
        # Every operation that may still be unsettled: the journal's unsettled
        # records at first use, and each admission since.
        self._unsettled: set[OperationId] = set()
        self._lapse_lock = asyncio.Lock()
        self._lapse_checked_at: float | None = None
        # One composition and one authority lease, whichever thread asks first:
        # a worker thread serving an operation or the service loop.
        self._composition_lock = RLock()

    def _bind_execution(self, registry: OperationRegistry) -> ProfileWorkerOperationAuthority:
        from .operation_authority import ProfileWorkerOperationAuthority

        self._execution = ProfileWorkerOperationAuthority(
            custody=self.custody, client=self._client, registry=registry, authority_operation=self._pinned()
        )
        return self._execution

    def _governed(self) -> AbstractContextManager[None]:
        """Scope governed facts to this worker's one pinned authority generation."""
        from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts

        return validating_governed_facts(self._pinned())

    def _composed(self) -> OperationComposedServices:
        if self._closed:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        services = self._services
        if services is not None:
            return services
        with self._composition_lock:
            if self._closed:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            if self._services is None:
                self._services = self._compose()
            return self._services

    def _await_composition(self) -> None:
        with self._composition_lock:
            return

    async def _composed_off_loop(self) -> OperationComposedServices:
        """Join or start the one composition without holding the service loop.

        The first operation after a person's sign-in composes the registry; the
        loop keeps serving sign-ins and status on the other channel meanwhile.
        """
        if self._services is not None:
            return self._composed()
        return await asyncio.to_thread(self._composed)

    def _compose(self) -> OperationComposedServices:
        from ...application.local_reader_provisioning import RuntimeServerOwnerStart
        from ..operation_composition import compose_operation_dependencies

        with startup_phase(_log, "worker_operation_compose"), self._governed():
            return compose_operation_dependencies(
                authority_operation=self._pinned(),
                operation_owner_id=self.custody.identity.operation_owner_id,
                execution_authority_factory=self._bind_execution,
                automation_inventory_reader=self._automation_inventory,
                automation_administration_factory=self._automation_administration,
                workbench_generation_reader=self._workbench_generation,
                profile_rotation_finalizer=self._finalize_password_rotation,
                modelo_profile_resolver=self._modelo_profile,
                execution_caller_reader=self._execution_caller,
                runtime_server_owner_start=RuntimeServerOwnerStart(self._start_runtime_server),
            )

    def in_flight_operation_count(self) -> int:
        """Read the owning supervisor without creating services or touching custody."""
        services = self._services
        return 0 if services is None else services.submission.supervisor.in_flight_operation_count()

    def prepare(self) -> None:
        """Finish cold registry composition before the caller continues.

        Key-based admission keeps this one-time cost inside its own preparation
        budget. A person's sign-in never composes: the first operation a
        session asks for does, off the service loop.
        """
        with startup_phase(_log, "worker_operation_prepare"):
            self._composed()

    def _execution_caller(self, identity: OperationIdentity) -> OperationExecutionCaller:
        """Answer from this worker's own admission binding, never from caller-supplied facts."""
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return self._execution.execution_caller(identity)

    async def _start_runtime_server(self, identity: OperationIdentity) -> int | None:
        """Ask the runtime that owns this worker to start the model runtime's server for one invocation."""
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return await self._execution.start_runtime_server(identity)

    def _modelo_profile(self, operation: PinnedAuthorityOperation) -> TaxpayerProfile:
        """Read filing facts only from this worker's immutable profile custody."""
        from ...application.user_profile.profile_record_repository import ProfileRecordRepository
        from ...application.user_profile.projections import projection_for_taxpayer

        profile_id = str(self.custody.identity.binding.profile_id)
        repository = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=operation.profile_decode_context()
        )
        record = repository.load(profile_id)
        if str(record.profile_id) != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return projection_for_taxpayer(record, schema=repository.session.profile_decode_context.schema)

    async def _finalize_password_rotation(
        self, identity: OperationIdentity, outcome: ProfilePassphraseRotationOutcome
    ) -> None:
        """Retire original custody after encrypted result persistence in COMMIT."""
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        self._execution.retire_password_successor(identity, outcome)

    async def _workbench_generation(
        self, identity: OperationIdentity, payload: WorkbenchGenerationOperationRequest
    ) -> WorkbenchGenerationV1:
        """Retain native read authority through one exact-profile generation capture."""
        from ...application.overview.home import HomeAccountSession, HomeSessionPosture
        from ...application.workflow.profile_bucket_scan import read_profile_bucket_by_id
        from ..workbench_generation_composition import compose_secure_workbench_generation_provider

        execution, services = self._execution, self._services
        if execution is None or services is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

        def account_session() -> HomeAccountSession:
            execution.workbench_session(identity, payload)
            profile = read_profile_bucket_by_id(str(payload.profile_id), root=self.custody.root)
            if profile is None or profile.bucket_id != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            lease = execution.workbench_session(identity, payload)
            return HomeAccountSession(
                posture=HomeSessionPosture.ACTIVE, profile_label=profile.label, expires_at=lease.expires_at
            )

        def capture() -> WorkbenchGenerationV1:
            with override_settings(cadrumo_output_language=payload.output_language.value):
                provider = compose_secure_workbench_generation_provider(
                    profile_id=str(payload.profile_id),
                    operation=self._pinned(),
                    operation_contracts=services.public_contracts,
                    account_session_reader=account_session,
                )
                result = provider()
                account_session()
                return result

        async with execution.guard(identity, AccessAction.START):
            return await await_cancellation_complete(
                asyncio.to_thread(capture), task_name="runtime-workbench-generation"
            )

    def _automation_administration(
        self, identity: OperationIdentity, profile_id: UUID
    ) -> WorkerAutomationAdministration:
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        from .automation_execution import WorkerAutomationAdministration

        return WorkerAutomationAdministration(self._execution, identity, profile_id)

    async def _automation_inventory(self, identity: OperationIdentity, profile_id: UUID) -> AutomationInventory:
        """Use the canonical operation identity, never caller-supplied authority facts."""
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return await self._execution.automation_inventory(identity, profile_id)

    def _pinned(self) -> PinnedAuthorityOperation:
        authority = self._authority
        if authority is not None:
            return authority
        from ...domain.calculations.registry.authority import bundled_indexed_authority

        with self._composition_lock:
            if self._authority is None:
                self._authority = self._lifetime.enter_context(bundled_indexed_authority().lease_operation())
            return self._authority

    def profile_decode_context(self) -> ProfileDecodeContext:
        """Use the same publication for password candidates and hosted operations."""
        return self._pinned().profile_decode_context()

    async def _require_current_inventory(self) -> None:
        """Refuse unreadable startup state before any hosted private operation.

        Inventory only checks the current journal format and notes which records
        are unsettled. It replays no work. Each requested continuation still
        resolves encrypted provenance and goes through canonical lease
        reconciliation; only operations whose owner lapsed are then settled.
        """
        await self._verify_inventory()
        await self._settle_lapsed_operations()

    async def _verify_inventory(self) -> None:
        async with self._inventory_lock:
            if self._inventory_verified:
                return
            services = await self._composed_off_loop()
            from ...application.operations.persistence.journal import OperationRecoveryInventoryDisposition

            after = None
            refused = False
            unsettled: set[OperationId] = set()
            try:
                while True:
                    page = await services.recovery_inventory(after=after, limit=128)
                    refused |= any(
                        entry.disposition is OperationRecoveryInventoryDisposition.REFUSED for entry in page.entries
                    )
                    unsettled.update(
                        entry.operation_id
                        for entry in page.entries
                        if entry.disposition is OperationRecoveryInventoryDisposition.NONTERMINAL
                    )
                    if not page.has_more:
                        break
                    after = page.next_cursor
            except (RepositoryError, ValueError):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
            if refused or self._closed:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            self._unsettled.update(unsettled)
            self._inventory_verified = True

    def _track_unsettled(self, operation_id: OperationId, definition_id: str) -> None:
        """Note an admission whose owner the lapse sweep may one day have to settle.

        An ephemeral operation is never noted: it ends with this worker, and
        once memory forgets it the durable journal the sweep would read never
        held it, so settling it would only take the journal lock and fail.
        """
        registry = self._composed().submission.supervisor.registry
        if registry.lookup_public_contract(definition_id).durability is not OperationDurability.EPHEMERAL:
            self._unsettled.add(operation_id)

    def release_delivered_result(self, operation_id: OperationId) -> None:
        """Forget an ephemeral operation once its whole result has been written to its reader.

        Its result is decrypted profile data in plain memory; a reader that
        needs it again reads the profile again, which has no effect.
        """
        services = self._services
        if services is not None:
            services.release_ephemeral_result(operation_id)

    def forget_settled_ephemeral(self) -> None:
        """Forget every settled ephemeral result: the worker outlives its last session, its reads do not."""
        services = self._services
        if services is not None:
            services.forget_settled_ephemeral()

    async def _settle_lapsed_operations(self) -> None:
        """Settle every operation whose owner stopped renewing its lease and whose grace has passed.

        Its owner is gone, and its submitter has had a whole lease to continue
        it, so nothing else would ever settle it. Checked at most every
        :data:`_LAPSE_CHECK_SECONDS` as the profile is used; a failure is logged
        with the operation and never refuses the caller's own request.
        """
        now = monotonic()
        checked_at = self._lapse_checked_at
        if self._lapse_lock.locked() or (checked_at is not None and now - checked_at < _LAPSE_CHECK_SECONDS):
            return
        async with self._lapse_lock:
            self._lapse_checked_at = now
            supervisor = self._composed().submission.supervisor
            for operation_id in sorted(self._unsettled):
                try:
                    settled = await supervisor.settle_lapsed(operation_id, grace=supervisor.lease_duration)
                except (RepositoryError, ValueError) as error:
                    _log.warning(
                        "lapsed operation left unsettled operation=%s error=%s", operation_id, type(error).__name__
                    )
                    continue
                if settled is not None and settled.lifecycle is OperationLifecycle.TERMINAL:
                    self._unsettled.discard(operation_id)

    def contract(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionContractV1:
        """Resolve an allowed definition from the real production service inventory."""
        lease = self.custody.require(session_id)
        if definition_id not in lease.scope.operations:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        for definition in self._composed().public_contracts.definitions:
            if definition.definition_id == definition_id:
                self.custody.require(session_id)
                return definition
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def describe(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionDescriptionV1:
        """Bind discovery to the same live custody and exact registered request model."""
        self.contract(session_id, definition_id)
        description = self._composed().observation.registry.describe_public_definition(definition_id)
        self.custody.require(session_id)
        return description

    async def submit(
        self, *, session_id: UUID, frontend: OperationFrontendProjection, request: OperationRequest[BaseModel]
    ) -> OperationSubmission:
        """Admit a fresh invocation through the canonical supervisor and live authority."""
        self.custody.require(session_id)
        await self._require_current_inventory()
        services = self._composed()
        execution = self._execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        from .operation_authority import WorkerOperationBinding

        operation_id = new_operation_id()
        execution.bind(operation_id, WorkerOperationBinding(session_id, frontend, request))

        async def admit() -> OperationSubmission:
            # Guard and canonical admission execute in the same retained task.
            # Cancelling the caller cannot release custody while a repository
            # thread still writes, or discard a binding after durable admission.
            try:
                identity = OperationIdentity(
                    operation_id=operation_id, definition_id=request.definition_id, subject_ref=request.subject_ref
                )
                async with execution.guard(identity, AccessAction.SUBMIT):
                    submitted = await services.submission.submit(
                        request,
                        actor_ref=f"session:{session_id}",
                        operation_id=operation_id,
                        provenance=execution.capture_provenance(identity),
                    )
                    if submitted.receipt.operation_id == operation_id:
                        self._submissions[operation_id] = session_id, submitted
                        self._track_unsettled(operation_id, request.definition_id)
                    else:
                        # Replay does not revive the original response bearer.
                        execution.discard(operation_id)
                    return submitted
            except OperationSubjectBusyError as busy:
                execution.discard(operation_id)
                # The log and the refused frontend both name the holder: it is the operation to follow.
                _log.warning(
                    "operation subject busy definition=%s holder=%s",
                    request.definition_id,
                    busy.holder_operation_id or "unknown",
                )
                raise ProfileAccessRefusedError(
                    AccessDenialCode.SUBJECT_BUSY, holder_operation_id=busy.holder_operation_id
                ) from None
            except RepositoryError:
                execution.discard(operation_id)
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
            except BaseException:
                execution.discard(operation_id)
                raise

        return await await_cancellation_complete(admit(), task_name="profile-operation-admission")

    async def start(self, operation_id: OperationId, session_id: UUID) -> OperationId:
        """Start only an invocation already bound by this worker's admission door."""
        self._require_owner(operation_id, session_id)
        await self._require_current_inventory()
        try:
            with self._governed():
                return await self._composed().submission.start(operation_id)
        except (RepositoryError, ValueError):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    async def settlement(self, identity: OperationIdentity, *, timeout: float) -> bool:
        """Wait for an original rotation's terminal journal without old-key disclosure.

        Timeout cancels only this waiter. The canonical supervisor shields its
        settlement task, which remains owned until it terminates or is drained.
        A terminal failure is settled too; this acknowledgment claims no
        successful domain effect or available private result.
        """
        supervisor = self._settlement_supervisor(identity, timeout)
        return await self._await_settlement(supervisor, identity, timeout)

    def _settlement_supervisor(self, identity: OperationIdentity, timeout: float) -> OperationSupervisor:
        from ...application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID

        original = self._submissions.get(identity.operation_id)
        services = self._services
        if (
            self._closed
            or services is None
            or original is None
            or original[1].receipt.operation_id != identity.operation_id
            or identity.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
            or not isfinite(timeout)
            or not 0 < timeout <= 5
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return services.submission.supervisor

    async def _await_settlement(
        self, supervisor: OperationSupervisor, identity: OperationIdentity, timeout: float
    ) -> bool:
        wait = asyncio.timeout(timeout)
        try:
            async with wait:
                observed = await supervisor.inspect(identity.operation_id)
                if observed.identity != identity:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                terminal = await supervisor.settled(identity.operation_id)
                if terminal.identity != identity or terminal.lifecycle is not OperationLifecycle.TERMINAL:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                return True
        except TimeoutError:
            if wait.expired():
                return False
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        except (RepositoryError, OperationUnsettledError, KeyError, ValueError):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    @asynccontextmanager
    async def operation_secret(
        self,
        session_id: UUID,
        requirement: OperationSecretRequirement,
        *,
        frontend: OperationFrontendProjection,
        secret: bytearray | None = None,
    ) -> AsyncGenerator[WorkerAuthorityRequest]:
        """Authorize only the original submitter's exact one-use secret requirement."""
        try:
            operation_id = requirement.identity.operation_id
            self._require_owner(operation_id, session_id)
            original = self._submissions.get(operation_id)
            if (
                original is None
                or original[0] != session_id
                or original[1].receipt.secret_requirement != requirement
                or now() >= requirement.expires_at
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            async with self.release(session_id, operation_id, frontend, AccessAction.SUBMIT) as authorization:
                try:
                    if secret is None:
                        await self._composed().submission.require_secret_ready(requirement)
                    else:
                        await await_cancellation_complete(
                            self._composed().submission.submit_secret(requirement, secret),
                            task_name="profile-operation-secret",
                        )
                except (RepositoryError, ValueError):
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
                yield authorization
        finally:
            if secret is not None:
                zeroize_secret_buffer(secret)

    async def resume(
        self, operation_id: OperationId, session_id: UUID, *, frontend: OperationFrontendProjection
    ) -> OperationId:
        """Reauthorize stored intent and let its existing owner reconcile before entry."""
        self.custody.require(session_id)
        await self._require_current_inventory()
        services = self._composed()
        invocation = await self._stored_invocation(operation_id, require_idle=True)
        execution = self._execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        from .operation_authority import WorkerOperationBinding

        binding = WorkerOperationBinding(session_id, frontend, invocation.request, invocation.provenance)
        async with execution.guard_binding(invocation.identity, AccessAction.RESUME, binding):
            execution.bind_reentry(operation_id, binding)
        try:
            # START/RESUME at actual entry and COMMIT each acquire fresh guards.
            with self._governed():
                return await services.submission.continue_operation(operation_id)
        except (RepositoryError, ValueError):
            execution.discard(operation_id)
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    @asynccontextmanager
    async def observe(
        self, session_id: UUID, request: OperationObservationRequestV1, *, frontend: OperationFrontendProjection
    ) -> AsyncGenerator[tuple[OperationObservationResultV1, WorkerAuthorityRequest]]:
        """Lend a canonical projection only while its native disclosure guard is held."""
        async with self.release(session_id, request.operation_id, frontend, AccessAction.OBSERVE) as authorization:
            observed = await await_cancellation_complete(
                self._composed().observation.observe(request), task_name="profile-operation-observation"
            )
            yield observed, authorization

    @asynccontextmanager
    async def release(
        self, session_id: UUID, operation_id: OperationId, frontend: OperationFrontendProjection, action: AccessAction
    ) -> AsyncGenerator[WorkerAuthorityRequest]:
        """Bind each internal projection to policy the runtime must recheck on final output."""
        self.custody.require(session_id)
        await self._require_current_inventory()
        self._composed()
        execution = self._execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        task = asyncio.current_task()
        if task is None or task in self._output_tasks:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._output_tasks[task] = operation_id
        from ...application.workbench_generation_operation import WORKBENCH_GENERATION_OPERATION_DEFINITION_ID
        from .operation_authority import WorkerOperationBinding

        try:
            invocation = await self._stored_invocation(operation_id)
            binding = WorkerOperationBinding(session_id, frontend, invocation.request, invocation.provenance)
            async with execution.guard_binding(invocation.identity, action, binding) as authorization:
                # The full-owner workbench projection is released only to the
                # session that generated it; observing its lifecycle discloses
                # operation metadata alone and stays caller-independent.
                if (
                    action in _PRIVATE_RESULT_RELEASE_ACTIONS
                    and invocation.identity.definition_id == WORKBENCH_GENERATION_OPERATION_DEFINITION_ID
                ):
                    execution.require_owner(operation_id, session_id)
                yield authorization
        finally:
            self._output_tasks.pop(task, None)

    @asynccontextmanager
    async def release_submission(
        self, session_id: UUID, operation_id: OperationId, frontend: OperationFrontendProjection
    ) -> AsyncGenerator[WorkerAuthorityRequest]:
        """Release a fresh admission's receipt, settling the admission when its submitter is refused it.

        The admission is durable before its receipt is released. Withheld, the
        receipt leaves nobody able to start the operation, and an unstarted
        operation keeps its subject's lease and refuses every later submission
        for that subject.
        """
        released = False
        try:
            async with self.release(session_id, operation_id, frontend, AccessAction.SUBMIT) as authorization:
                released = True
                yield authorization
        except (ProfileAccessRefusedError, AutomationCustodyError) as refusal:
            if not released:
                await self._settle_undelivered_admission(operation_id, session_id, refusal)
            raise

    async def _settle_undelivered_admission(
        self, operation_id: OperationId, session_id: UUID, refusal: ProfileAccessRefusedError | AutomationCustodyError
    ) -> None:
        original = self._submissions.get(operation_id)
        if original is None or original[0] != session_id:
            # A replayed receipt names an earlier admission, which keeps its own course.
            return
        reason = (
            refusal
            if isinstance(refusal, ProfileAccessRefusedError)
            else ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
        )
        try:
            await self._composed().submission.supervisor.settle_refused_start(operation_id, reason)
        except (RepositoryError, ValueError):
            _log.warning("undelivered admission left unsettled operation=%s", operation_id)
            return
        self._submissions.pop(operation_id, None)
        if self._execution is not None:
            self._execution.discard(operation_id)

    async def _stored_invocation(
        self, operation_id: OperationId, *, require_idle: bool = False
    ) -> OperationStoredInvocation:
        try:
            with self._governed():
                return await self._composed().submission.stored_invocation(operation_id, require_idle=require_idle)
        except (RepositoryError, KeyError, ValueError):
            # Unknown, damaged, foreign-profile and stale-contract records have
            # the same safe refusal. Their contents never become a projection.
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    @asynccontextmanager
    async def project(
        self,
        session_id: UUID,
        request: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1,
        *,
        frontend: OperationFrontendProjection,
    ) -> AsyncGenerator[tuple[dict[str, JsonValue], WorkerAuthorityRequest]]:
        """Serialize only the canonical registered public projection under consent."""
        is_result = isinstance(request, OperationResultProjectionRequestV1)
        operation_id = request.operation_id if is_result else request.reference.operation_id
        action = AccessAction.RESULT if is_result else AccessAction.REVIEW
        async with self.release(session_id, operation_id, frontend, action) as authorization:
            services = self._composed()
            if isinstance(request, OperationResultProjectionRequestV1):
                result = await await_cancellation_complete(
                    services.result.resolve(request, BaseModel), task_name="profile-operation-result"
                )
            else:
                result = await await_cancellation_complete(
                    services.review.resolve(request, BaseModel), task_name="profile-operation-review"
                )
            # Polymorphic canonical projections retain their validated fields;
            # serializing as the BaseModel parameter would discard them.
            document = _PROJECTION_DOCUMENT.validate_python(result.model_dump(mode="json", serialize_as_any=True))
            yield document, authorization

    def _require_owner(self, operation_id: OperationId, session_id: UUID) -> None:
        if self._execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._execution.require_owner(operation_id, session_id)

    @asynccontextmanager
    async def manage(
        self,
        session_id: UUID,
        request: OperationManagementRequest,
        *,
        frontend: OperationFrontendProjection,
    ) -> AsyncGenerator[tuple[dict[str, JsonValue], WorkerAuthorityRequest]]:
        """Use canonical controls without recovering an earlier session's response proof."""
        submission = self._submissions.get(request.operation_id)
        if isinstance(request, OperationResponseControlRequestV1) and (
            request.actor_ref != f"session:{session_id}"
            or submission is None
            or submission[0] != session_id
            or submission[1].response_capability is None
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)

        async def control() -> BaseModel:
            services = self._composed()
            if isinstance(request, OperationCancellationRequestV1):
                return await services.cancellation.request(request)
            if isinstance(request, OperationDetachRequestV1):
                return await services.detach.detach(request)
            # The exact original capability stays local. A new session,
            # idempotent receipt or reattached operation cannot obtain it.
            if submission is None:
                raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
            if isinstance(request, OperationResponseApplyRequestV1):
                response = await services.response(request, submission[1].response_capability)
                return await response.apply(request)
            if isinstance(request, OperationResponseRejectRequestV1):
                response = await services.response(request, submission[1].response_capability)
                return await response.reject(request)
            response = await services.inspect_response(request, submission[1].response_capability)
            return await response.inspect(request)

        async with self.release(
            session_id, request.operation_id, frontend, operation_management_action(request)
        ) as authorization:
            result = await await_cancellation_complete(control(), task_name="profile-operation-control")
            document = _PROJECTION_DOCUMENT.validate_python(result.model_dump(mode="json", serialize_as_any=True))
            yield document, authorization

    async def submit_financial_input(
        self,
        *,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        input_json: str,
    ) -> OperationSubmission:
        """Convert volatile human input before binding or journaling the safe request."""
        from ...application.modelo.edit_operator_input import prepare_modelo_edit_operand
        from ...application.operations.financial_operand_contract import OperationFinancialOperandRefusedError

        await self._composed_off_loop()
        contract = self.contract(session_id, definition_id)
        if contract.transient_financial_operand is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        # A fault of the operand is a validator's message and never the operand itself.
        with _refusing_what_its_readers_refuse(), self._governed():
            prepared = prepare_modelo_edit_operand(
                definition_id=definition_id,
                profile_id=self.custody.identity.binding.profile_id,
                subject_ref=subject_ref,
                input_json=input_json,
            )
        input_json = ""

        async def transfer() -> OperationSubmission:
            try:
                submitted = await self.submit(
                    session_id=session_id,
                    frontend=frontend,
                    request=OperationRequest(
                        definition_id=definition_id,
                        subject_ref=subject_ref,
                        payload=prepared.request,
                        idempotency_key=None,
                    ),
                )
                operand = prepared.operand
                if operand is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                supervisor = self._composed().submission.supervisor
                try:
                    await supervisor.bind_typed_financial_operand(submitted.receipt.operation_id, operand)
                except OperationFinancialOperandRefusedError as refused:
                    await supervisor.refuse_unstarted_financial_input(submitted.receipt.operation_id)
                    faults = (registered_error_fault(refused),)
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=faults) from None
                finally:
                    del operand
                return submitted
            finally:
                prepared.release()

        return await await_cancellation_complete(transfer(), task_name="profile-financial-operand-admission")

    async def submit_payload(
        self,
        *,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        payload_json: str,
        idempotency_key: str | None = None,
    ) -> OperationSubmission:
        """Decode through the exact registered model after exact-profile custody."""
        await self._composed_off_loop()
        self.contract(session_id, definition_id)
        if self._execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        with _refusing_what_its_readers_refuse(), self._governed():
            payload = self._execution.registry.decode_request_payload(definition_id, payload_json)
        return await self.submit(
            session_id=session_id,
            frontend=frontend,
            request=OperationRequest(
                definition_id=definition_id,
                subject_ref=subject_ref,
                payload=payload,
                idempotency_key=idempotency_key,
            ),
        )

    async def close(self) -> OperationDrainResult:
        """Bound canonical drain; retain publication while native containment is required."""
        if self._drain_result is not None:
            return self._drain_result
        self._closed = True
        # A composition an operation already started finishes, off the loop, and
        # is drained like any other; none can start once the host is closed.
        await await_cancellation_complete(
            asyncio.to_thread(self._await_composition), task_name="profile-operation-compose-join"
        )
        result = (
            await await_cancellation_complete(
                self._services.drain(timedelta(seconds=5)), task_name="profile-operation-drain"
            )
            if self._services is not None
            else OperationDrainResult(unresolved=(), recovery_required=())
        )
        if self._output_tasks:
            # Canonical execution drain does not own frontend projection tasks.
            # Retain their publication until the parent contains this worker.
            result = OperationDrainResult(
                unresolved=tuple(sorted(set(result.unresolved) | set(self._output_tasks.values()))),
                recovery_required=result.recovery_required,
            )
        self._drain_result = result
        if not result.needs_containment:
            self._lifetime.close()
            if self._authority is not None:
                from ...domain.calculations.registry.authority import release_bundled_indexed_authority

                # The worker admitted the process-shared owner for this lease; close its
                # database handles with the host rather than at interpreter teardown.
                release_bundled_indexed_authority()
        return result
