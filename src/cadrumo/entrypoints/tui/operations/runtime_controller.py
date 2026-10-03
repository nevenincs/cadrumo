"""TUI operation control over an exact authenticated runtime connection."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel, JsonValue, RootModel, TypeAdapter, ValidationError

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationResponseControlResultV1,
    OperationResponseMutationResultV1,
    OperationReviewProjectionResultV1,
)
from ....application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from ....application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from ....application.operations.models import OperationId, OperationRevision
from ....application.operations.persistence.replay import OperationReplayLimit
from ....application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.deadline_budget import remaining_budget
from ....application.runtime.operation_access import (
    OperationManagementRequest,
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationManaged,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ....core.async_cleanup import await_cancellation_complete
from ....core.hashing import canonical_json_bytes
from ....core.operations import OperationLifecycle, OperationTerminalCondition

_CANCELLATION = TypeAdapter[OperationCancellationResultV1](OperationCancellationResultV1)
_DETACH = TypeAdapter[OperationDetachResultV1](OperationDetachResultV1)
_RESPONSE_CONTROL = TypeAdapter[OperationResponseControlResultV1](OperationResponseControlResultV1)
_RESPONSE_MUTATION = TypeAdapter[OperationResponseMutationResultV1](OperationResponseMutationResultV1)


def _settled_result_expected[ResultT: BaseModel](
    projection: OperationPublicProjectionV1,
    result_type: type[ResultT],
    result_version: int,
) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(
        schema_id=projection.definition_id + ".result",
        schema_version=result_version,
        model_type=result_type,
    )


def _settled_result_is_readable(
    controller: RuntimeOperationController,
    projection: OperationPublicProjectionV1,
    expected: OperationSchemaIdentityV1,
    *,
    allow_refusal_detail: bool,
) -> bool:
    contract = projection.definition_contract
    eligible_terminal = (
        projection.terminal_condition is OperationTerminalCondition.SUCCEEDED and projection.result_ref is not None
    ) or (
        allow_refusal_detail
        and projection.terminal_condition is OperationTerminalCondition.REFUSED
        and projection.refusal_ref in contract.refusal_detail_codes
    )
    return not (
        controller.client.session_id != controller.session_id
        or projection.operation_id != controller.operation_id
        or contract.definition_id != projection.definition_id
        or contract.result_schema != expected
        or projection.lifecycle is not OperationLifecycle.TERMINAL
        or not eligible_terminal
    )


def _parse_settled_result[ResultT: BaseModel](
    document: dict[str, JsonValue], result_type: type[ResultT]
) -> OperationResultProjectionSuccessV1[ResultT]:
    try:
        encoded = canonical_json_bytes(document)
        if document.get("outcome") == "refused":
            refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
            raise RuntimeFrontendRefusedError(refusal.code.value)
        # CAST-RATIONALE-TUI-SETTLED-RESULT-GENERIC: Pydantic's runtime
        # specialization binds the success envelope's projection field to
        # this exact result_type; __class_getitem__ has an overly broad
        # typing stub, so restore that generic result for static checking.
        success_type = cast(
            "type[OperationResultProjectionSuccessV1[ResultT]]",
            OperationResultProjectionSuccessV1.__class_getitem__(result_type),
        )
        result = success_type.model_validate_json(encoded)
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    return result


def _settled_result_matches_binding[ResultT: BaseModel](
    result: OperationResultProjectionSuccessV1[ResultT],
    expected: OperationSchemaIdentityV1,
    contract_digest: str,
    *,
    current_session_id: UUID,
    session_id: UUID,
) -> bool:
    return (
        result.result_schema == expected
        and result.definition_contract_digest == contract_digest
        and current_session_id == session_id
    )


class RuntimeReviewDocument(RootModel[dict[str, JsonValue]]):
    """Preserve a registered server-validated review for the generic modal renderer.

    The enclosing review envelope is checked against the exact schema identity
    and contract digest before this transport document is exposed. Specific
    renderers instead request their canonical projection model directly.
    """


@dataclass(frozen=True, slots=True)
class RuntimeOperationController:
    """Retain one submitted operation's original connection and actor binding."""

    client: RuntimeFrontendClient = field(repr=False)
    operation_id: OperationId
    session_id: UUID
    deadline: float | None = None

    def __post_init__(self) -> None:
        """Refuse another frontend or an already replaced application session."""
        if self.client.frontend is not OperationFrontendProjection.TUI or self.client.session_id != self.session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    @property
    def actor_ref(self) -> str:
        """Name the runtime-assigned submission actor; this is not response proof."""
        return f"session:{self.session_id}"

    async def _exchange(self, request: RuntimeOperationRequest) -> RuntimeOperationReply:
        if self.client.session_id != self.session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        # Cancellation cannot leave an unowned native exchange running while
        # the modal tears down its connection. It never implies rollback.
        reply = await await_cancellation_complete(
            asyncio.to_thread(self.client.operation, request, deadline=self._call_deadline()),
            task_name="tui-runtime-operation",
        )
        if self.client.session_id != self.session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        return reply

    def _call_deadline(self) -> float:
        deadline = time.monotonic() + 30
        if self.deadline is not None:
            deadline = min(deadline, self.deadline)
        if deadline <= time.monotonic():
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        return deadline

    @classmethod
    async def submit(
        cls,
        client: RuntimeFrontendClient,
        *,
        definition_id: str,
        subject_ref: str,
        payload: BaseModel,
        idempotency_key: str | None = None,
        deadline: float | None = None,
        expected_session_id: UUID | None = None,
    ) -> RuntimeOperationController:
        """Submit a registered request without transferring response capabilities."""
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        session_id = client.session_id
        if expected_session_id is not None and session_id != expected_session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        exchange_deadline = min(time.monotonic() + 30, deadline) if deadline is not None else time.monotonic() + 30
        if exchange_deadline <= time.monotonic():
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        contract = await await_cancellation_complete(
            asyncio.to_thread(client.contract, definition_id, deadline=exchange_deadline),
            task_name="tui-runtime-definition",
        )
        if contract.ephemeral_secret_required:
            # This door carries credential-free operands only. Refuse before
            # persisting work whose separate secret handoff is not composed.
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if client.session_id != session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        request = RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=session_id,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload_json=payload.model_dump_json(),
            idempotency_key=idempotency_key,
        )
        reply = await await_cancellation_complete(
            asyncio.to_thread(client.operation, request, deadline=exchange_deadline),
            task_name="tui-runtime-submission",
        )
        if not isinstance(reply, RuntimeOperationSubmitted) or reply.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if client.session_id != session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        return cls(client=client, operation_id=reply.receipt.operation_id, session_id=session_id, deadline=deadline)

    async def read_settled_result[ResultT: BaseModel](
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[ResultT],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> ResultT:
        """Read one exact registered terminal result through current disclosure."""
        contract = projection.definition_contract
        expected = _settled_result_expected(projection, result_type, result_version)
        if not _settled_result_is_readable(self, projection, expected, allow_refusal_detail=allow_refusal_detail):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        request = OperationResultProjectionRequestV1(
            operation_id=self.operation_id,
            terminal_revision=projection.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=expected,
        )
        document = await await_cancellation_complete(
            asyncio.to_thread(
                self.client.read_result_document,
                request,
                deadline=self._call_deadline(),
            ),
            task_name="tui-runtime-result",
        )
        result = _parse_settled_result(document, result_type)
        if not _settled_result_matches_binding(
            result,
            expected,
            contract.definition_contract_digest,
            current_session_id=self.client.session_id,
            session_id=self.session_id,
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return result.projection

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        """Read a refused or failed operation's recorded public detail, or ``None`` when it has none.

        The detail is presentation. An operation that recorded none, a session
        that may no longer read it, or a malformed document leaves the caller
        with the registered code the projection already carries.
        """
        if (
            self.client.session_id != self.session_id
            or projection.operation_id != self.operation_id
            or projection.lifecycle is not OperationLifecycle.TERMINAL
            or projection.terminal_condition
            not in {OperationTerminalCondition.REFUSED, OperationTerminalCondition.FAILED}
        ):
            return None
        contract = projection.definition_contract
        schema = operation_error_detail_schema()
        request = OperationResultProjectionRequestV1(
            operation_id=self.operation_id,
            terminal_revision=projection.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=schema,
        )
        try:
            document = await await_cancellation_complete(
                asyncio.to_thread(self.client.read_result_document, request, deadline=self._call_deadline()),
                task_name="tui-runtime-error-detail",
            )
            if document.get("outcome") == "refused":
                return None
            result = OperationResultProjectionSuccessV1[OperationErrorDetailV1].model_validate_json(
                canonical_json_bytes(document)
            )
        except (RuntimeRefusalError, RuntimeFrontendRefusedError, ValidationError):
            return None
        if (
            result.result_schema != schema
            or result.definition_contract_digest != contract.definition_contract_digest
            or self.client.session_id != self.session_id
        ):
            return None
        return result.projection

    async def start(self) -> OperationId:
        """Request canonical execution admission for the bound operation."""
        reply = await self._exchange(
            RuntimeOperationControl(
                action="operation_start",
                request_id=uuid4(),
                profile_id=self.client.profile_id,
                session_id=self.session_id,
                operation_id=self.operation_id,
            )
        )
        if not isinstance(reply, RuntimeOperationAcknowledged) or reply.operation_id != self.operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return self.operation_id

    async def observe(
        self, after_cursor: OperationEventCursor, *, page_limit: OperationReplayLimit = 256
    ) -> OperationObservationResultV1:
        """Read the canonical projection and its event cursor through fresh scope."""
        reply = await self._exchange(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=self.client.profile_id,
                session_id=self.session_id,
                observation=OperationObservationRequestV1(
                    operation_id=self.operation_id,
                    after_cursor=after_cursor,
                    page_limit=page_limit,
                ),
            )
        )
        if not isinstance(reply, RuntimeOperationObserved):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if reply.observation.outcome == "success" and reply.observation.projection.operation_id != self.operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply.observation

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        """Resolve only the original reference's registered schema and contract."""
        if reference.operation_id != self.operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        reply = await self._exchange(
            RuntimeOperationReview(
                request_id=uuid4(),
                profile_id=self.client.profile_id,
                session_id=self.session_id,
                review=OperationReviewProjectionRequestV1(reference=reference),
            )
        )
        if (
            not isinstance(reply, RuntimeOperationProjected)
            or reply.operation_id != self.operation_id
            or reply.projection_kind != "review"
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        raw = canonical_json_bytes(reply.document)
        try:
            if reply.document.get("outcome") == "refused":
                return OperationReviewProjectionRefusalV1.model_validate_json(raw)
            model = RuntimeReviewDocument if projection_type is BaseModel else projection_type
            resolved = OperationReviewProjectionSuccessV1[model].model_validate_json(raw)
        except ValidationError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        if (
            resolved.projection_schema != reference.review_projection_schema
            or resolved.definition_contract_digest != reference.definition_contract_digest
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        # When the caller explicitly asks for BaseModel, retain all registered
        # JSON fields in its transport RootModel rather than discard them.
        return cast("OperationReviewProjectionResultV1[ReviewT]", resolved)

    async def manage(self, request: OperationManagementRequest) -> dict[str, JsonValue]:
        """Use canonical controls under this operation's original session binding."""
        if request.operation_id != self.operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        reply = await self._exchange(
            RuntimeOperationManage(
                request_id=uuid4(),
                profile_id=self.client.profile_id,
                session_id=self.session_id,
                management=request,
            )
        )
        if not isinstance(reply, RuntimeOperationManaged) or reply.operation_id != self.operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply.document

    async def response_control(self, *, interaction_id: str, revision: OperationRevision) -> RuntimeResponseControl:
        """Bind response coordinates; only the runtime retains the actual bearer."""
        return RuntimeResponseControl(
            self,
            OperationResponseControlRequestV1(
                operation_id=self.operation_id,
                interaction_id=interaction_id,
                revision=revision,
                actor_ref=self.actor_ref,
            ),
        )

    async def cancel(self, *, expected_revision: OperationRevision) -> OperationCancellationResultV1:
        """Request cancellation at the reviewed revision without claiming rollback."""
        document = await self.manage(
            OperationCancellationRequestV1(operation_id=self.operation_id, expected_revision=expected_revision)
        )
        return _decode(_CANCELLATION, document)

    async def detach(self, *, expected_revision: OperationRevision) -> OperationDetachResultV1:
        """Delegate detach behavior to the registered canonical owner."""
        document = await self.manage(
            OperationDetachRequestV1(operation_id=self.operation_id, expected_revision=expected_revision)
        )
        return _decode(_DETACH, document)


async def await_terminal_projection(
    controller: RuntimeOperationController,
    *,
    definition_id: str,
    subject_ref: str,
    request_schema: OperationSchemaIdentityV1,
    deadline: float,
    poll_seconds: float = 0.05,
) -> OperationPublicProjectionV1:
    """Poll one started operation's current projection until it is terminal.

    Each poll reads only the latest projection, never the event history. A
    projection naming another operation, definition, subject or request schema
    is an invalid frame; the deadline bounds both observation and waiting.
    """
    while True:
        remaining_budget(deadline)
        observed = await controller.observe(0, page_limit=1)
        if isinstance(observed, OperationObservationRefusalV1):
            raise RuntimeFrontendRefusedError(observed.code.value)
        if not isinstance(observed, OperationObservationSuccessV1):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        state = observed.projection
        if (
            state.operation_id != controller.operation_id
            or state.definition_id != definition_id
            or state.subject_ref != subject_ref
            or state.definition_contract.request_schema != request_schema
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if state.lifecycle is OperationLifecycle.TERMINAL:
            return state
        await asyncio.sleep(min(poll_seconds, remaining_budget(deadline)))


def _decode[T](adapter: TypeAdapter[T], document: dict[str, JsonValue]) -> T:
    try:
        return adapter.validate_json(canonical_json_bytes(document))
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None


@dataclass(frozen=True, slots=True)
class RuntimeResponseControl:
    """One review binding; observation never reconstructs its server-side proof."""

    controller: RuntimeOperationController
    request: OperationResponseControlRequestV1

    async def inspect(self) -> OperationResponseControlResultV1:
        """Inspect without consuming the held runtime response capability."""
        return _decode(_RESPONSE_CONTROL, await self.controller.manage(self.request))

    async def _respond(
        self, request: OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1
    ) -> OperationResponseMutationResultV1:
        if (request.operation_id, request.interaction_id, request.revision, request.actor_ref) != (
            self.request.operation_id,
            self.request.interaction_id,
            self.request.revision,
            self.request.actor_ref,
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return _decode(_RESPONSE_MUTATION, await self.controller.manage(request))

    async def apply(self, request: OperationResponseApplyRequestV1) -> OperationResponseMutationResultV1:
        """Apply only the exact bound review through the original actor proof."""
        return await self._respond(request)

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationResultV1:
        """Reject only the exact bound review through the original actor proof."""
        return await self._respond(request)
