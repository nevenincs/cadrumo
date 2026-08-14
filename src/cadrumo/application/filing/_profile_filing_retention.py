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
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.time import validate_utc_aware
from ...domain.modelos import ModeloRecord
from ...domain.retention import assess_retention_floor
from .._profile_deletion_hold_contract import ProfileDeletionHoldOwnerProjection
from ..profile_custody import (
    ProfileCustodyLocalRecordStore,
    canonical_snapshot_bytes,
    canonical_snapshot_digest,
    canonical_snapshot_payload,
    default_profile_custody_local_record_store,
    ensure_profile_custody_owner_root,
    profile_custody_owner_root,
)

_MAX_BYTES = 32 * 1024


class FilingRetentionFact(BaseModel):
    """The retention-relevant immutable projection of a real modelo filing."""

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: str = Field(min_length=64, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=2000, le=2099)
    filed_at: datetime

    @model_validator(mode="after")
    def _validate_fact(self) -> FilingRetentionFact:
        validate_utc_aware(self.filed_at)
        return self


class FilingRetentionSnapshot(BaseModel):
    """Canonical filing-owner input; it contains facts, never a verdict."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=1, frozen=True)
    profile_id: UUID
    filing_records: tuple[FilingRetentionFact, ...]
    observed_at: datetime
    self_digest: str = Field(min_length=71, max_length=71)

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
            limit_error="filing retention snapshot exceeds its byte limit",
        )

    def canonical_json_bytes(self) -> bytes:
        return canonical_snapshot_bytes(
            self,
            maximum_bytes=_MAX_BYTES,
            limit_error="filing retention snapshot exceeds its byte limit",
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
            schema_version=1,
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
        self._root = profile_custody_owner_root(root, "filing-retention-owner")

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

    def project(self, profile_id: UUID, *, now: datetime) -> ProfileDeletionHoldOwnerProjection:
        """Evaluate persisted filing facts using the domain retention authority."""
        validate_utc_aware(now)
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
        assessment = assess_retention_floor(snapshot.filing_records, as_of=now.astimezone(UTC))
        return ProfileDeletionHoldOwnerProjection(
            owner="filing",
            profile_id=profile_id,
            blocks_local_deletion=assessment.blocks_erase,
            source_record_id=f"filing-retention-snapshot-{profile_id}",
            source_record_digest=snapshot.self_digest,
            assessed_at=now.astimezone(UTC),
        )

    def path(self, profile_id: UUID) -> Path:
        return self._root / f"{profile_id}.json"

    def _ensure_root(self) -> None:
        ensure_profile_custody_owner_root(self._local_record_store, self._root)


__all__ = ["FilingRetentionAuthority", "FilingRetentionSnapshot"]
