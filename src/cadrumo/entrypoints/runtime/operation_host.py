"""Lazy canonical operation composition within one immutable profile worker."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from datetime import timedelta
from math import isfinite
from uuid import UUID

from pydantic import BaseModel, JsonValue, TypeAdapter

from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.persistence.storage.errors import RepositoryError
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID
from ...application.operations.composition import OperationComposedServices, OperationSubmission
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
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.persistence.journal import OperationRecoveryInventoryDisposition
from ...application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionDescriptionV1,
    OperationRegistry,
)
from ...application.operations.secret_submission import OperationSecretRequirement, zeroize_secret_buffer
from ...application.overview.home import HomeAccountSession, HomeSessionPosture
from ...application.runtime.operation_access import OperationManagementRequest, operation_management_action
from ...application.runtime.worker_authorization import WorkerAuthorityRequest
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import AutomationInventory
from ...application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.projections import projection_for_taxpayer
from ...application.workbench_generation import WorkbenchGenerationV1
from ...application.workbench_generation_operation import (
    WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
    WorkbenchGenerationOperationRequest,
)
from ...application.workflow.profile_bucket_scan import read_profile_bucket_by_id
from ...core.async_cleanup import await_cancellation_complete
from ...core.config import override_settings
from ...core.operations import OperationLifecycle
from ...core.time.clock import now
from ...domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
    release_bundled_indexed_authority,
)
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.deadlines.models import TaxpayerProfile
from ..operation_composition import compose_operation_dependencies
from ..workbench_generation_composition import compose_secure_workbench_generation_provider
from .automation_execution import WorkerAutomationAdministration
from .operation_authority import ProfileWorkerOperationAuthority, WorkerOperationBinding

_PROJECTION_DOCUMENT = TypeAdapter(dict[str, JsonValue])


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

    def _bind_execution(self, registry: OperationRegistry) -> ProfileWorkerOperationAuthority:
        self._execution = ProfileWorkerOperationAuthority(
            custody=self.custody, client=self._client, registry=registry, authority_operation=self._pinned()
        )
        return self._execution

    def _composed(self) -> OperationComposedServices:
        if self._closed:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        if self._services is None:
            with validating_governed_facts(self._pinned()):
                self._services = compose_operation_dependencies(
                    authority_operation=self._pinned(),
                    execution_authority_factory=self._bind_execution,
                    automation_inventory_reader=self._automation_inventory,
                    automation_administration_factory=self._automation_administration,
                    workbench_generation_reader=self._workbench_generation,
                    profile_rotation_finalizer=self._finalize_password_rotation,
                    modelo_profile_resolver=self._modelo_profile,
                )
        return self._services

    def prepare(self) -> None:
        """Finish cold registry composition before any admitted lease is published.

        The first contract and submission retain their ordinary short worker
        exchange deadlines. Admission owns this one-time compilation cost while
        the profile is already pinned and before a client can start an operation.
        """
        self._composed()

    def _modelo_profile(self, operation: PinnedAuthorityOperation) -> TaxpayerProfile:
        """Read filing facts only from this worker's immutable profile custody."""
        profile_id = str(self.custody.identity.binding.profile_id)
        repository = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=operation.profile_decode_context()
        )
        record = repository.load(profile_id)
        if str(record.profile_id) != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return projection_for_taxpayer(record, schema=repository.session.profile_decode_context.schema)

    async def _finalize_password_rotation(
        self, context: OperationExecutorContext, outcome: ProfilePassphraseRotationOutcome
    ) -> None:
        """Retire original custody after encrypted result persistence in COMMIT."""
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        self._execution.retire_password_successor(context.identity, outcome)

    async def _workbench_generation(
        self, context: OperationExecutorContext, payload: WorkbenchGenerationOperationRequest
    ) -> WorkbenchGenerationV1:
        """Retain native read authority through one exact-profile generation capture."""
        execution, services = self._execution, self._services
        if execution is None or services is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

        def account_session() -> HomeAccountSession:
            execution.workbench_session(context.identity, payload)
            profile = read_profile_bucket_by_id(str(payload.profile_id), root=self.custody.root)
            if profile is None or profile.bucket_id != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            lease = execution.workbench_session(context.identity, payload)
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

        async with execution.guard(context.identity, AccessAction.START):
            return await await_cancellation_complete(
                asyncio.to_thread(capture), task_name="runtime-workbench-generation"
            )

    def _automation_administration(
        self, context: OperationExecutorContext, profile_id: UUID
    ) -> WorkerAutomationAdministration:
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return WorkerAutomationAdministration(self._execution, context.identity, profile_id)

    async def _automation_inventory(self, context: OperationExecutorContext, profile_id: UUID) -> AutomationInventory:
        """Use the canonical operation identity, never caller-supplied authority facts."""
        if self._execution is None or self._closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return await self._execution.automation_inventory(context.identity, profile_id)

    def _pinned(self) -> PinnedAuthorityOperation:
        if self._authority is None:
            self._authority = self._lifetime.enter_context(bundled_indexed_authority().lease_operation())
        return self._authority

    def profile_decode_context(self) -> ProfileDecodeContext:
        """Use the same publication for password candidates and hosted operations."""
        return self._pinned().profile_decode_context()

    async def _require_current_inventory(self) -> None:
        """Refuse unreadable startup state before any hosted private operation.

        Inventory only checks the current journal format. It neither takes over
        owner leases nor replays work. Each requested continuation still resolves
        encrypted provenance and goes through canonical lease reconciliation.
        """
        async with self._inventory_lock:
            if self._inventory_verified:
                return
            services = self._composed()
            after = None
            refused = False
            try:
                while True:
                    page = await services.recovery_inventory(after=after, limit=128)
                    refused |= any(
                        entry.disposition is OperationRecoveryInventoryDisposition.REFUSED for entry in page.entries
                    )
                    if not page.has_more:
                        break
                    after = page.next_cursor
            except (RepositoryError, ValueError):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
            if refused or self._closed:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            self._inventory_verified = True

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
                    else:
                        # Replay does not revive the original response bearer.
                        execution.discard(operation_id)
                    return submitted
            except (RepositoryError, OperationSubjectBusyError):
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
            with validating_governed_facts(self._pinned()):
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
        wait = asyncio.timeout(timeout)
        try:
            async with wait:
                supervisor = services.submission.supervisor
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
                frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
                or original is None
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
        binding = WorkerOperationBinding(session_id, frontend, invocation.request, invocation.provenance)
        async with execution.guard_binding(invocation.identity, AccessAction.RESUME, binding):
            execution.bind_reentry(operation_id, binding)
        try:
            # START/RESUME at actual entry and COMMIT each acquire fresh guards.
            with validating_governed_facts(self._pinned()):
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
        try:
            invocation = await self._stored_invocation(operation_id)
            binding = WorkerOperationBinding(session_id, frontend, invocation.request, invocation.provenance)
            async with execution.guard_binding(invocation.identity, action, binding) as authorization:
                if invocation.identity.definition_id == WORKBENCH_GENERATION_OPERATION_DEFINITION_ID:
                    execution.require_owner(operation_id, session_id, frontend=frontend)
                yield authorization
        finally:
            self._output_tasks.pop(task, None)

    async def _stored_invocation(
        self, operation_id: OperationId, *, require_idle: bool = False
    ) -> OperationStoredInvocation:
        try:
            with validating_governed_facts(self._pinned()):
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
        self.contract(session_id, definition_id)
        if self._execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        try:
            with validating_governed_facts(self._pinned()):
                payload = self._execution.registry.decode_request_payload(definition_id, payload_json)
        except (ValueError, TypeError, RecursionError):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
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
            # The worker admitted the process-shared owner for this lease; close its
            # database handles with the host rather than at interpreter teardown.
            release_bundled_indexed_authority()
        return result
