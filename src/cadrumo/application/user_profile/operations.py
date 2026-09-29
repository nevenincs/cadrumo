"""Canonical public registered operations for active user-profile maintenance."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, SecretStr, field_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
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
from ...domain.user_profile.plantilla_media import PlantillaMediaState
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from .access_errors import ProfileAccessRefusedError
from .bundle_export import export_profile_bundle
from .bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportResult,
    ProfileBundleExportTransport,
)
from .descendant_rows import ProfileDescendantRow, replace_profile_descendants
from .fact_write import apply_manager_profile_field_mutation
from .login_session import logout_active_profile
from .plantilla_media_rows import PlantillaMediaWriteSurface, remove_plantilla_media_year, set_plantilla_media_year
from .profile_record_repository import ProfileRecordRepository
from .section_rows import (
    add_profile_repeatable_section_row,
    remove_profile_repeatable_section_row,
    update_profile_repeatable_section_row,
)
from .view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    PROFILE_VIEW_PHASES,
    ProfileViewOperationProjection,
    ProfileViewOperationRequest,
    ProfileViewOperationResult,
    project_profile_view_result,
    read_profile_view_page,
)

PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID = "user-profile.field-mutation"
PROFILE_PATCH_OPERATION_DEFINITION_ID = "user-profile.patch"
PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID = "user-profile.plantilla-media"
PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID = "user-profile.descendants"
PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID = "user-profile.repeatable-row-mutation"
PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID = "user-profile.repeatable-row-update"
PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID = "user-profile.repeatable-row-remove"
PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID = "user-profile.complete-setup"
PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID = "user-profile.bundle-export"
PROFILE_LOGOUT_OPERATION_DEFINITION_ID = "user-profile.logout"

_PROFILE_FIELD_MUTATION_PHASES = (
    "user-profile.field-mutation.preflight",
    "user-profile.field-mutation.execute",
    "user-profile.field-mutation.settlement",
)
_PROFILE_PATCH_PHASES = (
    "user-profile.patch.preflight",
    "user-profile.patch.execute",
    "user-profile.patch.settlement",
)
_PROFILE_PLANTILLA_MEDIA_PHASES = (
    "user-profile.plantilla-media.preflight",
    "user-profile.plantilla-media.execute",
    "user-profile.plantilla-media.settlement",
)
_PROFILE_DESCENDANTS_PHASES = (
    "user-profile.descendants.preflight",
    "user-profile.descendants.execute",
    "user-profile.descendants.settlement",
)
_PROFILE_REPEATABLE_ROW_MUTATION_PHASES = (
    "user-profile.repeatable-row-mutation.preflight",
    "user-profile.repeatable-row-mutation.execute",
    "user-profile.repeatable-row-mutation.settlement",
)
_PROFILE_REPEATABLE_ROW_UPDATE_PHASES = (
    "user-profile.repeatable-row-update.preflight",
    "user-profile.repeatable-row-update.execute",
    "user-profile.repeatable-row-update.settlement",
)
_PROFILE_REPEATABLE_ROW_REMOVE_PHASES = (
    "user-profile.repeatable-row-remove.preflight",
    "user-profile.repeatable-row-remove.execute",
    "user-profile.repeatable-row-remove.settlement",
)
_PROFILE_COMPLETE_SETUP_PHASES = (
    "user-profile.complete-setup.preflight",
    "user-profile.complete-setup.execute",
    "user-profile.complete-setup.settlement",
)
_PROFILE_BUNDLE_EXPORT_PHASES = (
    "user-profile.bundle-export.preflight",
    "user-profile.bundle-export.secret-consume",
    "user-profile.bundle-export.execute",
    "user-profile.bundle-export.settlement",
)
_PROFILE_BUNDLE_EXPORT_KIND = "profile.bundle-export.passphrase"
_PROFILE_LOGOUT_PHASES = (
    "user-profile.logout.preflight",
    "user-profile.logout.execute",
    "user-profile.logout.settlement",
)


class ProfileFieldMutationOperationRequest(BaseModel):
    """One manager-style scalar field replacement for the active profile."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest
    path: str = Field(min_length=3, max_length=160)
    value: str


class ProfilePatchValue(BaseModel):
    """One explicitly supplied wizard answer, including an explicit blank."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    question_id: str = Field(min_length=1, max_length=120)
    value: str = Field(max_length=4096, repr=False)


class ProfilePatchOperationRequest(BaseModel):
    """One atomic wizard patch against an exact encrypted profile revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest
    values: tuple[ProfilePatchValue, ...] = Field(default=(), max_length=256, repr=False)
    colegio_concertado: bool | None = None

    @field_validator("values")
    @classmethod
    @pydantic_validation_boundary
    def _require_distinct_questions(cls, values: tuple[ProfilePatchValue, ...]) -> tuple[ProfilePatchValue, ...]:
        if len({item.question_id for item in values}) != len(values):
            raise ValueError("profile patch must not repeat a question")
        return values


class ProfilePlantillaMediaSet(BaseModel):
    """Declare one calendar year's exact, unrounded workforce amount."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["set"] = "set"
    average_workforce: str = Field(min_length=1, max_length=128, repr=False)
    state: PlantillaMediaState

    @field_validator("average_workforce")
    @classmethod
    @pydantic_validation_boundary
    def _require_finite_decimal(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("average workforce must be decimal text") from error
        if not amount.is_finite():
            raise ValueError("average workforce must be finite")
        return value


class ProfilePlantillaMediaRemove(BaseModel):
    """Withdraw a declared calendar year without reusing its stored index."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["remove"] = "remove"


class ProfilePlantillaMediaOperationRequest(BaseModel):
    """One atomic year mutation against an exact profile revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest
    year: int
    change: Annotated[ProfilePlantillaMediaSet | ProfilePlantillaMediaRemove, Field(discriminator="kind")]


class ProfileDescendantsOperationRequest(BaseModel):
    """Replace a complete descendant family at an exact encrypted revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest
    descendants: tuple[ProfileDescendantRow, ...] = Field(max_length=256, repr=False)


class ProfileRepeatableRowValue(BaseModel):
    """One submitted value keyed by its field within a schema-declared row."""

    model_config = STRICT_FROZEN_CONFIG

    field_key: str = Field(min_length=1, max_length=120)
    value: str


class ProfileRepeatableRowMutationOperationRequest(BaseModel):
    """One atomic new-row request for a schema-declared repeatable section."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest
    section_key: str = Field(min_length=1, max_length=120)
    values: tuple[ProfileRepeatableRowValue, ...] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    @pydantic_validation_boundary
    def _require_distinct_field_keys(
        cls, value: tuple[ProfileRepeatableRowValue, ...]
    ) -> tuple[ProfileRepeatableRowValue, ...]:
        keys = tuple(item.field_key for item in value)
        if len(set(keys)) != len(keys):
            raise ValueError("repeatable-row operation values must not repeat a field key")
        if not any(item.value.strip() for item in value):
            raise ValueError("repeatable-row operation must include at least one non-blank value")
        return value


class ProfileRepeatableRowTargetOperationRequest(BaseModel):
    """One stable existing schema row and exact profile revision."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest
    section_key: str = Field(min_length=1, max_length=120)
    row_key: str = Field(max_length=20)

    @field_validator("row_key")
    @classmethod
    @pydantic_validation_boundary
    def _require_canonical_row_key(cls, value: str) -> str:
        if value and (not value.isdecimal() or str(int(value)) != value):
            raise ValueError("repeatable-row identity must be a canonical index or empty base row")
        return value


class ProfileRepeatableRowUpdateOperationRequest(ProfileRepeatableRowTargetOperationRequest):
    """Replace only named row fields and explicitly clear named fields."""

    values: tuple[ProfileRepeatableRowValue, ...] = ()
    clear_fields: tuple[str, ...] = ()

    @field_validator("values")
    @classmethod
    @pydantic_validation_boundary
    def _require_distinct_values(
        cls, value: tuple[ProfileRepeatableRowValue, ...]
    ) -> tuple[ProfileRepeatableRowValue, ...]:
        if len({item.field_key for item in value}) != len(value):
            raise ValueError("repeatable-row update values must not repeat a field key")
        return value

    @field_validator("clear_fields")
    @classmethod
    @pydantic_validation_boundary
    def _require_distinct_clears(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("repeatable-row update clear fields must not repeat a key")
        return value


class ProfileRepeatableRowRemoveOperationRequest(ProfileRepeatableRowTargetOperationRequest):
    """Remove one stable schema row through the canonical tombstone writer."""


class ProfileCompleteSetupOperationRequest(BaseModel):
    """Promote one fully populated exact profile revision to complete setup."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest


class ProfileBundleExportOperationRequest(BaseModel):
    """One active-profile bundle publication request retained in encrypted custody."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    destination: Path
    purpose: ProfileBundleExportPurpose

    @field_validator("destination")
    @classmethod
    @pydantic_validation_boundary
    def _require_absolute_destination(cls, destination: Path) -> Path:
        if not destination.is_absolute():
            raise ValueError("runtime bundle export requires an absolute destination")
        return destination


class ProfileBundleExportOperationProjection(ProfileBundleExportResult):
    """Public typed export receipt, released only after profile-value consent."""


def project_profile_bundle_export_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the canonical export receipt only for its settled profile subject."""
    if not isinstance(result, ProfileBundleExportResult):
        raise TypeError("unexpected profile bundle export result")
    if receipt.identity.subject_ref != _profile_subject(str(result.profile_id)):
        raise ValueError("profile bundle export result does not match its settled subject")
    return ProfileBundleExportOperationProjection.model_validate(result.model_dump(mode="python"))


class ProfileMutationOperationResult(BaseModel):
    """Safe revision witness for a completed profile-fact mutation."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest


class ProfilePatchOperationResult(ProfileMutationOperationResult):
    """Encrypted revision witness for the complete atomic patch."""

    changed: bool


class ProfilePlantillaMediaOperationResult(ProfileMutationOperationResult):
    """Encrypted publication witness for one calendar year's workforce."""

    year: int
    changed: bool


class ProfileDescendantsOperationResult(ProfileMutationOperationResult):
    """Encrypted family replacement witness without retained personal rows."""

    total: NonNegativeInt
    changed: bool


class ProfileRepeatableRowMutationOperationResult(ProfileMutationOperationResult):
    """Safe row identity and revision witness for a completed row mutation."""

    section_key: str = Field(min_length=1, max_length=120)
    row_index: NonNegativeInt


class ProfileRepeatableRowChangeOperationResult(ProfileMutationOperationResult):
    """Safe durable witness for an existing row's update or removal."""

    section_key: str = Field(min_length=1, max_length=120)
    row_key: str = Field(max_length=20)
    changed: bool


class ProfileCompleteSetupOperationResult(ProfileMutationOperationResult):
    """Safe durable witness for a setup promotion or idempotent no-op."""

    already_complete: bool


class ProfileMutationOperationProjection(BaseModel):
    """Public profile revision witness, excluding private result content fingerprints."""

    model_config = STRICT_FROZEN_CONFIG
    profile_id: UUID
    record_revision: int = Field(ge=1)


class ProfilePatchOperationProjection(ProfileMutationOperationProjection):
    """Public atomic patch outcome without private facts or content fingerprint."""

    changed: bool


class ProfilePlantillaMediaOperationProjection(ProfileMutationOperationProjection):
    """Settled year and revision without private workforce values or fingerprints."""

    year: int
    changed: bool


class ProfileDescendantsOperationProjection(ProfileMutationOperationProjection):
    """Settled family count and change without personal rows or fingerprints."""

    total: NonNegativeInt
    changed: bool


class ProfileRepeatableRowMutationOperationProjection(ProfileMutationOperationProjection):
    """Public location of the newly committed profile row."""

    section_key: str = Field(min_length=1, max_length=120)
    row_index: NonNegativeInt


class ProfileRepeatableRowChangeOperationProjection(ProfileMutationOperationProjection):
    """Public stable row identity and whether the record changed."""

    section_key: str = Field(min_length=1, max_length=120)
    row_key: str = Field(max_length=20)
    changed: bool


class ProfileCompleteSetupOperationProjection(ProfileMutationOperationProjection):
    """Public setup completion witness without private content digest."""

    already_complete: bool


def project_profile_mutation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the declared profile witness after exact-subject validation."""
    if not isinstance(result, ProfileMutationOperationResult):
        raise TypeError("unexpected profile mutation result")
    if receipt.identity.subject_ref != _profile_subject(str(result.profile_id)):
        raise ValueError("profile mutation result does not match its settled subject")
    if isinstance(result, ProfilePatchOperationResult):
        return ProfilePatchOperationProjection(
            profile_id=result.profile_id,
            record_revision=result.record_revision,
            changed=result.changed,
        )
    if isinstance(result, ProfilePlantillaMediaOperationResult):
        return ProfilePlantillaMediaOperationProjection(
            profile_id=result.profile_id,
            record_revision=result.record_revision,
            year=result.year,
            changed=result.changed,
        )
    if isinstance(result, ProfileDescendantsOperationResult):
        return ProfileDescendantsOperationProjection(
            profile_id=result.profile_id,
            record_revision=result.record_revision,
            total=result.total,
            changed=result.changed,
        )
    if isinstance(result, ProfileRepeatableRowChangeOperationResult):
        return ProfileRepeatableRowChangeOperationProjection(
            profile_id=result.profile_id,
            record_revision=result.record_revision,
            section_key=result.section_key,
            row_key=result.row_key,
            changed=result.changed,
        )
    if isinstance(result, ProfileRepeatableRowMutationOperationResult):
        return ProfileRepeatableRowMutationOperationProjection(
            profile_id=result.profile_id,
            record_revision=result.record_revision,
            section_key=result.section_key,
            row_index=result.row_index,
        )
    if isinstance(result, ProfileCompleteSetupOperationResult):
        return ProfileCompleteSetupOperationProjection(
            profile_id=result.profile_id,
            record_revision=result.record_revision,
            already_complete=result.already_complete,
        )
    return ProfileMutationOperationProjection(profile_id=result.profile_id, record_revision=result.record_revision)


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
        subject_ref=_profile_subject(str(profile_id)),
        payload=ProfileLogoutOperationRequest(profile_id=profile_id),
    )


def _require_active_profile_subject[PayloadT: BaseModel](request: OperationRequest[PayloadT], profile_id: UUID) -> None:
    """Bind every active-profile authority to exactly its secure operation subject."""
    if request.subject_ref != _profile_subject(str(profile_id)):
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
        async with context.cancellation.irreversible_section():
            record = await await_cancellation_complete(
                asyncio.to_thread(
                    apply_manager_profile_field_mutation,
                    profile_id=str(payload.profile_id),
                    path=payload.path,
                    value=payload.value,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-field-mutation",
            )
            result = ProfileMutationOperationResult(
                profile_id=payload.profile_id,
                record_revision=record.record_revision,
                content_digest=record.content_digest,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(
            OperationEffect.UPDATED if record.record_revision != payload.expected_revision else OperationEffect.NONE
        )
        await context.events.phase(_PROFILE_FIELD_MUTATION_PHASES[2])
        return result_ref


class ProfilePatchOperationExecutor:
    """Validate and commit every supplied wizard answer as one profile change."""

    async def execute(
        self,
        request: OperationRequest[ProfilePatchOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        from ..wizard.catalogue import build_setup_flow
        from ..wizard.patch_edit import apply_profile_patch

        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_PATCH_PHASES[0])
        flow = build_setup_flow(context.authority_operation)
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(_PROFILE_PATCH_PHASES[1])
        async with context.cancellation.irreversible_section():
            record = await await_cancellation_complete(
                asyncio.to_thread(
                    apply_profile_patch,
                    flow=flow,
                    profile_id=str(payload.profile_id),
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    supplied={item.question_id: item.value for item in payload.values},
                    colegio_concertado=payload.colegio_concertado,
                    operation=context.authority_operation,
                ),
                task_name="profile-atomic-patch",
            )
            result = ProfilePatchOperationResult(
                profile_id=payload.profile_id,
                record_revision=record.record_revision,
                content_digest=record.content_digest,
                changed=record.record_revision != payload.expected_revision,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED if result.changed else OperationEffect.NONE)
        await context.events.phase(_PROFILE_PATCH_PHASES[2])
        return result_ref


class ProfilePlantillaMediaOperationExecutor:
    """Own the canonical year's publication and result through cancellation."""

    async def execute(
        self,
        request: OperationRequest[ProfilePlantillaMediaOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Persist the actual year mutation witness inside its commit guard."""
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_PLANTILLA_MEDIA_PHASES[0])
        decode = context.authority_operation.profile_decode_context()
        await context.events.phase(_PROFILE_PLANTILLA_MEDIA_PHASES[1])

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                if isinstance(payload.change, ProfilePlantillaMediaSet):
                    mutation = await asyncio.to_thread(
                        set_plantilla_media_year,
                        profile_id=str(payload.profile_id),
                        year=payload.year,
                        average_workforce=Decimal(payload.change.average_workforce),
                        state=payload.change.state,
                        surface=PlantillaMediaWriteSurface.MANAGER,
                        expected_revision=payload.expected_revision,
                        expected_content_digest=payload.expected_content_digest,
                        profile_decode_context=decode,
                    )
                else:
                    mutation = await asyncio.to_thread(
                        remove_plantilla_media_year,
                        profile_id=str(payload.profile_id),
                        year=payload.year,
                        surface=PlantillaMediaWriteSurface.MANAGER,
                        expected_revision=payload.expected_revision,
                        expected_content_digest=payload.expected_content_digest,
                        profile_decode_context=decode,
                    )
                result_ref = await _result_reference(
                    ProfilePlantillaMediaOperationResult(
                        profile_id=payload.profile_id,
                        record_revision=mutation.record.record_revision,
                        content_digest=mutation.record.content_digest,
                        year=payload.year,
                        changed=mutation.changed,
                    ),
                    context,
                )
                await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
                return result_ref

        result_ref = await await_cancellation_complete(publish(), task_name="profile-plantilla-media-publication")
        await context.events.phase(_PROFILE_PLANTILLA_MEDIA_PHASES[2])
        return result_ref


class ProfileDescendantsOperationExecutor:
    """Retain one atomic family publication through cancellation and settlement."""

    async def execute(
        self,
        request: OperationRequest[ProfileDescendantsOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Publish count, canonical rows and orphan clears through one guarded CAS."""
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_DESCENDANTS_PHASES[0])
        await context.events.phase(_PROFILE_DESCENDANTS_PHASES[1])

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                mutation = await asyncio.to_thread(
                    replace_profile_descendants,
                    profile_id=str(payload.profile_id),
                    descendants=payload.descendants,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    operation=context.authority_operation,
                )
                result_ref = await _result_reference(
                    ProfileDescendantsOperationResult(
                        profile_id=payload.profile_id,
                        record_revision=mutation.record.record_revision,
                        content_digest=mutation.record.content_digest,
                        total=mutation.total,
                        changed=mutation.changed,
                    ),
                    context,
                )
                await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
                return result_ref

        result_ref = await await_cancellation_complete(publish(), task_name="profile-descendants-publication")
        await context.events.phase(_PROFILE_DESCENDANTS_PHASES[2])
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
        async with context.cancellation.irreversible_section():
            mutation = await await_cancellation_complete(
                asyncio.to_thread(
                    add_profile_repeatable_section_row,
                    profile_id=str(payload.profile_id),
                    section_key=payload.section_key,
                    values=values,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    schema=context.authority_operation.profile_schema(),
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-repeatable-row-mutation",
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


class ProfileRepeatableRowUpdateOperationExecutor:
    """Apply one exact-row patch through the canonical schema/fact writer."""

    async def execute(
        self,
        request: OperationRequest[ProfileRepeatableRowUpdateOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_UPDATE_PHASES[0])
        values = {item.field_key: item.value for item in payload.values}
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_UPDATE_PHASES[1])
        async with context.cancellation.irreversible_section():
            mutation = await await_cancellation_complete(
                asyncio.to_thread(
                    update_profile_repeatable_section_row,
                    profile_id=str(payload.profile_id),
                    section_key=payload.section_key,
                    row_key=payload.row_key,
                    values=values,
                    clear_fields=payload.clear_fields,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    schema=context.authority_operation.profile_schema(),
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-repeatable-row-update",
            )
            result = ProfileRepeatableRowChangeOperationResult(
                profile_id=payload.profile_id,
                record_revision=mutation.record.record_revision,
                content_digest=mutation.record.content_digest,
                section_key=mutation.section_key,
                row_key=mutation.row_key,
                changed=mutation.changed,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_UPDATE_PHASES[2])
        return result_ref


class ProfileRepeatableRowRemoveOperationExecutor:
    """Remove one exact row through the canonical schema/tombstone writer."""

    async def execute(
        self,
        request: OperationRequest[ProfileRepeatableRowRemoveOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_REMOVE_PHASES[0])
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_REMOVE_PHASES[1])
        async with context.cancellation.irreversible_section():
            mutation = await await_cancellation_complete(
                asyncio.to_thread(
                    remove_profile_repeatable_section_row,
                    profile_id=str(payload.profile_id),
                    section_key=payload.section_key,
                    row_key=payload.row_key,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    schema=context.authority_operation.profile_schema(),
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-repeatable-row-remove",
            )
            result = ProfileRepeatableRowChangeOperationResult(
                profile_id=payload.profile_id,
                record_revision=mutation.record.record_revision,
                content_digest=mutation.record.content_digest,
                section_key=mutation.section_key,
                row_key=mutation.row_key,
                changed=mutation.changed,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
        await context.events.phase(_PROFILE_REPEATABLE_ROW_REMOVE_PHASES[2])
        return result_ref


class ProfileCompleteSetupOperationExecutor:
    """Promote one complete profile through the canonical CAS lifecycle."""

    async def execute(
        self,
        request: OperationRequest[ProfileCompleteSetupOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(_PROFILE_COMPLETE_SETUP_PHASES[0])
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(_PROFILE_COMPLETE_SETUP_PHASES[1])
        async with context.cancellation.irreversible_section():
            record = await await_cancellation_complete(
                asyncio.to_thread(
                    lambda: ProfileRecordRepository.for_current_session(
                        payload.profile_id,
                        profile_decode_context=context.authority_operation.profile_decode_context(),
                    ).complete_setup(
                        payload.profile_id,
                        expected_revision=payload.expected_revision,
                        expected_content_digest=payload.expected_content_digest,
                    )
                ),
                task_name="profile-complete-setup",
            )
            already_complete = record.record_revision == payload.expected_revision
            result = ProfileCompleteSetupOperationResult(
                profile_id=payload.profile_id,
                record_revision=record.record_revision,
                content_digest=record.content_digest,
                already_complete=already_complete,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.NONE if already_complete else OperationEffect.UPDATED)
        await context.events.phase(_PROFILE_COMPLETE_SETUP_PHASES[2])
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
                async with context.cancellation.irreversible_section():
                    result = await await_cancellation_complete(
                        asyncio.to_thread(
                            export_profile_bundle,
                            ProfileBundleExportRequest(
                                profile_name=None,
                                destination=payload.destination,
                                purpose=payload.purpose,
                                transport=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED,
                                passphrase=SecretStr(passphrase),
                            ),
                            profile_decode_context=context.authority_operation.profile_decode_context(),
                            authorized_profile_id=str(payload.profile_id),
                        ),
                        task_name="profile-bundle-export",
                    )
                    result_ref = await _result_reference(result, context)
            finally:
                passphrase = ""
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
        # The revocation takes the root pointer lock and deletes files; the session it
        # closes is bound process-wide, so the worker thread sees and clears it.
        signed_out = await asyncio.to_thread(logout_active_profile)
        await context.events.effect(OperationEffect.UPDATED if signed_out is not None else OperationEffect.NONE)
        await context.events.phase(_PROFILE_LOGOUT_PHASES[2])
        return request.subject_ref


class ProfileViewOperationExecutor:
    """Read one pinned page through the canonical encrypted profile record owner."""

    async def execute(
        self,
        request: OperationRequest[ProfileViewOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_VIEW_PHASES[0])
        result = await await_cancellation_complete(
            asyncio.to_thread(
                read_profile_view_page,
                payload,
                authority_operation=context.authority_operation,
            ),
            task_name="profile-view-page",
        )
        await context.events.phase(PROFILE_VIEW_PHASES[1])
        result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.NONE)
        return result_ref


def _definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    phase_codes: tuple[str, ...],
    ephemeral_secret: OperationEphemeralSecretDeclaration | None = None,
    permitted_effects: frozenset[OperationEffect] = EFFECTS_WITHOUT_PARTIAL_COMMIT,
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
            permitted_effects=permitted_effects,
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
        definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
        request_type=ProfileViewOperationRequest,
        result_type=ProfileViewOperationResult,
        executor_type=ProfileViewOperationExecutor,
        phase_codes=PROFILE_VIEW_PHASES,
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
    ),
    _definition(
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        request_type=ProfileFieldMutationOperationRequest,
        result_type=ProfileMutationOperationResult,
        executor_type=ProfileFieldMutationOperationExecutor,
        phase_codes=_PROFILE_FIELD_MUTATION_PHASES,
    ),
    _definition(
        definition_id=PROFILE_PATCH_OPERATION_DEFINITION_ID,
        request_type=ProfilePatchOperationRequest,
        result_type=ProfilePatchOperationResult,
        executor_type=ProfilePatchOperationExecutor,
        phase_codes=_PROFILE_PATCH_PHASES,
    ),
    _definition(
        definition_id=PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID,
        request_type=ProfilePlantillaMediaOperationRequest,
        result_type=ProfilePlantillaMediaOperationResult,
        executor_type=ProfilePlantillaMediaOperationExecutor,
        phase_codes=_PROFILE_PLANTILLA_MEDIA_PHASES,
    ),
    _definition(
        definition_id=PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
        request_type=ProfileDescendantsOperationRequest,
        result_type=ProfileDescendantsOperationResult,
        executor_type=ProfileDescendantsOperationExecutor,
        phase_codes=_PROFILE_DESCENDANTS_PHASES,
    ),
    _definition(
        definition_id=PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
        request_type=ProfileRepeatableRowMutationOperationRequest,
        result_type=ProfileRepeatableRowMutationOperationResult,
        executor_type=ProfileRepeatableRowMutationOperationExecutor,
        phase_codes=_PROFILE_REPEATABLE_ROW_MUTATION_PHASES,
    ),
    _definition(
        definition_id=PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
        request_type=ProfileRepeatableRowUpdateOperationRequest,
        result_type=ProfileRepeatableRowChangeOperationResult,
        executor_type=ProfileRepeatableRowUpdateOperationExecutor,
        phase_codes=_PROFILE_REPEATABLE_ROW_UPDATE_PHASES,
    ),
    _definition(
        definition_id=PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
        request_type=ProfileRepeatableRowRemoveOperationRequest,
        result_type=ProfileRepeatableRowChangeOperationResult,
        executor_type=ProfileRepeatableRowRemoveOperationExecutor,
        phase_codes=_PROFILE_REPEATABLE_ROW_REMOVE_PHASES,
    ),
    _definition(
        definition_id=PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
        request_type=ProfileCompleteSetupOperationRequest,
        result_type=ProfileCompleteSetupOperationResult,
        executor_type=ProfileCompleteSetupOperationExecutor,
        phase_codes=_PROFILE_COMPLETE_SETUP_PHASES,
    ),
    _definition(
        definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ProfileBundleExportOperationRequest,
        result_type=ProfileBundleExportResult,
        executor_type=ProfileBundleExportOperationExecutor,
        phase_codes=_PROFILE_BUNDLE_EXPORT_PHASES,
        ephemeral_secret=OperationEphemeralSecretDeclaration(
            secret_kind=_PROFILE_BUNDLE_EXPORT_KIND,
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


def resolve_profile_mutation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize profile facts as profile-wide work, without tax-period impersonation."""
    payload = request.payload
    if not isinstance(
        payload,
        ProfileFieldMutationOperationRequest
        | ProfilePatchOperationRequest
        | ProfilePlantillaMediaOperationRequest
        | ProfileDescendantsOperationRequest
        | ProfileRepeatableRowMutationOperationRequest
        | ProfileRepeatableRowUpdateOperationRequest
        | ProfileRepeatableRowRemoveOperationRequest
        | ProfileCompleteSetupOperationRequest,
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != _profile_subject(str(payload.profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT and context.contract.result_schema is not None:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=context.contract.result_schema.schema_id,
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
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def resolve_profile_bundle_export_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require the exact active profile and explicit export-result disclosure."""
    payload = request.payload
    if not isinstance(payload, ProfileBundleExportOperationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != _profile_subject(str(payload.profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT and context.contract.result_schema is not None:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=context.contract.result_schema.schema_id,
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
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def resolve_profile_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact active profile and explicit result disclosure for a view page."""
    payload = request.payload
    if not isinstance(payload, ProfileViewOperationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != _profile_subject(str(payload.profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT and context.contract.result_schema is not None:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=context.contract.result_schema.schema_id,
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
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def build_user_profile_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind profile-maintenance definitions to their stable public schemas."""
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        if definition.definition_id == PROFILE_VIEW_OPERATION_DEFINITION_ID:
            registrations.append(
                OperationPublicDefinitionRegistrationV1.compose(
                    definition=definition,
                    request_schema=OperationSchemaBindingV1.bind(
                        schema_id=f"{definition.definition_id}.request",
                        schema_version=1,
                        model_type=definition.request_type,
                    ),
                    result_schema=OperationSchemaBindingV1.bind(
                        schema_id=f"{definition.definition_id}.result",
                        schema_version=1,
                        model_type=ProfileViewOperationProjection,
                    ),
                    result_projector=project_profile_view_result,
                    access_resolver=resolve_profile_view_access,
                )
            )
        elif definition.definition_id in {
            PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
            PROFILE_PATCH_OPERATION_DEFINITION_ID,
            PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID,
            PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
            PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
            PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
            PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
            PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
        }:
            projection_type: type[BaseModel]
            if definition.definition_id == PROFILE_PATCH_OPERATION_DEFINITION_ID:
                projection_type = ProfilePatchOperationProjection
            elif definition.definition_id == PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID:
                projection_type = ProfilePlantillaMediaOperationProjection
            elif definition.definition_id == PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID:
                projection_type = ProfileDescendantsOperationProjection
            elif definition.definition_id == PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID:
                projection_type = ProfileRepeatableRowMutationOperationProjection
            elif definition.definition_id in {
                PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
                PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
            }:
                projection_type = ProfileRepeatableRowChangeOperationProjection
            elif definition.definition_id == PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID:
                projection_type = ProfileCompleteSetupOperationProjection
            else:
                projection_type = ProfileMutationOperationProjection
            registrations.append(
                OperationPublicDefinitionRegistrationV1.compose(
                    definition=definition,
                    request_schema=OperationSchemaBindingV1.bind(
                        schema_id=f"{definition.definition_id}.request",
                        schema_version=1,
                        model_type=definition.request_type,
                    ),
                    result_schema=OperationSchemaBindingV1.bind(
                        schema_id=f"{definition.definition_id}.result", schema_version=1, model_type=projection_type
                    ),
                    result_projector=project_profile_mutation_result,
                    access_resolver=resolve_profile_mutation_access,
                )
            )
        elif definition.definition_id == PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID:
            registrations.append(
                OperationPublicDefinitionRegistrationV1.compose(
                    definition=definition,
                    request_schema=OperationSchemaBindingV1.bind(
                        schema_id=f"{definition.definition_id}.request",
                        schema_version=1,
                        model_type=ProfileBundleExportOperationRequest,
                    ),
                    result_schema=OperationSchemaBindingV1.bind(
                        schema_id=f"{definition.definition_id}.result",
                        schema_version=1,
                        model_type=ProfileBundleExportOperationProjection,
                    ),
                    result_projector=project_profile_bundle_export_result,
                    access_resolver=resolve_profile_bundle_export_access,
                )
            )
        else:
            registrations.append(
                OperationPublicDefinitionRegistrationV1.compose_request_only(
                    definition=definition, request_schema_id=f"{definition.definition_id}.request"
                )
            )
    return tuple(sorted(registrations, key=lambda item: item.contract.definition_id))


__all__ = [
    "PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID",
    "PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID",
    "PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID",
    "PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID",
    "PROFILE_LOGOUT_OPERATION_DEFINITION_ID",
    "PROFILE_PATCH_OPERATION_DEFINITION_ID",
    "PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID",
    "PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID",
    "PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID",
    "PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID",
    "PROFILE_VIEW_OPERATION_DEFINITION_ID",
    "USER_PROFILE_OPERATION_DEFINITIONS",
    "ProfileBundleExportOperationProjection",
    "ProfileBundleExportOperationRequest",
    "ProfileCompleteSetupOperationProjection",
    "ProfileCompleteSetupOperationRequest",
    "ProfileCompleteSetupOperationResult",
    "ProfileDescendantsOperationExecutor",
    "ProfileDescendantsOperationProjection",
    "ProfileDescendantsOperationRequest",
    "ProfileDescendantsOperationResult",
    "ProfileFieldMutationOperationRequest",
    "ProfileLogoutOperationRequest",
    "ProfileLogoutOperationResult",
    "ProfileMutationOperationProjection",
    "ProfileMutationOperationResult",
    "ProfilePatchOperationProjection",
    "ProfilePatchOperationRequest",
    "ProfilePatchOperationResult",
    "ProfilePatchValue",
    "ProfilePlantillaMediaOperationExecutor",
    "ProfilePlantillaMediaOperationProjection",
    "ProfilePlantillaMediaOperationRequest",
    "ProfilePlantillaMediaOperationResult",
    "ProfilePlantillaMediaRemove",
    "ProfilePlantillaMediaSet",
    "ProfileRepeatableRowChangeOperationProjection",
    "ProfileRepeatableRowChangeOperationResult",
    "ProfileRepeatableRowMutationOperationProjection",
    "ProfileRepeatableRowMutationOperationRequest",
    "ProfileRepeatableRowMutationOperationResult",
    "ProfileRepeatableRowRemoveOperationRequest",
    "ProfileRepeatableRowUpdateOperationRequest",
    "ProfileRepeatableRowValue",
    "ProfileViewOperationProjection",
    "ProfileViewOperationRequest",
    "ProfileViewOperationResult",
    "build_profile_logout_operation_request",
    "build_user_profile_operation_definitions",
    "build_user_profile_operation_registrations",
    "project_profile_bundle_export_result",
    "project_profile_mutation_result",
    "resolve_profile_bundle_export_access",
    "resolve_profile_mutation_access",
    "resolve_profile_view_access",
]
