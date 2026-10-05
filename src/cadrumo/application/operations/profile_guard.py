"""Shared profile identity checks for operation access and execution."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import profile_operation_subject
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .models import OperationRequest
from .owner import OperationExecutorContext


def require_access_request_profile_identity[RequestPayloadT: BaseModel](
    request: OperationRequest[RequestPayloadT],
    *,
    payload_profile_id: UUID,
    access_profile_id: UUID,
) -> None:
    """Require an access request's profile and profile-derived subject to agree."""
    if payload_profile_id != access_profile_id or request.subject_ref != profile_operation_subject(
        str(payload_profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


class ProfileAccessPayload(Protocol):
    """An operation payload that names the profile it targets."""

    @property
    def profile_id(self) -> UUID:
        """The profile the operation acts for."""
        ...


class WorkUnitAccessPayload(ProfileAccessPayload, Protocol):
    """An operation payload that names its profile and the work unit it addresses."""

    @property
    def work_unit_id(self) -> str:
        """The work unit the request's subject must name."""
        ...


def require_access_request_payload[RequestPayloadT: BaseModel, PayloadT](
    request: OperationRequest[RequestPayloadT],
    *,
    definition_id: str,
    payload_type: type[PayloadT],
) -> PayloadT:
    """Return this operation's payload, refusing another operation or payload type as unavailable."""
    payload = request.payload
    if request.definition_id != definition_id or not isinstance(payload, payload_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return payload


def require_access_request_profile_payload[RequestPayloadT: BaseModel, PayloadT: ProfileAccessPayload](
    request: OperationRequest[RequestPayloadT],
    *,
    definition_id: str,
    payload_type: type[PayloadT],
    access_profile_id: UUID,
) -> PayloadT:
    """Return this operation's payload once it targets the accessing profile's own subject.

    Another operation or payload type is unavailable; it is checked before the
    profile, so a foreign request never learns whether its profile matched.
    """
    payload = require_access_request_payload(request, definition_id=definition_id, payload_type=payload_type)
    require_access_request_profile_identity(
        request, payload_profile_id=payload.profile_id, access_profile_id=access_profile_id
    )
    return payload


def require_access_request_work_unit_payload[RequestPayloadT: BaseModel, PayloadT: WorkUnitAccessPayload](
    request: OperationRequest[RequestPayloadT],
    *,
    definition_id: str,
    payload_type: type[PayloadT],
    access_profile_id: UUID,
) -> PayloadT:
    """Return this operation's payload once it targets the accessing profile and names its work-unit subject.

    Another operation or payload type is unavailable; it is checked before the
    profile and subject.
    """
    payload = require_access_request_payload(request, definition_id=definition_id, payload_type=payload_type)
    if payload.profile_id != access_profile_id or request.subject_ref != payload.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def require_operation_profile[RequestPayloadT: BaseModel](
    request: OperationRequest[RequestPayloadT],
    context: OperationExecutorContext,
    profile_id: UUID,
    *,
    expected_subject_ref: str | None = None,
) -> None:
    """Require the operation target and executor identity to match the active profile."""
    require_profile_operation_identity(
        request,
        context,
        profile_id,
        expected_subject_ref=expected_subject_ref,
    )
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def require_profile_operation_identity[RequestPayloadT: BaseModel](
    request: OperationRequest[RequestPayloadT],
    context: OperationExecutorContext,
    profile_id: UUID,
    *,
    expected_subject_ref: str | None = None,
) -> None:
    """Require request and executor identities to agree on the profile target."""
    subject_ref = profile_operation_subject(str(profile_id)) if expected_subject_ref is None else expected_subject_ref
    if (
        request.subject_ref != subject_ref
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
