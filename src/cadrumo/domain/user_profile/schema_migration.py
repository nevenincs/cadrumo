"""Forward migration of stored profile records from schema 6 to schema 7.

Schema 7 reads the dated payer facts as three-state: an absent fact is
unanswered, ``True`` is a declared yes and ``False`` is a declared no. Under
schema 6 the setup wizard defaulted those questions to ``false`` and wrote the
default as an ordinary ``manual_cli`` fact, so a stored ``false`` cannot be
told apart from a question nobody answered. The migration therefore drops
every stored ``false`` on exactly those paths, keeps every stored ``true`` and
leaves every other fact untouched. The cleared paths travel with the migration
as typed data so the operator can be asked to answer them again.

The transform is pure and deterministic: the same schema-6 facts always yield
the same kept facts and the same cleared paths, and a schema-7 record is never
passed through it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import UserProfileValidationError
from .schema import ProfileSchemaDefinition
from .values import UserProfileFact, UserProfileRecord, section_field_key

LEGACY_PROFILE_SCHEMA_VERSION: Final[int] = 6
"""The one stored profile schema version this build migrates forward."""

MIGRATED_PROFILE_SCHEMA_VERSION: Final[int] = 7
"""The profile schema version the migration writes."""

PAYER_FACT_PATHS_CLEARED_FROM_V6: Final[frozenset[str]] = frozenset(
    {
        "obligations.third_party_transactions_above_347_threshold",
        "obligations.bienes_extranjero_above_threshold",
        "obligations.monedas_virtuales_extranjero_above_threshold",
    },
)
"""Schema-6 payer-fact paths whose stored ``false`` is not a proven answer.

Frozen with the transition it describes: a later schema that adds payer facts
does not rewrite what schema 6 stored.
"""

PATHS_INTRODUCED_IN_V7: Final[frozenset[str]] = frozenset(
    {
        "obligations.premio_loteria_gravamen_especial_sin_retencion",
        "obligations.premio_loteria_gravamen_especial_trimestres",
        "irpf.plantilla_media",
    },
)
"""Fields schema 6 did not declare; a schema-6 record carrying one is refused.

Compared by declared ``section.field``, so an indexed instance path such as
``irpf.plantilla_media.0.year`` counts as its field.
"""

_EVENT_FROM_KEY: Final[str] = "schema_migration_from"
_EVENT_TO_KEY: Final[str] = "schema_migration_to"
_EVENT_CLEARED_KEY: Final[str] = "schema_migration_cleared_paths"
_PATH_SEPARATOR: Final[str] = "|"


def legacy_profile_schema(current: ProfileSchemaDefinition) -> ProfileSchemaDefinition:
    """Return the schema a stored schema-6 record is authenticated against.

    Schema 7 only adds optional fields to schema 6, so schema 6 is the current
    declaration stamped with the legacy version; the migration separately
    refuses a legacy record that carries a schema-7-only path.

    Raises:
        UserProfileValidationError: When ``current`` is not the schema this
            migration writes.
    """
    if current.version != MIGRATED_PROFILE_SCHEMA_VERSION:
        raise UserProfileValidationError(
            f"profile schema {current.version} has no forward migration from schema {LEGACY_PROFILE_SCHEMA_VERSION}",
        )
    return current.model_copy(update={"version": LEGACY_PROFILE_SCHEMA_VERSION})


class ProfileSchemaMigration(BaseModel):
    """The typed outcome of migrating one stored record's facts."""

    model_config = STRICT_FROZEN_CONFIG

    from_version: int = LEGACY_PROFILE_SCHEMA_VERSION
    to_version: int = MIGRATED_PROFILE_SCHEMA_VERSION
    cleared_paths: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_cleared_paths(self) -> Self:
        if tuple(sorted(set(self.cleared_paths))) != self.cleared_paths:
            raise UserProfileValidationError("cleared payer-fact paths must be sorted and unique")
        unknown = set(self.cleared_paths) - PAYER_FACT_PATHS_CLEARED_FROM_V6
        if unknown:
            raise UserProfileValidationError(f"migration names paths it never clears: {sorted(unknown)!r}")
        return self

    def to_event_payload(self) -> dict[str, str]:
        """Return the string payload persisted on the migration's history event."""
        return {
            _EVENT_FROM_KEY: str(self.from_version),
            _EVENT_TO_KEY: str(self.to_version),
            _EVENT_CLEARED_KEY: _PATH_SEPARATOR.join(self.cleared_paths),
        }

    @classmethod
    def from_event_payload(cls, payload: Mapping[str, str]) -> Self:
        """Parse the payload :meth:`to_event_payload` wrote.

        Raises:
            UserProfileValidationError: When a key is missing or malformed.
        """
        try:
            from_version = int(payload[_EVENT_FROM_KEY])
            to_version = int(payload[_EVENT_TO_KEY])
            cleared = payload[_EVENT_CLEARED_KEY]
        except (KeyError, ValueError) as exc:
            raise UserProfileValidationError("profile schema migration event payload is malformed") from exc
        return cls(
            from_version=from_version,
            to_version=to_version,
            cleared_paths=tuple(path for path in cleared.split(_PATH_SEPARATOR) if path),
        )


def migrate_profile_facts(
    facts: Iterable[UserProfileFact],
) -> tuple[tuple[UserProfileFact, ...], ProfileSchemaMigration]:
    """Return the schema-7 facts and the migration outcome for schema-6 facts.

    Raises:
        UserProfileValidationError: When a schema-6 fact names a path schema 6
            did not declare.
    """
    stored = tuple(facts)
    introduced = sorted({fact.path for fact in stored if section_field_key(fact.path) in PATHS_INTRODUCED_IN_V7})
    if introduced:
        raise UserProfileValidationError(f"schema-6 profile record carries schema-7 paths {introduced!r}")
    kept: list[UserProfileFact] = []
    cleared: set[str] = set()
    for fact in stored:
        if fact.path in PAYER_FACT_PATHS_CLEARED_FROM_V6 and fact.value is False:
            cleared.add(fact.path)
            continue
        kept.append(fact)
    return tuple(kept), ProfileSchemaMigration(cleared_paths=tuple(sorted(cleared)))


def pending_cleared_payer_fact_paths(
    record: UserProfileRecord,
    migrations: Iterable[ProfileSchemaMigration],
) -> tuple[str, ...]:
    """Return cleared payer-fact paths the current record has not answered again.

    A path counts as answered once the record carries a fact on it with a
    value, whether yes or no; a cleared (``None``) fact is still unanswered.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    answered = {fact.path for fact in record.facts if fact.value is not None}
    cleared = {path for migration in migrations for path in migration.cleared_paths}
    return tuple(sorted(cleared - answered))


__all__ = [
    "LEGACY_PROFILE_SCHEMA_VERSION",
    "MIGRATED_PROFILE_SCHEMA_VERSION",
    "PATHS_INTRODUCED_IN_V7",
    "PAYER_FACT_PATHS_CLEARED_FROM_V6",
    "ProfileSchemaMigration",
    "legacy_profile_schema",
    "migrate_profile_facts",
    "pending_cleared_payer_fact_paths",
]
