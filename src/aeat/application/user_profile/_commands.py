"""Pydantic command and result contracts for the user-profile boundary.

These classes were previously declared at the body of
:mod:`aeat.application.user_profile`'s ``__init__.py``. Pydantic v2
resolves field types at class-creation time, so declaring them at the
package boundary forced an eager import of
:mod:`aeat.domain.user_profile` (which pulls the full registry via its
``_registry_contract`` companion) for every consumer that touched the
boundary — including the state-free CLI surfaces that must never pay
the registry cost.

Relocating the classes here lets the boundary re-export them through
its PEP 562 ``__getattr__`` block, deferring the domain-record import
to first reference rather than boundary-import time. The public
surface is unchanged: every name remains reachable via
``aeat.application.user_profile.<name>`` because the boundary's
``__getattr__`` resolves to this module on demand.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import BaseSeverity as _BaseSeverity
from ...core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI as _PROVENANCE_SOURCE_MANUAL_CLI
from ...core.identity import ProfileId
from ...domain.user_profile import (
    UserProfileFact,
    UserProfileFactValue,
    UserProfileRecord,
    UserProfileStatus,
)

# Sha-256 content-fingerprint shape shared by the profile-snapshot canonical
# hash, the stored-hash snapshot pointer, and the current-hash recompute
# result. Stays bare-str under ADR Rule 7 (fingerprint, not identity);
# factored to a single annotated alias to remove the three-way duplication
# of the shape literal while preserving full static type information.
_ProfileSnapshotHash = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]


# ---------------------------------------------------------------------------
# Lifecycle commands
# ---------------------------------------------------------------------------


class RegisterProfileCommand(BaseModel):
    """Register a new active profile root in the secure DB backend."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    display_name: str = Field(min_length=1, max_length=160)
    facts: tuple[UserProfileFact, ...] = ()


class EditProfileFieldCommand(BaseModel):
    """Upsert one effective-dated profile fact."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    path: str = Field(min_length=3, max_length=192)
    value: UserProfileFactValue
    valid_from: date | None = None
    valid_to: date | None = None
    source: str = Field(default=_PROVENANCE_SOURCE_MANUAL_CLI, min_length=1, max_length=80)


class EditProfileSectionCommand(BaseModel):
    """Bulk-upsert every fact in one schema section."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    section_key: str = Field(min_length=1, max_length=64)
    facts: tuple[UserProfileFact, ...]
    source: str = Field(default=_PROVENANCE_SOURCE_MANUAL_CLI, min_length=1, max_length=80)


class RemoveProfileCommand(BaseModel):
    """Tombstone the live profile root (immutable filing snapshots are retained)."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId


class DuplicateProfileCommand(BaseModel):
    """Copy an existing profile under a new id and display name."""

    model_config = _STRICT_FROZEN

    source_profile_id: ProfileId
    target_profile_id: ProfileId
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

    profile_id: ProfileId
    target_display_name: str = Field(min_length=1, max_length=160)


# ---------------------------------------------------------------------------
# Lifecycle results
# ---------------------------------------------------------------------------


class ProfileLifecycleResult(BaseModel):
    """Result of a lifecycle mutation (register / edit / remove / duplicate).

    Attributes:
        profile: The mutated :class:`UserProfileRecord`.
        applied_at: The timestamp when the mutation was applied.
    """

    model_config = _STRICT_FROZEN

    profile: UserProfileRecord
    applied_at: datetime


class ProfileListing(BaseModel):
    """One row of a profile-listing result."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
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

    severity: _BaseSeverity
    code: str = Field(min_length=1, max_length=64)
    path: str | None = None
    message: str = Field(min_length=1, max_length=512)


class ProfileValidationReport(BaseModel):
    """Aggregate validation report for a profile or a registration command."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
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

    profile_id: ProfileId
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

    profile_id: ProfileId
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1, max_length=8)


class ProfileSnapshot(BaseModel):
    """Immutable filing-time snapshot of one profile's projection."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    profile_id: ProfileId
    schema_version: int = Field(ge=1)
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1, max_length=8)
    canonical_hash: _ProfileSnapshotHash
    created_at: datetime
    facts: tuple[UserProfileFact, ...]


class ProfileStaleCheckReport(BaseModel):
    """Result of checking a draft's stored snapshot against the current projection."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    profile_id: ProfileId
    stored_hash: _ProfileSnapshotHash
    current_hash: _ProfileSnapshotHash
    stale: bool


# ---------------------------------------------------------------------------
# Portable export / import
# ---------------------------------------------------------------------------


class ProfileImportResult(BaseModel):
    """Outcome of importing a portable bundle.

    Attributes:
        profile: The imported :class:`UserProfileRecord`.
        imported_at: The timestamp of import.
        issues: Any validation issues.
    """

    model_config = _STRICT_FROZEN

    profile: UserProfileRecord
    imported_at: datetime
    issues: tuple[ProfileValidationIssue, ...] = ()
