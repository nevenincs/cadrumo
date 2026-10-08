"""Exact-profile authority and bounded result for provider configuration."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...core.auth_provider import AuthProviderKind
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.access_resolution import (
    HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_frontend_and_action,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.registry import OperationFrontendProjection
from ..operator_actions.models import PreconditionVerdict
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .operation_definitions import AUTH_CONFIGURE_OPERATION_DEFINITION_ID, AuthConfigureOperationRequest
from .operator_result_projections import incomplete_auth_configuration_verdict
from .operator_results import AuthConfigureResult

_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
AUTH_CONFIGURE_RESULT_SCHEMA_ID = AUTH_CONFIGURE_OPERATION_DEFINITION_ID + ".result"


class AuthConfigurePublicResultV2(BaseModel):
    """Configured profile and its readiness facts, without a private path or prose.

    The certificate file is reported only as provided or not, and the identity
    alignment only as its finite state, so neither a filesystem location nor a
    taxpayer identifier crosses the runtime boundary.
    """

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[2] = 2
    profile_id: UUID
    provider: AuthProviderKind
    changed: bool
    certificate_file_provided: bool
    complete: bool
    profile_tax_id_present: bool
    provider_identity_present: bool
    identity_alignment: Literal[
        "not_applicable",
        "matches",
        "mismatch",
        "clave_identity_missing",
        "profile_tax_id_missing",
        "profile_tax_id_missing_and_clave_identity_missing",
    ]

    @property
    def precondition_verdict(self) -> PreconditionVerdict | None:
        """Derive canonical recovery evidence from the finite public facts."""
        if self.complete:
            return None
        return incomplete_auth_configuration_verdict(
            provider=self.provider.value,
            certificate_file_provided=self.certificate_file_provided,
            profile_tax_id_present=self.profile_tax_id_present,
            provider_identity_present=self.provider_identity_present,
            identity_alignment=self.identity_alignment,
        )


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
    access_profile = HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS
    require_declared_frontend_and_action(context, frontends=_FRONTENDS, actions=access_profile.actions)
    return bind_operation_access_profile(
        context, access_profile, profile_id=context.profile_id, definition_id=request.definition_id, periods=frozenset()
    )


def project_auth_configure_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the finite readiness facts of a successful exact-profile configuration.

    An unchanged selection settles with no effect and a change with an update;
    any other pairing is refused rather than projected.
    """
    if (
        type(result) is not AuthConfigureResult
        or receipt.identity.definition_id != AUTH_CONFIGURE_OPERATION_DEFINITION_ID
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
    ):
        raise ValueError("invalid provider configuration result")
    try:
        profile_id = UUID(receipt.identity.subject_ref.removeprefix("profile:"))
    except ValueError:
        raise ValueError("invalid provider configuration subject") from None
    if receipt.identity.subject_ref != profile_operation_subject(str(profile_id)):
        raise ValueError("invalid provider configuration subject")
    validated = AuthConfigureResult.model_validate_json(result.model_dump_json(), strict=True)
    if receipt.effect is not (OperationEffect.UPDATED if validated.changed else OperationEffect.NONE):
        raise ValueError("provider configuration effect does not match its change")
    return AuthConfigurePublicResultV2.model_validate(
        {
            "profile_id": profile_id,
            "provider": AuthProviderKind(validated.provider),
            "changed": validated.changed,
            "certificate_file_provided": bool(validated.file),
            "complete": validated.complete,
            "profile_tax_id_present": validated.profile_tax_id_present,
            "provider_identity_present": validated.provider_identity_present,
            "identity_alignment": validated.identity_alignment,
        },
        strict=True,
    )


__all__ = [
    "AUTH_CONFIGURE_RESULT_SCHEMA_ID",
    "AuthConfigurePublicResultV2",
    "project_auth_configure_result",
    "resolve_auth_configure_access",
]
