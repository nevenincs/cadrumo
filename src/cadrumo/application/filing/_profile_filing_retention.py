"""Canonical filing-retention facts used by current local profile deletion.

The owner accepts real ``ModeloRecord`` facts and derives retention from the
domain legal floor.  It never accepts a caller-selected clear/held outcome and
is intentionally not re-exported through ``application.user_profile``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ...core.storage_taxonomy_locations import storage_location
from ...core.storage_taxonomy import StorageCategory
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.filing_year import FilingYear
from ...core.identity import FilingRecordId, PrefixedContentDigest
from ...core.logging import get_logger
from ...core.time import validate_utc_aware
from ...domain.modelos.filing_record import ModeloRecord
from ...domain.retention import RetentionFloorAssessment, assess_retention_floor
from ..profile_deletion_hold_contract import ProfileDeletionHoldOwnerProjection
from ..user_profile.custody_ports import (
    ProfileCustodyLocalRecordStore,
    canonical_snapshot_bytes,
    canonical_snapshot_digest,
    canonical_snapshot_payload,
    default_profile_custody_local_record_store,
    ensure_profile_custody_owner_root,
    profile_custody_owner_root,
)

_MAX_BYTES = 32 * 1024

FILING_RETENTION_OWNER_DIRNAME: Final[str] = (
    storage_location(
        StorageCategory.PROFILE_CUSTODY_HOLD_FILING_OWNER,
    )
    .relative_path()
    .name
)
"""This owner's directory name, read from its one declaration in the taxonomy.

The storage path registry spells the same segment in this format's grammar, so
the name is declared once and read in both places rather than typed in each.
"""

FILING_RETENTION_SNAPSHOT_SCHEMA_VERSION: Final[int] = 1
"""Current on-disk schema version of :class:`FilingRetentionSnapshot` documents."""


class FilingRetentionFact(BaseModel):
    """The retention-relevant immutable projection of a real modelo filing."""

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: FilingRecordId
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    filed_at: datetime

    @model_validator(mode="after")
    def _validate_fact(self) -> FilingRetentionFact:
        validate_utc_aware(self.filed_at)
        return self


class FilingRetentionSnapshot(BaseModel):
    """Canonical filing-owner input; it contains facts, never a verdict."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=FILING_RETENTION_SNAPSHOT_SCHEMA_VERSION, frozen=True)
    profile_id: UUID
    filing_records: tuple[FilingRetentionFact, ...]
    observed_at: datetime
    self_digest: PrefixedContentDigest

    @field_validator("filing_records")
    @classmethod
    def _validate_records(cls, value: tuple[FilingRetentionFact, ...]) -> tuple[FilingRetentionFact, ...]:
        identifiers = tuple(record.filing_record_id for record in value)
        if identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("filing retention facts must be unique and sorted by filing record id")
        return value

    @model_validator(mode="after")
    def _validate_snapshot(self) -> FilingRetentionSnapshot:
        validate_utc_aware(self.observed_at)
        if self.self_digest != self.computed_self_digest:
            raise ValueError("filing retention snapshot digest does not match its canonical fields")
        return self

    @property
    def canonical_payload(self) -> dict[str, object]:
        return canonical_snapshot_payload(self)

    @property
    def computed_self_digest(self) -> str:
        return canonical_snapshot_digest(
            self,
            maximum_bytes=_MAX_BYTES,
            subject="filing retention snapshot",
        )

    def canonical_json_bytes(self) -> bytes:
        return canonical_snapshot_bytes(
            self,
            maximum_bytes=_MAX_BYTES,
            subject="filing retention snapshot",
        )

    @classmethod
    def from_modelo_records(
        cls,
        *,
        profile_id: UUID,
        records: Iterable[ModeloRecord],
        observed_at: datetime,
    ) -> FilingRetentionSnapshot:
        facts = tuple(
            sorted(
                (
                    FilingRetentionFact(
                        filing_record_id=str(record.filing_record_id),
                        modelo=str(record.modelo),
                        filing_year=record.filing_year,
                        filed_at=record.filed_at,
                    )
                    for record in records
                ),
                key=lambda fact: fact.filing_record_id,
            )
        )
        unsigned = cls.model_construct(
            schema_version=FILING_RETENTION_SNAPSHOT_SCHEMA_VERSION,
            profile_id=profile_id,
            filing_records=facts,
            observed_at=observed_at,
            self_digest="",
        )
        return cls(
            profile_id=profile_id,
            filing_records=facts,
            observed_at=observed_at,
            self_digest=unsigned.computed_self_digest,
        )


class FilingRetentionAuthority:
    """Filing-owner source mutation and read-only deletion projection."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        local_record_store: ProfileCustodyLocalRecordStore | None = None,
    ) -> None:
        self._local_record_store = local_record_store or default_profile_custody_local_record_store()
        self._root = profile_custody_owner_root(root, FILING_RETENTION_OWNER_DIRNAME)

    def record_filing_catalogue(
        self,
        *,
        profile_id: UUID,
        records: Iterable[ModeloRecord],
        observed_at: datetime,
    ) -> FilingRetentionSnapshot:
        """Persist actual filing facts; retention verdict remains domain-derived."""
        materialized = tuple(records)
        if any(str(record.bucket_id) != str(profile_id) for record in materialized):
            raise ValueError("filing retention facts must belong to their profile")
        snapshot = FilingRetentionSnapshot.from_modelo_records(
            profile_id=profile_id,
            records=materialized,
            observed_at=observed_at,
        )
        self._ensure_root()
        with self._local_record_store.lock(self._root / ".filing-retention-owner.lock"):
            self._local_record_store.write(
                self.path(profile_id),
                snapshot.canonical_json_bytes(),
                publish_once=False,
            )
        return snapshot

    def assess(self, profile_id: UUID, *, now: datetime) -> RetentionFloorAssessment:
        """Return the FULL retention position for one profile's filed records.

        The same computation :meth:`project` performs, returned whole instead of
        reduced to a blocking flag. Two consumers want different halves of one
        answer: the custody deletion gate needs only "may I erase", while the
        operator-facing refusal must say how many records are retained, against
        what floor, and when erasure becomes safe -- a message that cites Ley
        58/2003 (LGT) arts. 66 and 70 and is worthless if it cannot name them.
        Exposing the assessment keeps :func:`assess_retention_floor` the single
        source for both rather than growing a second retention path.

        There is deliberately NO empty-assessment fallback. An absent or
        unreadable snapshot raises, exactly as it does for :meth:`project`,
        because an assessment defaulted to zero retained records is
        indistinguishable from a genuine "nothing is retained" and would read as
        permission to erase.

        Raises:
            FileNotFoundError: The canonical filing snapshot is absent.
            ValueError: The snapshot is invalid, or its identity or bytes
                disagree with its path.
        """
        return assess_retention_floor(
            self._verified_snapshot(profile_id).filing_records,
            as_of=now.astimezone(UTC),
        )

    def project(self, profile_id: UUID, *, now: datetime) -> ProfileDeletionHoldOwnerProjection:
        """Evaluate persisted filing facts using the domain retention authority."""
        validate_utc_aware(now)
        snapshot = self._verified_snapshot(profile_id)
        assessment = assess_retention_floor(snapshot.filing_records, as_of=now.astimezone(UTC))
        return ProfileDeletionHoldOwnerProjection(
            owner="filing",
            profile_id=profile_id,
            blocks_local_deletion=assessment.blocks_erase,
            source_record_id=f"filing-retention-snapshot-{profile_id}",
            source_record_digest=snapshot.self_digest,
            assessed_at=now.astimezone(UTC),
        )

    def _verified_snapshot(self, profile_id: UUID) -> FilingRetentionSnapshot:
        """Load one profile's filing snapshot, proving its identity and bytes."""
        path = self.path(profile_id)
        if not os.path.lexists(path):
            raise FileNotFoundError("canonical filing retention snapshot is absent")
        payload = self._local_record_store.read(path, maximum_bytes=_MAX_BYTES)
        try:
            snapshot = FilingRetentionSnapshot.model_validate_json(payload)
        except ValidationError as exc:
            raise ValueError("canonical filing retention snapshot is invalid") from exc
        if snapshot.profile_id != profile_id or snapshot.canonical_json_bytes() != payload:
            raise ValueError("canonical filing retention snapshot identity or bytes differ from its path")
        return snapshot

    def path(self, profile_id: UUID) -> Path:
        return self._root / f"{profile_id}.json"

    def _ensure_root(self) -> None:
        ensure_profile_custody_owner_root(self._local_record_store, self._root)


def try_record_filing_retention_snapshot(
    *,
    bucket_id: str,
    records: Iterable[ModeloRecord],
    observed_at: datetime,
) -> bool:
    """Record one profile's filing facts, and never raise doing it.

    The deletion preflight cannot read a profile's filing catalogue -- it runs
    against profiles it has not unlocked -- so this plaintext snapshot is how
    the retention position stays knowable without the key. Two callers write it:
    profile creation, so "never filed" is a RECORDED fact, and filing
    persistence, so the position stays current.

    Never raises, and the asymmetry is the reason rather than convenience.
    Neither caller exists to serve deletion: one creates a profile and one
    discharges a statutory filing obligation. A caller REFUSED because a
    deletion-support record could not be written is a worse outcome than a
    profile whose snapshot is stale or missing, and it would put a deletion
    concern in the path of both.

    Swallowing is safe only while absence fails CLOSED: with no snapshot the
    retention assessment refuses, which blocks a deletion rather than
    permitting one. An empty RECORDED snapshot is a different thing from an
    absent one and must stay so -- if absence ever comes to mean "nothing
    retained", this function's contract becomes a fail-open and must be
    revisited with it.

    Returns:
        ``True`` when the snapshot was written, ``False`` when it was not. The
        caller is expected to ignore it; it exists so a test can assert the
        write happened rather than inferring it.
    """
    try:
        FilingRetentionAuthority().record_filing_catalogue(
            profile_id=UUID(str(bucket_id)),
            records=records,
            observed_at=observed_at,
        )
    except Exception:
        get_logger(__name__).warning(
            "filing retention snapshot not recorded; a later deletion preflight will refuse",
            exc_info=True,
        )
        return False
    return True


__all__ = [
    "FILING_RETENTION_SNAPSHOT_SCHEMA_VERSION",
    "FilingRetentionAuthority",
    "FilingRetentionSnapshot",
    "try_record_filing_retention_snapshot",
]
