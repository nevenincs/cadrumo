"""Canonical registered auth operations composed from existing authorities."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SecretStr

from ...core.auth_provider import AuthProviderKind
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.operations import profile_operation_subject as _profile_subject
from ...core.time.clock import now
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
)
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from ..user_profile.login_session import ProfileLoginOutcome, login_profile
from ..user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome, rotate_profile_passphrase
from .operator import configure_operator_auth, login_operator_auth, logout_operator_auth, reset_operator_auth
from .operator_results import AuthConfigureResult, AuthLoginResult, AuthLogoutResult, AuthResetResult

PROFILE_LOGIN_OPERATION_DEFINITION_ID = "auth.profile.login"
AUTH_CONFIGURE_OPERATION_DEFINITION_ID = "auth.provider.configure"
AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID = "auth.session.acquire"
AUTH_LOGOUT_OPERATION_DEFINITION_ID = "auth.session.logout"
AUTH_RESET_OPERATION_DEFINITION_ID = "auth.session.reset"
PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID = "auth.profile.passphrase-rotate"  # noqa: S105
_PUBLIC_REQUEST_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class ProfileLoginOperationRequest(CredentialFreeOperationRequest):
    profile_id: UUID


class AuthConfigureOperationRequest(BaseModel):
    model_config = _PUBLIC_REQUEST_CONFIG

    provider: AuthProviderKind
    certificate_path: Path | None = None


class AuthSessionAcquireOperationRequest(BaseModel):
    model_config = _PUBLIC_REQUEST_CONFIG

    provider: AuthProviderKind | None = None
    fresh: bool = False
    reset_lock: bool = False


class AuthTeardownOperationRequest(BaseModel):
    model_config = _PUBLIC_REQUEST_CONFIG

    provider: AuthProviderKind | None = None
    all_providers: bool = False


class ProfilePassphraseRotationOperationRequest(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID


class _PassphraseRotationSecret(BaseModel):
    """Runtime-only JSON carried solely by the one-shot broker."""

    model_config = STRICT_FROZEN_CONFIG

    current_passphrase: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


def _require_profile_subject[PayloadT: BaseModel](request: OperationRequest[PayloadT], profile_id: UUID) -> None:
    if request.subject_ref != _profile_subject(profile_id):
        raise ValueError("auth operation subject does not match its exact profile")


def _require_active_profile_subject[PayloadT: BaseModel](request: OperationRequest[PayloadT]) -> str:
    """Bind active-profile authorities to the operation's exact profile subject."""
    try:
        profile_id = UUID(request.subject_ref.removeprefix("profile:"))
    except ValueError as error:
        raise ValueError("auth operation subject is not a canonical profile reference") from error
    if request.subject_ref != _profile_subject(profile_id):
        raise ValueError("auth operation subject is not a canonical profile reference")
    if require_active_bucket_id() != str(profile_id):
        raise ValueError("auth operation requires its profile to be active")
    return str(profile_id)


async def _result_reference(result: BaseModel, context: OperationExecutorContext) -> str:
    """Persist a post-custody result or retain the safe profile reference."""
    if context.identity.definition_id in {
        PROFILE_LOGIN_OPERATION_DEFINITION_ID,
        PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID,
    }:
        return context.identity.subject_ref
    return await context.operands.put(result, written_at=now())


class ProfileLoginOperationExecutor:
    def __init__(self, *, login: Callable[..., ProfileLoginOutcome] = login_profile) -> None:
        self._login = login

    async def execute(
        self,
        request: OperationRequest[ProfileLoginOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        _require_profile_subject(request, request.payload.profile_id)
        await context.events.phase("auth.login.secret-consume")
        async with context.ephemeral_secret.consume() as secret:
            passphrase = bytes(secret).decode("utf-8")
            try:
                await context.events.effect(OperationEffect.UNKNOWN)
                await context.events.phase("auth.login.execute")
                result = self._login(name=str(request.payload.profile_id), passphrase_callback=lambda: passphrase)
            finally:
                passphrase = ""
        if result.bucket_id != str(request.payload.profile_id):
            raise ValueError("profile login returned a different profile")
        await context.events.effect(OperationEffect.NONE if result.already_authenticated else OperationEffect.UPDATED)
        await context.events.phase("auth.login.settlement")
        return await _result_reference(result, context)


class ProfilePassphraseRotationOperationExecutor:
    def __init__(
        self,
        *,
        rotate_passphrase: Callable[..., ProfilePassphraseRotationOutcome] = rotate_profile_passphrase,
    ) -> None:
        self._rotate_passphrase = rotate_passphrase

    async def execute(
        self,
        request: OperationRequest[ProfilePassphraseRotationOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        _require_profile_subject(request, request.payload.profile_id)
        await context.events.phase("auth.passphrase.secret-consume")
        async with context.ephemeral_secret.consume() as secret:
            parsed = _PassphraseRotationSecret.model_validate(json.loads(bytes(secret).decode("utf-8")), strict=True)
            current = parsed.current_passphrase.get_secret_value()
            replacement = parsed.new_passphrase.get_secret_value()
            confirmation = parsed.new_passphrase_confirmation.get_secret_value()
            try:
                await context.events.effect(OperationEffect.UNKNOWN)
                await context.events.phase("auth.passphrase.execute")
                result = self._rotate_passphrase(
                    profile_id=request.payload.profile_id,
                    current_passphrase=current,
                    new_passphrase=replacement,
                    new_passphrase_confirmation=confirmation,
                )
            finally:
                current = replacement = confirmation = ""
                del parsed
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase("auth.passphrase.settlement")
        return await _result_reference(result, context)


class AuthConfigureOperationExecutor:
    def __init__(self, *, configure: Callable[..., AuthConfigureResult] = configure_operator_auth) -> None:
        self._configure = configure

    async def execute(
        self,
        request: OperationRequest[AuthConfigureOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        _require_active_profile_subject(request)
        await context.events.phase("auth.configure.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.configure.execute")
        result = self._configure(
            request.payload.provider.value,
            certificate_path=request.payload.certificate_path,
        )
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase("auth.configure.settlement")
        return await _result_reference(result, context)


class AuthSessionAcquireOperationExecutor:
    def __init__(self, *, acquire: Callable[..., Awaitable[AuthLoginResult]] = login_operator_auth) -> None:
        self._acquire = acquire

    async def execute(
        self,
        request: OperationRequest[AuthSessionAcquireOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        _require_active_profile_subject(request)
        await context.events.phase("auth.acquire.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.acquire.execute")
        result = await self._acquire(
            request.payload.provider.value if request.payload.provider is not None else None,
            fresh=request.payload.fresh,
            reset_lock=request.payload.reset_lock,
        )
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase("auth.acquire.settlement")
        return await _result_reference(result, context)


class AuthLogoutOperationExecutor:
    def __init__(self, *, logout: Callable[..., AuthLogoutResult] = logout_operator_auth) -> None:
        self._logout = logout

    async def execute(
        self,
        request: OperationRequest[AuthTeardownOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        target_bucket_id = _require_active_profile_subject(request)
        await context.events.phase("auth.logout.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.logout.execute")
        result = self._logout(
            provider=request.payload.provider.value if request.payload.provider is not None else None,
            all_providers=request.payload.all_providers,
            target_bucket_id=target_bucket_id,
        )
        changed = result.removed_sessions or result.cleared_session_state
        await context.events.effect(OperationEffect.UPDATED if changed else OperationEffect.NONE)
        await context.events.phase("auth.logout.settlement")
        return await _result_reference(result, context)


class AuthResetOperationExecutor:
    def __init__(self, *, reset: Callable[..., AuthResetResult] = reset_operator_auth) -> None:
        self._reset = reset

    async def execute(
        self,
        request: OperationRequest[AuthTeardownOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        target_bucket_id = _require_active_profile_subject(request)
        await context.events.phase("auth.reset.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.reset.execute")
        result = self._reset(
            provider=request.payload.provider.value if request.payload.provider is not None else None,
            all_providers=request.payload.all_providers,
            target_bucket_id=target_bucket_id,
        )
        changed = any(
            (
                result.removed_sessions,
                result.cleared_provider_configuration,
                result.cleared_locks,
                result.removed_certificate_sources,
                result.removed_certificate_secrets,
            )
        )
        await context.events.effect(OperationEffect.UPDATED if changed else OperationEffect.NONE)
        await context.events.phase("auth.reset.settlement")
        return await _result_reference(result, context)


def _definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build: Callable[[], object],
    phases: tuple[str, ...],
    secret_kind: str | None = None,
    request_storage: OperationRequestStoragePolicy = OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=phases,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=request_storage,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP, OperationFrontendProjection.TUI}
        ),
        ephemeral_secret=(
            None
            if secret_kind is None
            else OperationEphemeralSecretDeclaration(
                secret_kind=secret_kind,
                lifetime=timedelta(minutes=5),
            )
        ),
    )


def _build_auth_operation_definitions(
    *,
    profile_login: Callable[..., ProfileLoginOutcome] = login_profile,
    rotate_passphrase: Callable[..., ProfilePassphraseRotationOutcome] = rotate_profile_passphrase,
    configure: Callable[..., AuthConfigureResult] = configure_operator_auth,
    acquire: Callable[..., Awaitable[AuthLoginResult]] = login_operator_auth,
    logout: Callable[..., AuthLogoutResult] = logout_operator_auth,
    reset: Callable[..., AuthResetResult] = reset_operator_auth,
) -> tuple[OperationDefinition, ...]:
    return (
        _definition(
            definition_id=PROFILE_LOGIN_OPERATION_DEFINITION_ID,
            request_type=ProfileLoginOperationRequest,
            result_type=ProfileLoginOutcome,
            executor_type=ProfileLoginOperationExecutor,
            build=lambda: ProfileLoginOperationExecutor(login=profile_login),
            phases=("auth.login.secret-consume", "auth.login.execute", "auth.login.settlement"),
            secret_kind="profile.login.passphrase",  # noqa: S106
        ),
        _definition(
            definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            request_type=AuthConfigureOperationRequest,
            result_type=AuthConfigureResult,
            executor_type=AuthConfigureOperationExecutor,
            build=lambda: AuthConfigureOperationExecutor(configure=configure),
            phases=("auth.configure.preflight", "auth.configure.execute", "auth.configure.settlement"),
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        ),
        _definition(
            definition_id=AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
            request_type=AuthSessionAcquireOperationRequest,
            result_type=AuthLoginResult,
            executor_type=AuthSessionAcquireOperationExecutor,
            build=lambda: AuthSessionAcquireOperationExecutor(acquire=acquire),
            phases=("auth.acquire.preflight", "auth.acquire.execute", "auth.acquire.settlement"),
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        ),
        _definition(
            definition_id=AUTH_LOGOUT_OPERATION_DEFINITION_ID,
            request_type=AuthTeardownOperationRequest,
            result_type=AuthLogoutResult,
            executor_type=AuthLogoutOperationExecutor,
            build=lambda: AuthLogoutOperationExecutor(logout=logout),
            phases=("auth.logout.preflight", "auth.logout.execute", "auth.logout.settlement"),
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        ),
        _definition(
            definition_id=AUTH_RESET_OPERATION_DEFINITION_ID,
            request_type=AuthTeardownOperationRequest,
            result_type=AuthResetResult,
            executor_type=AuthResetOperationExecutor,
            build=lambda: AuthResetOperationExecutor(reset=reset),
            phases=("auth.reset.preflight", "auth.reset.execute", "auth.reset.settlement"),
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        ),
        _definition(
            definition_id=PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID,
            request_type=ProfilePassphraseRotationOperationRequest,
            result_type=ProfilePassphraseRotationOutcome,
            executor_type=ProfilePassphraseRotationOperationExecutor,
            build=lambda: ProfilePassphraseRotationOperationExecutor(rotate_passphrase=rotate_passphrase),
            phases=("auth.passphrase.secret-consume", "auth.passphrase.execute", "auth.passphrase.settlement"),
            secret_kind="profile.passphrase.rotation",  # noqa: S106
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        ),
    )


AUTH_OPERATION_DEFINITIONS = _build_auth_operation_definitions()


def build_auth_operation_definitions(
    *,
    profile_login: Callable[..., ProfileLoginOutcome] | None = None,
    rotate_passphrase: Callable[..., ProfilePassphraseRotationOutcome] | None = None,
    configure: Callable[..., AuthConfigureResult] | None = None,
    acquire: Callable[..., Awaitable[AuthLoginResult]] | None = None,
    logout: Callable[..., AuthLogoutResult] | None = None,
    reset: Callable[..., AuthResetResult] | None = None,
) -> tuple[OperationDefinition, ...]:
    """Build the owner registrations with optional outer authority ports."""
    if all(item is None for item in (profile_login, rotate_passphrase, configure, acquire, logout, reset)):
        return AUTH_OPERATION_DEFINITIONS
    return _build_auth_operation_definitions(
        profile_login=login_profile if profile_login is None else profile_login,
        rotate_passphrase=rotate_profile_passphrase if rotate_passphrase is None else rotate_passphrase,
        configure=configure_operator_auth if configure is None else configure,
        acquire=login_operator_auth if acquire is None else acquire,
        logout=logout_operator_auth if logout is None else logout,
        reset=reset_operator_auth if reset is None else reset,
    )


def build_auth_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind the auth-owned definitions to their stable public schemas."""
    return tuple(
        sorted(
            (
                OperationPublicDefinitionRegistrationV1.compose_request_only(
                    definition=definition,
                    request_schema_id=f"{definition.definition_id}.request",
                )
                for definition in definitions
            ),
            key=lambda item: item.contract.definition_id,
        )
    )


__all__ = [
    "AUTH_OPERATION_DEFINITIONS",
    "build_auth_operation_definitions",
    "build_auth_operation_registrations",
]
