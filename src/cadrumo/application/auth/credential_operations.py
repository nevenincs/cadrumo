"""Protected provider password persistence for profile authentication setup."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, SecretStr

from ...core.async_cleanup import await_cancellation_complete
from ...core.config import load_settings
from ...core.hashing import reject_duplicate_json_members, reject_json_constant
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ..operations.access_resolution import (
    HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_action,
)
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .certificate_sources import active_certificate_source
from .credentials import CLAVE_PERMANENTE_PASSWORD_SECRET_NAME, UNNAMED_CERTIFICATE_PASSWORD_SECRET_NAME
from .operator_scope import active_profile_storage_span, assert_auth_recovery_not_in_progress, auth_mutation_span

if TYPE_CHECKING:
    from .operation_definitions import AuthOperationPorts

AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID = "auth.credential.save"
AUTH_CREDENTIAL_PASSWORD_SECRET_KIND = "auth.credential.password"  # noqa: S105 - protocol discriminator


class AuthCredentialSaveRequest(BaseModel):
    """Credential-free routing for a protected password submission."""

    model_config = STRICT_FROZEN_CONFIG
    provider: Literal["clave_permanente", "certificate"]


class AuthCredentialSaveResult(BaseModel):
    """Public confirmation containing no credential material."""

    model_config = STRICT_FROZEN_CONFIG
    provider: Literal["clave_permanente", "certificate"]
    saved: bool = True


class _PasswordInput(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    password: SecretStr


def _parse_password(secret: memoryview) -> SecretStr:
    try:
        parsed = _PasswordInput.model_validate(
            json.loads(
                bytes(secret).decode("utf-8"),
                object_pairs_hook=reject_duplicate_json_members,
                parse_constant=reject_json_constant,
            ),
            strict=True,
        )
        if parsed.password.get_secret_value():
            return parsed.password
    except (UnicodeError, ValueError, TypeError, RecursionError):
        pass
    raise ValueError("A non-empty protected authentication password is required")


class AuthCredentialSaveExecutor:
    """Save one exact-profile password through encrypted secret storage."""

    def __init__(self, *, ports: AuthOperationPorts) -> None:
        """Bind the existing profile custody and secret-store capabilities."""
        self._ports = ports

    async def execute(
        self, request: OperationRequest[AuthCredentialSaveRequest], context: OperationExecutorContext
    ) -> str:
        """Consume the protected frame and publish the profile-scoped secret."""
        from .operation_definitions import _require_active_profile_subject

        profile_id = _require_active_profile_subject(request)
        await context.events.phase("auth.credential.secret-consume")
        async with context.ephemeral_secret.consume() as secret:
            password = _parse_password(secret)

            async def publish() -> str:
                async with context.cancellation.irreversible_section():
                    await context.events.phase("auth.credential.execute")
                    await context.events.effect(OperationEffect.UNKNOWN)

                    def save() -> None:
                        from ..workflow.persistence import workflow_state_repository

                        settings = load_settings()
                        with active_profile_storage_span(
                            settings, operator_scope_ports=self._ports.operator_scope_ports
                        ) as bucket_id:
                            if bucket_id != profile_id:
                                raise ValueError("Authentication credential profile changed")
                            with auth_mutation_span(
                                settings=settings,
                                bucket_id=bucket_id,
                                operator_scope_ports=self._ports.operator_scope_ports,
                            ):
                                state = workflow_state_repository().load()
                                assert_auth_recovery_not_in_progress(state)
                                source = active_certificate_source(state)
                                name = (
                                    (source.name if source is not None else UNNAMED_CERTIFICATE_PASSWORD_SECRET_NAME)
                                    if request.payload.provider == "certificate"
                                    else CLAVE_PERMANENTE_PASSWORD_SECRET_NAME
                                )
                                backend = self._ports.certificate_secret_backend_factory(
                                    bucket_id=bucket_id, settings=settings
                                )
                                backend.set(name, password)

                    await asyncio.to_thread(save)
                    await context.events.effect(OperationEffect.UPDATED)
                    await context.events.phase("auth.credential.settlement")
                    return await context.operands.put(
                        AuthCredentialSaveResult(provider=request.payload.provider), written_at=now()
                    )

            try:
                return await await_cancellation_complete(publish(), task_name="auth-credential-publication")
            finally:
                password = SecretStr("")


def resolve_auth_credential_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human authority over this exact profile and definition."""
    if (
        request.definition_id != AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID
        or type(request.payload) is not AuthCredentialSaveRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.subject_ref != profile_operation_subject(str(context.profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    access = HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS
    require_declared_action(context, actions=access.actions)
    return bind_operation_access_profile(
        context, access, profile_id=context.profile_id, definition_id=request.definition_id, periods=frozenset()
    )
