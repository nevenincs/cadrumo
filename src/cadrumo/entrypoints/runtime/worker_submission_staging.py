"""Volatile bounded upload staging inside one immutable profile worker.

Only the worker's verified parent can send these commands. A staged document
has no operation identity, journal entry, or publication effect until finish
hands its verified text to the canonical operation host.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from uuid import UUID

from ...application.operations.models import OperationDefinitionId, OperationReference
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.profile_worker import (
    ProfileWorkerSubmissionAbortRequest,
    ProfileWorkerSubmissionBeginRequest,
    ProfileWorkerSubmissionChunkRequest,
    ProfileWorkerSubmissionFinishRequest,
)
from ...application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
    FinancialOperandInputDescriptor,
    SubmissionPayloadBuffer,
)
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError

_MAX_UPLOADS = 2


@dataclass(frozen=True, slots=True)
class StagedSubmission:
    """Verified text and original admission coordinates for canonical SUBMIT."""

    session_id: UUID
    frontend: OperationFrontendProjection
    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    payload_json: str = field(repr=False)
    idempotency_key: str | None = field(repr=False)
    financial_input: bool = False


@dataclass(slots=True)
class _Upload:
    connection_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    idempotency_key: str | None = field(repr=False)
    expires_at: float
    financial_input: bool
    buffer: SubmissionPayloadBuffer


class WorkerSubmissionStaging:
    """Own at most two exact-session payloads, wiping them on every exit path."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        """Use a monotonic clock, injectable only to prove finite expiry."""
        self._clock = clock
        self._uploads: dict[UUID, _Upload] = {}
        self._closed = False

    def begin(self, request: ProfileWorkerSubmissionBeginRequest) -> None:
        """Reserve one worker-local slot without admitting a canonical operation."""
        self.expire()
        if self._closed:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        if request.upload_id in self._uploads or len(self._uploads) >= _MAX_UPLOADS:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        self._uploads[request.upload_id] = _Upload(
            connection_id=request.connection_id,
            session_id=request.session_id,
            frontend=request.frontend,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            idempotency_key=request.idempotency_key,
            expires_at=self._clock() + SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
            buffer=SubmissionPayloadBuffer(request.descriptor),
            financial_input=isinstance(request.descriptor, FinancialOperandInputDescriptor),
        )

    def append(self, request: ProfileWorkerSubmissionChunkRequest) -> None:
        """Append one exact contiguous chunk or wipe a malformed upload."""
        upload = self._bound(request.upload_id, request.connection_id, request.session_id)
        try:
            upload.buffer.append(request.chunk)
        except (ValueError, TypeError):
            self._drop(request.upload_id)
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None

    def finish(self, request: ProfileWorkerSubmissionFinishRequest) -> StagedSubmission:
        """Verify the complete payload and relinquish its mutable staging bytes."""
        upload = self._bound(request.upload_id, request.connection_id, request.session_id)
        try:
            payload_json = upload.buffer.finish()
        except (ValueError, TypeError, UnicodeError):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        finally:
            self._drop(request.upload_id)
        return StagedSubmission(
            session_id=upload.session_id,
            frontend=upload.frontend,
            definition_id=upload.definition_id,
            subject_ref=upload.subject_ref,
            payload_json=payload_json,
            idempotency_key=upload.idempotency_key,
            financial_input=upload.financial_input,
        )

    def abort(self, request: ProfileWorkerSubmissionAbortRequest) -> None:
        """Wipe a matching upload even if its session has since been retired."""
        self.expire()
        if request.upload_id not in self._uploads:
            return
        self._bound(request.upload_id, request.connection_id, request.session_id)
        self._drop(request.upload_id)

    def expire(self, *, live_sessions: Collection[UUID] | None = None) -> None:
        """Wipe elapsed uploads and leases absent from a fresh custody snapshot."""
        now = self._clock()
        for upload_id, upload in tuple(self._uploads.items()):
            if now >= upload.expires_at or (live_sessions is not None and upload.session_id not in live_sessions):
                self._drop(upload_id)

    def close(self) -> None:
        """Wipe all incomplete payloads on drain, failure, or worker exit."""
        self._closed = True
        for upload_id in tuple(self._uploads):
            self._drop(upload_id)

    def _bound(self, upload_id: UUID, connection_id: UUID, session_id: UUID) -> _Upload:
        self.expire()
        upload = self._uploads.get(upload_id)
        if upload is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        if upload.connection_id != connection_id or upload.session_id != session_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return upload

    def _drop(self, upload_id: UUID) -> None:
        upload = self._uploads.pop(upload_id, None)
        if upload is not None:
            upload.buffer.close()
