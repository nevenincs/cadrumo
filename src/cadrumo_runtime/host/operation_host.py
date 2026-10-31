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
from collections.abc import AsyncGenerator
from contextlib import AbstractContextManager, ExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from pydantic import BaseModel, JsonValue, TypeAdapter

from cadrumo.adapters.persistence.storage.errors import RepositoryError
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.application.operations.errors import OperationSubjectBusyError
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.models import (
    OperationId,
    OperationIdentity,
    OperationRequest,
    OperationStoredInvocation,
    new_operation_id,
)
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.secret_submission import OperationSecretRequirement, zeroize_secret_buffer
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.config import override_settings
from cadrumo.core.logging import get_logger
from cadrumo.core.operations import OperationDurability, OperationEffect, OperationLifecycle
from cadrumo.core.startup_phase_log import startup_phase
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.operation_access import (
    OperationManagementRequest,
)
from cadrumo_client.contracts.projection_pages import (
    EncodedProjectionDocument,
    ProjectionPage,
    ProjectionPageRequest,
    encode_projection_document,
    project_encoded_page,
)

from .operation_input_admission import submit_financial_input, submit_payload
from .operation_progress_reporter import OperationProgressReporter
from .operation_review_management import manage_operation
from .operation_settlement import settle_lapsed_operations, settlement, verify_inventory

if TYPE_CHECKING:
    from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
    from cadrumo.application.operations.composition import OperationComposedServices, OperationSubmission
    from cadrumo.application.operations.execution_actor import OperationExecutionCaller
    from cadrumo.application.operations.registry import (
        OperationFrontendProjection,
        OperationPublicDefinitionContractV1,
        OperationPublicDefinitionDescriptionV1,
        OperationRegistry,
    )
    from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
    from cadrumo.application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
    from cadrumo.application.workbench_generation_contracts import WorkbenchGenerationV1
    from cadrumo.application.workbench_generation_operation import WorkbenchGenerationOperationRequest
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from cadrumo.domain.deadlines.models import TaxpayerProfile
    from cadrumo_client.contracts.view_stream import ViewStreamSink, ViewStreamSinks
    from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorityRequest

    from ..adapters.worker_authorization_client import WorkerAuthorizationClient
    from .automation_execution import WorkerAutomationAdministration
    from .operation_authority import ProfileWorkerOperationAuthority

_PROJECTION_DOCUMENT = TypeAdapter(dict[str, JsonValue])
_PAGED_PROJECTION_DOCUMENT = TypeAdapter(dict[str, Any])
_log = get_logger(__name__)
_PRIVATE_RESULT_RELEASE_ACTIONS = frozenset({AccessAction.RESULT, AccessAction.REVIEW})
# What the first composition imports: its own entry points, the persistence and
# supervisor modules it binds, and the profile operations a session reads first.
_COMPOSITION_MODULES = (
    "cadrumo.entrypoints.operation_composition",
    "cadrumo.adapters.persistence.operations.durability_router",
    "cadrumo.adapters.persistence.operations.journal",
    "cadrumo.adapters.persistence.operations.lease",
    "cadrumo.adapters.persistence.operations.secure_references",
    "cadrumo.adapters.persistence.operations.typed_financial_operand_custody",
    "cadrumo.application.operations.composition",
    "cadrumo.application.user_profile.operations",
)


def _projection_document(result: BaseModel, *, paged: bool) -> dict[str, JsonValue]:
    """Keep the full result shape and validate the paged document root once."""
    serialized = result.model_dump(mode="json", serialize_as_any=True)
    if paged:
        # Pydantic already serialized the full model; the page encoder checks
        # each value's JSON compatibility while producing canonical bytes.
        return cast("dict[str, JsonValue]", _PAGED_PROJECTION_DOCUMENT.validate_python(serialized))
    return _PROJECTION_DOCUMENT.validate_python(serialized)


def _projection_target(
    request: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1,
) -> tuple[OperationId, AccessAction]:
    """Name the operation a projection reads and the disclosure it asks for."""
    if isinstance(request, OperationResultProjectionRequestV1):
        return request.operation_id, AccessAction.RESULT
    return request.reference.operation_id, AccessAction.REVIEW


@dataclass(frozen=True, slots=True)
class _PagedDelivery:
    """The one result being delivered in pages, with what its later pages reuse.

    Its invocation and document are immutable once resolved. Reusing them spares
    no authority check: every page still takes the disclosure guard, and the
    settled result is still rechecked. Held for as long as the result snapshot.
    """

    operation_id: OperationId
    session_id: UUID
    frontend: OperationFrontendProjection
    invocation: OperationStoredInvocation
    result: BaseModel
    document: EncodedProjectionDocument


class ProfileWorkerOperationHost:
    """Own the existing services and publication lease, never a second dispatcher."""

    def __init__(
        self,
        custody: ProfileWorkerCustody,
        *,
        authorization: WorkerAuthorizationClient,
        view_streams: ViewStreamSinks | None = None,
    ) -> None:
        """Defer publication and backend loading until a governed capability needs it.

        ``view_streams`` opens the worker's view channel for a running Sede view;
        without it the view refuses every run.
        """
        self.custody = custody
        self._view_streams = view_streams
        self._lifetime = ExitStack()
        self._authority: PinnedAuthorityOperation | None = None
        self.services: OperationComposedServices | None = None
        self._client = authorization
        # Committed operations reach the runtime as a cue to their observers.
        self._record_effects: set[OperationId] = set()
        self._record_effects_guard = RLock()
        self._progress = OperationProgressReporter(self._report_progress)
        self.execution: ProfileWorkerOperationAuthority | None = None
        self.closed = False
        self._drain_result: OperationDrainResult | None = None
        self._output_tasks: dict[asyncio.Task[object], OperationId] = {}
        self._paged_delivery: _PagedDelivery | None = None
        self.submissions: dict[OperationId, tuple[UUID, OperationSubmission]] = {}
        self.inventory_lock = asyncio.Lock()
        self.inventory_verified = False
        # Every operation that may still be unsettled: the journal's unsettled
        # records at first use, and each admission since.
        self.unsettled: set[OperationId] = set()
        self.lapse_lock = asyncio.Lock()
        self.lapse_checked_at: float | None = None
        # One composition and one authority lease, whichever thread asks first:
        # a worker thread serving an operation or the service loop.
        self._composition_lock = RLock()
        # The idle import of the composition graph. A sign-in never waits for
        # it; a composition does, so the two never import the graph at once.
        self._imports_lock = RLock()

    def _report_progress(self, operation_ids: tuple[OperationId, ...]) -> None:
        with self._record_effects_guard:
            affected = self._record_effects.intersection(operation_ids)
        self._client.operations_advanced(operation_ids, records_changed=bool(affected))
        with self._record_effects_guard:
            self._record_effects.difference_update(affected)

    def _journal_committed(self, snapshot: OperationPersistedSnapshot) -> None:
        """Queue progress and a value-free invalidation after a settled record effect."""
        if snapshot.lifecycle is OperationLifecycle.TERMINAL and snapshot.effect is not OperationEffect.NONE:
            with self._record_effects_guard:
                self._record_effects.add(snapshot.operation_id)
        self._progress.committed(snapshot.operation_id)

    def _bind_execution(self, registry: OperationRegistry) -> ProfileWorkerOperationAuthority:
        from .operation_authority import ProfileWorkerOperationAuthority

        self.execution = ProfileWorkerOperationAuthority(
            custody=self.custody, client=self._client, registry=registry, authority_operation=self.pinned()
        )
        return self.execution

    def governed(self) -> AbstractContextManager[None]:
        """Scope governed facts to this worker's one pinned authority generation."""
        from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

        return validating_governed_facts(self.pinned())

    def composed(self) -> OperationComposedServices:
        """Return the lazily composed services while the worker is open."""
        if self.closed:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        services = self.services
        if services is not None:
            return services
        with self._imports_lock, self._composition_lock:
            if self.closed:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            if self.services is None:
                started = monotonic()
                self.services = self._compose()
                _log.info(
                    "worker operation composition total_seconds=%.3f (includes cold imports)", monotonic() - started
                )
            return self.services

    def _await_composition(self) -> None:
        with self._composition_lock:
            return

    async def composed_off_loop(self) -> OperationComposedServices:
        """Join or start the one composition without holding the service loop.

        The first operation after a person's sign-in composes the registry; the
        loop keeps serving sign-ins and status on the other channel meanwhile.
        """
        if self.services is not None:
            return self.composed()
        return await asyncio.to_thread(self.composed)

    def _compose(self) -> OperationComposedServices:
        from cadrumo.entrypoints.operation_composition import compose_operation_dependencies

        with startup_phase(_log, "worker_operation_compose"), self.governed():
            return compose_operation_dependencies(
                authority_operation=self.pinned(),
                operation_owner_id=self.custody.identity.operation_owner_id,
                execution_authority_factory=self._bind_execution,
                automation_inventory_reader=self._automation_inventory,
                automation_administration_factory=self._automation_administration,
                workbench_generation_reader=self._workbench_generation,
                profile_rotation_finalizer=self._finalize_password_rotation,
                modelo_profile_resolver=self._modelo_profile,
                execution_caller_reader=self._execution_caller,
                sede_view_stream_opener=None if self._view_streams is None else self._open_sede_view,
                journal_committed=self._journal_committed,
            )

    def warm_imports(self) -> None:
        """Import the composition's module graph while the worker waits for its first operation.

        A watched profile's worker starts before its password is typed and
        reaches readiness without this graph. Loading it now, key-free, keeps
        it off the first operation. A composition that starts meanwhile waits
        for these imports instead of racing them; a sign-in does not.
        """
        with self._imports_lock:
            if self.closed or self.services is not None:
                return
            with startup_phase(_log, "worker_operation_imports"):
                for module in _COMPOSITION_MODULES:
                    import_module(module)

    def in_flight_operation_count(self) -> int:
        """Read the owning supervisor without creating services or touching custody."""
        services = self.services
        return 0 if services is None else services.submission.supervisor.in_flight_operation_count()

    def prepare(self) -> None:
        """Finish cold registry composition before the caller continues.

        Key-based admission keeps this one-time cost inside its own preparation
        budget. A person's sign-in never composes: the first operation a
        session asks for does, off the service loop.
        """
        with startup_phase(_log, "worker_operation_prepare"):
            self.composed()

    def _execution_caller(self, identity: OperationIdentity) -> OperationExecutionCaller:
        """Answer from this worker's own admission binding, never from caller-supplied facts."""
        if self.execution is None or self.closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return self.execution.execution_caller(identity)

    def _open_sede_view(self, identity: OperationIdentity) -> ViewStreamSink:
        """Open the view stream bound to the desktop session that admitted this exact view."""
        streams = self._view_streams
        if streams is None or self.execution is None or self.closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        session_id = self.execution.sede_view_session(identity)
        return streams.open_view(operation_id=identity.operation_id, session_id=session_id)

    def _modelo_profile(self, operation: PinnedAuthorityOperation) -> TaxpayerProfile:
        """Read filing facts only from this worker's immutable profile custody."""
        from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
        from cadrumo.application.user_profile.projections import projection_for_taxpayer

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
        if self.execution is None or self.closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        await self.execution.retire_password_successor(identity, outcome)

    async def _workbench_generation(
        self, identity: OperationIdentity, payload: WorkbenchGenerationOperationRequest
    ) -> WorkbenchGenerationV1:
        """Retain native read authority through one exact-profile generation capture."""
        from cadrumo.application.overview.home import HomeAccountSession, HomeSessionPosture
        from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id
        from cadrumo.entrypoints.workbench_generation_composition import compose_secure_workbench_generation_provider

        execution, services = self.execution, self.services
        if execution is None or services is None or self.closed:
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
                    operation=self.pinned(),
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
        if self.execution is None or self.closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        from .automation_execution import WorkerAutomationAdministration

        return WorkerAutomationAdministration(self.execution, identity, profile_id)

    async def _automation_inventory(self, identity: OperationIdentity, profile_id: UUID) -> AutomationInventory:
        """Use the canonical operation identity, never caller-supplied authority facts."""
        if self.execution is None or self.closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return await self.execution.automation_inventory(identity, profile_id)

    def pinned(self) -> PinnedAuthorityOperation:
        """Return this worker’s pinned authority lease."""
        authority = self._authority
        if authority is not None:
            return authority
        from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

        with self._composition_lock:
            if self._authority is None:
                self._authority = self._lifetime.enter_context(bundled_indexed_authority().lease_operation())
            return self._authority

    def profile_decode_context(self) -> ProfileDecodeContext:
        """Use the same publication for password candidates and hosted operations."""
        return self.pinned().profile_decode_context()

    async def require_current_inventory(self) -> None:
        """Refuse unreadable startup state before any hosted private operation.

        Inventory only checks the current journal format and notes which records
        are unsettled. It replays no work. Each requested continuation still
        resolves encrypted provenance and goes through canonical lease
        reconciliation; only operations whose owner lapsed are then settled.
        """
        await self._verify_inventory()
        await self._settle_lapsed_operations()

    async def _verify_inventory(self) -> None:
        await verify_inventory(self)

    def _track_unsettled(self, operation_id: OperationId, definition_id: str) -> None:
        """Note an admission whose owner the lapse sweep may one day have to settle.

        An ephemeral operation is never noted: it ends with this worker, and
        once memory forgets it the durable journal the sweep would read never
        held it, so settling it would only take the journal lock and fail.
        """
        registry = self.composed().submission.supervisor.registry
        if registry.lookup_public_contract(definition_id).durability is not OperationDurability.EPHEMERAL:
            self.unsettled.add(operation_id)

    def release_delivered_result(self, operation_id: OperationId) -> None:
        """Forget an ephemeral operation once its whole result has been written to its reader.

        Its result is decrypted profile data in plain memory; a reader that
        needs it again reads the profile again, which has no effect.
        """
        delivery = self._paged_delivery
        if delivery is not None and delivery.operation_id == operation_id:
            self._paged_delivery = None
        services = self.services
        if services is not None:
            services.release_ephemeral_result(operation_id)

    def forget_settled_ephemeral(self) -> None:
        """Forget pending private projections: the worker outlives its last session, its reads do not."""
        self._paged_delivery = None
        services = self.services
        if services is not None:
            services.forget_settled_ephemeral()

    async def _settle_lapsed_operations(self) -> None:
        await settle_lapsed_operations(self)

    def contract(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionContractV1:
        """Resolve an allowed definition from the real production service inventory."""
        lease = self.custody.require(session_id)
        if definition_id not in lease.scope.operations:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        for definition in self.composed().public_contracts.definitions:
            if definition.definition_id == definition_id:
                self.custody.require(session_id)
                return definition
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def describe(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionDescriptionV1:
        """Bind discovery to the same live custody and exact registered request model."""
        self.contract(session_id, definition_id)
        description = self.composed().observation.registry.describe_public_definition(definition_id)
        self.custody.require(session_id)
        return description

    async def submit(
        self, *, session_id: UUID, frontend: OperationFrontendProjection, request: OperationRequest[BaseModel]
    ) -> OperationSubmission:
        """Admit a fresh invocation through the canonical supervisor and live authority."""
        await self.custody.require_off_loop(session_id)
        await self.require_current_inventory()
        services = self.composed()
        execution = self.execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        from .worker_operation_binding import WorkerOperationBinding

        operation_id = new_operation_id()
        await execution.bind(operation_id, WorkerOperationBinding(session_id, frontend, request))

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
                        provenance=await execution.capture_provenance(identity),
                    )
                    if submitted.receipt.operation_id == operation_id:
                        self.submissions[operation_id] = session_id, submitted
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
        await self._require_owner(operation_id, session_id)
        await self.require_current_inventory()
        try:
            with self.governed():
                return await self.composed().submission.start(operation_id)
        except (RepositoryError, ValueError):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    async def settlement(self, identity: OperationIdentity, *, timeout: float) -> bool:
        """Wait for the admitted rotation's terminal journal."""
        return await settlement(self, identity, timeout=timeout)

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
            await self._require_owner(operation_id, session_id)
            original = self.submissions.get(operation_id)
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
                        await self.composed().submission.require_secret_ready(requirement)
                    else:
                        await await_cancellation_complete(
                            self.composed().submission.submit_secret(requirement, secret),
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
        await self.custody.require_off_loop(session_id)
        await self.require_current_inventory()
        services = self.composed()
        invocation = await self.stored_invocation(operation_id, require_idle=True)
        execution = self.execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        from .worker_operation_binding import WorkerOperationBinding

        binding = WorkerOperationBinding(session_id, frontend, invocation.request, invocation.provenance)
        async with execution.guard_binding(invocation.identity, AccessAction.RESUME, binding):
            await execution.bind_reentry(operation_id, binding)
        try:
            # START/RESUME at actual entry and COMMIT each acquire fresh guards.
            with self.governed():
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
                self.composed().observation.observe(request), task_name="profile-operation-observation"
            )
            yield observed, authorization

    @asynccontextmanager
    async def release(
        self, session_id: UUID, operation_id: OperationId, frontend: OperationFrontendProjection, action: AccessAction
    ) -> AsyncGenerator[WorkerAuthorityRequest]:
        """Bind each internal projection to policy the runtime must recheck on final output."""
        async with self._release_invocation(session_id, operation_id, frontend, action) as (authorization, _invocation):
            yield authorization

    @asynccontextmanager
    async def _release_invocation(
        self,
        session_id: UUID,
        operation_id: OperationId,
        frontend: OperationFrontendProjection,
        action: AccessAction,
        *,
        retained: OperationStoredInvocation | None = None,
    ) -> AsyncGenerator[tuple[WorkerAuthorityRequest, OperationStoredInvocation]]:
        """Hold the release guard over ``retained``, or over the invocation read afresh."""
        await self.custody.require_off_loop(session_id)
        await self.require_current_inventory()
        self.composed()
        execution = self.execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        task = asyncio.current_task()
        if task is None or task in self._output_tasks:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._output_tasks[task] = operation_id
        from cadrumo.application.workbench_generation_identity import WORKBENCH_GENERATION_OPERATION_DEFINITION_ID

        from .worker_operation_binding import WorkerOperationBinding

        try:
            invocation = retained if retained is not None else await self.stored_invocation(operation_id)
            binding = WorkerOperationBinding(session_id, frontend, invocation.request, invocation.provenance)
            async with execution.guard_binding(invocation.identity, action, binding) as authorization:
                # The full-owner workbench projection is released only to the
                # session that generated it; observing its lifecycle discloses
                # operation metadata alone and stays caller-independent.
                if (
                    action in _PRIVATE_RESULT_RELEASE_ACTIONS
                    and invocation.identity.definition_id == WORKBENCH_GENERATION_OPERATION_DEFINITION_ID
                ):
                    await execution.require_owner(operation_id, session_id)
                yield authorization, invocation
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
        original = self.submissions.get(operation_id)
        if original is None or original[0] != session_id:
            # A replayed receipt names an earlier admission, which keeps its own course.
            return
        reason = (
            refusal
            if isinstance(refusal, ProfileAccessRefusedError)
            else ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
        )
        try:
            await self.composed().submission.supervisor.settle_refused_start(operation_id, reason)
        except (RepositoryError, ValueError):
            _log.warning("undelivered admission left unsettled operation=%s", operation_id)
            return
        self.submissions.pop(operation_id, None)
        if self.execution is not None:
            self.execution.discard(operation_id)

    async def stored_invocation(
        self, operation_id: OperationId, *, require_idle: bool = False
    ) -> OperationStoredInvocation:
        """Read an invocation through the governed operation store."""
        try:
            with self.governed():
                return await self.composed().submission.stored_invocation(operation_id, require_idle=require_idle)
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
        operation_id, action = _projection_target(request)
        async with self.release(session_id, operation_id, frontend, action) as authorization:
            result = await self._resolve_projection(request, session_id, frontend, page=None)
            yield _projection_document(result, paged=False), authorization

    @asynccontextmanager
    async def project_page(
        self,
        session_id: UUID,
        request: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1,
        *,
        frontend: OperationFrontendProjection,
        page: ProjectionPageRequest,
    ) -> AsyncGenerator[tuple[ProjectionPage, WorkerAuthorityRequest]]:
        """Release one page, reusing only what the same delivery already resolved.

        Every page takes the disclosure guard and rechecks the settled result; a
        later page spares the invocation read and the whole-document encoding.
        """
        operation_id, action = _projection_target(request)
        held = self._paged_delivery
        continued = (
            held
            if page.offset > 0
            and held is not None
            and held.operation_id == operation_id
            and held.session_id == session_id
            and held.frontend is frontend
            else None
        )
        async with self._release_invocation(
            session_id,
            operation_id,
            frontend,
            action,
            retained=None if continued is None else continued.invocation,
        ) as (authorization, invocation):
            result = await self._resolve_projection(request, session_id, frontend, page=page)
            if continued is not None and continued.result is result:
                document = continued.document
            else:
                document = encode_projection_document(_projection_document(result, paged=True))
                self._paged_delivery = _PagedDelivery(operation_id, session_id, frontend, invocation, result, document)
            yield project_encoded_page(document, page), authorization

    async def _resolve_projection(
        self,
        request: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        *,
        page: ProjectionPageRequest | None,
    ) -> BaseModel:
        """Resolve the registered public model; a polymorphic one keeps its validated fields when dumped."""
        services = self.composed()
        if isinstance(request, OperationResultProjectionRequestV1):
            return await await_cancellation_complete(
                services.result.resolve(
                    request,
                    BaseModel,
                    snapshot_scope=(session_id, frontend) if page is not None else None,
                    continue_snapshot=page is not None and page.offset > 0,
                ),
                task_name="profile-operation-result",
            )
        return await await_cancellation_complete(
            services.review.resolve(request, BaseModel), task_name="profile-operation-review"
        )

    async def _require_owner(self, operation_id: OperationId, session_id: UUID) -> None:
        if self.execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        await self.execution.require_owner(operation_id, session_id)

    @asynccontextmanager
    async def manage(
        self,
        session_id: UUID,
        request: OperationManagementRequest,
        *,
        frontend: OperationFrontendProjection,
    ) -> AsyncGenerator[tuple[dict[str, JsonValue], WorkerAuthorityRequest]]:
        """Manage an operation under its response and release authority."""
        async with manage_operation(self, session_id, request, frontend=frontend) as result:
            yield result

    async def submit_financial_input(
        self,
        *,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        input_json: str,
    ) -> OperationSubmission:
        """Admit transient financial input through its registered contract."""
        return await submit_financial_input(
            self,
            session_id=session_id,
            frontend=frontend,
            definition_id=definition_id,
            subject_ref=subject_ref,
            input_json=input_json,
        )

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
        """Admit a decoded registered operation payload."""
        return await submit_payload(
            self,
            session_id=session_id,
            frontend=frontend,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload_json=payload_json,
            idempotency_key=idempotency_key,
        )

    async def close(self) -> OperationDrainResult:
        """Bound canonical drain; retain publication while native containment is required."""
        if self._drain_result is not None:
            return self._drain_result
        self.closed = True
        # A composition an operation already started finishes, off the loop, and
        # is drained like any other; none can start once the host is closed.
        await await_cancellation_complete(
            asyncio.to_thread(self._await_composition), task_name="profile-operation-compose-join"
        )
        result = (
            await await_cancellation_complete(
                self.services.drain(timedelta(seconds=5)), task_name="profile-operation-drain"
            )
            if self.services is not None
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
        # The drain's settlements are reported before the host lets go.
        await await_cancellation_complete(
            asyncio.to_thread(self._progress.close), task_name="profile-operation-progress-close"
        )
        if not result.needs_containment:
            self._lifetime.close()
            if self._authority is not None:
                from cadrumo.domain.calculations.registry.authority import release_bundled_indexed_authority

                # The worker admitted the process-shared owner for this lease; close its
                # database handles with the host rather than at interpreter teardown.
                release_bundled_indexed_authority()
        return result
