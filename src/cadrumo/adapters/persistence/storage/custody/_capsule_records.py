"""Canonical current-format capsule marker and label records."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.identity import ProfileLabel
from ._errors import ProfileCustodyRecordError
from ._filesystem import ProfileCustodyPasswordReadOperation
from ._records import ProfileCustodyEnvelope
from ._recovery import (
    canonical_custody_digest,
    canonical_custody_json_bytes,
    reject_custody_json_constant,
    reject_duplicate_custody_members,
)
from ._sentinel_contract import ProfileCustodySentinelRecord

if TYPE_CHECKING:
    pass

PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION: Final = 1
PROFILE_CUSTODY_LAYOUT_VERSION: Final = 1
PROFILE_CUSTODY_COMMIT_MAX_BYTES: Final = 512
PROFILE_CUSTODY_DELETION_FILENAME: Final = "profile.deletion.v1.json"
PROFILE_CUSTODY_LABEL_FILENAME: Final = "profile-label.v1.txt"
PROFILE_CUSTODY_LABEL_MAX_BYTES: Final = 512
_COMMIT_TIME_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z\Z")


class ProfileCustodyCapsuleLabel(BaseModel):
    """Typed canonical label payload used inside a committed data directory."""

    model_config = _STRICT_FROZEN

    label: ProfileLabel


class _ProfileCustodyCommitPayload(BaseModel):
    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    layout_version: Literal[1]
    profile_id: UUID
    transaction_id: UUID
    publication_kind: Literal["enroll", "restore"]
    published_at: str

    @field_validator("published_at")
    @classmethod
    def _validate_published_at(cls, value: str) -> str:
        if _COMMIT_TIME_RE.fullmatch(value) is None:
            raise ValueError("profile capsule publication time must be canonical UTC microseconds")
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError as exc:
            raise ValueError("profile capsule publication time is invalid") from exc
        return value


class ProfileCustodyCommit(_ProfileCustodyCommitPayload):
    """Minimal immutable marker that is the sole current-format discovery proof."""

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        if (
            len(value) != 71
            or not value.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value[7:])
        ):
            raise ValueError("profile capsule self_digest must be a lowercase sha256 digest")
        return value

    @model_validator(mode="after")
    def _verify_self_digest(self) -> ProfileCustodyCommit:
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile capsule commit self_digest does not match")
        return self

    @property
    def canonical_payload(self) -> dict[str, object]:
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["self_digest"]
        return payload

    @property
    def computed_self_digest(self) -> str:
        return canonical_custody_digest(
            self.canonical_payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile capsule commit",
        )

    def canonical_json_bytes(self) -> bytes:
        return canonical_custody_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile capsule commit",
        )

    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        publication_kind: Literal["enroll", "restore"],
        published_at: datetime | None = None,
    ) -> ProfileCustodyCommit:
        instant = (published_at or datetime.now(UTC)).astimezone(UTC)
        serialized_time = instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        payload = _ProfileCustodyCommitPayload(
            schema_version=PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION,
            layout_version=PROFILE_CUSTODY_LAYOUT_VERSION,
            profile_id=profile_id,
            transaction_id=transaction_id,
            publication_kind=publication_kind,
            published_at=serialized_time,
        ).model_dump(mode="json")
        payload["self_digest"] = canonical_custody_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile capsule commit",
        )
        try:
            return cls.model_validate_json(
                canonical_custody_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                    subject="profile capsule commit",
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a profile capsule commit") from exc


class ProfileCustodyDeletionMarker(BaseModel):
    """Transaction ownership proof carried with a capsule during local deletion."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1] = 1
    owner: Literal["application-local-custody"] = "application-local-custody"
    profile_id: UUID
    transaction_id: UUID
    inventory_digest: str
    self_digest: str

    @model_validator(mode="after")
    def _verify_self_digest(self) -> ProfileCustodyDeletionMarker:
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile deletion marker self_digest does not match")
        return self

    @property
    def computed_self_digest(self) -> str:
        payload = self.model_dump(mode="json")
        del payload["self_digest"]
        return canonical_custody_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile deletion marker",
        )

    def canonical_json_bytes(self) -> bytes:
        return canonical_custody_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile deletion marker",
        )

    @classmethod
    def create(cls, *, profile_id: UUID, transaction_id: UUID, inventory_digest: str) -> ProfileCustodyDeletionMarker:
        payload: dict[str, object] = {
            "schema_version": 1,
            "owner": "application-local-custody",
            "profile_id": str(profile_id),
            "transaction_id": str(transaction_id),
            "inventory_digest": inventory_digest,
        }
        payload["self_digest"] = canonical_custody_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile deletion marker",
        )
        try:
            return cls.model_validate_json(
                canonical_custody_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                    subject="profile deletion marker",
                )
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a profile deletion marker") from exc


def parse_profile_custody_commit(value: bytes) -> ProfileCustodyCommit:
    """Parse only one bounded canonical commit marker."""
    if len(value) > PROFILE_CUSTODY_COMMIT_MAX_BYTES:
        raise ProfileCustodyRecordError("profile capsule commit exceeds its canonical byte limit")
    try:
        parsed = json.loads(
            value.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicate_custody_members,
            parse_constant=reject_custody_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile capsule commit must be a JSON object")
        commit = ProfileCustodyCommit.model_validate_json(
            canonical_custody_json_bytes(
                cast(dict[str, object], parsed),
                maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                subject="profile capsule commit",
            ),
        )
        if commit.canonical_json_bytes() != value:
            raise ValueError("profile capsule commit is not canonical")
        return commit
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile capsule commit is not a valid current-format record") from exc


@dataclass(frozen=True, slots=True)
class ProfileCustodyPasswordMaterial:
    """The exact normal-password read set, intentionally excluding optional recovery."""

    capsule_path: Path
    commit: ProfileCustodyCommit
    envelope: ProfileCustodyEnvelope
    sentinel: ProfileCustodySentinelRecord
    access_trace: tuple[ProfileCustodyPasswordReadOperation, ...]


def parse_profile_custody_deletion_marker(value: bytes) -> ProfileCustodyDeletionMarker:
    try:
        marker = ProfileCustodyDeletionMarker.model_validate_json(value)
        if marker.canonical_json_bytes() != value:
            raise ValueError("profile deletion marker is not canonical")
        return marker
    except (ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile deletion marker is invalid") from exc


__all__ = [
    "PROFILE_CUSTODY_COMMIT_MAX_BYTES",
    "PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION",
    "PROFILE_CUSTODY_DELETION_FILENAME",
    "PROFILE_CUSTODY_LABEL_FILENAME",
    "PROFILE_CUSTODY_LABEL_MAX_BYTES",
    "PROFILE_CUSTODY_LAYOUT_VERSION",
    "ProfileCustodyCapsuleLabel",
    "ProfileCustodyCommit",
    "ProfileCustodyDeletionMarker",
    "ProfileCustodyPasswordMaterial",
    "parse_profile_custody_commit",
    "parse_profile_custody_deletion_marker",
]
