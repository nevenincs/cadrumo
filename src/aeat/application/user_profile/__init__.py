"""Application-layer command and result contracts for the user profile backend.

This package owns the lifecycle API contracts for the centralised
schema-driven profile backend. The domain layer
(``aeat.domain.user_profile``) owns the schema, value records, and
registry-contract validation; this package owns the application-layer
service surface: strict Pydantic command and result records that flow
between the CLI thin adapters, the secure-storage persistence wiring,
and the calculation/filing/aggregation consumers.

The records here have no business logic — they are the typed contract.
The service implementations live in sibling modules
(``ProfileLifecycleService``, ``ProfileSnapshotService``,
``ProfileValidationService``, ``ProfilePreflightService``) and the
secure-storage adapters that consume these records.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import BaseSeverity
from ...domain.user_profile import (
    ProfileFactValue,
    UserProfileFact,
    UserProfilePortableExport,
    UserProfileRecord,
    UserProfileStatus,
)
from . import _language_resolver as _language_resolver  # side-effect: registers the core.i18n language resolver

if TYPE_CHECKING:
    from ._censo_errors import (
        CensoApplyConflictError,
        CensoFieldValidationError,
        CensoNotAvailableError,
        CensoSyncError,
    )
    from ._censo_sync import (
        CENSUS_SOURCE_TAG,
        CensoApplyResult,
        CensoComparisonStatus,
        CensoFactSource,
        CensoFieldComparison,
        CensoProfileComparison,
        CensoSyncService,
    )
    from ._lifecycle import ProfileLifecycleService
    from ._preflight import ProfilePreflightService
    from ._projections import facts_to_values, projection_for_taxpayer, record_to_values, snapshot_to_values
    from ._repository import (
        USER_PROFILE_SNAPSHOT_NAMESPACE,
        USER_PROFILE_VALUE_NAMESPACE,
        UserProfileLifecycleRepository,
        UserProfileSnapshotRepository,
        user_profile_snapshot_object_key,
        user_profile_value_object_key,
    )
    from ._validation import ProfileValidationService

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# Lifecycle commands
# ---------------------------------------------------------------------------


class RegisterProfileCommand(BaseModel):
    """Register a new active profile root in the secure DB backend."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    display_name: str = Field(min_length=1, max_length=160)
    facts: tuple[UserProfileFact, ...] = ()


class EditProfileFieldCommand(BaseModel):
    """Upsert one effective-dated profile fact."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    path: str = Field(min_length=3, max_length=192)
    value: ProfileFactValue
    valid_from: date | None = None
    valid_to: date | None = None
    source: str = Field(default="manual_cli", min_length=1, max_length=80)


class EditProfileSectionCommand(BaseModel):
    """Bulk-upsert every fact in one schema section."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    section_key: str = Field(min_length=1, max_length=64)
    facts: tuple[UserProfileFact, ...]
    source: str = Field(default="manual_cli", min_length=1, max_length=80)


class RemoveProfileCommand(BaseModel):
    """Tombstone the live profile root (immutable filing snapshots are retained)."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)


class DuplicateProfileCommand(BaseModel):
    """Copy an existing profile under a new id and display name."""

    model_config = _STRICT_FROZEN

    source_profile_id: str = Field(min_length=1, max_length=96)
    target_profile_id: str = Field(min_length=1, max_length=96)
    target_display_name: str = Field(min_length=1, max_length=160)


class RenameProfileCommand(BaseModel):
    """Update a live profile's display label.

    Profile identity is an immutable UUID, so a rename is a pure
    label edit: the live record's ``display_name`` is updated and the
    record is re-saved under the same secure-object key. There is no
    directory move, no re-key, and no rollback machinery. The
    orchestration layer updates the parallel copy of the label in the
    plaintext bucket manifest.
    """

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    target_display_name: str = Field(min_length=1, max_length=160)


# ---------------------------------------------------------------------------
# Lifecycle results
# ---------------------------------------------------------------------------


class ProfileLifecycleResult(BaseModel):
    """Result of a lifecycle mutation (register / edit / remove / duplicate)."""

    model_config = _STRICT_FROZEN

    profile: UserProfileRecord
    applied_at: datetime


class ProfileListing(BaseModel):
    """One row of a profile-listing result."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    display_name: str = Field(min_length=1, max_length=160)
    status: UserProfileStatus
    created_at: datetime
    updated_at: datetime


class ProfileListResult(BaseModel):
    """Frozen tuple of profile listings returned by `list_profiles`."""

    model_config = _STRICT_FROZEN

    profiles: tuple[ProfileListing, ...] = ()


# ---------------------------------------------------------------------------
# Validation and preflight
# ---------------------------------------------------------------------------


class ProfileValidationIssue(BaseModel):
    """One validation finding raised against a profile snapshot."""

    model_config = _STRICT_FROZEN

    severity: BaseSeverity
    code: str = Field(min_length=1, max_length=64)
    path: str | None = None
    message: str = Field(min_length=1, max_length=512)


class ProfileValidationReport(BaseModel):
    """Aggregate validation report for a profile or a registration command."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    schema_version: int = Field(ge=1)
    issues: tuple[ProfileValidationIssue, ...] = ()


class ProfilePreflightRequirement(BaseModel):
    """One required-but-missing profile selector for a modelo / revision."""

    model_config = _STRICT_FROZEN

    selector: str = Field(min_length=1, max_length=128)
    section_key: str = Field(min_length=1, max_length=64)
    field_key: str = Field(min_length=1, max_length=128)


class ProfilePreflightReport(BaseModel):
    """Per-`(modelo, revision, filing_year, period)` profile readiness report."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1, max_length=8)
    missing: tuple[ProfilePreflightRequirement, ...] = ()
    ready: bool


# ---------------------------------------------------------------------------
# Filing snapshots
# ---------------------------------------------------------------------------


class ProfileSnapshotRequest(BaseModel):
    """Request an immutable filing-time snapshot of one profile."""

    model_config = _STRICT_FROZEN

    profile_id: str = Field(min_length=1, max_length=96)
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1, max_length=8)


class ProfileSnapshot(BaseModel):
    """Immutable filing-time snapshot of one profile's projection."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=96)
    schema_version: int = Field(ge=1)
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1, max_length=8)
    canonical_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    facts: tuple[UserProfileFact, ...]


class ProfileStaleCheckReport(BaseModel):
    """Result of checking a draft's stored snapshot against the current projection."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=96)
    stored_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    current_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    stale: bool


# ---------------------------------------------------------------------------
# Portable export / import
# ---------------------------------------------------------------------------

# ProfileExportBundle consolidated onto UserProfilePortableExport (domain).
# Callers should import UserProfilePortableExport from aeat.domain.user_profile
# or from this module; the canonical definition lives in domain/_values.py.


class ProfileImportResult(BaseModel):
    """Outcome of importing a portable bundle."""

    model_config = _STRICT_FROZEN

    profile: UserProfileRecord
    imported_at: datetime
    issues: tuple[ProfileValidationIssue, ...] = ()


def __getattr__(name: str):
    """Lazy-import the service modules to keep the contract surface light."""

    if name == "ProfileLifecycleService":
        from ._lifecycle import ProfileLifecycleService

        return ProfileLifecycleService
    if name in (
        "CensoApplyConflictError",
        "CensoFieldValidationError",
        "CensoNotAvailableError",
        "CensoSyncError",
    ):
        from . import _censo_errors

        return getattr(_censo_errors, name)
    if name in (
        "CENSUS_SOURCE_TAG",
        "CensoApplyResult",
        "CensoComparisonStatus",
        "CensoFactSource",
        "CensoFieldComparison",
        "CensoProfileComparison",
        "CensoSyncService",
    ):
        from . import _censo_sync

        return getattr(_censo_sync, name)
    if name in ("facts_to_values", "projection_for_taxpayer", "record_to_values", "snapshot_to_values"):
        from . import _projections

        return getattr(_projections, name)
    if name == "ProfilePreflightService":
        from ._preflight import ProfilePreflightService

        return ProfilePreflightService
    if name == "ProfileValidationService":
        from ._validation import ProfileValidationService

        return ProfileValidationService
    if name in (
        "USER_PROFILE_SNAPSHOT_NAMESPACE",
        "USER_PROFILE_VALUE_NAMESPACE",
        "UserProfileLifecycleRepository",
        "UserProfileSnapshotRepository",
        "user_profile_snapshot_object_key",
        "user_profile_value_object_key",
    ):
        from . import _repository

        return getattr(_repository, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CENSUS_SOURCE_TAG",
    "USER_PROFILE_SNAPSHOT_NAMESPACE",
    "USER_PROFILE_VALUE_NAMESPACE",
    "CensoApplyConflictError",
    "CensoApplyResult",
    "CensoComparisonStatus",
    "CensoFactSource",
    "CensoFieldComparison",
    "CensoFieldValidationError",
    "CensoNotAvailableError",
    "CensoProfileComparison",
    "CensoSyncError",
    "CensoSyncService",
    "DuplicateProfileCommand",
    "EditProfileFieldCommand",
    "EditProfileSectionCommand",
    "ProfileImportResult",
    "ProfileLifecycleResult",
    "ProfileLifecycleService",
    "ProfileListResult",
    "ProfileListing",
    "ProfilePreflightReport",
    "ProfilePreflightRequirement",
    "ProfilePreflightService",
    "ProfileSnapshot",
    "ProfileSnapshotRequest",
    "ProfileStaleCheckReport",
    "ProfileValidationIssue",
    "ProfileValidationReport",
    "ProfileValidationService",
    "RegisterProfileCommand",
    "RemoveProfileCommand",
    "RenameProfileCommand",
    "UserProfileLifecycleRepository",
    "UserProfilePortableExport",
    "UserProfileSnapshotRepository",
    "facts_to_values",
    "projection_for_taxpayer",
    "record_to_values",
    "snapshot_to_values",
    "user_profile_snapshot_object_key",
    "user_profile_value_object_key",
]
