"""Strict Pydantic value records for centralized user profiles.

The portable-export bundle (:class:`UserProfilePortableExport`) lives in
the sibling :mod:`.portable_export` module so its heavy domain-type
imports do not enter ``sys.modules`` at user-profile package init.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core.decimal._grammar import try_parse_canonical_decimal
from ...core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI as _PROVENANCE_SOURCE_MANUAL_CLI
from ...core.hashing import canonical_json_bytes, content_hash_hex
from ...core.identity import ContentDigest, ContentDigestOrAbsent
from ...core.identity import ProfileId as _ProfileId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.parsing import parse_bool, parse_iso8601_date
from ...core.time.clock import now as _utc_now
from ...core.time.utc import UtcInstant
from .errors import UserProfileValidationError
from .loader import load_user_profile_schema

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
# Decimal -- it is a zero-significant identifier such as a Spanish 5-digit
# postcode, and must stay a ``str``.
#
# This guard is NOT redundant with the canonical grammar and must not be
# removed as though it were: the grammar accepts ``08001`` and returns
# ``Decimal("8001")``, silently discarding the leading zero that carries the
# meaning. The two rules answer different questions -- this one whether the
# string is a serialised Decimal at all, the grammar whether it is an
# unambiguous one -- and both have to hold.
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
    # Routed through the canonical strict grammar rather than a bare
    # ``Decimal()``. The local regex admitted the Spanish thousands shape, so
    # an operator's ``8.000`` was promoted to eight euros -- silently, three
    # orders of magnitude low, and past the numeric-field authority, which runs
    # AFTER this coercion and by then sees a legal Decimal in range. The string
    # is the only place that ambiguity is still visible, and this is the last
    # point that holds it.
    #
    # A non-conforming string is left AS a string rather than coerced. That is
    # the loud direction: the write door's numeric check then refuses it as not
    # a number, so the operator is told, instead of a wrong figure being stored
    # as a right-looking one.
    if isinstance(value, str) and _DECIMAL_STRING_RE.fullmatch(value):
        parsed = try_parse_canonical_decimal(value)
        if parsed is not None:
            return parsed
    return value



PayloadSchemaVersion = Annotated[int, Field(ge=1)]
"""Which version of a persisted payload schema a record was written against."""


class ProfileSetupState(StrEnum):
    """The only current fact-record readiness state."""

    INCOMPLETE = "incomplete"
    COMPLETE = "complete"


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
    instant = created_at or _utc_now()
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


def _canonical_payload_schema_version() -> int:
    """Return the version the loaded user-profile schema declares.

    Read through the loader on every call rather than captured at import,
    for the same reason :func:`declared_provenance_sources` is: the schema
    is the authority for its own version, and a module-level copy would be
    a second one that goes stale the moment the schema advances. The loader
    owns the caching, keyed on the schema file's stat fingerprint.
    """
    return load_user_profile_schema().version


def _validate_payload_schema_identity(schema_id: str, schema_version: int, *, surface: str) -> None:
    """Refuse payload schema metadata that is not exactly the current schema.

    ``schema_id`` and ``schema_version`` name the authority a persisted
    payload claims to have been written under, and both were free: any
    non-empty id and any integer at or above one validated, were hashed into
    the canonical snapshot digest, and were read back later as if current. An
    unknown authority is not a value with a typo in it -- it is a record
    asserting a contract nothing in this codebase defines.

    Both halves are pinned to exactly what the loaded schema declares, so the
    two failure directions refuse alike. A FUTURE version was written by
    something newer than this code, so reading it as current understates what
    the payload means. A PRE-CURRENT version was written under a contract this
    code no longer implements, and accepting it silently is read-tolerance for
    a shape nothing here is entitled to interpret -- the more dangerous of the
    two, because it produces a plausible profile rather than an error. Neither
    is repaired on the read path: the refusal names the claimed version and the
    canonical one so the payload can be rewritten under the current schema.
    """
    schema = load_user_profile_schema()
    if schema_id != schema.id:
        raise UserProfileValidationError(
            f"{surface}: schema_id {schema_id!r} is not the canonical profile schema {schema.id!r}",
        )
    if schema_version != schema.version:
        raise UserProfileValidationError(
            f"{surface}: schema_version {schema_version} is not the canonical profile schema version {schema.version}",
        )


class UserProfileRecord(BaseModel):
    """The current typed fact record, without label or removal projections."""

    model_config = _STRICT_FROZEN

    schema_id: str = "cadrumo.user_profile"
    # Read from the loaded schema rather than pinned to a literal. A literal
    # default is a second authority for the schema's own version, and the
    # moment it falls behind, every record written without an explicit version
    # is itself a pre-current payload the identity guard has to refuse.
    schema_version: PayloadSchemaVersion = Field(default_factory=_canonical_payload_schema_version)
    profile_id: _ProfileId
    facts: tuple[UserProfileFact, ...] = Field(default=())
    setup_state: ProfileSetupState
    record_revision: int = Field(default=1, ge=1)
    previous_record_digest: ContentDigest | None = None
    content_digest: ContentDigestOrAbsent = ""
    created_at: UtcInstant = Field(default_factory=_utc_now)
    updated_at: UtcInstant = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def _validate_payload_schema(self) -> UserProfileRecord:
        _validate_payload_schema_identity(self.schema_id, self.schema_version, surface="user profile record")
        return self

    @model_validator(mode="after")
    def _validate_current_record(self) -> UserProfileRecord:
        if self.created_at > self.updated_at:
            raise UserProfileValidationError("created_at must be before or equal to updated_at")
        if self.record_revision == 1 and self.previous_record_digest is not None:
            raise UserProfileValidationError("first record revision must not carry a previous record digest")
        if self.record_revision > 1 and self.previous_record_digest is None:
            raise UserProfileValidationError("later record revision must carry the previous record digest")
        computed = content_hash_hex(self.model_dump(mode="json", exclude={"content_digest"}))
        if not self.content_digest:
            object.__setattr__(self, "content_digest", computed)
        elif self.content_digest != computed:
            raise UserProfileValidationError("profile record content digest does not match its canonical content")
        return self


class UserProfileSnapshot(BaseModel):
    """Immutable filing/export profile snapshot."""

    model_config = _STRICT_FROZEN

    snapshot_id: _SnapshotId
    profile_id: _ProfileId
    schema_id: str = "cadrumo.user_profile"
    schema_version: int = Field(ge=1)
    created_at: UtcInstant = Field(default_factory=_utc_now)
    facts: tuple[UserProfileFact, ...]
    canonical_hash: ContentDigest

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
                defaults to the core UTC clock when ``None``.

        Returns:
            An immutable :class:`UserProfileSnapshot` for the given profile.
        """
        if profile.setup_state is not ProfileSetupState.COMPLETE:
            raise UserProfileValidationError("cannot snapshot an incomplete profile record")
        instant = created_at or _utc_now()
        facts = tuple(
            sorted(
                profile.facts,
                key=lambda fact: (
                    fact.path,
                    fact.valid_from or date.min,
                    fact.valid_to or date.max,
                    canonical_json_bytes(fact.model_dump(mode="json")),
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

    The serialisation itself is :func:`~cadrumo.core.hashing.content_hash_hex`,
    the project's one content-addressing primitive. A module-local
    ``_canonical_payload`` previously restated it and **disagreed with it**: it
    passed ``ensure_ascii=False`` where
    :func:`~cadrumo.core.hashing.canonical_json_bytes` does not, so a fact
    carrying any non-ASCII character — an accented Spanish name, which is the
    common case here rather than an edge case — serialised to different bytes
    and hashed to a different digest than every other content-addressed id in
    the tree. Two "canonical" forms that disagree are worse than one duplicated
    helper, so the local one is gone.
    """
    return content_hash_hex(
        {
            "schema_id": schema_id,
            "schema_version": schema_version,
            "profile_id": profile_id,
            "facts": [fact.model_dump(mode="json") for fact in facts],
        },
    )
