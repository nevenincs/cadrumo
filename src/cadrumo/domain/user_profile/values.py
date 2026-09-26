"""Strict Pydantic value records for centralized user profiles.

The portable-export bundle (:class:`UserProfilePortableExport`) lives in
the sibling :mod:`.portable_export` module so its heavy domain-type
imports do not enter ``sys.modules`` at user-profile package init.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, StringConstraints, ValidationInfo, field_validator, model_validator

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI as _PROVENANCE_SOURCE_MANUAL_CLI
from ...core.hashing import canonical_json_bytes, content_hash_hex
from ...core.identity.digest import ContentDigest, ContentDigestOrAbsent
from ...core.identity.profile import ProfileId as _ProfileId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.parsing.dates import parse_iso8601_date
from ...core.parsing.utils import parse_bool
from ...core.time.clock import now as _utc_now
from ...core.time.utc import UtcInstant
from .errors import UserProfileValidationError
from .schema import ProfileSchemaDefinition

if TYPE_CHECKING:
    from ..calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext

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
_Source = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


def declared_provenance_sources(schema: ProfileSchemaDefinition) -> frozenset[str]:
    """Return the provenance tokens declared by *schema*.

    The schema is an explicit input now.  This helper deliberately performs
    no authority or filesystem lookup; callers that need a profile schema
    must obtain it from their pinned authority generation first.
    """
    return frozenset(schema.field("provenance.source").enum_values)


if TYPE_CHECKING:
    type ProfileContext = ProfileCreateContext | ProfileDecodeContext
else:
    ProfileContext = object


def _authority_context_types() -> tuple[type[ProfileCreateContext], type[ProfileDecodeContext]]:
    """Resolve the frozen authority context classes after package import."""
    from ..calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext

    return ProfileCreateContext, ProfileDecodeContext


def _schema_from_context(info: ValidationInfo, *, surface: str) -> ProfileSchemaDefinition:
    """Extract a pinned profile schema from pydantic validation context.

    Pydantic's direct constructor API cannot carry a context.  Domain value
    records therefore use the explicit factory functions below for authority-
    bound creation and decoding.  Fact-level construction remains useful for
    building a pending edit; the record factory supplies the context when it
    validates the complete payload.
    """
    context = info.context
    if isinstance(context, _authority_context_types()):
        return context.schema
    raise UserProfileValidationError(f"{surface}: validation requires an explicit pinned profile context")


def _context_for_schema(context: object) -> ProfileContext:
    """Validate the small context contract before entering pydantic."""
    if not isinstance(context, _authority_context_types()):
        raise TypeError("profile operations require ProfileCreateContext or ProfileDecodeContext")
    schema = context.schema
    if not isinstance(schema, ProfileSchemaDefinition):
        raise TypeError("profile context schema must be a ProfileSchemaDefinition")
    return context


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


def _coerce_profile_fact_date(value: str) -> date | str:
    """Restore an ISO date string when it names a real calendar date."""
    if not _DATE_STRING_RE.fullmatch(value):
        return value
    try:
        return parse_iso8601_date(value) or value
    except ValueError:
        return value


def _coerce_profile_fact_bool(value: str) -> bool | None:
    """Restore only the two boolean tokens emitted by JSON model dumps."""
    if value not in ("true", "false"):
        return None
    parsed = parse_bool(value)
    return parsed if isinstance(parsed, bool) else None


def _coerce_profile_fact_decimal(value: str) -> Decimal | None:
    """Restore a canonical Decimal string without consuming identifiers."""
    if not _DECIMAL_STRING_RE.fullmatch(value):
        return None
    return try_parse_canonical_decimal(value)


def restore_profile_fact_value(value: object) -> object:
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
    if not isinstance(value, str):
        return value
    date_candidate = _coerce_profile_fact_date(value)
    if isinstance(date_candidate, date):
        return date_candidate
    # JSON has no boolean primitive distinct from integer — pydantic encodes
    # ``True``/``False`` as the canonical lowercase tokens ``"true"``/``"false"``
    # when ``model_dump(mode="json")`` serialises a ``bool``-typed fact. Promote
    # these tokens back to ``bool`` before the decimal check so the union
    # resolves to ``bool`` (not ``str`` or ``Decimal``) on re-parse.
    # Only promote the two JSON-serialized boolean tokens produced by
    # model_dump(mode="json"). Broader token sets (e.g. "0"/"1") must
    # not be promoted to bool here because "0" is also a valid Decimal fact.
    bool_candidate = _coerce_profile_fact_bool(value)
    if bool_candidate is not None:
        return bool_candidate
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
    decimal_candidate = _coerce_profile_fact_decimal(value)
    if decimal_candidate is not None:
        return decimal_candidate
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
    @pydantic_validation_boundary
    def _restore_typed_value(cls, value: object) -> object:
        return restore_profile_fact_value(value)

    @field_validator("source")
    @classmethod
    @pydantic_validation_boundary
    def _validate_declared_source(cls, value: str) -> str:
        """Keep standalone fact construction free of authority I/O.

        Schema membership is checked by :func:`validate_profile_fact` while
        validating a complete record against its pinned schema.
        """
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_window(self) -> UserProfileFact:
        if self.valid_from is not None and self.valid_to is not None and self.valid_from > self.valid_to:
            raise UserProfileValidationError(f"{self.path}: valid_from is after valid_to")
        return self


def validate_profile_schema_identity(
    schema_id: str,
    schema_version: int,
    *,
    schema: ProfileSchemaDefinition,
    surface: str,
) -> None:
    """Refuse payload schema metadata that is not exactly the current schema.

    ``schema_id`` and ``schema_version`` name the authority a persisted
    payload claims to have been written under, and both were free: any
    non-empty id and any integer at or above one validated, were hashed into
    the canonical snapshot digest, and were read back later as if current. An
    unknown authority is not a value with a typo in it -- it is a record
    asserting a contract nothing in this codebase defines.

    Both halves are pinned to exactly what the supplied schema declares, so the
    two failure directions refuse alike. A FUTURE version was written by
    something newer than this code, so reading it as current understates what
    the payload means. A PRE-CURRENT version was written under a contract this
    code no longer implements, and accepting it silently is read-tolerance for
    a shape nothing here is entitled to interpret -- the more dangerous of the
    two, because it produces a plausible profile rather than an error. Neither
    is repaired on the read path: the refusal names the claimed version and the
    canonical one so the payload can be rewritten under the current schema.
    """
    if schema_id != schema.id:
        raise UserProfileValidationError(
            f"{surface}: schema_id {schema_id!r} is not the canonical profile schema {schema.id!r}",
        )
    if schema_version != schema.version:
        raise UserProfileValidationError(
            f"{surface}: schema_version {schema_version} is not the canonical profile schema version {schema.version}",
        )


def validate_profile_fact(fact: UserProfileFact, *, schema: ProfileSchemaDefinition) -> None:
    """Validate schema-dependent provenance for one already-typed fact."""
    declared = declared_provenance_sources(schema)
    if fact.source not in declared:
        raise UserProfileValidationError(
            f"provenance source {fact.source!r} is not declared by the profile schema; "
            f"declared sources are {', '.join(sorted(declared))}",
        )


class UserProfileRecord(BaseModel):
    """The current typed fact record, without label or removal projections."""

    model_config = _STRICT_FROZEN

    schema_id: str
    schema_version: PayloadSchemaVersion
    profile_id: _ProfileId
    facts: tuple[UserProfileFact, ...] = Field(default=())
    setup_state: ProfileSetupState
    record_revision: int = Field(default=1, ge=1)
    previous_record_digest: ContentDigest | None = None
    content_digest: ContentDigestOrAbsent = ""
    created_at: UtcInstant = Field(default_factory=_utc_now)
    updated_at: UtcInstant = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_payload_schema(self, info: ValidationInfo) -> UserProfileRecord:
        schema = _schema_from_context(info, surface="user profile record")
        validate_profile_schema_identity(
            self.schema_id,
            self.schema_version,
            schema=schema,
            surface="user profile record",
        )
        for fact in self.facts:
            validate_profile_fact(fact, schema=schema)
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
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
    schema_id: str
    schema_version: PayloadSchemaVersion
    created_at: UtcInstant = Field(default_factory=_utc_now)
    facts: tuple[UserProfileFact, ...]
    canonical_hash: ContentDigest

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_payload_schema(self, info: ValidationInfo) -> UserProfileSnapshot:
        schema = _schema_from_context(info, surface="user profile snapshot")
        validate_profile_schema_identity(
            self.schema_id,
            self.schema_version,
            schema=schema,
            surface="user profile snapshot",
        )
        for fact in self.facts:
            validate_profile_fact(fact, schema=schema)
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
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
        context: ProfileCreateContext,
        snapshot_id: str | None = None,
        created_at: datetime | None = None,
    ) -> UserProfileSnapshot:
        """Create an immutable snapshot from a live profile record.

        Args:
            profile: The :class:`UserProfileRecord` to snapshot.
            context: The pinned schema context for this creation operation.
            snapshot_id: Optional explicit snapshot identifier; when ``None``
                a deterministic id is derived from the profile state.
            created_at: Optional UTC timestamp stamped on the snapshot;
                defaults to the core UTC clock when ``None``.

        Returns:
            An immutable :class:`UserProfileSnapshot` for the given profile.
        """
        return create_user_profile_snapshot(
            profile,
            context=context,
            snapshot_id=snapshot_id,
            created_at=created_at,
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


def _typed_profile_facts(
    facts: Iterable[object],
    *,
    schema: ProfileSchemaDefinition,
) -> tuple[UserProfileFact, ...]:
    """Materialise and schema-check facts for an authority-bound operation."""
    typed: list[UserProfileFact] = []
    for raw in facts:
        fact = raw if isinstance(raw, UserProfileFact) else UserProfileFact.model_validate(raw)
        validate_profile_fact(fact, schema=schema)
        typed.append(fact)
    return tuple(typed)


def create_user_profile_record(
    *,
    context: ProfileCreateContext,
    profile_id: str,
    facts: tuple[UserProfileFact, ...] | list[UserProfileFact] | tuple[object, ...] = (),
    setup_state: ProfileSetupState,
    record_revision: int = 1,
    previous_record_digest: ContentDigest | None = None,
    content_digest: ContentDigestOrAbsent = "",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> UserProfileRecord:
    """Create a profile record under one pinned compiled schema.

    This is the only production creation door.  It stamps the schema
    identity supplied by the authority and validates every fact against that
    same immutable declaration.  It never consults the bundled TOML loader.
    """
    checked = _context_for_schema(context)
    create_context_type, _ = _authority_context_types()
    if not isinstance(checked, create_context_type):
        raise TypeError("creating a profile record requires ProfileCreateContext")
    schema = checked.schema
    typed_facts = _typed_profile_facts(tuple(facts), schema=schema)
    instant_created = created_at or _utc_now()
    instant_updated = updated_at or instant_created
    payload: dict[str, object] = {
        "schema_id": schema.id,
        "schema_version": schema.version,
        "profile_id": profile_id,
        "facts": typed_facts,
        "setup_state": setup_state,
        "record_revision": record_revision,
        "previous_record_digest": previous_record_digest,
        "content_digest": content_digest,
        "created_at": instant_created,
        "updated_at": instant_updated,
    }
    return UserProfileRecord.model_validate(payload, context=checked)


def decode_user_profile_record(
    payload: bytes | str | Mapping[str, object],
    *,
    context: ProfileDecodeContext,
) -> UserProfileRecord:
    """Decode a secure profile record against the operation-pinned schema."""
    checked = _context_for_schema(context)
    _, decode_context_type = _authority_context_types()
    if not isinstance(checked, decode_context_type):
        raise TypeError("decoding a profile record requires ProfileDecodeContext")
    if isinstance(payload, Mapping):
        record = UserProfileRecord.model_validate(payload, context=checked)
    else:
        record = UserProfileRecord.model_validate_json(payload, context=checked)
    return record


def create_user_profile_snapshot(
    profile: UserProfileRecord,
    *,
    context: ProfileCreateContext,
    snapshot_id: str | None = None,
    created_at: datetime | None = None,
) -> UserProfileSnapshot:
    """Create an immutable encrypted-persistence snapshot under one schema.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    checked = _context_for_schema(context)
    create_context_type, _ = _authority_context_types()
    if not isinstance(checked, create_context_type):
        raise TypeError("creating a profile snapshot requires ProfileCreateContext")
    if profile.setup_state is not ProfileSetupState.COMPLETE:
        raise UserProfileValidationError("cannot snapshot an incomplete profile record")
    validate_profile_schema_identity(
        profile.schema_id,
        profile.schema_version,
        schema=checked.schema,
        surface="user profile record",
    )
    typed_facts = _typed_profile_facts(tuple(profile.facts), schema=checked.schema)
    instant = created_at or _utc_now()
    facts = tuple(
        sorted(
            typed_facts,
            key=lambda fact: (
                fact.path,
                fact.valid_from or date.min,
                fact.valid_to or date.max,
                canonical_json_bytes(fact.model_dump(mode="json")),
            ),
        ),
    )
    digest = _derive_canonical_hash(
        schema_id=checked.schema.id,
        schema_version=checked.schema.version,
        profile_id=profile.profile_id,
        facts=facts,
    )
    snapshot = UserProfileSnapshot.model_validate(
        {
            "snapshot_id": snapshot_id or new_profile_snapshot_id(profile.profile_id, created_at=instant),
            "profile_id": profile.profile_id,
            "schema_id": checked.schema.id,
            "schema_version": checked.schema.version,
            "created_at": instant,
            "facts": facts,
            "canonical_hash": digest,
        },
        context=checked,
    )
    return snapshot


__all__ = [
    "PayloadSchemaVersion",
    "ProfileContext",
    "ProfileSetupState",
    "UserProfileFact",
    "UserProfileFactValue",
    "UserProfileRecord",
    "UserProfileSnapshot",
    "create_user_profile_record",
    "create_user_profile_snapshot",
    "declared_provenance_sources",
    "decode_user_profile_record",
    "new_profile_id",
    "new_profile_snapshot_id",
    "restore_profile_fact_value",
    "section_field_key",
    "validate_profile_fact",
    "validate_profile_schema_identity",
]
