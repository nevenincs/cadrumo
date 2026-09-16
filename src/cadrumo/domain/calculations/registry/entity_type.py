"""Typed projections for the taxpayer entity and legal-form vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ...contribuyente.entity_type import EntityType, LegalEntityForm
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
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

    def entity_type_definition(self, value: object) -> EntityTypeDefinition:
        """Return the registry definition for one entity type."""
        token = self.require_entity_type(value)
        return next(item for item in self.entity_types if item.token == token)

    def legal_entity_form_definition(self, value: object) -> LegalEntityFormDefinition:
        """Return the registry definition for one legal-entity form."""
        token = self.require_legal_entity_form(value)
        return next(item for item in self.legal_entity_forms if item.token == token)


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(
        token.strip()
        for token in required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).split(",")
        if token.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"taxpayer entity vocabulary {key!r} must contain unique tokens")
    return values


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(
        token.strip()
        for token in required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).split(",")
        if token.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"taxpayer entity vocabulary {key!r} must contain unique legal references")
    return values


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).lower()
    if value not in {"true", "false"}:
        raise RegistryValidationError(f"taxpayer entity vocabulary {key!r} must be true or false")
    return value == "true"


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("taxpayer entity vocabulary entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate taxpayer entity vocabulary key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_mapping_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("taxpayer entity vocabulary must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError("entity vocabulary requires an explicit authority operation or scope")


def _selected_mapping_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    coordinate = effective_date or date.today()
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is not None:
        return _resolve_mapping_entries(effective_date=coordinate, authority=selected_authority)
    return _bundled_mapping_entries(coordinate)


def resolve_entity_vocabulary(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EntityVocabulary:
    """Resolve and validate all entity types and legal forms from fact 0124."""
    entries = _selected_mapping_entries(effective_date=effective_date, authority=authority)
    entity_types: list[EntityTypeDefinition] = []
    for raw_token in _csv(entries, _ENTITY_TYPE_ORDER_KEY):
        token = EntityType.from_registry(raw_token)
        prefix = f"{_ENTITY_TYPE_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"entity-type token {raw_token!r} declares a mismatched value")
        entity_types.append(
            EntityTypeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                tax_regime=required_mapping_entry(entries, f"{prefix}tax_regime", subject=_ENTRY_SUBJECT),
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    vocabulary = EntityVocabulary(entity_types=tuple(entity_types), legal_entity_forms=())
    legal_entity_forms: list[LegalEntityFormDefinition] = []
    for raw_token in _csv(entries, _LEGAL_FORM_ORDER_KEY):
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
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
                choice_description=_boolean(entries, f"{prefix}choice_description"),
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
