"""Canonical public registered operations for active user-profile maintenance."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject as _profile_subject
from ...domain.user_profile.plantilla_media import PlantillaMediaState
from ..operations.models import OperationTerminalReceipt
from .bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportResult,
)
from .descendant_rows import ProfileDescendantRow

PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID = "user-profile.field-mutation"

PROFILE_PATCH_OPERATION_DEFINITION_ID = "user-profile.patch"

PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID = "user-profile.plantilla-media"

PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID = "user-profile.descendants"

PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID = "user-profile.repeatable-row-mutation"

PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID = "user-profile.repeatable-row-update"

PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID = "user-profile.repeatable-row-remove"

PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID = "user-profile.complete-setup"

PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID = "user-profile.bundle-export"

PROFILE_FIELD_MUTATION_PHASES = (
    "user-profile.field-mutation.preflight",
    "user-profile.field-mutation.execute",
    "user-profile.field-mutation.settlement",
)

PROFILE_PATCH_PHASES = (
    "user-profile.patch.preflight",
    "user-profile.patch.execute",
    "user-profile.patch.settlement",
)

PROFILE_PLANTILLA_MEDIA_PHASES = (
    "user-profile.plantilla-media.preflight",
    "user-profile.plantilla-media.execute",
    "user-profile.plantilla-media.settlement",
)

PROFILE_DESCENDANTS_PHASES = (
    "user-profile.descendants.preflight",
    "user-profile.descendants.execute",
    "user-profile.descendants.settlement",
)

PROFILE_REPEATABLE_ROW_MUTATION_PHASES = (
    "user-profile.repeatable-row-mutation.preflight",
    "user-profile.repeatable-row-mutation.execute",
    "user-profile.repeatable-row-mutation.settlement",
)

PROFILE_REPEATABLE_ROW_UPDATE_PHASES = (
    "user-profile.repeatable-row-update.preflight",
    "user-profile.repeatable-row-update.execute",
    "user-profile.repeatable-row-update.settlement",
)

PROFILE_REPEATABLE_ROW_REMOVE_PHASES = (
    "user-profile.repeatable-row-remove.preflight",
    "user-profile.repeatable-row-remove.execute",
    "user-profile.repeatable-row-remove.settlement",
)

PROFILE_COMPLETE_SETUP_PHASES = (
    "user-profile.complete-setup.preflight",
    "user-profile.complete-setup.execute",
    "user-profile.complete-setup.settlement",
)

PROFILE_BUNDLE_EXPORT_PHASES = (
    "user-profile.bundle-export.preflight",
    "user-profile.bundle-export.secret-consume",
    "user-profile.bundle-export.execute",
    "user-profile.bundle-export.settlement",
)

PROFILE_BUNDLE_EXPORT_INPUT_KIND = "profile.bundle-export.passphrase"


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
