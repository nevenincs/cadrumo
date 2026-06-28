"""Strict Pydantic value records for centralized user profiles.

The portable-export bundle (:class:`UserProfilePortableExport`) lives in
the sibling :mod:`._portable_export` module so its heavy domain-type
imports do not enter ``sys.modules`` at user-profile package init.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI as _PROVENANCE_SOURCE_MANUAL_CLI
from ...core.hashing import sha256_hex
from ...core.identity import ProfileId as _ProfileId
from ...core.parsing._dates import _parse_iso8601_date
from ...core.parsing._utils import _parse_bool
from ...core.time import now as utc_now
from ._errors import UserProfileValidationError

_SnapshotId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z_0-9.:-]*$"),
]
_FieldPath = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=192,
        pattern=r"^[a-z][a-z0-9_]*(?:\.(?:[0-9]+|[a-z][a-z0-9_]*))+$",
    ),
]
_DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
_Source = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

type UserProfileFactValue = str | bool | int | Decimal | date | None

# A JSON-encoded canonical Decimal never carries an insignificant leading
# zero: ``Decimal`` normalises ``08001`` to ``8001`` and ``model_dump(mode=
# "json")`` emits that normalised form. A multi-digit string whose integer
# part starts with ``0`` (``08001``) is therefore never a round-tripped
# Decimal — it is a zero-significant identifier such as a Spanish 5-digit
# postcode, and must stay a ``str``. The integer-part alternative below
# matches a lone ``0`` or any digit run that does not start with ``0``.
_DECIMAL_STRING_RE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
_DATE_STRING_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _coerce_profile_fact_value(value: object) -> object:
    """Restore Decimal / date types lost when ``UserProfileFactValue`` was JSON-encoded.

    JSON has no Decimal or date primitive, so ``model_dump_json`` emits both
    as strings. On re-parse the union ``str | bool | int | Decimal | date``
    would otherwise resolve to ``str`` first under pydantic's smart-union
    matcher, silently dropping numeric / temporal semantics on persisted
    facts (e.g. ``usage_ratios.business_ratio`` or
    ``irpf.minimum_personal_amount``). This validator inspects strings
    against the canonical Decimal and ISO date shapes and promotes them
    back to the original Python type before the union resolves.
    """
    if isinstance(value, str) and _DATE_STRING_RE.fullmatch(value):
        try:
            return _parse_iso8601_date(value) or value
        except ValueError:
            return value
    # JSON has no boolean primitive distinct from integer — pydantic encodes
    # ``True``/``False`` as the canonical lowercase tokens ``"true"``/``"false"``
    # when ``model_dump(mode="json")`` serialises a ``bool``-typed fact. Promote
    # these tokens back to ``bool`` before the decimal check so the union
    # resolves to ``bool`` (not ``str`` or ``Decimal``) on re-parse.
    # Only promote the two JSON-serialized boolean tokens produced by
    # model_dump(mode="json"). Broader token sets (e.g. "0"/"1") must
    # not be promoted to bool here because "0" is also a valid Decimal fact.
    if isinstance(value, str) and value in ("true", "false"):
        _bool_candidate = _parse_bool(value)
        if isinstance(_bool_candidate, bool):
            return _bool_candidate
    if isinstance(value, str) and _DECIMAL_STRING_RE.fullmatch(value):
        try:
            return Decimal(value)
        except (ArithmeticError, ValueError):
            return value
    return value


class UserProfileStatus(StrEnum):
    """Lifecycle status for a live profile root."""

    ACTIVE = "active"
    TOMBSTONED = "tombstoned"


def new_profile_id() -> str:
    """Mint a fresh immutable profile identity.

    A profile's identity is a generated UUIDv4 in the canonical
    hyphenated 36-character form. It is created once at profile
    creation and never changes — the bucket directory, keystore
    directory, secure-object key, and active-profile pointer all key
    on it. The operator-chosen display name is a fully decoupled
    mutable label with no role in any key or path.
    """
    return str(uuid4())


def new_profile_snapshot_id(profile_id: str, *, created_at: datetime | None = None) -> str:
    """Create a deterministic-shape but unique snapshot id."""
    instant = created_at or utc_now()
    return f"{profile_id}:{instant.strftime('%Y%m%dT%H%M%S%fZ')}:{uuid4().hex}"


class UserProfileFact(BaseModel):
    """One effective-dated user-profile fact."""

    model_config = _STRICT_FROZEN

    path: _FieldPath
    value: UserProfileFactValue
    source: _Source = _PROVENANCE_SOURCE_MANUAL_CLI
    valid_from: date | None = None
    valid_to: date | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _restore_typed_value(cls, value: object) -> object:
        return _coerce_profile_fact_value(value)

    @model_validator(mode="after")
    def _validate_window(self) -> UserProfileFact:
        if self.valid_from is not None and self.valid_to is not None and self.valid_from > self.valid_to:
            raise UserProfileValidationError(f"{self.path}: valid_from is after valid_to")
        return self


class UserProfileRecord(BaseModel):
    """Live secure user-profile aggregate before persistence encoding."""

    model_config = _STRICT_FROZEN

    schema_id: str = "aeat.user_profile"
    schema_version: int = Field(default=1, ge=1)
    profile_id: _ProfileId
    display_name: _DisplayName
    status: UserProfileStatus = UserProfileStatus.ACTIVE
    facts: tuple[UserProfileFact, ...] = Field(default=())
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    removed_at: datetime | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _parse_status(cls, value: object) -> object:
        if isinstance(value, UserProfileStatus):
            return value
        if isinstance(value, str):
            return UserProfileStatus(value)
        return value

    @model_validator(mode="after")
    def _validate_lifecycle(self) -> UserProfileRecord:
        if self.created_at > self.updated_at:
            raise UserProfileValidationError("created_at must be before or equal to updated_at")
        if self.status is UserProfileStatus.ACTIVE and self.removed_at is not None:
            raise UserProfileValidationError("active profiles must not carry removed_at")
        if self.status is UserProfileStatus.TOMBSTONED and self.removed_at is None:
            raise UserProfileValidationError("tombstoned profiles must carry removed_at")
        return self

    def tombstone(self, *, removed_at: datetime | None = None) -> UserProfileRecord:
        """Return a tombstoned :class:`UserProfileRecord` copy of the live profile root."""
        instant = removed_at or utc_now()
        return self.model_copy(
            update={
                "status": UserProfileStatus.TOMBSTONED,
                "updated_at": instant,
                "removed_at": instant,
            },
        )


class UserProfileSnapshot(BaseModel):
    """Immutable filing/export profile snapshot."""

    model_config = _STRICT_FROZEN

    snapshot_id: _SnapshotId
    profile_id: _ProfileId
    schema_id: str = "aeat.user_profile"
    schema_version: int = Field(ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    facts: tuple[UserProfileFact, ...]
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _canonical_hash_matches_facts(self) -> UserProfileSnapshot:
        """Re-derive ``canonical_hash`` from the facts and reject drift.

        Without this validator the snapshot's canonical_hash field is
        only computed by :meth:`from_profile` at construction time; a
        persisted snapshot whose facts are mutated post-save (or whose
        canonical_hash drifts post-save) would load silently with a
        stale digest. Re-deriving on every construction (including
        ``model_validate_json``) anchors the content-addressing
        guarantee at the boundary: the persisted hash MUST match the
        persisted facts.
        """
        derived = _derive_canonical_hash(
            schema_id=self.schema_id,
            schema_version=self.schema_version,
            profile_id=self.profile_id,
            facts=self.facts,
        )
        if derived != self.canonical_hash:
            raise UserProfileValidationError(
                f"canonical_hash {self.canonical_hash!r} does not match "
                f"the derived hash {derived!r} for profile "
                f"{self.profile_id!r}; facts or hash drifted post-save",
            )
        return self

    @classmethod
    def from_profile(
        cls,
        profile: UserProfileRecord,
        *,
        snapshot_id: str | None = None,
        created_at: datetime | None = None,
    ) -> UserProfileSnapshot:
        """Create an immutable snapshot from a live profile record.

        Args:
            profile: The :class:`UserProfileRecord` to snapshot.
            snapshot_id: Optional explicit snapshot identifier; when ``None``
                a deterministic id is derived from the profile state.
            created_at: Optional UTC timestamp stamped on the snapshot;
                defaults to ``utc_now()`` when ``None``.

        Returns:
            An immutable :class:`UserProfileSnapshot` for the given profile.
        """
        if profile.status is not UserProfileStatus.ACTIVE:
            raise UserProfileValidationError("cannot snapshot a tombstoned profile")
        instant = created_at or utc_now()
        facts = tuple(
            sorted(
                profile.facts,
                key=lambda fact: (
                    fact.path,
                    fact.valid_from or date.min,
                    fact.valid_to or date.max,
                    _canonical_payload(fact.model_dump(mode="json")),
                ),
            ),
        )
        digest = _derive_canonical_hash(
            schema_id=profile.schema_id,
            schema_version=profile.schema_version,
            profile_id=profile.profile_id,
            facts=facts,
        )
        return cls(
            snapshot_id=snapshot_id or new_profile_snapshot_id(profile.profile_id, created_at=instant),
            profile_id=profile.profile_id,
            schema_id=profile.schema_id,
            schema_version=profile.schema_version,
            created_at=instant,
            facts=facts,
            canonical_hash=digest,
        )


def _derive_canonical_hash(
    *,
    schema_id: str,
    schema_version: int,
    profile_id: str,
    facts: tuple[UserProfileFact, ...],
) -> str:
    """Compute the canonical-hash digest for a snapshot.

    Used both at :meth:`UserProfileSnapshot.from_profile` (to stamp
    the snapshot at creation) and inside the post-construction
    model_validator (to verify the persisted hash matches the
    persisted facts on load). Sharing the derivation across both
    sides anchors the content-addressing invariant — there is only
    one place where the canonical payload shape is defined.
    """
    payload = _canonical_payload(
        {
            "schema_id": schema_id,
            "schema_version": schema_version,
            "profile_id": profile_id,
            "facts": [fact.model_dump(mode="json") for fact in facts],
        },
    )
    return sha256_hex(payload)


def _canonical_payload(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
