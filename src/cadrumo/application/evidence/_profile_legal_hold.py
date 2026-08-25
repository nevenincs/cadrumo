"""Canonical legal-case owner facts for local profile-deletion holds.

This module owns legal-case snapshots.  It deliberately exposes no
``cleared``/``held`` switch: the custody transaction can only project whether
the authoritative snapshot names any open case.  The user-profile facade does
not re-export this mutation owner.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, StorageCategory, storage_location
from ...core.logging import get_logger
from ...core.time import validate_utc_aware
from .._profile_deletion_hold_contract import ProfileDeletionHoldOwnerProjection
from ..user_profile.custody_ports import ProfileCustodyLocalRecordStore, canonical_snapshot_bytes, canonical_snapshot_digest, canonical_snapshot_payload, default_profile_custody_local_record_store, ensure_profile_custody_owner_root, profile_custody_owner_root

_MAX_BYTES = 8 * 1024

LEGAL_HOLD_OWNER_DIRNAME: Final[str] = (
    storage_location(
        StorageCategory.PROFILE_CUSTODY_HOLD_LEGAL_OWNER,
    )
    .relative_path()
    .name
)
"""This owner's directory name, read from its one declaration in the taxonomy.

The storage path registry spells the same segment in this format's grammar, so
the name is declared once and read in both places rather than typed in each.
"""

LEGAL_HOLD_SNAPSHOT_SCHEMA_VERSION: Final[int] = 1
"""Current on-disk schema version of :class:`LegalHoldCaseSnapshot` documents."""


class LegalHoldCaseSnapshot(BaseModel):
    """Durable legal-owner fact: exactly the known open case identifiers."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=LEGAL_HOLD_SNAPSHOT_SCHEMA_VERSION, frozen=True)
    profile_id: UUID
    open_case_ids: tuple[str, ...]
    observed_at: datetime
    self_digest: str = Field(min_length=71, max_length=71)

    @field_validator("open_case_ids")
    @classmethod
    def _validate_case_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("legal open case identifiers must be unique and sorted")
        if any(
            len(case_id) < 3
            or len(case_id) > 256
            or case_id != case_id.strip()
            or any(character in case_id for character in "\\/\x00")
            for case_id in value
        ):
            raise ValueError("legal open case identifiers must be bounded canonical identifiers")
        return value

    @model_validator(mode="after")
    def _validate_snapshot(self) -> LegalHoldCaseSnapshot:
        validate_utc_aware(self.observed_at)
        if self.self_digest != self.computed_self_digest:
            raise ValueError("legal hold snapshot digest does not match its canonical fields")
        return self

    @property
    def canonical_payload(self) -> dict[str, object]:
        return canonical_snapshot_payload(self)

    @property
    def computed_self_digest(self) -> str:
        return canonical_snapshot_digest(
            self,
            maximum_bytes=_MAX_BYTES,
            subject="legal hold snapshot",
        )

    def canonical_json_bytes(self) -> bytes:
        return canonical_snapshot_bytes(
            self,
            maximum_bytes=_MAX_BYTES,
            subject="legal hold snapshot",
        )

    @classmethod
    def from_open_cases(
        cls,
        *,
        profile_id: UUID,
        open_case_ids: tuple[str, ...],
        observed_at: datetime,
    ) -> LegalHoldCaseSnapshot:
        unsigned = cls.model_construct(
            schema_version=LEGAL_HOLD_SNAPSHOT_SCHEMA_VERSION,
            profile_id=profile_id,
            open_case_ids=open_case_ids,
            observed_at=observed_at,
            self_digest="",
        )
        return cls(
            profile_id=profile_id,
            open_case_ids=open_case_ids,
            observed_at=observed_at,
            self_digest=unsigned.computed_self_digest,
        )


class LegalHoldCaseAuthority:
    """Legal-owner mutation and projection surface, outside deletion ownership."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        local_record_store: ProfileCustodyLocalRecordStore | None = None,
    ) -> None:
        self._local_record_store = local_record_store or default_profile_custody_local_record_store()
        self._root = profile_custody_owner_root(root, LEGAL_HOLD_OWNER_DIRNAME)

    def record_open_case_snapshot(
        self,
        *,
        profile_id: UUID,
        open_case_ids: tuple[str, ...],
        observed_at: datetime,
    ) -> LegalHoldCaseSnapshot:
        """Persist a legal case-owner observation; outcome derives from the cases."""
        snapshot = LegalHoldCaseSnapshot.from_open_cases(
            profile_id=profile_id,
            open_case_ids=open_case_ids,
            observed_at=observed_at,
        )
        self._ensure_root()
        with self._local_record_store.lock(self._root / ".legal-case-owner.lock"):
            self._local_record_store.write(
                self.path(profile_id),
                snapshot.canonical_json_bytes(),
                publish_once=False,
            )
        return snapshot

    def project(self, profile_id: UUID, *, now: datetime) -> ProfileDeletionHoldOwnerProjection:
        """Load canonical legal facts and derive the hold without caller disposition input."""
        validate_utc_aware(now)
        path = self.path(profile_id)
        if not os.path.lexists(path):
            raise FileNotFoundError("canonical legal case snapshot is absent")
        payload = self._local_record_store.read(path, maximum_bytes=_MAX_BYTES)
        try:
            snapshot = LegalHoldCaseSnapshot.model_validate_json(payload)
        except ValidationError as exc:
            raise ValueError("canonical legal case snapshot is invalid") from exc
        if snapshot.profile_id != profile_id or snapshot.canonical_json_bytes() != payload:
            raise ValueError("canonical legal case snapshot identity or bytes differ from its path")
        return ProfileDeletionHoldOwnerProjection(
            owner="legal",
            profile_id=profile_id,
            blocks_local_deletion=bool(snapshot.open_case_ids),
            source_record_id=f"legal-case-snapshot-{profile_id}",
            source_record_digest=snapshot.self_digest,
            assessed_at=now.astimezone(UTC),
        )

    def path(self, profile_id: UUID) -> Path:
        return self._root / f"{profile_id}.json"

    def _ensure_root(self) -> None:
        ensure_profile_custody_owner_root(self._local_record_store, self._root)


def try_record_legal_hold_snapshot(
    *,
    bucket_id: str,
    open_case_ids: Iterable[str],
    observed_at: datetime,
) -> bool:
    """Record one profile's known open legal cases, and never raise doing it.

    The deletion preflight cannot read a profile's encrypted records -- it runs
    against profiles it has not unlocked -- so this plaintext snapshot is how
    the legal-hold position stays knowable without the key. Mirrors
    :func:`~cadrumo.application.filing.try_record_filing_retention_snapshot`
    exactly: same best-effort contract, same reason a caller that exists to do
    something else must never be refused over a deletion-support record.

    The sole caller today is profile registration, recording ``()`` -- and
    that empty tuple is a fact, not a shrug. Genuinely external legal holds
    (a court order, live litigation, an adviser instruction) are unknowable
    to this system and must never be defaulted to cleared; writing an empty
    snapshot for THAT kind of hold at registration would be manufacturing
    consent nobody gave. But a profile at the instant of registration has no
    filings, no expedientes, no records of any kind -- there is structurally
    nothing yet for an outside hold to be a hold ON. "Zero known open cases"
    is therefore not an unverified assumption of clearance at registration
    the way it would be later; it is the same class of fact
    ``try_record_filing_retention_snapshot`` already records for a brand-new
    profile's filing history ("no filings exist" rather than "nobody
    checked").

    This does NOT close the legal-hold gap for a profile's later life. Once a
    profile has real filings or captured AEAT expedientes, "zero known open
    cases" recorded once at registration goes stale the moment either
    changes, and nothing today refreshes it -- there is no capture-time
    producer for AEAT expedientes and no operator affirmation surface for a
    genuinely external hold. A future producer at expedientes-capture time,
    and an operator-affirmation surface with a freshness bound, remain open
    work; this function only ever asserts what is true at the instant it is
    called.

    Swallowing is safe only while absence fails CLOSED: with no snapshot the
    hold assessment refuses, which blocks a deletion rather than permitting
    one. An empty RECORDED snapshot is a different thing from an absent one
    and must stay so.

    Returns:
        ``True`` when the snapshot was written, ``False`` when it was not. The
        caller is expected to ignore it; it exists so a test can assert the
        write happened rather than inferring it.
    """
    try:
        LegalHoldCaseAuthority().record_open_case_snapshot(
            profile_id=UUID(str(bucket_id)),
            open_case_ids=tuple(open_case_ids),
            observed_at=observed_at,
        )
    except Exception:
        get_logger(__name__).warning(
            "legal hold snapshot not recorded; a later deletion preflight will refuse",
            exc_info=True,
        )
        return False
    return True


__all__ = [
    "LEGAL_HOLD_SNAPSHOT_SCHEMA_VERSION",
    "LegalHoldCaseAuthority",
    "LegalHoldCaseSnapshot",
    "try_record_legal_hold_snapshot",
]
