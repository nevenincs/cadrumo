"""Forward one protected request to bounded worker staging without local files."""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from contextlib import suppress
from threading import BoundedSemaphore
from uuid import uuid4

from ...adapters.local_runtime.framing import read_secret, write_document
from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationPayloadReady,
    RuntimeOperationSubmitPayload,
    RuntimeOperationSubmitted,
)
from ...application.runtime.submission_payload import SUBMISSION_PAYLOAD_CHUNK_BYTES, SubmissionPayloadChunk
from ...application.runtime.worker_authorization import WorkerAuthorityRequest
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from .operation_projection import validate_operation_release
from .profile_host import ProfileConnection, RuntimeProfileHost


def stream_operation_submission(
    host: RuntimeProfileHost,
    connection: ProfileConnection,
    request: RuntimeOperationSubmitPayload,
    channel: RuntimeByteChannel,
    *,
    slots: BoundedSemaphore,
    require_session: Callable[[], None],
    deadline: float,
) -> tuple[RuntimeOperationSubmitted, WorkerAuthorityRequest]:
    """Admit finite staging, then use canonical submission and its fresh release.

    The upload identity is generated here and never crosses to the frontend.
    Each internal exchange is a complete frame, so a departing frontend can
    discard its upload without desynchronizing another session's worker.
    """
    if not slots.acquire(blocking=False):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    upload_id = uuid4()
    worker = None
    begun = receiving = False
    try:
        require_session()
        worker = host.owner.operation_worker()
        begun = True
        worker.begin_submission_payload(
            upload_id=upload_id,
            connection_id=connection.context.connection_id,
            session_id=request.session_id,
            frontend=connection.frontend,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            idempotency_key=request.idempotency_key,
            descriptor=request.descriptor,
            deadline=deadline,
        )
        require_session()
        write_document(
            channel,
            RuntimeOperationPayloadReady(
                request_id=request.request_id,
                runtime_boot_id=connection.context.runtime_boot_id,
                connection_id=connection.context.connection_id,
                descriptor=request.descriptor,
            ),
            deadline=deadline,
        )
        receiving = True
        for offset in range(0, request.descriptor.byte_count, SUBMISSION_PAYLOAD_CHUNK_BYTES):
            require_session()
            with read_secret(channel, deadline=deadline) as chunk:
                if len(chunk) != min(SUBMISSION_PAYLOAD_CHUNK_BYTES, request.descriptor.byte_count - offset):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                worker.append_submission_payload(
                    upload_id=upload_id,
                    connection_id=connection.context.connection_id,
                    session_id=request.session_id,
                    chunk=SubmissionPayloadChunk(offset=offset, encoded=base64.b64encode(chunk).decode("ascii")),
                    deadline=deadline,
                )
        receiving = False
        require_session()
        submitted = worker.finish_submission_payload(
            upload_id=upload_id,
            connection_id=connection.context.connection_id,
            session_id=request.session_id,
            deadline=deadline,
        )
        begun = False
        validate_operation_release(
            submitted.release,
            connection=connection,
            profile_id=request.profile_id,
            session_id=request.session_id,
            action=AccessAction.SUBMIT,
            operation_id=submitted.receipt.operation_id,
        )
        return (
            RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=connection.context.runtime_boot_id,
                connection_id=connection.context.connection_id,
                receipt=submitted.receipt,
            ),
            submitted.release,
        )
    except BaseException:
        if receiving:
            # A stream abandoned before its declared end cannot carry a reply
            # followed by ordinary documents; close only this frontend.
            channel.close()
        raise
    finally:
        try:
            if begun and worker is not None:
                # Cleanup has its own bounded budget after the caller expires.
                # A failed worker still owns a finite staging lifetime and will
                # independently wipe the entry on expiry or process exit.
                with suppress(RuntimeRefusalError, ProfileAccessRefusedError, AutomationCustodyError):
                    worker.abort_submission_payload(
                        upload_id=upload_id,
                        connection_id=connection.context.connection_id,
                        session_id=request.session_id,
                        deadline=time.monotonic() + 5,
                    )
        finally:
            slots.release()
