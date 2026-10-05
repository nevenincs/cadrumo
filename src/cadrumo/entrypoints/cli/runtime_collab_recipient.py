"""Authenticated CLI transport for registered collaboration-recipient operations."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import BaseModel, ValidationError

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.review_package_recipient_operations import (
    REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
    REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID,
    REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID,
    ReviewPackageRecipientAddProjection,
    ReviewPackageRecipientAddRequest,
    ReviewPackageRecipientListProjection,
    ReviewPackageRecipientListRequest,
    ReviewPackageRecipientRemoveProjection,
    ReviewPackageRecipientRemoveRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def _profile_client(ctx: typer.Context) -> tuple[UUID, RuntimeFrontendClient]:
    profile_id = UUID(active_bucket_id_or_refuse())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    return profile_id, client


def _active_profile_id() -> UUID:
    return UUID(active_bucket_id_or_refuse())


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    profile_id, client = _profile_client(ctx)
    if getattr(request, "profile_id", None) != profile_id or client.profile_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    if (
        getattr(completed.projection, "profile_id", None) != profile_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return completed


def submit_collab_recipient_add(
    ctx: typer.Context,
    *,
    recipient_id: str,
    public_key: str,
    label: str,
) -> RegisteredOperationCompletion[ReviewPackageRecipientAddProjection]:
    """Submit the strict normalized recipient-add request to its profile worker."""
    profile_id = _active_profile_id()
    try:
        request = ReviewPackageRecipientAddRequest(
            profile_id=profile_id,
            recipient_id=recipient_id,
            public_key_hex=public_key.strip().lower(),
            label=label,
        )
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    completed = _submit(
        ctx,
        request,
        definition_id=REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        result_type=ReviewPackageRecipientAddProjection,
    )
    if completed.effect is not OperationEffect.UPDATED:
        raise invalid_completion_error(completed)
    return completed


def submit_collab_recipient_list(
    ctx: typer.Context,
) -> RegisteredOperationCompletion[ReviewPackageRecipientListProjection]:
    """Submit a read-only request for the full recipient register."""
    profile_id = _active_profile_id()
    request = ReviewPackageRecipientListRequest(profile_id=profile_id)
    completed = _submit(
        ctx,
        request,
        definition_id=REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID,
        result_type=ReviewPackageRecipientListProjection,
    )
    projection = completed.projection
    if (
        completed.effect is not OperationEffect.NONE
        or projection.count != len(projection.recipients)
        or tuple(row.recipient_id for row in projection.recipients)
        != tuple(sorted(row.recipient_id for row in projection.recipients))
    ):
        raise invalid_completion_error(completed)
    return completed


def submit_collab_recipient_remove(
    ctx: typer.Context,
    *,
    recipient_id: str,
) -> RegisteredOperationCompletion[ReviewPackageRecipientRemoveProjection]:
    """Submit the exact-profile recipient removal request."""
    profile_id = _active_profile_id()
    try:
        request = ReviewPackageRecipientRemoveRequest(profile_id=profile_id, recipient_id=recipient_id)
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    completed = _submit(
        ctx,
        request,
        definition_id=REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID,
        result_type=ReviewPackageRecipientRemoveProjection,
    )
    if completed.effect is not OperationEffect.UPDATED or completed.projection.recipient_id != recipient_id:
        raise invalid_completion_error(completed)
    return completed


__all__ = [
    "submit_collab_recipient_add",
    "submit_collab_recipient_list",
    "submit_collab_recipient_remove",
]
