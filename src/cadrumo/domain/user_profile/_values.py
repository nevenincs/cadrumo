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
from ...core.parsing import parse_bool, parse_iso8601_date
from ...core.time import UtcInstant
from ...core.time import now as utc_now
from ._errors import UserProfileValidationError
from ._loader import load_user_profile_schema

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


def declared_provenance_sources() -> frozenset[str]:
    """Return the provenance tokens the user-profile schema declares.

    Read through the schema loader rather than cached here, so a caller
    that swaps the schema sees its declared set rather than a stale copy;
    the loader owns the caching.
    """
    return frozenset(load_user_profile_schema().field("provenance.source").enum_values)


def declared_field_paths() -> frozenset[str]:
    """Return the ``section.field`` paths the user-profile schema declares."""
    schema = load_user_profile_schema()
    return frozenset(f"{section.key}.{field.key}" for section in schema.sections for field in section.fields)


def section_field_key(path: str) -> str:
    """Reduce a fact path to the ``section.field`` form the schema declares.

    A repeatable section addresses its rows by index
    (``activities.0.iae_epigraph``), and the schema declares the field
    once rather than per row, so the index is dropped before the
    declared set is consulted.
    """
    head, _, tail = path.partition(".")
    if not tail:
        return path
    if "." in tail and tail.split(".", 1)[0].isdigit():
        tail = tail.split(".", 1)[1]
    return f"{head}.{tail.split('.', 1)[0]}"


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
            return parse_iso8601_date(value) or value
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
        _bool_candidate = parse_bool(value)
        if isinstance(_bool_candidate, bool):
            return _bool_candidate
    if isinstance(value, str) and _DECIMAL_STRING_RE.fullmatch(value):
        try:
            return Decimal(value)
        except (ArithmeticError, ValueError):
            return value
    return value


class UserProfileStatus(StrEnum):
    """Lifecycle status for a live profile root.

    ``SETUP_INCOMPLETE`` marks a profile minted at the start of the
    interactive setup flow whose answer set is still being collected: it
    is live (listed, resumable, its tax id reserved against duplicates)
    but not workable — modelo work is refused until setup completes and
    the record transitions to ``ACTIVE`` via :meth:`UserProfileRecord.complete_setup`.
    """

    ACTIVE = "active"
    SETUP_INCOMPLETE = "setup_incomplete"
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

    @field_validator("source")
    @classmethod
    def _validate_declared_source(cls, value: str) -> str:
        """Refuse a provenance token the schema does not declare.

        The schema declares the provenance set as a closed enum, so a
        length-constrained string bound nothing and a typo persisted
        silently as a new, unqueryable origin. A token that is genuinely
        in use belongs in the declared set; widening the schema is the
        way to add one, not stamping it and hoping.
        """
        declared = declared_provenance_sources()
        if value not in declared:
            raise UserProfileValidationError(
                f"provenance source {value!r} is not declared by the profile schema; "
                f"declared sources are {', '.join(sorted(declared))}",
            )
        return value

    @model_validator(mode="after")
    def _validate_window(self) -> UserProfileFact:
        if self.valid_from is not None and self.valid_to is not None and self.valid_from > self.valid_to:
            raise UserProfileValidationError(f"{self.path}: valid_from is after valid_to")
        return self


def _validate_payload_schema_identity(schema_id: str, schema_version: int, *, surface: str) -> None:
    """Refuse payload schema metadata the loaded schema does not sanction.

    ``schema_id`` and ``schema_version`` name the authority a persisted
    payload claims to have been written under, and both were free: any
    non-empty id and any integer at or above one validated, were hashed into
    the canonical snapshot digest, and were read back later as if current. An
    unknown authority is not a value with a typo in it -- it is a record
    asserting a contract nothing in this codebase defines.

    The version is bounded above rather than pinned. Pinning would refuse the
    defaulted records this codebase actually writes, and the loaded schema's
    version is the highest this code can be said to understand: a payload
    claiming a FUTURE version was written by something newer, so reading it as
    current is the failure worth closing.
    """
    schema = load_user_profile_schema()
    if schema_id != schema.id:
        raise UserProfileValidationError(
            f"{surface}: schema_id {schema_id!r} is not the canonical profile schema {schema.id!r}",
        )
    if schema_version > schema.version:
        raise UserProfileValidationError(
            f"{surface}: schema_version {schema_version} is newer than the canonical "
            f"profile schema version {schema.version}",
        )


class UserProfileRecord(BaseModel):
    """Live secure user-profile aggregate before persistence encoding."""

    model_config = _STRICT_FROZEN

    schema_id: str = "cadrumo.user_profile"
    schema_version: int = Field(default=1, ge=1)
    profile_id: _ProfileId
    display_name: _DisplayName
    status: UserProfileStatus = UserProfileStatus.ACTIVE
    facts: tuple[UserProfileFact, ...] = Field(default=())
    # Lifecycle instants, held to the canonical UTC contract. The ordering and
    # tombstone validators below compare these values, and a naive one compares
    # against an aware one by raising rather than by being wrong -- so the
    # invariants they enforce were only as sound as the timezone discipline of
    # whoever constructed the record. Encrypted hydration could carry a naive
    # value straight back into live profile state.
    created_at: UtcInstant = Field(default_factory=utc_now)
    updated_at: UtcInstant = Field(default_factory=utc_now)
    removed_at: UtcInstant | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _parse_status(cls, value: object) -> object:
        if isinstance(value, UserProfileStatus):
            return value
        if isinstance(value, str):
            return UserProfileStatus(value)
        return value

    @model_validator(mode="after")
    def _validate_payload_schema(self) -> UserProfileRecord:
        _validate_payload_schema_identity(self.schema_id, self.schema_version, surface="user profile record")
        return self

    @model_validator(mode="after")
    def _validate_lifecycle(self) -> UserProfileRecord:
        if self.created_at > self.updated_at:
            raise UserProfileValidationError("created_at must be before or equal to updated_at")
        if self.status is not UserProfileStatus.TOMBSTONED and self.removed_at is not None:
            raise UserProfileValidationError(f"{self.status.value} profiles must not carry removed_at")
        if self.status is UserProfileStatus.TOMBSTONED and self.removed_at is None:
            raise UserProfileValidationError("tombstoned profiles must carry removed_at")
        return self

    def complete_setup(self, *, completed_at: datetime | None = None) -> UserProfileRecord:
        """Return an ``ACTIVE`` copy of a ``SETUP_INCOMPLETE`` profile root.

        The one-way transition out of the interactive setup flow: fires at
        the flow's final commit after flow-scope validation, never before.
        Refuses any other source status so a tombstoned or already-active
        record cannot be laundered through the setup transition.
        """
        if self.status is not UserProfileStatus.SETUP_INCOMPLETE:
            raise UserProfileValidationError(
                f"complete_setup requires a setup_incomplete profile; got {self.status.value}",
            )
        instant = completed_at or utc_now()
        return self.model_copy(
            update={
                "status": UserProfileStatus.ACTIVE,
                "updated_at": instant,
            },
        )

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

    def reactivate(self, *, reactivated_at: datetime | None = None) -> UserProfileRecord:
        """Return an active :class:`UserProfileRecord` copy of a tombstoned profile root.

        The symmetric inverse of :meth:`tombstone`: clears ``removed_at``
        and restores ``status`` to :attr:`UserProfileStatus.ACTIVE` so the
        lifecycle invariant (``active`` profiles never carry
        ``removed_at``) holds on the returned copy.
        """
        instant = reactivated_at or utc_now()
        return self.model_copy(
            update={
                "status": UserProfileStatus.ACTIVE,
                "updated_at": instant,
                "removed_at": None,
            },
        )


class UserProfileSnapshot(BaseModel):
    """Immutable filing/export profile snapshot."""

    model_config = _STRICT_FROZEN

    snapshot_id: _SnapshotId
    profile_id: _ProfileId
    schema_id: str = "cadrumo.user_profile"
    schema_version: int = Field(ge=1)
    created_at: UtcInstant = Field(default_factory=utc_now)
    facts: tuple[UserProfileFact, ...]
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _validate_payload_schema(self) -> UserProfileSnapshot:
        _validate_payload_schema_identity(self.schema_id, self.schema_version, surface="user profile snapshot")
        return self

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
