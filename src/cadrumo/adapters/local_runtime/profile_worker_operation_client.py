"""ProfileWorkerOperationClient for runtime-owned profile worker custody."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel

from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from ...application.operations.models import OperationId, OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionDescriptionV1
from ...application.operations.secret_submission import OperationSecretRequirement
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import OperationManagementRequest
from ...application.runtime.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerManageRequest,
    ProfileWorkerObservation,
    ProfileWorkerObserveRequest,
    ProfileWorkerOperationContract,
    ProfileWorkerOperationReceipt,
    ProfileWorkerOperationRequest,
    ProfileWorkerProjection,
    ProfileWorkerProjectionPage,
    ProfileWorkerProjectPageRequest,
    ProfileWorkerProjectRequest,
    ProfileWorkerRequest,
    ProfileWorkerResumeRequest,
    ProfileWorkerSecretRequest,
    ProfileWorkerSubmission,
    ProfileWorkerSubmissionAbortRequest,
    ProfileWorkerSubmissionBeginRequest,
    ProfileWorkerSubmissionChunkRequest,
    ProfileWorkerSubmissionFinishRequest,
    ProfileWorkerSubmitRequest,
    ProfileWorkerUploadAccepted,
)
from ...application.runtime.projection_pages import ProjectionPageRequest
from ...application.runtime.submission_payload import (
    FinancialOperandInputDescriptor,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from .profile_worker_transport import ProfileWorkerTransport


class ProfileWorkerOperationClient(ProfileWorkerTransport):
    """Own the worker capability while retaining native custody and deadlines."""

    def describe(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionDescriptionV1:
        """Read one exact canonical contract and request schema through live custody."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerContractRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    definition_id=definition_id,
                )
            ),
            ProfileWorkerOperationContract,
        )
        return OperationPublicDefinitionDescriptionV1(
            contract=result.contract, request_json_schema=result.request_json_schema
        )

    def submit[Payload: BaseModel](
        self, session_id: UUID, request: OperationRequest[Payload], *, frontend: OperationFrontendProjection
    ) -> ProfileWorkerSubmission:
        """Submit private operands only to this profile's owned canonical supervisor."""
        return self.submit_serialized(
            session_id=session_id,
            frontend=frontend,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            payload_json=request.payload.model_dump_json(),
            idempotency_key=request.idempotency_key,
        )

    def submit_serialized(
        self,
        *,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        payload_json: str,
        idempotency_key: str | None,
    ) -> ProfileWorkerSubmission:
        """Keep domain decoding at the registered owner within immutable profile custody."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerSubmitRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    definition_id=definition_id,
                    subject_ref=subject_ref,
                    payload_json=payload_json,
                    idempotency_key=idempotency_key,
                )
            ),
            ProfileWorkerSubmission,
            operation=True,
        )
        return result

    def _acknowledge_upload(self, request: ProfileWorkerRequest, upload_id: UUID, *, deadline: float) -> None:
        acknowledgement = self._exchange(
            request,
            ProfileWorkerUploadAccepted,
            operation=True,
            deadline=deadline,
        )
        if acknowledgement.upload_id != upload_id:
            self.close(deadline=deadline)
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    def begin_submission_payload(
        self,
        *,
        upload_id: UUID,
        connection_id: UUID,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        idempotency_key: str | None,
        descriptor: SubmissionPayloadDescriptor | FinancialOperandInputDescriptor,
        deadline: float,
    ) -> None:
        """Reserve a worker-local upload; canonical admission waits for finish."""
        self._acknowledge_upload(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionBeginRequest(
                    request_id=uuid4(),
                    upload_id=upload_id,
                    connection_id=connection_id,
                    session_id=session_id,
                    frontend=frontend,
                    definition_id=definition_id,
                    subject_ref=subject_ref,
                    idempotency_key=idempotency_key,
                    descriptor=descriptor,
                )
            ),
            upload_id,
            deadline=deadline,
        )

    def append_submission_payload(
        self,
        *,
        upload_id: UUID,
        connection_id: UUID,
        session_id: UUID,
        chunk: SubmissionPayloadChunk,
        deadline: float,
    ) -> None:
        """Send one bounded frame without retaining the worker wire lock."""
        self._acknowledge_upload(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionChunkRequest(
                    request_id=uuid4(),
                    upload_id=upload_id,
                    connection_id=connection_id,
                    session_id=session_id,
                    chunk=chunk,
                )
            ),
            upload_id,
            deadline=deadline,
        )

    def finish_submission_payload(
        self, *, upload_id: UUID, connection_id: UUID, session_id: UUID, deadline: float
    ) -> ProfileWorkerSubmission:
        """Receive the ordinary canonical submission receipt after verified bytes."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionFinishRequest(
                    request_id=uuid4(), upload_id=upload_id, connection_id=connection_id, session_id=session_id
                )
            ),
            ProfileWorkerSubmission,
            operation=True,
            deadline=deadline,
        )

    def abort_submission_payload(
        self, *, upload_id: UUID, connection_id: UUID, session_id: UUID, deadline: float
    ) -> None:
        """Wipe one matching upload even when the original lease has expired."""
        self._acknowledge_upload(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionAbortRequest(
                    request_id=uuid4(), upload_id=upload_id, connection_id=connection_id, session_id=session_id
                )
            ),
            upload_id,
            deadline=deadline,
        )

    def start(
        self,
        session_id: UUID,
        operation_id: OperationId,
        *,
        frontend: OperationFrontendProjection = OperationFrontendProjection.MCP,
    ) -> ProfileWorkerOperationReceipt:
        """Start an already admitted invocation with its original session binding."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerOperationRequest(
                    action="operation_start",
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    operation_id=operation_id,
                )
            ),
            ProfileWorkerOperationReceipt,
            operation=True,
        )

    def observe(
        self,
        session_id: UUID,
        request: OperationObservationRequestV1,
        *,
        frontend: OperationFrontendProjection = OperationFrontendProjection.MCP,
    ) -> ProfileWorkerObservation:
        """Read a bounded canonical projection through fresh disclosure authority."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerObserveRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    observation=request,
                )
            ),
            ProfileWorkerObservation,
            operation=True,
        )
        return result

    def resume(
        self, session_id: UUID, operation_id: OperationId, *, frontend: OperationFrontendProjection
    ) -> ProfileWorkerOperationReceipt:
        """Request fresh authority and canonical recovery without a response credential."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerResumeRequest(
                    request_id=uuid4(), session_id=session_id, frontend=frontend, operation_id=operation_id
                )
            ),
            ProfileWorkerOperationReceipt,
            operation=True,
        )

    def project(
        self,
        session_id: UUID,
        request: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1,
        *,
        frontend: OperationFrontendProjection,
    ) -> ProfileWorkerProjection:
        """Resolve a canonical result/review projection with separate output consent."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerProjectRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    projection=request,
                )
            ),
            ProfileWorkerProjection,
            operation=True,
        )

    def project_page(
        self,
        session_id: UUID,
        request: OperationResultProjectionRequestV1,
        page: ProjectionPageRequest,
        *,
        frontend: OperationFrontendProjection,
    ) -> ProfileWorkerProjectionPage:
        """Reauthorize each bounded slice of the same canonical settled result."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerProjectPageRequest(
                    request_id=uuid4(), session_id=session_id, frontend=frontend, projection=request, page=page
                )
            ),
            ProfileWorkerProjectionPage,
            operation=True,
        )

    def manage(
        self,
        session_id: UUID,
        request: OperationManagementRequest,
        *,
        frontend: OperationFrontendProjection,
    ) -> ProfileWorkerProjection:
        """Send one canonical control through the worker's guarded operation channel."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerManageRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    management=request,
                )
            ),
            ProfileWorkerProjection,
            operation=True,
        )

    def operation_secret(
        self,
        session_id: UUID,
        requirement: OperationSecretRequirement,
        *,
        frontend: OperationFrontendProjection,
        secret: bytearray | None = None,
    ) -> ProfileWorkerOperationReceipt:
        """Preflight or consume a secret on the contained worker's original submission."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerSecretRequest(
                    action="operation_secret_ready" if secret is None else "operation_secret",
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    requirement=requirement,
                )
            ),
            ProfileWorkerOperationReceipt,
            secret,
            operation=True,
        )
