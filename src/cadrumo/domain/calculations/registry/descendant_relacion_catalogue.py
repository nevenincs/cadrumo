"""Typed projection of the governed descendant-relationship catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from ....core.descendant_relacion import DescendantRelacion
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "descendant relationship catalogue"

_FACT_ID = "lirpf-art-81-maternity-descendant-relations"
_ORDER_KEY = "catalogue.ids"
_DEFAULT_KEY = "catalogue.default_id"
_ADOPTION_KEY = "catalogue.adoption_id"
_MATERNITY_KEY = "art_81_1.entitling_ids"
_ENTITLING_KEY = "art_58_2.entitling_ids"


@dataclass(frozen=True, slots=True)
class DescendantRelacionCatalogue:
    """The dated Art. 58/81 descendant relationship projection."""

    relations: tuple[DescendantRelacion, ...]
    default_token: DescendantRelacion
    adoption_token: DescendantRelacion
    maternity_tokens: tuple[DescendantRelacion, ...]
    entitling_tokens: tuple[DescendantRelacion, ...]

    @property
    def all_relations(self) -> frozenset[DescendantRelacion]:
        """Return every relationship declared by the authority."""
        return frozenset(self.relations)

    def require(self, value: object) -> DescendantRelacion:
        """Return one relationship only when the authority declares it."""
        if isinstance(value, DescendantRelacion):
            token = value
        elif isinstance(value, str):
            try:
                token = DescendantRelacion.from_registry(value.strip())
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("descendant relationship must be a non-empty token") from exc
        else:
            raise RegistryValidationError("descendant relationship must be a registry-projected token")
        if token not in self.all_relations:
            raise RegistryValidationError(
                f"descendant relationship {str(token)!r} is not declared by the facts registry",
            )
        return token


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_descendant_relacion_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> DescendantRelacionCatalogue:
    """Resolve the complete Art. 58/81 relationship catalogue."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    relations, default_token, adoption_token, maternity_tokens, entitling_tokens = _parse_relation_declarations(entries)
    catalogue = DescendantRelacionCatalogue(
        relations=relations,
        default_token=default_token,
        adoption_token=adoption_token,
        maternity_tokens=maternity_tokens,
        entitling_tokens=entitling_tokens,
    )
    _validate_relation_declaration_membership(catalogue)
    return catalogue


def _parse_relation_declarations(
    entries: Mapping[str, str],
) -> tuple[
    tuple[DescendantRelacion, ...],
    DescendantRelacion,
    DescendantRelacion,
    tuple[DescendantRelacion, ...],
    tuple[DescendantRelacion, ...],
]:
    try:
        relations = tuple(
            DescendantRelacion.from_registry(raw)
            for raw in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT)
        )
        default_token = DescendantRelacion.from_registry(
            required_mapping_entry(entries, _DEFAULT_KEY, subject=_ENTRY_SUBJECT)
        )
        adoption_token = DescendantRelacion.from_registry(
            required_mapping_entry(entries, _ADOPTION_KEY, subject=_ENTRY_SUBJECT)
        )
        maternity_tokens = tuple(
            DescendantRelacion.from_registry(raw)
            for raw in unique_mapping_tokens(entries, _MATERNITY_KEY, subject=_ENTRY_SUBJECT)
        )
        entitling_tokens = tuple(
            DescendantRelacion.from_registry(raw)
            for raw in unique_mapping_tokens(entries, _ENTITLING_KEY, subject=_ENTRY_SUBJECT)
        )
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError("descendant relationship catalogue contains an invalid token") from exc
    return relations, default_token, adoption_token, maternity_tokens, entitling_tokens


def _validate_relation_declaration_membership(catalogue: DescendantRelacionCatalogue) -> None:
    declared = catalogue.all_relations
    if len(catalogue.relations) != len(declared):
        raise RegistryValidationError("descendant relationship catalogue contains duplicate relations")
    if catalogue.default_token not in declared or catalogue.adoption_token not in declared:
        raise RegistryValidationError("descendant relationship semantic tokens must be declared in catalogue.ids")
    if not set(catalogue.maternity_tokens).issubset(declared):
        raise RegistryValidationError("Art. 81.1 relations must be declared in catalogue.ids")
    if not set(catalogue.entitling_tokens).issubset(declared):
        raise RegistryValidationError("Art. 58.2 entitling relations must be declared in catalogue.ids")


def require_descendant_relacion(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> DescendantRelacion:
    """Return one registry-declared relationship or refuse it."""
    return resolve_descendant_relacion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def descendant_relacion_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[DescendantRelacion, ...]:
    """Return relationship choices in authority order."""
    return resolve_descendant_relacion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).relations


def descendant_relacion_default_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> DescendantRelacion:
    """Return the authority-declared absent-relation default."""
    return resolve_descendant_relacion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).default_token


def descendant_relacion_adoption_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> DescendantRelacion:
    """Return the authority-declared adoption relation token."""
    return resolve_descendant_relacion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).adoption_token


def descendant_relacion_entitling_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[DescendantRelacion]:
    """Return the Art. 58.2 entry-event entitlement projection."""
    return frozenset(
        resolve_descendant_relacion_catalogue(
            effective_date=effective_date,
            authority=authority,
        ).entitling_tokens
    )


def descendant_relacion_maternity_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[DescendantRelacion]:
    """Return the Art. 81.1 maternity relationship projection."""
    return frozenset(
        resolve_descendant_relacion_catalogue(
            effective_date=effective_date,
            authority=authority,
        ).maternity_tokens
    )


__all__ = [
    "DescendantRelacionCatalogue",
    "descendant_relacion_adoption_token",
    "descendant_relacion_default_token",
    "descendant_relacion_entitling_tokens",
    "descendant_relacion_maternity_tokens",
    "descendant_relacion_tokens",
    "require_descendant_relacion",
    "resolve_descendant_relacion_catalogue",
]
