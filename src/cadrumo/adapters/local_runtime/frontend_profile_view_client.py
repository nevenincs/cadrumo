"""Bounded one-revision profile view collection through registered read operations."""

from __future__ import annotations

import time
from uuid import uuid4

from pydantic import ValidationError

from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import deadline_after, remaining_budget
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationResult,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.view_operation import (
    PROFILE_VIEW_MAX_ITEMS,
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewOperationProjection,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
    ProfileViewRefusalCode,
)
from ...core.external_constants import OutputLanguage
from ...core.hashing import canonical_json_bytes
from ...core.identity.digest import ContentDigest
from ...core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from ...domain.user_profile.values import ProfileSetupState
from .frontend_client_contracts import ProfileViewCollection, RuntimeFrontendRefusedError
from .frontend_operation_client import RuntimeOperationFrontend


class RuntimeProfileViewFrontend(RuntimeOperationFrontend):
    """Collect only complete page streams pinned to one canonical profile revision."""

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
        _require_profile_view_request(page_kinds, max_pages, expected_revision, expected_content_digest)
        deadline = deadline_after(timeout)
        contract = self.contract(PROFILE_VIEW_OPERATION_DEFINITION_ID, deadline=deadline)
        pages: list[ProfileViewOperationProjection] = []
        pin: _ProfileViewPin | None = None
        for kind in page_kinds:
            cursor = 0
            while True:
                remaining_budget(deadline)
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
                page = self._collect_profile_view_page(request, contract, deadline)
                pin = _profile_view_page_pin(page, pin, expected_revision, expected_content_digest)
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

    def _collect_profile_view_page(
        self, request: ProfileViewOperationRequest, contract: OperationPublicDefinitionContractV1, deadline: float
    ) -> ProfileViewOperationProjection:
        """Require one successful registered operation and its exact addressed page."""
        operation_id = self.submit(request, deadline=deadline)
        self.start(operation_id, deadline=deadline)
        projection = self._await_profile_view_terminal(operation_id, deadline)
        page = self.result(
            operation_id,
            terminal_revision=projection.revision,
            contract=contract,
            deadline=deadline,
        )
        if (
            page.profile_id != self.profile_id
            or page.page_kind is not request.page_kind
            or page.cursor != request.cursor
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if page.outcome == "refused":
            if page.refusal_code is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            raise RuntimeFrontendRefusedError(page.refusal_code.value)
        return page

    def _await_profile_view_terminal(self, operation_id: OperationId, deadline: float) -> OperationPublicProjectionV1:
        """Poll one submitted read within the shared deadline and require success."""
        while True:
            remaining_budget(deadline)
            observed = self.observe(operation_id, deadline=deadline)
            projection = observed.projection
            if projection.lifecycle is OperationLifecycle.TERMINAL:
                break
            time.sleep(min(0.02, remaining_budget(deadline)))
        if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            if projection.terminal_condition is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            raise RuntimeFrontendRefusedError(
                projection.refusal_ref or projection.failure_error_code or projection.terminal_condition.value
            )
        return projection


type _ProfileViewPin = tuple[int, ContentDigest, ProfileSetupState, int, bool]


def _require_profile_view_request(
    page_kinds: tuple[ProfileViewPageKind, ...],
    max_pages: int,
    expected_revision: int | None,
    expected_content_digest: ContentDigest | None,
) -> None:
    """Require distinct bounded streams and a paired caller revision pin."""
    if not page_kinds or len(set(page_kinds)) != len(page_kinds) or not 1 <= max_pages <= 512:
        raise ValueError("request distinct profile view streams and at most 512 pages")
    if (expected_revision is None) != (expected_content_digest is None):
        raise ValueError("profile view revision and digest pin must be paired")


def _profile_view_page_pin(
    page: ProfileViewOperationProjection,
    pin: _ProfileViewPin | None,
    expected_revision: int | None,
    expected_content_digest: ContentDigest | None,
) -> _ProfileViewPin:
    """Pin the first page or refuse any subsequent revision or shape change."""
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
    return pin
