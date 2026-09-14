"""Typed projection of the Art. 82 LIRPF family-situation vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType

from ...contribuyente.renta_codes import SituacionFamiliar
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "lirpf-family-situation-vocabulary"
_ORDER_KEY = "situacion_familiar.order"
_PREFIX = "situacion_familiar."
_VALUE_SUFFIX = ".value"
_DESCRIPTION_SUFFIX = ".description"
_LEGAL_REFS_SUFFIX = ".legal_refs"
_MONOPARENTAL_SUFFIX = ".monoparental_required"


@dataclass(frozen=True, slots=True)
class SituacionFamiliarDefinition:
    """One registry-declared Art. 82 family-situation token."""

    token: SituacionFamiliar
    description: str
    legal_refs: tuple[str, ...]
    monoparental_required: bool


@dataclass(frozen=True, slots=True)
class SituacionFamiliarCatalogue:
    """Complete typed projection of the dated family-situation fact."""

    definitions: tuple[SituacionFamiliarDefinition, ...]

    @property
    def choices(self) -> tuple[SituacionFamiliar, ...]:
        """Return the registry-declared choices in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def all_situaciones(self) -> frozenset[SituacionFamiliar]:
        """Return the registry-declared family-situation tokens."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> SituacionFamiliar:
        """Project one token only when the selected authority declares it."""
        if isinstance(value, SituacionFamiliar):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("family-situation token must be non-empty")
            try:
                token = SituacionFamiliar._from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("family-situation token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("family-situation token must be a string token")
        if token not in self.all_situaciones:
            raise RegistryValidationError(
                f"family-situation token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> SituacionFamiliarDefinition:
        """Return the complete legal definition for one declared token."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"family-situation vocabulary is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"family-situation vocabulary {key!r} must contain unique tokens")
    return values


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"family-situation vocabulary {key!r} must contain unique legal references")
    return values


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = _required(entries, key).lower()
    if value not in {"true", "false"}:
        raise RegistryValidationError(f"family-situation vocabulary {key!r} must be true or false")
    return value == "true"


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("family-situation vocabulary entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate family-situation vocabulary key {entry.key!r}")
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
        raise RegistryValidationError("family-situation vocabulary must resolve as a mapping fact")
    return _mapping_entries(resolved)


@lru_cache(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_mapping_entries(effective_date=effective_date, authority=bundled_authority())


def _selected_mapping_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is not None:
        return _resolve_mapping_entries(effective_date=coordinate, authority=selected)
    return _bundled_mapping_entries(coordinate)


def resolve_situacion_familiar_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliarCatalogue:
    """Resolve the dated Art. 82 vocabulary through the facts authority."""
    entries = _selected_mapping_entries(effective_date=effective_date, authority=authority)
    definitions: list[SituacionFamiliarDefinition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        try:
            token = SituacionFamiliar._from_registry(raw_token)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError("family-situation vocabulary contains an invalid token") from exc
        prefix = f"{_PREFIX}{raw_token}"
        if _required(entries, f"{prefix}{_VALUE_SUFFIX}") != raw_token:
            raise RegistryValidationError(f"family-situation token {raw_token!r} declares a mismatched value")
        definitions.append(
            SituacionFamiliarDefinition(
                token=token,
                description=_required(entries, f"{prefix}{_DESCRIPTION_SUFFIX}"),
                legal_refs=_refs(entries, f"{prefix}{_LEGAL_REFS_SUFFIX}"),
                monoparental_required=_boolean(entries, f"{prefix}{_MONOPARENTAL_SUFFIX}"),
            ),
        )
    catalogue = SituacionFamiliarCatalogue(definitions=tuple(definitions))
    if len(catalogue.all_situaciones) != len(catalogue.definitions):
        raise RegistryValidationError("family-situation vocabulary contains duplicate tokens")
    return catalogue


def require_situacion_familiar(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliar:
    """Return a family-situation token only when the fact declares it."""
    return resolve_situacion_familiar_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def situacion_familiar_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[SituacionFamiliar, ...]:
    """Return family-situation choices in authority order."""
    return resolve_situacion_familiar_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def situacion_familiar_monoparental_required(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return the registry-declared Art. 82.1.2ª mapping for one token."""
    return resolve_situacion_familiar_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).definition(value).monoparental_required


__all__ = [
    "SituacionFamiliarCatalogue",
    "SituacionFamiliarDefinition",
    "require_situacion_familiar",
    "resolve_situacion_familiar_catalogue",
    "situacion_familiar_choices",
    "situacion_familiar_monoparental_required",
]
