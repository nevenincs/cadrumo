"""Canonical current-format capsule marker and label records."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from .....core.hashing import (
    bounded_canonical_json_bytes,
    canonical_json_digest,
    reject_duplicate_json_members,
    reject_json_constant,
    validate_prefixed_digest,
)
from .....core.identity import PrefixedContentDigest, ProfileLabel, canonical_profile_bucket_id
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.profile_publication import ProfilePublicationKindValue
from .....core.time.clock import now as _now
from .digest_model import CustodyDigestModel
from .errors import ProfileCustodyRecordError
from .filesystem_primitives import ProfileCustodyPasswordReadOperation
from .records import ProfileCustodyEnvelope
from .sentinel_contract import ProfileCustodySentinelRecord

if TYPE_CHECKING:
    pass

PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION: Final = 1
PROFILE_CUSTODY_LAYOUT_VERSION: Final = 1
PROFILE_CUSTODY_COMMIT_MAX_BYTES: Final = 512
PROFILE_CUSTODY_DELETION_FILENAME: Final = "profile.deletion.v1.json"
PROFILE_CUSTODY_LABEL_FILENAME: Final = "profile-label.v1.json"
PROFILE_CUSTODY_LABEL_MAX_BYTES: Final = 512
_COMMIT_TIME_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z\Z")


class _ProfileCustodyCapsuleLabelPayload(BaseModel):
    """The immutable label lineage excluding its two derived digests."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    profile_id: UUID
    label: ProfileLabel
    label_revision: int
    previous_label_digest: str | None

    @field_validator("label_revision")
    @classmethod
    def _validate_label_revision(cls, value: int) -> int:
        if value < 1:
            raise ValueError("profile capsule label revision must be at least one")
        return value

    @field_validator("previous_label_digest")
    @classmethod
    def _validate_previous_label_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_prefixed_digest(value, field_name="profile capsule previous label digest")

    @model_validator(mode="after")
    def _validate_label_lineage(self) -> _ProfileCustodyCapsuleLabelPayload:
        if self.label_revision == 1 and self.previous_label_digest is not None:
            raise ValueError("first profile capsule label revision must not carry a predecessor")
        if self.label_revision > 1 and self.previous_label_digest is None:
            raise ValueError("later profile capsule label revision must carry the previous label digest")
        return self


class ProfileCustodyCapsuleLabel(_ProfileCustodyCapsuleLabelPayload):
    """UUID-bound, revisioned canonical label provenance in capsule data.

    The label remains separately readable while a profile is locked, but is
    never a loose presentation string: its strict canonical record binds it to
    one capsule UUID and carries both content and self-authentication digests.
    """

    content_digest: PrefixedContentDigest
    self_digest: str

    @field_validator("content_digest")
    @classmethod
    def _validate_content_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="profile capsule label content digest")

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="profile capsule label self digest")

    @model_validator(mode="after")
    def _verify_digests(self) -> ProfileCustodyCapsuleLabel:
        if self.content_digest != self.computed_content_digest:
            raise ValueError("profile capsule label content digest does not match")
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile capsule label self digest does not match")
        return self

    @property
    def content_payload(self) -> dict[str, object]:
        """Return the fields ``content_digest`` itself commits to.

        This is the NARROWER of the label's two digest scopes: content only,
        excluding both digest fields. It exists separately from
        :attr:`self_payload` because the label carries two independently
        checkable claims — "this content is what it says it is" and "this
        whole record, digests included, has not been altered" — and each
        needs its own excluded-field view to stay self-consistent.
        """
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["content_digest"]
        del payload["self_digest"]
        return payload

    @property
    def self_payload(self) -> dict[str, object]:
        """Return the fields ``self_digest`` itself commits to.

        The WIDER of the two scopes: everything except ``self_digest``,
        including ``content_digest``. Chaining self_digest over content_digest
        is what lets a caller detect a content_digest swapped onto a label it
        was never computed for, not just a tampered label field.
        """
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["self_digest"]
        return payload

    @property
    def computed_content_digest(self) -> str:
        """Recompute the digest a tamper check compares against ``content_digest``."""
        return canonical_json_digest(
            self.content_payload,
            maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
            subject="profile capsule label content",
        )

    @property
    def computed_self_digest(self) -> str:
        """Recompute the digest a tamper check compares against ``self_digest``."""
        return canonical_json_digest(
            self.self_payload,
            maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
            subject="profile capsule label",
        )

    def canonical_json_bytes(self) -> bytes:
        """Serialise to the exact canonical bytes this label's identity is pinned to."""
        return bounded_canonical_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
            subject="profile capsule label",
        )

    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        label: str,
        label_revision: int = 1,
        previous_label_digest: str | None = None,
    ) -> ProfileCustodyCapsuleLabel:
        """Build the one valid construction path: content digest, then self digest, then re-validate.

        The two digests are computed in sequence — ``content_digest`` first,
        then ``self_digest`` over the payload WITH that content digest already
        attached — so the chained relationship the validators check is the
        same order construction actually performs, never assembled out of
        order.
        """
        try:
            payload = _ProfileCustodyCapsuleLabelPayload(
                schema_version=1,
                profile_id=profile_id,
                label=label,
                label_revision=label_revision,
                previous_label_digest=previous_label_digest,
            ).model_dump(mode="json")
            content_digest = canonical_json_digest(
                payload,
                maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
                subject="profile capsule label content",
            )
            with_content = {**payload, "content_digest": content_digest}
            self_digest = canonical_json_digest(
                with_content,
                maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
                subject="profile capsule label",
            )
            return cls.model_validate_json(
                bounded_canonical_json_bytes(
                    {**with_content, "self_digest": self_digest},
                    maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
                    subject="profile capsule label",
                )
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a profile capsule label") from exc


class _ProfileCustodyCommitPayload(BaseModel):
    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    layout_version: Literal[1]
    profile_id: UUID
    transaction_id: UUID
    publication_kind: ProfilePublicationKindValue
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


class ProfileCustodyCommit(_ProfileCustodyCommitPayload, CustodyDigestModel):
    """Minimal immutable marker that is the sole current-format discovery proof."""

    _digest_maximum_bytes: ClassVar[int] = PROFILE_CUSTODY_COMMIT_MAX_BYTES
    _digest_subject: ClassVar[str] = "profile capsule commit"
    _digest_mismatch_message: ClassVar[str] = "profile capsule commit self_digest does not match"

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="profile capsule self_digest")

    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        publication_kind: ProfilePublicationKindValue,
        published_at: datetime | None = None,
    ) -> ProfileCustodyCommit:
        """Build the one valid construction path, stamping the publication instant and digest together.

        ``published_at`` defaults to now rather than being left for a caller
        to supply separately, so the commit instant and the digest computed
        over it can never be set by two different code paths that drift.
        """
        instant = (published_at or _now()).astimezone(UTC)
        serialized_time = instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        payload = _ProfileCustodyCommitPayload(
            schema_version=PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION,
            layout_version=PROFILE_CUSTODY_LAYOUT_VERSION,
            profile_id=profile_id,
            transaction_id=transaction_id,
            publication_kind=publication_kind,
            published_at=serialized_time,
        ).model_dump(mode="json")
        payload["self_digest"] = canonical_json_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile capsule commit",
        )
        try:
            return cls.model_validate_json(
                bounded_canonical_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                    subject="profile capsule commit",
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a profile capsule commit") from exc


class ProfileCustodyDeletionMarker(CustodyDigestModel):
    """Transaction ownership proof carried with a capsule during local deletion."""

    _digest_maximum_bytes: ClassVar[int] = PROFILE_CUSTODY_COMMIT_MAX_BYTES
    _digest_subject: ClassVar[str] = "profile custody deletion marker"
    _digest_mismatch_message: ClassVar[str] = "profile deletion marker self_digest does not match"

    model_config = _STRICT_FROZEN

    schema_version: Literal[1] = 1
    owner: Literal["application-local-custody"] = "application-local-custody"
    profile_id: UUID
    transaction_id: UUID
    inventory_digest: str
    self_digest: str

    @classmethod
    def create(cls, *, profile_id: UUID, transaction_id: UUID, inventory_digest: str) -> ProfileCustodyDeletionMarker:
        """Build the one valid construction path for a deletion ownership proof.

        ``inventory_digest`` is supplied by the caller rather than derived
        here, because it commits to the capsule INVENTORY state at deletion
        time — a fact this marker records, not one it can compute from its
        own fields.
        """
        payload: dict[str, object] = {
            "schema_version": 1,
            "owner": "application-local-custody",
            "profile_id": canonical_profile_bucket_id(profile_id),
            "transaction_id": str(transaction_id),
            "inventory_digest": inventory_digest,
        }
        payload["self_digest"] = canonical_json_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile deletion marker",
        )
        try:
            return cls.model_validate_json(
                bounded_canonical_json_bytes(
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
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile capsule commit must be a JSON object")
        commit = ProfileCustodyCommit.model_validate_json(
            bounded_canonical_json_bytes(
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


def parse_profile_custody_capsule_label(value: bytes) -> ProfileCustodyCapsuleLabel:
    """Parse exactly one bounded, UUID-bound canonical label provenance record."""
    if len(value) > PROFILE_CUSTODY_LABEL_MAX_BYTES:
        raise ProfileCustodyRecordError("profile capsule label exceeds its canonical byte limit")
    try:
        parsed = json.loads(
            value.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile capsule label must be a JSON object")
        label = ProfileCustodyCapsuleLabel.model_validate_json(
            bounded_canonical_json_bytes(
                cast(dict[str, object], parsed),
                maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
                subject="profile capsule label",
            )
        )
        if label.canonical_json_bytes() != value:
            raise ValueError("profile capsule label is not canonical")
        return label
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile capsule label is not a valid current-format record") from exc


@dataclass(frozen=True, slots=True)
class ProfileCustodyPasswordMaterial:
    """The exact normal-password read set, intentionally excluding recovery material."""

    capsule_path: Path
    commit: ProfileCustodyCommit
    envelope: ProfileCustodyEnvelope
    sentinel: ProfileCustodySentinelRecord
    access_trace: tuple[ProfileCustodyPasswordReadOperation, ...]


def parse_profile_custody_deletion_marker(value: bytes) -> ProfileCustodyDeletionMarker:
    """Parse a deletion marker and reject one whose stored bytes are not its own canonical form.

    The byte-identity check (not just the digest check the model validator
    already runs) catches a marker re-encoded differently from how
    :meth:`ProfileCustodyDeletionMarker.create` would have produced it — the
    same non-canonical-bytes hazard :func:`parse_profile_custody_commit`
    guards against for commits.
    """
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
    "parse_profile_custody_capsule_label",
    "parse_profile_custody_commit",
    "parse_profile_custody_deletion_marker",
]
