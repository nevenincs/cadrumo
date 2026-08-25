"""Canonical public registered operations for active user-profile maintenance."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    require_active_bucket_id,
)
from ...core.identity import ContentDigest
from ...core.time import now
from ..operations import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationEphemeralSecretDeclaration,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.owner import OperationExecutorContext
from ._bundle_export import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportResult,
    ProfileBundleExportTransport,
    export_profile_bundle,
)
from ._fact_write import apply_manager_profile_field_mutation
from ._login_session import logout_active_profile
from ._section_rows import add_profile_repeatable_section_row

PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID = "user-profile.field-mutation"
PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID = "user-profile.repeatable-row-mutation"
PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID = "user-profile.bundle-export"
PROFILE_LOGOUT_OPERATION_DEFINITION_ID = "user-profile.logout"

_PROFILE_FIELD_MUTATION_PHASES = (
    "user-profile.field-mutation.preflight",
    "user-profile.field-mutation.execute",
    "user-profile.field-mutation.settlement",
)
_PROFILE_REPEATABLE_ROW_MUTATION_PHASES = (
    "user-profile.repeatable-row-mutation.preflight",
    "user-profile.repeatable-row-mutation.execute",
    "user-profile.repeatable-row-mutation.settlement",
)
_PROFILE_BUNDLE_EXPORT_PHASES = (
    "user-profile.bundle-export.preflight",
    "user-profile.bundle-export.secret-consume",
    "user-profile.bundle-export.execute",
    "user-profile.bundle-export.settlement",
)
_PROFILE_LOGOUT_PHASES = (
    "user-profile.logout.preflight",
    "user-profile.logout.execute",
    "user-profile.logout.settlement",
)


class ProfileFieldMutationOperationRequest(BaseModel):
    """One manager-style scalar field replacement for the active profile."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    path: str = Field(min_length=3, max_length=160)
    value: str


class ProfileRepeatableRowValue(BaseModel):
    """One submitted value keyed by its field within a schema-declared row."""

    model_config = STRICT_FROZEN_CONFIG

    field_key: str = Field(min_length=1, max_length=120)
    value: str


class ProfileRepeatableRowMutationOperationRequest(BaseModel):
    """One atomic new-row request for a schema-declared repeatable section."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    section_key: str = Field(min_length=1, max_length=120)
    values: tuple[ProfileRepeatableRowValue, ...] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _require_distinct_field_keys(
        cls, value: tuple[ProfileRepeatableRowValue, ...]
    ) -> tuple[ProfileRepeatableRowValue, ...]:
        keys = tuple(item.field_key for item in value)
        if len(set(keys)) != len(keys):
            raise ValueError("repeatable-row operation values must not repeat a field key")
        if not any(item.value.strip() for item in value):
            raise ValueError("repeatable-row operation must include at least one non-blank value")
        return value


class ProfileBundleExportOperationRequest(BaseModel):
    """One active-profile bundle publication request retained in encrypted custody."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    destination: Path
    purpose: ProfileBundleExportPurpose


class ProfileMutationOperationResult(BaseModel):
    """Safe revision witness for a completed profile-fact mutation."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest


class ProfileRepeatableRowMutationOperationResult(ProfileMutationOperationResult):
    """Safe row identity and revision witness for a completed row mutation."""

    section_key: str = Field(min_length=1, max_length=120)
    row_index: int = Field(ge=0)


class ProfileLogoutOperationResult(BaseModel):
    """Declared result shape for a strong-close operation.

    The executor returns its profile subject reference instead of persisting this
    result after the strong close, because the active profile's encrypted
    operand store is deliberately no longer available at that point.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    logged_out: bool


class ProfileLogoutOperationRequest(BaseModel):
    """One strong-close request for the exact active profile subject."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID


def build_profile_logout_operation_request(
    profile_id: UUID,
) -> OperationRequest[ProfileLogoutOperationRequest]:
    """Build the sole typed strong-close request for an active profile."""
    return OperationRequest(
        definition_id=PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
        subject_ref=_profile_subject(profile_id),
        payload=ProfileLogoutOperationRequest(profile_id=profile_id),
    )


def _profile_subject(profile_id: UUID) -> str:
    return f"profile:{profile_id}"


def _require_active_profile_subject[PayloadT: BaseModel](request: OperationRequest[PayloadT], profile_id: UUID) -> None:
    """Bind every active-profile authority to exactly its secure operation subject."""
    if request.subject_ref != _profile_subject(profile_id):
        raise ValueError("user-profile operation subject does not match its exact profile")
    if require_active_bucket_id() != str(profile_id):
        raise ValueError("user-profile operation requires its profile to be active")


async def _result_reference(result: BaseModel, context: OperationExecutorContext) -> str:
    """Persist a post-mutation result through the supervisor's encrypted operand store."""
    return await context.operands.put(result, written_at=now())


class ProfileFieldMutationOperationExecutor:
    """Delegate one scalar replacement to the canonical profile-fact write door."""

    async def execute(
        self,
        request: OperationRequest[ProfileFieldMutationOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_FIELD_MUTATION_PHASES[0])
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(_PROFILE_FIELD_MUTATION_PHASES[1])
        record = apply_manager_profile_field_mutation(
            profile_id=str(payload.profile_id),
            path=payload.path,
            value=payload.value,
        )
        result = ProfileMutationOperationResult(
            profile_id=payload.profile_id,
            record_revision=record.record_revision,
            content_digest=record.content_digest,
        )
        result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase(_PROFILE_FIELD_MUTATION_PHASES[2])
        return result_ref


class ProfileRepeatableRowMutationOperationExecutor:
    """Delegate one whole repeatable row to the shared schema and fact-write authorities."""

    async def execute(
        self,
        request: OperationRequest[ProfileRepeatableRowMutationOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_MUTATION_PHASES[0])
        values = {item.field_key: item.value for item in payload.values}
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_MUTATION_PHASES[1])
        mutation = add_profile_repeatable_section_row(
            profile_id=str(payload.profile_id),
            section_key=payload.section_key,
            values=values,
        )
        result = ProfileRepeatableRowMutationOperationResult(
            profile_id=payload.profile_id,
            record_revision=mutation.record.record_revision,
            content_digest=mutation.record.content_digest,
            section_key=mutation.section_key,
            row_index=mutation.row_index,
        )
        result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_MUTATION_PHASES[2])
        return result_ref


class ProfileBundleExportOperationExecutor:
    """Publish through the existing crash-reconcilable bundle export authority."""

    async def execute(
        self,
        request: OperationRequest[ProfileBundleExportOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_BUNDLE_EXPORT_PHASES[0])
        await context.events.phase(_PROFILE_BUNDLE_EXPORT_PHASES[1])
        async with context.ephemeral_secret.consume() as secret:
            passphrase = bytes(secret).decode("utf-8")
            try:
                await context.events.effect(OperationEffect.UNKNOWN)
                await context.events.phase(_PROFILE_BUNDLE_EXPORT_PHASES[2])
                result = export_profile_bundle(
                    ProfileBundleExportRequest(
                        profile_name=None,
                        destination=payload.destination,
                        purpose=payload.purpose,
                        transport=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED,
                        passphrase=SecretStr(passphrase),
                    )
                )
            finally:
                passphrase = ""
        result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase(_PROFILE_BUNDLE_EXPORT_PHASES[3])
        return result_ref


class ProfileLogoutOperationExecutor:
    """Strong-close through the one session-revocation authority."""

    async def execute(
        self,
        request: OperationRequest[ProfileLogoutOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_LOGOUT_PHASES[0])
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(_PROFILE_LOGOUT_PHASES[1])
        signed_out = logout_active_profile()
        await context.events.effect(OperationEffect.UPDATED if signed_out is not None else OperationEffect.NONE)
        await context.events.phase(_PROFILE_LOGOUT_PHASES[2])
        return request.subject_ref


def _definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    phase_codes: tuple[str, ...],
    ephemeral_secret: OperationEphemeralSecretDeclaration | None = None,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=executor_type,
        ),
        phase_codes=phase_codes,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP, OperationFrontendProjection.TUI}
        ),
        ephemeral_secret=ephemeral_secret,
    )


USER_PROFILE_OPERATION_DEFINITIONS = (
    _definition(
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        request_type=ProfileFieldMutationOperationRequest,
        result_type=ProfileMutationOperationResult,
        executor_type=ProfileFieldMutationOperationExecutor,
        phase_codes=_PROFILE_FIELD_MUTATION_PHASES,
    ),
    _definition(
        definition_id=PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
        request_type=ProfileRepeatableRowMutationOperationRequest,
        result_type=ProfileRepeatableRowMutationOperationResult,
        executor_type=ProfileRepeatableRowMutationOperationExecutor,
        phase_codes=_PROFILE_REPEATABLE_ROW_MUTATION_PHASES,
    ),
    _definition(
        definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ProfileBundleExportOperationRequest,
        result_type=ProfileBundleExportResult,
        executor_type=ProfileBundleExportOperationExecutor,
        phase_codes=_PROFILE_BUNDLE_EXPORT_PHASES,
        ephemeral_secret=OperationEphemeralSecretDeclaration(
            secret_kind="profile.bundle-export.passphrase",  # noqa: S106
            lifetime=timedelta(minutes=5),
        ),
    ),
    _definition(
        definition_id=PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
        request_type=ProfileLogoutOperationRequest,
        result_type=ProfileLogoutOperationResult,
        executor_type=ProfileLogoutOperationExecutor,
        phase_codes=_PROFILE_LOGOUT_PHASES,
    ),
)


def build_user_profile_operation_definitions() -> tuple[OperationDefinition, ...]:
    """Return the one canonical profile-maintenance operation population."""
    return USER_PROFILE_OPERATION_DEFINITIONS


def build_user_profile_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind profile-maintenance definitions to their stable public schemas."""
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
    "PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID",
    "PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID",
    "PROFILE_LOGOUT_OPERATION_DEFINITION_ID",
    "PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID",
    "USER_PROFILE_OPERATION_DEFINITIONS",
    "ProfileBundleExportOperationRequest",
    "ProfileFieldMutationOperationRequest",
    "ProfileLogoutOperationRequest",
    "ProfileLogoutOperationResult",
    "ProfileMutationOperationResult",
    "ProfileRepeatableRowMutationOperationRequest",
    "ProfileRepeatableRowMutationOperationResult",
    "ProfileRepeatableRowValue",
    "build_profile_logout_operation_request",
    "build_user_profile_operation_definitions",
    "build_user_profile_operation_registrations",
]
