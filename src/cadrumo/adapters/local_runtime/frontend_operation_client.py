"""Current-session operation exchanges and complete verified public result documents."""

from __future__ import annotations

import json
import math
from typing import NoReturn
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError

from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
)
from ...application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionDescriptionV1,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import deadline_after, remaining_budget
from ...application.runtime.operation_access import (
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationPage,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationResultPage,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
)
from ...application.runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES, ProjectionPage, ProjectionPageRequest
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from ...core.identity.digest import ContentDigest
from .framing import VerifiedRuntimeConnection
from .frontend_client_contracts import RuntimeFrontendRefusedError


class RuntimeOperationFrontend:
    """Canonical runtime session binding and registered operation transport capability."""

    _connection: VerifiedRuntimeConnection
    _profile_id: UUID
    _frontend: OperationFrontendProjection
    _session_id: UUID | None

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
            self._raise_wire_refusal(reply)
        return reply

    def _session(self) -> UUID:
        if self._session_id is None:
            raise RuntimeFrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
        return self._session_id

    @staticmethod
    def _raise_wire_refusal(reply: RuntimeAccessRefusal) -> NoReturn:
        """Keep runtime failure provenance distinct from an authoritative access denial."""
        if isinstance(reply.code, RuntimeRefusalCode):
            raise RuntimeRefusalError(reply.code)
        raise RuntimeFrontendRefusedError(reply.code.value, sign_in=reply.sign_in)

    @staticmethod
    def _reply[ReplyT](reply: object, expected: type[ReplyT]) -> ReplyT:
        if isinstance(reply, RuntimeAccessRefusal):
            RuntimeOperationFrontend._raise_wire_refusal(reply)
        if not isinstance(reply, expected):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

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

    def read_result_page(
        self,
        result: OperationResultProjectionRequestV1,
        page: ProjectionPageRequest,
        *,
        deadline: float,
    ) -> ProjectionPage:
        """Read one bounded public result page under this connection's current authority."""
        if not math.isfinite(deadline):
            raise ValueError("result deadline must be finite")
        remaining_budget(deadline)
        reply = self._reply(
            self.operation(
                RuntimeOperationResultPage(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    result=result,
                    page=page,
                ),
                deadline=deadline,
            ),
            RuntimeOperationPage,
        )
        released = reply.page
        if (
            reply.operation_id != result.operation_id
            or released.offset != page.offset
            or released.total_bytes > PROJECTION_DOCUMENT_MAX_BYTES
            or (page.expected_digest is not None and released.document_digest != page.expected_digest)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            released.decode()
        except ValueError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        remaining_budget(deadline)
        return released

    def read_result_document(
        self, result: OperationResultProjectionRequestV1, *, timeout: float = 60, deadline: float | None = None
    ) -> dict[str, JsonValue]:
        """Collect one canonical settled result with fresh consent for every page.

        The runtime applies the registered projector and current disclosure
        guard on every request. No cache, reference or digest grants access.
        A refusal, changed document or total deadline discards partial output.
        """
        timeout_deadline = deadline_after(timeout)
        if deadline is not None and not math.isfinite(deadline):
            raise ValueError("result deadline must be finite")
        deadline = timeout_deadline if deadline is None else min(timeout_deadline, deadline)
        collected = bytearray()
        digest: ContentDigest | None = None
        total: int | None = None
        try:
            while total is None or len(collected) < total:
                remaining_budget(deadline)
                page = self.read_result_page(
                    result, ProjectionPageRequest(offset=len(collected), expected_digest=digest), deadline=deadline
                )
                if total is not None and page.total_bytes != total:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                digest, total = page.document_digest, page.total_bytes
                collected.extend(page.decode())
            encoded = bytes(collected)
            return _validated_result_document(encoded, total, digest, deadline)
        except (ValueError, TypeError, RecursionError):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        finally:
            collected[:] = bytes(len(collected))


_RESULT_DOCUMENT = TypeAdapter(dict[str, JsonValue])


def _validated_result_document(
    encoded: bytes, total: int | None, digest: ContentDigest | None, deadline: float
) -> dict[str, JsonValue]:
    """Require complete digest-verified canonical JSON within the remaining budget."""
    if len(encoded) != total or sha256_hex(encoded) != digest:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    document = _RESULT_DOCUMENT.validate_python(
        json.loads(encoded, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant),
        strict=True,
    )
    if canonical_json_bytes(document) != encoded:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    remaining_budget(deadline)
    return document
