"""Typed projections for the taxpayer entity and legal-form vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from ....core.time.clock import today_madrid
from ...contribuyente.entity_type import EntityType, LegalEntityForm
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    required_mapping_boolean,
    unique_mapping_legal_refs,
)
from .governed_fact_scope import (
    GovernedFactSource,
    cache_governed_projection,
    governed_facts_in_scope,
    require_governed_fact_authority,
    validating_governed_facts,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "taxpayer entity vocabulary"

_FACT_ID = "taxpayer-entity-vocabulary"
_ENTITY_TYPE_ORDER_KEY = "entity_type.order"
_ENTITY_TYPE_PREFIX = "entity_type."
_LEGAL_FORM_ORDER_KEY = "legal_entity_form.order"
_LEGAL_FORM_PREFIX = "legal_entity_form."


@dataclass(frozen=True, slots=True)
class EntityTypeDefinition:
    """One registry-declared taxpayer entity type and its legal semantics."""

    token: EntityType
    description: str
    tax_regime: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LegalEntityFormDefinition:
    """One registry-declared legal form and its governing entity axis."""

    token: LegalEntityForm
    description: str
    entity_type: EntityType
    legal_refs: tuple[str, ...]
    choice_description: bool


@dataclass(frozen=True, slots=True)
class EntityVocabulary:
    """Complete typed projection of fact ``taxpayer-entity-vocabulary``."""

    entity_types: tuple[EntityTypeDefinition, ...]
    legal_entity_forms: tuple[LegalEntityFormDefinition, ...]

    @property
    def all_entity_types(self) -> frozenset[EntityType]:
        """Return every taxpayer entity type declared by the registry."""
        return frozenset(item.token for item in self.entity_types)

    @property
    def all_legal_entity_forms(self) -> frozenset[LegalEntityForm]:
        """Return every legal-entity form declared by the registry."""
        return frozenset(item.token for item in self.legal_entity_forms)

    def require_entity_type(self, value: object) -> EntityType:
        """Validate and return one registry-declared entity type."""
        if isinstance(value, EntityType):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("entity-type token must be non-empty")
            try:
                token = EntityType.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("entity-type token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("entity-type token must be a string token")
        if token not in self.all_entity_types:
            raise RegistryValidationError(
                f"entity-type token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def require_legal_entity_form(self, value: object) -> LegalEntityForm:
        """Validate and return one registry-declared legal-entity form."""
        if isinstance(value, LegalEntityForm):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("legal-entity-form token must be non-empty")
            try:
                token = LegalEntityForm.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("legal-entity-form token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("legal-entity-form token must be a string token")
        if token not in self.all_legal_entity_forms:
            raise RegistryValidationError(
                f"legal-entity-form token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_entity_vocabulary(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EntityVocabulary:
    """Resolve and validate all entity types and legal forms from fact 0124."""
    coordinate = effective_date or today_madrid()
    selected = require_governed_fact_authority(authority, subject=_ENTRY_SUBJECT)
    if selected is governed_facts_in_scope():
        return _scoped_entity_vocabulary(coordinate)
    with validating_governed_facts(selected):
        return _scoped_entity_vocabulary(coordinate)


@cache_governed_projection(maxsize=64)
def _scoped_entity_vocabulary(effective_date: date) -> EntityVocabulary:
    """Build the vocabulary once per scoped authority generation and coordinate."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=None)
    entity_types: list[EntityTypeDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _ENTITY_TYPE_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = EntityType.from_registry(raw_token)
        prefix = f"{_ENTITY_TYPE_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"entity-type token {raw_token!r} declares a mismatched value")
        entity_types.append(
            EntityTypeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                tax_regime=required_mapping_entry(entries, f"{prefix}tax_regime", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    vocabulary = EntityVocabulary(entity_types=tuple(entity_types), legal_entity_forms=())
    legal_entity_forms: list[LegalEntityFormDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _LEGAL_FORM_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = LegalEntityForm.from_registry(raw_token)
        prefix = f"{_LEGAL_FORM_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"legal-entity-form token {raw_token!r} declares a mismatched value")
        entity_type = vocabulary.require_entity_type(
            required_mapping_entry(entries, f"{prefix}entity_type", subject=_ENTRY_SUBJECT)
        )
        if entity_type.value != "legal_entity":
            raise RegistryValidationError(
                f"legal-entity-form token {raw_token!r} must be scoped to legal_entity",
            )
        legal_entity_forms.append(
            LegalEntityFormDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                entity_type=entity_type,
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
                choice_description=required_mapping_boolean(
                    entries,
                    f"{prefix}choice_description",
                    subject=_ENTRY_SUBJECT,
                    case=BooleanTokenCase.CASE_INSENSITIVE,
                ),
            ),
        )
    return EntityVocabulary(entity_types=vocabulary.entity_types, legal_entity_forms=tuple(legal_entity_forms))


def require_entity_type(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EntityType:
    """Return an entity-type token only when fact 0124 declares it."""
    return resolve_entity_vocabulary(effective_date=effective_date, authority=authority).require_entity_type(value)


def require_legal_entity_form(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> LegalEntityForm:
    """Return a legal-form token only when fact 0124 declares it."""
    return resolve_entity_vocabulary(
        effective_date=effective_date,
        authority=authority,
    ).require_legal_entity_form(value)


def entity_type_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[EntityType, ...]:
    """Return entity-type choices in the authored order."""
    return tuple(
        item.token
        for item in resolve_entity_vocabulary(effective_date=effective_date, authority=authority).entity_types
    )


def legal_entity_form_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[LegalEntityForm, ...]:
    """Return legal-form choices in the authored order."""
    return tuple(
        item.token
        for item in resolve_entity_vocabulary(effective_date=effective_date, authority=authority).legal_entity_forms
    )


def legal_entity_form_choice_description_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[LegalEntityForm, ...]:
    """Return legal-form tokens whose registry metadata enables choice copy."""
    return tuple(
        item.token
        for item in resolve_entity_vocabulary(effective_date=effective_date, authority=authority).legal_entity_forms
        if item.choice_description
    )


def _entity_type_token(
    raw_token: str,
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> EntityType:
    return require_entity_type(raw_token, effective_date=effective_date, authority=authority)


def entity_type_natural_person_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EntityType:
    """Return the registry-declared natural-person entity token."""
    return _entity_type_token("natural_person", effective_date=effective_date, authority=authority)


def entity_type_legal_entity_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EntityType:
    """Return the registry-declared legal-entity token."""
    return _entity_type_token("legal_entity", effective_date=effective_date, authority=authority)


def entity_type_attribution_entity_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EntityType:
    """Return the registry-declared attribution-entity token."""
    return _entity_type_token("attribution_entity", effective_date=effective_date, authority=authority)


def legal_entity_form_sin_fines_lucrativos_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> LegalEntityForm:
    """Return the registry-declared non-profit legal-form token."""
    return resolve_entity_vocabulary(
        effective_date=effective_date,
        authority=authority,
    ).require_legal_entity_form("sin_fines_lucrativos")


__all__ = [
    "EntityTypeDefinition",
    "EntityVocabulary",
    "LegalEntityFormDefinition",
    "entity_type_attribution_entity_token",
    "entity_type_legal_entity_token",
    "entity_type_natural_person_token",
    "entity_type_tokens",
    "legal_entity_form_choice_description_tokens",
    "legal_entity_form_sin_fines_lucrativos_token",
    "legal_entity_form_tokens",
    "require_entity_type",
    "require_legal_entity_form",
    "resolve_entity_vocabulary",
]
