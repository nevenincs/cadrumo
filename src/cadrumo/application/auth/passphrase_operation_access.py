"""Human-only authority and settled projection for registered password rotation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...core.operations import profile_operation_subject as _profile_subject
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.registry import OperationFrontendProjection
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from .operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID, ProfilePassphraseRotationOperationRequest

PROFILE_ROTATION_RESULT_SCHEMA_ID = "auth.profile.passphrase-rotate.result"
_ROTATION_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT}
)
_ROTATION_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})


class ProfilePassphraseRotationResultProjection(BaseModel):
    """Nonsecret completed outcome, still tied to its settled profile subject."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: ProfilePassphraseRotationOutcome


def resolve_profile_rotation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve only exact-profile human CLI/TUI rotation actions and output."""
    payload = request.payload
    if type(payload) is not ProfilePassphraseRotationOperationRequest:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        request.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
        or payload.profile_id != context.profile_id
        or request.subject_ref != _profile_subject(str(payload.profile_id))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if context.frontend not in _ROTATION_FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ROTATION_ACTIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    disclosure = None
    if context.action is AccessAction.OBSERVE:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != PROFILE_ROTATION_RESULT_SCHEMA_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=_ROTATION_ACTIONS,
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )


def project_profile_rotation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a strictly validated completed outcome for its exact subject."""
    if (
        receipt.identity.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
        or type(result) is not ProfilePassphraseRotationOutcome
    ):
        raise ValueError("invalid passphrase rotation result")
    try:
        subject_id = UUID(receipt.identity.subject_ref.removeprefix("profile:"))
        outcome = ProfilePassphraseRotationOutcome.model_validate(
            result.model_dump(mode="python", warnings=False), strict=True
        )
    except (ValueError, TypeError):
        pass
    else:
        if receipt.identity.subject_ref == _profile_subject(str(subject_id)) and outcome.profile_id == str(subject_id):
            return ProfilePassphraseRotationResultProjection(outcome=outcome)
    raise ValueError("invalid passphrase rotation result")


__all__ = [
    "PROFILE_ROTATION_RESULT_SCHEMA_ID",
    "ProfilePassphraseRotationResultProjection",
    "project_profile_rotation_result",
    "resolve_profile_rotation_access",
]
