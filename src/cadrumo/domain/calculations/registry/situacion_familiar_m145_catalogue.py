"""Typed projection of the Modelo 145 family-situation vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ...contribuyente.renta_codes import SituacionFamiliarM145
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "lirpf-modelo-145-family-situation-vocabulary"
_ORDER_KEY = "situacion_familiar_m145.order"
_PREFIX = "situacion_familiar_m145."
_VALUE_SUFFIX = ".value"
_DESCRIPTION_SUFFIX = ".description"
_LEGAL_REFS_SUFFIX = ".legal_refs"
_ELIGIBLE_SUFFIX = ".supplementary_reduction_eligible"


@dataclass(frozen=True, slots=True)
class SituacionFamiliarM145Definition:
    """One registry-declared Modelo 145 family-situation token."""

    token: SituacionFamiliarM145
    description: str
    legal_refs: tuple[str, ...]
    supplementary_reduction_eligible: bool


@dataclass(frozen=True, slots=True)
class SituacionFamiliarM145Catalogue:
    """Complete typed projection of the dated Modelo 145 fact."""

    definitions: tuple[SituacionFamiliarM145Definition, ...]

    @property
    def choices(self) -> tuple[SituacionFamiliarM145, ...]:
        """Return the registry-declared choices in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def all_situaciones(self) -> frozenset[SituacionFamiliarM145]:
        """Return the registry-declared family-situation tokens."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> SituacionFamiliarM145:
        """Project one token only when the selected authority declares it."""
        if isinstance(value, SituacionFamiliarM145):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("Modelo 145 family-situation token must be non-empty")
            try:
                token = SituacionFamiliarM145._from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    "Modelo 145 family-situation token must be a non-empty string",
                ) from exc
        else:
            raise RegistryValidationError("Modelo 145 family-situation token must be a string token")
        if token not in self.all_situaciones:
            raise RegistryValidationError(
                f"Modelo 145 family-situation token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> SituacionFamiliarM145Definition:
        """Return the complete legal definition for one declared token."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"Modelo 145 family-situation vocabulary is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(
            f"Modelo 145 family-situation vocabulary {key!r} must contain unique tokens",
        )
    return values


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(
            f"Modelo 145 family-situation vocabulary {key!r} must contain unique legal references",
        )
    return values


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = _required(entries, key).lower()
    if value not in {"true", "false"}:
        raise RegistryValidationError(
            f"Modelo 145 family-situation vocabulary {key!r} must be true or false",
        )
    return value == "true"


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError(
                "Modelo 145 family-situation entries must be string-to-string",
            )
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate Modelo 145 family-situation key {entry.key!r}")
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
        raise RegistryValidationError("Modelo 145 family-situation vocabulary must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError(
        "Modelo 145 family-situation catalogue requires an explicit authority operation or scope"
    )


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


def resolve_situacion_familiar_m145_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliarM145Catalogue:
    """Resolve the dated Modelo 145 vocabulary through the facts authority."""
    entries = _selected_mapping_entries(effective_date=effective_date, authority=authority)
    definitions: list[SituacionFamiliarM145Definition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        try:
            token = SituacionFamiliarM145._from_registry(raw_token)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(
                "Modelo 145 family-situation vocabulary contains an invalid token",
            ) from exc
        prefix = f"{_PREFIX}{raw_token}"
        if _required(entries, f"{prefix}{_VALUE_SUFFIX}") != raw_token:
            raise RegistryValidationError(
                f"Modelo 145 family-situation token {raw_token!r} declares a mismatched value"
            )
        definitions.append(
            SituacionFamiliarM145Definition(
                token=token,
                description=_required(entries, f"{prefix}{_DESCRIPTION_SUFFIX}"),
                legal_refs=_refs(entries, f"{prefix}{_LEGAL_REFS_SUFFIX}"),
                supplementary_reduction_eligible=_boolean(entries, f"{prefix}{_ELIGIBLE_SUFFIX}"),
            ),
        )
    catalogue = SituacionFamiliarM145Catalogue(definitions=tuple(definitions))
    if len(catalogue.all_situaciones) != len(catalogue.definitions):
        raise RegistryValidationError("Modelo 145 family-situation vocabulary contains duplicate tokens")
    return catalogue


def require_situacion_familiar_m145(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliarM145:
    """Return a Modelo 145 token only when fact 0142 declares it."""
    return resolve_situacion_familiar_m145_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def situacion_familiar_m145_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[SituacionFamiliarM145, ...]:
    """Return Modelo 145 family-situation choices in authority order."""
    return resolve_situacion_familiar_m145_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def situacion_familiar_m145_is_eligible_for_supplementary_reduction(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return the registry-declared supplementary-reduction eligibility."""
    return (
        resolve_situacion_familiar_m145_catalogue(
            effective_date=effective_date,
            authority=authority,
        )
        .definition(value)
        .supplementary_reduction_eligible
    )


__all__ = [
    "SituacionFamiliarM145Catalogue",
    "SituacionFamiliarM145Definition",
    "require_situacion_familiar_m145",
    "resolve_situacion_familiar_m145_catalogue",
    "situacion_familiar_m145_choices",
    "situacion_familiar_m145_is_eligible_for_supplementary_reduction",
]
