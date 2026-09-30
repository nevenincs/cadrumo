"""Bounded frontend access to one native-verified profile runtime connection.

This adapter owns no admission or operation policy. The installed runtime and
its canonical operation services make every access and disclosure decision.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import dataclass
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError

from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionDescriptionV1,
)
from ...application.operations.secret_submission import OperationSecretRequirement
from ...application.runtime.access_management import (
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentRecorded,
)
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationPage,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationResult,
    RuntimeOperationResultPage,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES, ProjectionPageRequest
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_projections import PublicAccessSession
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationSecretStore
from ...application.user_profile.automation_enrollment import AutomationReceiptProjection, EnrollmentStage
from ...application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ...application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from ...application.user_profile.view_operation import (
    PROFILE_VIEW_MAX_ITEMS,
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewItem,
    ProfileViewOperationProjection,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
    ProfileViewRefusalCode,
)
from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from ...domain.user_profile.values import ProfileSetupState
from .enrollment_client import NativeEnrollmentClient
from .framing import VerifiedRuntimeConnection
from .startup import RuntimeLaunchDoor

_RESULT_DOCUMENT = TypeAdapter(dict[str, JsonValue])
# Profile admission may launch a cold isolated worker before the first reply.
# Keep this longer than its bounded pipe-accept and handshake stages.
_PROFILE_LOGIN_TIMEOUT_SECONDS = 75.0


class RuntimeFrontendRefusedError(CadrumoError):
    """A safe, typed application refusal from the installed runtime."""

    def __init__(self, code: str) -> None:
        """Retain an allowlisted refusal code without private diagnostic text."""
        self.reason = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProfileViewCollection:
    """Only complete page streams from one exact encrypted profile revision."""

    profile_id: UUID
    record_revision: int
    content_digest: ContentDigest
    setup_state: ProfileSetupState
    schema_version: int
    valid: bool
    page_kinds: tuple[ProfileViewPageKind, ...]
    pages: tuple[ProfileViewOperationProjection, ...]

    def items(self, kind: ProfileViewPageKind) -> tuple[ProfileViewItem, ...]:
        """Return the ordered items of one fully collected requested stream."""
        if kind not in self.page_kinds:
            raise ValueError("profile view stream was not requested")
        return tuple(item for page in self.pages if page.page_kind is kind for item in page.items)


def _deadline(timeout: float) -> float:
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return time.monotonic() + timeout


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


class RuntimeFrontendClient:
    """Own one exact profile/frontend connection and its connection-bound lease.

    The caller retains this object only for its frontend session. Every method
    derives the profile and session coordinates from a successful native login;
    copied IDs and ambient profile selection cannot retarget it. Blocking wire
    methods should be called off a UI event loop.
    """

    def __init__(
        self, connection: VerifiedRuntimeConnection, *, profile_id: UUID, frontend: OperationFrontendProjection
    ) -> None:
        """Bind one verified connection to an explicit immutable frontend target."""
        self._connection = connection
        self._profile_id = profile_id
        self._frontend = frontend
        self._session_id: UUID | None = None
        self._connection_purpose: Literal["fresh", "admission", "recovery", "enrollment"] = "fresh"

    @property
    def profile_id(self) -> UUID:
        """Return the immutable target selected before native admission."""
        return self._profile_id

    @property
    def storage_identity(self) -> ContentDigest:
        """Return the physical owner/root identity pinned by the verified handshake."""
        return self._connection.hello.storage_identity

    @property
    def frontend(self) -> OperationFrontendProjection:
        """Return the frontend bound before native admission."""
        return self._frontend

    @property
    def session_id(self) -> UUID:
        """Return this connection's admitted identity; it is not transferable proof."""
        return self._session()

    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        """Exchange a canonical operation message under this exact connection lease.

        Callers may compose the registered frontend protocol, but cannot select
        another profile or borrow a different connection's session. The runtime
        remains responsible for definition, scope, disclosure and response proof.
        """
        if request.profile_id != self.profile_id or request.session_id != self._session():
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        reply = self._connection.operation(request, deadline=deadline)
        if isinstance(reply, RuntimeAccessRefusal):
            raise RuntimeFrontendRefusedError(reply.code.value)
        return reply

    @classmethod
    async def open(
        cls,
        launch: RuntimeLaunchDoor,
        *,
        profile_id: UUID,
        frontend: OperationFrontendProjection,
        timeout: float = 10,
    ) -> Self:
        """Use the canonical owner-verified launch door before any credential."""
        return cls(await launch.open(timeout=timeout), profile_id=profile_id, frontend=frontend)

    def __enter__(self) -> Self:
        """Retain this owned connection for a synchronous frontend scope."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """Close this frontend's owned connection."""
        self.close()

    async def __aenter__(self) -> Self:
        """Retain this owned connection for an asynchronous frontend scope."""
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close this frontend's owned connection."""
        await await_cancellation_complete(asyncio.to_thread(self.close), task_name="frontend-runtime-close")

    def close(self) -> None:
        """End this connection's lease without stopping the shared runtime."""
        self._session_id = None
        self._connection.close()

    def _session(self) -> UUID:
        if self._session_id is None:
            raise RuntimeFrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
        return self._session_id

    @staticmethod
    def _reply[ReplyT](reply: object, expected: type[ReplyT]) -> ReplyT:
        if isinstance(reply, RuntimeAccessRefusal):
            raise RuntimeFrontendRefusedError(reply.code.value)
        if not isinstance(reply, expected):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

    def _login(
        self, method: str, secret: bytearray, *, timeout: float, persist_receipt: bool = False
    ) -> RuntimeProfileStatus:
        try:
            if self._connection_purpose in {"recovery", "enrollment"}:
                raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            if self._session_id is not None:
                raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "admission"
            request = RuntimeProfileLogin.model_validate(
                {
                    "request_id": uuid4(),
                    "profile_id": self.profile_id,
                    "frontend": self.frontend,
                    "method": method,
                    "persist_receipt": persist_receipt,
                }
            )
            reply = self._reply(
                self._connection.login(request, secret, deadline=_deadline(timeout)), RuntimeProfileStatus
            )
            status = reply.status
            if (
                status.denial is not None
                or not status.connected
                or not status.credential_authenticated
                or not status.profile_bound
                or status.profile_id != self.profile_id
                or status.session_id is None
            ):
                raise RuntimeFrontendRefusedError(
                    status.denial.value if status.denial is not None else AccessDenialCode.PROFILE_MISMATCH.value
                )
            self._session_id = status.session_id
            return reply
        finally:
            secret[:] = bytes(len(secret))

    def login_password(
        self, secret: bytearray, *, timeout: float = _PROFILE_LOGIN_TIMEOUT_SECONDS, persist_receipt: bool = False
    ) -> RuntimeProfileStatus:
        """Consume an explicit password only on the one-use verified secret frame."""
        return self._login("password", secret, timeout=timeout, persist_receipt=persist_receipt)

    def login_api_key(
        self, secret: bytearray, *, timeout: float = _PROFILE_LOGIN_TIMEOUT_SECONDS
    ) -> RuntimeProfileStatus:
        """Consume an explicit key without attempting human receipt fallback."""
        return self._login("api_key", secret, timeout=timeout)

    def resume_receipt(self, *, timeout: float = _PROFILE_LOGIN_TIMEOUT_SECONDS) -> RuntimeProfileStatus:
        """Borrow the exact profile's protected receipt proof for one verified frame."""
        from ...application.user_profile.login_session import borrow_profile_receipt_key

        with borrow_profile_receipt_key(bucket_id=self.profile_id) as proof:
            return self._login("receipt", proof, timeout=timeout)

    def submit_secret(
        self, requirement: OperationSecretRequirement, secret: bytearray, *, timeout: float = 20
    ) -> RuntimeOperationAcknowledged:
        """Consume a CLI/TUI secret through its exact operation's protected handoff."""
        try:
            if self.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
                raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
            return self._reply(
                self._connection.operation_secret(
                    RuntimeOperationSecret(
                        request_id=uuid4(),
                        profile_id=self.profile_id,
                        session_id=self._session(),
                        requirement=requirement,
                    ),
                    secret,
                    deadline=_deadline(timeout),
                ),
                RuntimeOperationAcknowledged,
            )
        finally:
            secret[:] = bytes(len(secret))

    def _session_status(
        self, action: Literal["session_status", "session_refresh"], *, timeout: float
    ) -> RuntimeProfileStatus:
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                RuntimeSessionRequest(
                    action=action, request_id=uuid4(), profile_id=self.profile_id, session_id=session_id
                ),
                deadline=_deadline(timeout),
            ),
            RuntimeProfileStatus,
        )
        if reply.status.session_id not in (None, session_id) or reply.status.profile_id not in (
            None,
            self.profile_id,
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

    def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        """Recheck the current connection-bound session without refreshing it."""
        return self._session_status("session_status", timeout=timeout)

    def refresh_api_key(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        """Explicitly renew this connection's API-key lease under current authority."""
        reply = self._session_status("session_refresh", timeout=timeout)
        status = reply.status
        if status.denial is not None:
            raise RuntimeFrontendRefusedError(status.denial.value)
        if (
            not status.connected
            or not status.credential_authenticated
            or not status.profile_bound
            or status.profile_id != self.profile_id
            or status.session_id != self._session()
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

    def lock(self, *, timeout: float = 5) -> RuntimeSessionsLocked:
        """Retire this lease through the runtime's own-session lock door."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                RuntimeSessionRequest(
                    action="session_lock", request_id=uuid4(), profile_id=self.profile_id, session_id=session_id
                ),
                deadline=_deadline(timeout),
            ),
            RuntimeSessionsLocked,
        )
        if session_id not in reply.session_ids:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._session_id = None
        return reply

    def revoke_session(self, target_session_id: UUID, *, timeout: float = 5) -> RuntimeSessionsLocked:
        """Request an explicit session cascade; the runtime requires human authority."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                RuntimeSessionRequest(
                    action="session_lock",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=session_id,
                    target_session_id=target_session_id,
                ),
                deadline=_deadline(timeout),
            ),
            RuntimeSessionsLocked,
        )
        if session_id in reply.session_ids:
            self._session_id = None
        return reply

    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        """Read only this session's authorized exact-profile public inventory."""
        request = RuntimeSessionInventory(request_id=uuid4(), profile_id=self.profile_id, session_id=self._session())
        reply = self._reply(
            self._connection.session_inventory(request, deadline=_deadline(timeout)), RuntimeSessionInventoryReply
        )
        return reply.sessions

    def deny_automation(
        self, kind: AutomationDenialKind, *, target_id: UUID | None = None, timeout: float = 10
    ) -> AutomationDenialReceipt:
        """Request a durable authority reduction under this exact current session."""
        request = RuntimeAutomationDeny(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self._session(),
            kind=kind,
            target_id=target_id,
        )
        reply = self._reply(
            self._connection.deny_automation(request, deadline=_deadline(timeout)), RuntimeAutomationDenied
        )
        if kind is AutomationDenialKind.PROFILE_LOCK:
            self._session_id = None
        return reply.receipt

    def recover_profile(
        self, password: bytearray, *, grants: frozenset[UUID] = frozenset(), timeout: float = 20
    ) -> AutomationResumeReceipt:
        """Resume selected grants on a dedicated unadmitted connection with one proof."""
        try:
            if self._connection_purpose != "fresh" or self._session_id is not None:
                raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "recovery"
            deadline = _deadline(timeout)
            prepared = self._reply(
                self._connection.recovery_prepare(
                    RuntimeProfileRecoveryPrepare(
                        request_id=uuid4(), profile_id=self.profile_id, frontend=self.frontend
                    ),
                    deadline=deadline,
                ),
                RuntimeProfileRecoveryPrepared,
            )
            request = RuntimeProfileResume(
                request_id=uuid4(),
                profile_id=self.profile_id,
                frontend=self.frontend,
                lock_generation=prepared.lock_generation,
                grants=grants,
            )
            reply = self._reply(
                self._connection.resume_profile(request, password, deadline=deadline), RuntimeProfileResumed
            )
            return reply.receipt
        finally:
            password[:] = bytes(len(password))

    def prepare_enrollment(
        self, secrets_store: AutomationSecretStore, *, timeout: float = 10
    ) -> NativeEnrollmentClient:
        """Prepare one pre-unlock client handoff on a fresh verified connection."""
        if self._connection_purpose != "fresh" or self._session_id is not None:
            raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        self._connection_purpose = "enrollment"
        prepared = self._reply(
            self._connection.enrollment_prepare(
                RuntimeEnrollmentPrepare(request_id=uuid4(), profile_id=self.profile_id, frontend=self.frontend),
                deadline=_deadline(timeout),
            ),
            RuntimeEnrollmentPrepared,
        )
        return NativeEnrollmentClient(connection=self._connection, prepared=prepared, secrets_store=secrets_store)

    def prepare_grant_change(
        self, secrets_store: AutomationSecretStore, *, timeout: float = 10
    ) -> NativeEnrollmentClient:
        """Request review for this root key's grant without extending its lease.

        Rotation uses the same protected delivery protocol as first enrollment.
        Renewal and scope approval invalidate old leases; a fresh key login is
        required after the human's canonical approval receipt confirms the change.
        """
        if self._connection_purpose != "admission":
            raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        prepared = self._reply(
            self._connection.enrollment_prepare(
                RuntimeEnrollmentPrepare(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    frontend=self.frontend,
                    session_id=self._session(),
                ),
                deadline=_deadline(timeout),
            ),
            RuntimeEnrollmentPrepared,
        )
        return NativeEnrollmentClient(connection=self._connection, prepared=prepared, secrets_store=secrets_store)

    def reconcile_enrollment(self, request_id: UUID, *, timeout: float = 10) -> AutomationReceiptProjection:
        """Recover terminal own-grant metadata without restoring an old offer.

        The runtime requires current root API-key authority. A receipt grants
        no authority and this call cannot submit, approve or redeliver a key.
        """
        request = RuntimeEnrollmentReconcile(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self._session(),
            enrollment_request_id=request_id,
        )
        reply = self._reply(
            self._connection.enrollment_inspect(request, deadline=_deadline(timeout)), RuntimeEnrollmentRecorded
        )
        if reply.receipt.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply.receipt

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        """Discover the runtime's current canonical definition under live scope."""
        return self.describe(definition_id, deadline=deadline).contract

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        """Return the registered input schema after live admission and fingerprint validation."""
        reply = self._reply(
            self._connection.operation(
                RuntimeOperationContract(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    definition_id=definition_id,
                ),
                deadline=deadline,
            ),
            RuntimeOperationContractReply,
        )
        if reply.contract.definition_id != definition_id or self.frontend not in reply.contract.permitted_frontends:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            return OperationPublicDefinitionDescriptionV1(
                contract=reply.contract, request_json_schema=reply.request_json_schema
            )
        except ValidationError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None

    def submit(self, payload: ProfileViewOperationRequest, *, deadline: float) -> OperationId:
        """Submit only the registered exact-profile view request."""
        if payload.profile_id != self.profile_id:
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        reply = self._reply(
            self._connection.operation(
                RuntimeOperationSubmit(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(self.profile_id)),
                    payload_json=payload.model_dump_json(),
                ),
                deadline=deadline,
            ),
            RuntimeOperationSubmitted,
        )
        if reply.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply.receipt.operation_id

    def start(self, operation_id: OperationId, *, deadline: float) -> None:
        """Admit one submitted operation; this acknowledgement is not settlement."""
        reply = self._reply(
            self._connection.operation(
                RuntimeOperationControl(
                    action="operation_start",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    operation_id=operation_id,
                ),
                deadline=deadline,
            ),
            RuntimeOperationAcknowledged,
        )
        if reply.operation_id != operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    def observe(self, operation_id: OperationId, *, deadline: float) -> OperationObservationSuccessV1:
        """Read current canonical state; a refusal never counts as completion."""
        reply = self._reply(
            self._connection.operation(
                RuntimeOperationObserve(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
                ),
                deadline=deadline,
            ),
            RuntimeOperationObserved,
        )
        observation = reply.observation
        if not isinstance(observation, OperationObservationSuccessV1):
            raise RuntimeFrontendRefusedError(observation.code.value)
        if (
            observation.projection.operation_id != operation_id
            or observation.projection.definition_id != PROFILE_VIEW_OPERATION_DEFINITION_ID
            or observation.projection.subject_ref != profile_operation_subject(str(self.profile_id))
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return observation

    def result(
        self,
        operation_id: OperationId,
        *,
        terminal_revision: int,
        contract: OperationPublicDefinitionContractV1,
        deadline: float,
    ) -> ProfileViewOperationProjection:
        """Validate a registered result envelope and its typed view page."""
        schema = contract.result_schema
        if contract.definition_id != PROFILE_VIEW_OPERATION_DEFINITION_ID or schema is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        reply = self._reply(
            self._connection.operation(
                RuntimeOperationResult(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    result=OperationResultProjectionRequestV1(
                        operation_id=operation_id,
                        terminal_revision=terminal_revision,
                        definition_contract_digest=contract.definition_contract_digest,
                        result_schema=schema,
                    ),
                ),
                deadline=deadline,
            ),
            RuntimeOperationProjected,
        )
        if reply.operation_id != operation_id or reply.projection_kind != "result":
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if reply.document.get("outcome") == "refused":
            try:
                refused = OperationResultProjectionRefusalV1.model_validate(reply.document)
            except ValidationError:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
            raise RuntimeFrontendRefusedError(refused.code.value)
        try:
            success = OperationResultProjectionSuccessV1[ProfileViewOperationProjection].model_validate_json(
                canonical_json_bytes(reply.document)
            )
        except ValidationError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        if success.result_schema != schema or success.definition_contract_digest != contract.definition_contract_digest:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return success.projection

    def read_result_document(
        self, result: OperationResultProjectionRequestV1, *, timeout: float = 60, deadline: float | None = None
    ) -> dict[str, JsonValue]:
        """Collect one canonical settled result with fresh consent for every page.

        The runtime applies the registered projector and current disclosure
        guard on every request. No cache, reference or digest grants access.
        A refusal, changed document or total deadline discards partial output.
        """
        timeout_deadline = _deadline(timeout)
        if deadline is not None and not math.isfinite(deadline):
            raise ValueError("result deadline must be finite")
        deadline = timeout_deadline if deadline is None else min(timeout_deadline, deadline)
        collected = bytearray()
        digest: ContentDigest | None = None
        total: int | None = None
        try:
            while total is None or len(collected) < total:
                _remaining(deadline)
                reply = self._reply(
                    self.operation(
                        RuntimeOperationResultPage(
                            request_id=uuid4(),
                            profile_id=self.profile_id,
                            session_id=self._session(),
                            result=result,
                            page=ProjectionPageRequest(offset=len(collected), expected_digest=digest),
                        ),
                        deadline=deadline,
                    ),
                    RuntimeOperationPage,
                )
                page = reply.page
                if (
                    reply.operation_id != result.operation_id
                    or page.offset != len(collected)
                    or page.total_bytes > PROJECTION_DOCUMENT_MAX_BYTES
                    or (digest is not None and page.document_digest != digest)
                    or (total is not None and page.total_bytes != total)
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                digest, total = page.document_digest, page.total_bytes
                collected.extend(page.decode())
            encoded = bytes(collected)
            if len(encoded) != total or sha256_hex(encoded) != digest:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            document = _RESULT_DOCUMENT.validate_python(
                json.loads(
                    encoded, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
                ),
                strict=True,
            )
            if canonical_json_bytes(document) != encoded:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            _remaining(deadline)
            return document
        except (ValueError, TypeError, RecursionError):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        finally:
            collected[:] = bytes(len(collected))

    def read_profile_view(
        self,
        page_kinds: tuple[ProfileViewPageKind, ...],
        *,
        output_language: OutputLanguage = OutputLanguage.ES,
        expected_revision: int | None = None,
        expected_content_digest: ContentDigest | None = None,
        timeout: float = 60,
        max_pages: int = 512,
    ) -> ProfileViewCollection:
        """Collect requested streams from one revision or refuse without partial output.

        Each page is a separate durable read operation. A changed record,
        refusal, oversized indivisible item or total deadline discards the
        entire local collection. The caller may explicitly restart.
        """
        if not page_kinds or len(set(page_kinds)) != len(page_kinds) or not 1 <= max_pages <= 512:
            raise ValueError("request distinct profile view streams and at most 512 pages")
        if (expected_revision is None) != (expected_content_digest is None):
            raise ValueError("profile view revision and digest pin must be paired")
        deadline = _deadline(timeout)
        contract = self.contract(PROFILE_VIEW_OPERATION_DEFINITION_ID, deadline=deadline)
        pages: list[ProfileViewOperationProjection] = []
        pin: tuple[int, ContentDigest, ProfileSetupState, int, bool] | None = None
        for kind in page_kinds:
            cursor = 0
            while True:
                _remaining(deadline)
                if len(pages) >= max_pages:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                request = ProfileViewOperationRequest(
                    profile_id=self.profile_id,
                    page_kind=kind,
                    cursor=cursor,
                    limit=PROFILE_VIEW_MAX_ITEMS,
                    expected_revision=expected_revision if pin is None else pin[0],
                    expected_content_digest=expected_content_digest if pin is None else pin[1],
                    output_language=output_language,
                )
                operation_id = self.submit(request, deadline=deadline)
                self.start(operation_id, deadline=deadline)
                while True:
                    _remaining(deadline)
                    observed = self.observe(operation_id, deadline=deadline)
                    projection = observed.projection
                    if projection.lifecycle is OperationLifecycle.TERMINAL:
                        break
                    time.sleep(min(0.02, _remaining(deadline)))
                if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
                    if projection.terminal_condition is None:
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                    raise RuntimeFrontendRefusedError(
                        projection.refusal_ref or projection.failure_error_code or projection.terminal_condition.value
                    )
                page = self.result(
                    operation_id,
                    terminal_revision=projection.revision,
                    contract=contract,
                    deadline=deadline,
                )
                if page.profile_id != self.profile_id or page.page_kind is not kind or page.cursor != cursor:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if page.outcome == "refused":
                    if page.refusal_code is None:
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                    raise RuntimeFrontendRefusedError(page.refusal_code.value)
                current = (
                    page.record_revision,
                    page.content_digest,
                    page.setup_state,
                    page.schema_version,
                    page.valid,
                )
                if pin is None:
                    if expected_revision is not None and current[:2] != (expected_revision, expected_content_digest):
                        raise RuntimeFrontendRefusedError(ProfileViewRefusalCode.STALE_REVISION.value)
                    pin = current
                elif current != pin:
                    raise RuntimeFrontendRefusedError(ProfileViewRefusalCode.STALE_REVISION.value)
                pages.append(page)
                if page.next_cursor is None:
                    break
                if page.next_cursor <= cursor:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                cursor = page.next_cursor
        if pin is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return ProfileViewCollection(
            profile_id=self.profile_id,
            record_revision=pin[0],
            content_digest=pin[1],
            setup_state=pin[2],
            schema_version=pin[3],
            valid=pin[4],
            page_kinds=page_kinds,
            pages=tuple(pages),
        )


__all__ = ["ProfileViewCollection", "RuntimeFrontendClient", "RuntimeFrontendRefusedError"]
