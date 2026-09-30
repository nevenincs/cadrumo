"""Exact-profile authority and bounded result for provider configuration."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.registry import OperationFrontendProjection
from ..operator_actions.projection import PreconditionVerdictSnapshot
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
from .operation_definitions import AUTH_CONFIGURE_OPERATION_DEFINITION_ID, AuthConfigureOperationRequest
from .operator_results import AuthConfigureResult

_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT}
)
_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
AUTH_CONFIGURE_RESULT_SCHEMA_ID = AUTH_CONFIGURE_OPERATION_DEFINITION_ID + ".result"


class AuthConfigureResultSnapshot(BaseModel):
    """Public configure result using the canonical serializer-free verdict shape."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    provider: str
    file: str = ""
    complete: bool = True
    incomplete_reason: str = ""
    profile_tax_id_present: bool = False
    provider_identity_present: bool = False
    identity_alignment: str = ""
    identity_alignment_detail: str = ""
    precondition_verdict: PreconditionVerdictSnapshot | None = None

    @classmethod
    def from_result(cls, result: AuthConfigureResult) -> AuthConfigureResultSnapshot:
        """Copy the existing result without its verdict's mapping serializer."""
        return cls(
            provider=result.provider,
            file=result.file,
            complete=result.complete,
            incomplete_reason=result.incomplete_reason,
            profile_tax_id_present=result.profile_tax_id_present,
            provider_identity_present=result.provider_identity_present,
            identity_alignment=result.identity_alignment,
            identity_alignment_detail=result.identity_alignment_detail,
            precondition_verdict=(
                PreconditionVerdictSnapshot.from_verdict(result.precondition_verdict)
                if result.precondition_verdict is not None
                else None
            ),
        )

    def to_result(self) -> AuthConfigureResult:
        """Restore the canonical result for existing CLI envelope rendering."""
        return AuthConfigureResult(
            provider=self.provider,
            file=self.file,
            complete=self.complete,
            incomplete_reason=self.incomplete_reason,
            profile_tax_id_present=self.profile_tax_id_present,
            provider_identity_present=self.provider_identity_present,
            identity_alignment=self.identity_alignment,
            identity_alignment_detail=self.identity_alignment_detail,
            precondition_verdict=(
                self.precondition_verdict.to_verdict() if self.precondition_verdict is not None else None
            ),
        )

    @model_validator(mode="after")
    def _canonical(self) -> AuthConfigureResultSnapshot:
        self.to_result()
        return self


class AuthConfigureOperationProjection(BaseModel):
    """The configured profile and its validated operator result snapshot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    profile_id: UUID
    result: AuthConfigureResultSnapshot


def resolve_auth_configure_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human profile authority at every provider configuration boundary."""
    if (
        request.definition_id != AUTH_CONFIGURE_OPERATION_DEFINITION_ID
        or type(request.payload) is not AuthConfigureOperationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.subject_ref != profile_operation_subject(str(context.profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if context.frontend not in _FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ACTIONS:
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
        if schema is None or schema.schema_id != AUTH_CONFIGURE_RESULT_SCHEMA_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
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
            actions=_ACTIONS,
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


def project_auth_configure_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the existing operator result only for a successful exact profile."""
    if (
        type(result) is not AuthConfigureResult
        or receipt.identity.definition_id != AUTH_CONFIGURE_OPERATION_DEFINITION_ID
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
    ):
        raise ValueError("invalid provider configuration result")
    try:
        profile_id = UUID(receipt.identity.subject_ref.removeprefix("profile:"))
    except ValueError:
        raise ValueError("invalid provider configuration subject") from None
    if receipt.identity.subject_ref != profile_operation_subject(str(profile_id)):
        raise ValueError("invalid provider configuration subject")
    validated = AuthConfigureResult.model_validate_json(result.model_dump_json(), strict=True)
    return AuthConfigureOperationProjection(
        profile_id=profile_id, result=AuthConfigureResultSnapshot.from_result(validated)
    )


__all__ = [
    "AUTH_CONFIGURE_RESULT_SCHEMA_ID",
    "AuthConfigureOperationProjection",
    "AuthConfigureResultSnapshot",
    "project_auth_configure_result",
    "resolve_auth_configure_access",
]
