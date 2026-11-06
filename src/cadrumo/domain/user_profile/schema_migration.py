"""Forward migration of stored profile records onto the current profile schema.

Each bump that changed what a stored value MEANS carries its own transition,
and every version this build has ever migrated stays a supported stored
source, so a profile that was not opened across one release still opens across
two.

- Schema 7 reads the dated payer facts (Modelos 347, 720, 721) as three-state.
- Schema 8 reads the withholding and intracommunity payer facts the same way:
  an absent fact is unanswered, ``True`` is a declared yes and ``False`` is a
  declared no.

Before each of those bumps the setup wizard defaulted the affected questions
to ``false`` and wrote the default as an ordinary ``manual_cli`` fact, so a
stored ``false`` cannot be told apart from a question nobody answered. The
migration therefore drops every stored ``false`` on exactly those paths, keeps
every stored ``true`` and leaves every other fact untouched. A record stored at
schema 6 crosses both transitions in one run and has both sets of negatives
dropped. The cleared paths travel with the migration as typed data so the
operator can be asked to answer them again.

The transform is pure and deterministic: the same stored facts and the same
stored version always yield the same kept facts and the same cleared paths,
and a current record is never passed through it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import UserProfileValidationError
from .schema import ProfileSchemaDefinition
from .values import UserProfileFact, UserProfileRecord, section_field_key

MIGRATED_PROFILE_SCHEMA_VERSION: Final[int] = 8
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

PAYER_FACT_PATHS_CLEARED_FROM_V7: Final[frozenset[str]] = frozenset(
    {
        "iva.does_intracomunitario",
        "withholding.has_employees",
        "withholding.pays_professionals_with_retencion",
        "withholding.pays_rent_with_retencion",
    },
)
"""Schema-7 payer-fact paths whose stored ``false`` is not a proven answer.

These four gate Modelos 111, 115, 180, 190, 216, 296 and 349 through the
three-state payer facts, and schema 7 still defaulted each question to
``false``. The two-state withholding facts and the cadence-only censo
enrolments keep their stored values: neither can turn an unanswered question
into a not-applicable verdict.
"""

_CLEARED_PATHS_BY_TRANSITION: Final[Mapping[int, frozenset[str]]] = MappingProxyType(
    {
        6: PAYER_FACT_PATHS_CLEARED_FROM_V6,
        7: PAYER_FACT_PATHS_CLEARED_FROM_V7,
    },
)
"""What the transition that LEAVES each version clears, keyed by that version."""

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

_PATHS_INTRODUCED_BY_VERSION: Final[Mapping[int, frozenset[str]]] = MappingProxyType(
    {
        7: PATHS_INTRODUCED_IN_V7,
        MIGRATED_PROFILE_SCHEMA_VERSION: frozenset[str](),
    },
)
"""Fields each version ADDED. Schema 8 adds none; it only re-reads four values."""

SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS: Final[tuple[int, ...]] = tuple(sorted(_CLEARED_PATHS_BY_TRANSITION))
"""Every stored profile schema version this build still migrates forward.

Lowest first. A record stored at any of these opens; anything older is refused
on read, because no transition out of it is declared here.
"""


_EVENT_FROM_KEY: Final[str] = "schema_migration_from"
_EVENT_TO_KEY: Final[str] = "schema_migration_to"
_EVENT_CLEARED_KEY: Final[str] = "schema_migration_cleared_paths"
_PATH_SEPARATOR: Final[str] = "|"


def cleared_payer_fact_paths_between(from_version: int, to_version: int) -> frozenset[str]:
    """Return every path the transitions from ``from_version`` to ``to_version`` clear.

    Raises:
        UserProfileValidationError: When the range is empty or names a version
            no declared transition covers.
    """
    if from_version >= to_version:
        raise UserProfileValidationError(
            f"profile schema migration must move forward, not {from_version} to {to_version}",
        )
    missing = [version for version in range(from_version, to_version) if version not in _CLEARED_PATHS_BY_TRANSITION]
    if missing:
        raise UserProfileValidationError(f"no profile schema transition leaves version(s) {missing!r}")
    return frozenset(
        path for version in range(from_version, to_version) for path in _CLEARED_PATHS_BY_TRANSITION[version]
    )


def _paths_introduced_after(version: int) -> frozenset[str]:
    """Return the fields every version later than ``version`` added."""
    return frozenset(
        path
        for introduced_in, paths in _PATHS_INTRODUCED_BY_VERSION.items()
        if introduced_in > version
        for path in paths
    )


def legacy_profile_schema(
    current: ProfileSchemaDefinition,
    *,
    version: int,
) -> ProfileSchemaDefinition:
    """Return the schema a record stored at ``version`` is authenticated against.

    Every later schema only ADDED optional fields, so the legacy schema is the
    current declaration stamped with the legacy version; :func:`migrate_profile_facts`
    separately refuses a legacy record that carries a field its own version
    never declared.

    Raises:
        UserProfileValidationError: When ``current`` is not the schema this
            migration writes, or ``version`` is not a supported stored version.
    """
    if current.version != MIGRATED_PROFILE_SCHEMA_VERSION:
        raise UserProfileValidationError(
            f"profile schema {current.version} is not the schema this build migrates records onto",
        )
    if version not in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS:
        raise UserProfileValidationError(f"profile schema {version} has no forward migration in this build")
    return current.model_copy(update={"version": version})


class ProfileSchemaMigration(BaseModel):
    """The typed outcome of migrating one stored record's facts."""

    model_config = STRICT_FROZEN_CONFIG

    from_version: int = SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS[-1]
    to_version: int = MIGRATED_PROFILE_SCHEMA_VERSION
    cleared_paths: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_cleared_paths(self) -> Self:
        if tuple(sorted(set(self.cleared_paths))) != self.cleared_paths:
            raise UserProfileValidationError("cleared payer-fact paths must be sorted and unique")
        clearable = cleared_payer_fact_paths_between(self.from_version, self.to_version)
        unknown = set(self.cleared_paths) - clearable
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
    *,
    from_version: int,
) -> tuple[tuple[UserProfileFact, ...], ProfileSchemaMigration]:
    """Return the current-schema facts and the outcome for facts stored at ``from_version``.

    Raises:
        UserProfileValidationError: When a stored fact names a path the record's
            own schema version did not declare, or ``from_version`` is not a
            supported stored version.
    """
    if from_version not in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS:
        raise UserProfileValidationError(f"profile schema {from_version} has no forward migration in this build")
    stored = tuple(facts)
    later_fields = _paths_introduced_after(from_version)
    introduced = sorted({fact.path for fact in stored if section_field_key(fact.path) in later_fields})
    if introduced:
        raise UserProfileValidationError(
            f"schema-{from_version} profile record carries later-schema paths {introduced!r}",
        )
    clearable = cleared_payer_fact_paths_between(from_version, MIGRATED_PROFILE_SCHEMA_VERSION)
    kept: list[UserProfileFact] = []
    cleared: set[str] = set()
    for fact in stored:
        if fact.path in clearable and fact.value is False:
            cleared.add(fact.path)
            continue
        kept.append(fact)
    migration = ProfileSchemaMigration(
        from_version=from_version,
        to_version=MIGRATED_PROFILE_SCHEMA_VERSION,
        cleared_paths=tuple(sorted(cleared)),
    )
    return tuple(kept), migration


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
    "MIGRATED_PROFILE_SCHEMA_VERSION",
    "PATHS_INTRODUCED_IN_V7",
    "PAYER_FACT_PATHS_CLEARED_FROM_V6",
    "PAYER_FACT_PATHS_CLEARED_FROM_V7",
    "SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS",
    "ProfileSchemaMigration",
    "cleared_payer_fact_paths_between",
    "legacy_profile_schema",
    "migrate_profile_facts",
    "pending_cleared_payer_fact_paths",
]
