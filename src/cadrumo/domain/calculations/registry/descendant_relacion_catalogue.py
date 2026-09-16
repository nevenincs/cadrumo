"""Typed projection of the governed descendant-relationship catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.descendant_relacion import DescendantRelacion
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
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


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("descendant relationship entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate descendant relationship key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(
        token.strip()
        for token in required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).split(",")
        if token.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"descendant relationship catalogue {key!r} must contain unique tokens")
    return values


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("descendant relationship catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


def resolve_descendant_relacion_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> DescendantRelacionCatalogue:
    """Resolve the complete Art. 58/81 relationship catalogue."""
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError(
            "descendant relationship catalogue requires an explicit authority operation or scope"
        )
    entries = _resolve_entries(effective_date=coordinate, authority=selected)
    try:
        relations = tuple(DescendantRelacion.from_registry(raw) for raw in _csv(entries, _ORDER_KEY))
        default_token = DescendantRelacion.from_registry(
            required_mapping_entry(entries, _DEFAULT_KEY, subject=_ENTRY_SUBJECT)
        )
        adoption_token = DescendantRelacion.from_registry(
            required_mapping_entry(entries, _ADOPTION_KEY, subject=_ENTRY_SUBJECT)
        )
        maternity_tokens = tuple(DescendantRelacion.from_registry(raw) for raw in _csv(entries, _MATERNITY_KEY))
        entitling_tokens = tuple(DescendantRelacion.from_registry(raw) for raw in _csv(entries, _ENTITLING_KEY))
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError("descendant relationship catalogue contains an invalid token") from exc
    catalogue = DescendantRelacionCatalogue(
        relations=relations,
        default_token=default_token,
        adoption_token=adoption_token,
        maternity_tokens=maternity_tokens,
        entitling_tokens=entitling_tokens,
    )
    declared = catalogue.all_relations
    if len(relations) != len(declared):
        raise RegistryValidationError("descendant relationship catalogue contains duplicate relations")
    if catalogue.default_token not in declared or catalogue.adoption_token not in declared:
        raise RegistryValidationError("descendant relationship semantic tokens must be declared in catalogue.ids")
    if not set(catalogue.maternity_tokens).issubset(declared):
        raise RegistryValidationError("Art. 81.1 relations must be declared in catalogue.ids")
    if not set(catalogue.entitling_tokens).issubset(declared):
        raise RegistryValidationError("Art. 58.2 entitling relations must be declared in catalogue.ids")
    return catalogue


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
