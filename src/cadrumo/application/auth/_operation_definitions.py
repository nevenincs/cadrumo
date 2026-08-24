"""Canonical registered auth operations composed from existing authorities."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, SecretStr

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..operations import (
    CredentialFreeOperationRequest,
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationEphemeralSecretDeclaration,
    OperationExecutorContext,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationReconciliationPolicy,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..user_profile import (
    ProfileLoginOutcome,
    ProfilePassphraseRotationOutcome,
    login_profile,
    rotate_profile_passphrase,
)
from ._operator import configure_operator_auth, login_operator_auth, logout_operator_auth, reset_operator_auth
from ._operator_results import AuthConfigureResult, AuthLoginResult, AuthLogoutResult, AuthResetResult

PROFILE_LOGIN_OPERATION_DEFINITION_ID = "auth.profile.login"
AUTH_CONFIGURE_OPERATION_DEFINITION_ID = "auth.provider.configure"
AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID = "auth.session.acquire"
AUTH_LOGOUT_OPERATION_DEFINITION_ID = "auth.session.logout"
AUTH_RESET_OPERATION_DEFINITION_ID = "auth.session.reset"
PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID = "auth.profile.passphrase-rotate"


class ProfileLoginOperationRequest(CredentialFreeOperationRequest):
    profile_id: UUID


class AuthConfigureOperationRequest(CredentialFreeOperationRequest):
    provider: str
    certificate_path: Path | None = None


class AuthSessionAcquireOperationRequest(CredentialFreeOperationRequest):
    provider: str | None = None
    fresh: bool = False
    reset_lock: bool = False


class AuthTeardownOperationRequest(CredentialFreeOperationRequest):
    provider: str | None = None
    all_providers: bool = False


class ProfilePassphraseRotationOperationRequest(CredentialFreeOperationRequest):
    profile_id: UUID


class _PassphraseRotationSecret(BaseModel):
    """Runtime-only JSON carried solely by the one-shot broker."""

    model_config = STRICT_FROZEN_CONFIG

    current_passphrase: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


def _profile_subject(profile_id: UUID) -> str:
    return f"profile:{profile_id}"


def _require_profile_subject(request: OperationRequest[CredentialFreeOperationRequest], profile_id: UUID) -> None:
    if request.subject_ref != _profile_subject(profile_id):
        raise ValueError("auth operation subject does not match its exact profile")


async def _result_reference(result: BaseModel, context: OperationExecutorContext) -> str:
    """Persist a post-custody result or retain the safe profile reference."""
    if context.identity.definition_id == PROFILE_LOGIN_OPERATION_DEFINITION_ID:
        return context.identity.subject_ref
    return await context.operands.put(result, written_at=context.snapshot.updated_at)


class ProfileLoginOperationExecutor:
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
                result = login_profile(name=str(request.payload.profile_id), passphrase_callback=lambda: passphrase)
            finally:
                passphrase = ""
        if result.bucket_id != str(request.payload.profile_id):
            raise ValueError("profile login returned a different profile")
        await context.events.effect(OperationEffect.NONE if result.already_authenticated else OperationEffect.UPDATED)
        await context.events.phase("auth.login.settlement")
        return await _result_reference(result, context)


class ProfilePassphraseRotationOperationExecutor:
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
                result = rotate_profile_passphrase(
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
    async def execute(self, request: OperationRequest[AuthConfigureOperationRequest], context: OperationExecutorContext) -> str:
        await context.events.phase("auth.configure.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.configure.execute")
        result = configure_operator_auth(request.payload.provider, certificate_path=request.payload.certificate_path)
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase("auth.configure.settlement")
        return await _result_reference(result, context)


class AuthSessionAcquireOperationExecutor:
    async def execute(self, request: OperationRequest[AuthSessionAcquireOperationRequest], context: OperationExecutorContext) -> str:
        await context.events.phase("auth.acquire.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.acquire.execute")
        result = await login_operator_auth(
            request.payload.provider,
            fresh=request.payload.fresh,
            reset_lock=request.payload.reset_lock,
        )
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase("auth.acquire.settlement")
        return await _result_reference(result, context)


class AuthLogoutOperationExecutor:
    async def execute(self, request: OperationRequest[AuthTeardownOperationRequest], context: OperationExecutorContext) -> str:
        await context.events.phase("auth.logout.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.logout.execute")
        result = logout_operator_auth(
            provider=request.payload.provider,
            all_providers=request.payload.all_providers,
            target_bucket_id=request.subject_ref.removeprefix("profile:"),
        )
        await context.events.effect(OperationEffect.UPDATED if result.removed_sessions or result.cleared_session_state else OperationEffect.NONE)
        await context.events.phase("auth.logout.settlement")
        return await _result_reference(result, context)


class AuthResetOperationExecutor:
    async def execute(self, request: OperationRequest[AuthTeardownOperationRequest], context: OperationExecutorContext) -> str:
        await context.events.phase("auth.reset.preflight")
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase("auth.reset.execute")
        result = reset_operator_auth(
            provider=request.payload.provider,
            all_providers=request.payload.all_providers,
            target_bucket_id=request.subject_ref.removeprefix("profile:"),
        )
        changed = any((result.removed_sessions, result.cleared_provider_configuration, result.cleared_locks, result.removed_certificate_sources, result.removed_certificate_secrets))
        await context.events.effect(OperationEffect.UPDATED if changed else OperationEffect.NONE)
        await context.events.phase("auth.reset.settlement")
        return await _result_reference(result, context)


def _definition(
    *, definition_id: str, request_type: type[CredentialFreeOperationRequest], result_type: type[BaseModel], executor_type: type[object], phases: tuple[str, ...], secret_kind: str | None = None
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(request_type=request_type, executor_type=executor_type, build=executor_type),
        phase_codes=phases,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        ephemeral_secret=(
            None if secret_kind is None else OperationEphemeralSecretDeclaration(secret_kind=secret_kind, lifetime=timedelta(minutes=5))
        ),
    )


AUTH_OPERATION_DEFINITIONS = (
    _definition(definition_id=PROFILE_LOGIN_OPERATION_DEFINITION_ID, request_type=ProfileLoginOperationRequest, result_type=ProfileLoginOutcome, executor_type=ProfileLoginOperationExecutor, phases=("auth.login.secret-consume", "auth.login.execute", "auth.login.settlement"), secret_kind="profile.login.passphrase"),
    _definition(definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID, request_type=AuthConfigureOperationRequest, result_type=AuthConfigureResult, executor_type=AuthConfigureOperationExecutor, phases=("auth.configure.preflight", "auth.configure.execute", "auth.configure.settlement")),
    _definition(definition_id=AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID, request_type=AuthSessionAcquireOperationRequest, result_type=AuthLoginResult, executor_type=AuthSessionAcquireOperationExecutor, phases=("auth.acquire.preflight", "auth.acquire.execute", "auth.acquire.settlement")),
    _definition(definition_id=AUTH_LOGOUT_OPERATION_DEFINITION_ID, request_type=AuthTeardownOperationRequest, result_type=AuthLogoutResult, executor_type=AuthLogoutOperationExecutor, phases=("auth.logout.preflight", "auth.logout.execute", "auth.logout.settlement")),
    _definition(definition_id=AUTH_RESET_OPERATION_DEFINITION_ID, request_type=AuthTeardownOperationRequest, result_type=AuthResetResult, executor_type=AuthResetOperationExecutor, phases=("auth.reset.preflight", "auth.reset.execute", "auth.reset.settlement")),
    _definition(definition_id=PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID, request_type=ProfilePassphraseRotationOperationRequest, result_type=ProfilePassphraseRotationOutcome, executor_type=ProfilePassphraseRotationOperationExecutor, phases=("auth.passphrase.secret-consume", "auth.passphrase.execute", "auth.passphrase.settlement"), secret_kind="profile.passphrase.rotation"),
)


def build_auth_operation_definitions() -> tuple[OperationDefinition, ...]:
    return AUTH_OPERATION_DEFINITIONS


__all__ = ["AUTH_OPERATION_DEFINITIONS", "build_auth_operation_definitions"]
