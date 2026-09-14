"""Typed projection of the registry-owned IVA prorrata regime vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ....domain.iva.prorrata import ProrrataRegime
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "renta-iva-deduction-ratio-policy"
_ORDER_KEY = "prorrata.regime_order"
_DEFAULT_KEY = "prorrata.default_regime"
_REGIME_PREFIX = "prorrata.regime."


@dataclass(frozen=True, slots=True)
class ProrrataRegimeDefinition:
    """One registry-declared prorrata regime and its legal semantics."""

    token: ProrrataRegime
    description: str
    legal_ref: str


@dataclass(frozen=True, slots=True)
class ProrrataRegimeCatalogue:
    """Typed projection of the dated prorrata regime mapping fact."""

    definitions: tuple[ProrrataRegimeDefinition, ...]
    default_regime: ProrrataRegime

    @property
    def all_regimes(self) -> frozenset[ProrrataRegime]:
        """Return every regime token declared by the selected authority."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> ProrrataRegime:
        """Validate one opaque regime token against the selected authority."""
        if isinstance(value, ProrrataRegime):
            token = value
        elif isinstance(value, str):
            token = ProrrataRegime(value.strip())
        else:
            raise RegistryValidationError("prorrata regime must be a string token")
        if not str(token):
            raise RegistryValidationError("prorrata regime token must not be blank")
        if token not in self.all_regimes:
            raise RegistryValidationError(
                f"prorrata regime {str(token)!r} is not declared by the facts registry",
            )
        return token


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow a resolved mapping payload to a unique string-to-string map."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("prorrata regime mapping entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate prorrata regime mapping key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"prorrata regime mapping is missing {key!r}")
    return value.strip()


def _csv_tokens(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not tokens or len(set(tokens)) != len(tokens):
        raise RegistryValidationError(f"prorrata regime mapping {key!r} must declare unique non-empty tokens")
    return tokens


def resolve_prorrata_regime_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataRegimeCatalogue:
    """Resolve the dated prorrata regime vocabulary through facts authority."""
    authority = authority or governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError("prorrata regime catalogue requires an explicit authority operation or scope")
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("Renta IVA ratio policy must resolve as a mapping fact")
    entries = _mapping_entries(resolved)
    ordered_tokens = _csv_tokens(entries, _ORDER_KEY)
    default_token = ProrrataRegime(_required(entries, _DEFAULT_KEY))
    definitions: list[ProrrataRegimeDefinition] = []
    for raw_token in ordered_tokens:
        token = ProrrataRegime(raw_token)
        prefix = f"{_REGIME_PREFIX}{raw_token}"
        declared_value = _required(entries, f"{prefix}.value")
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"prorrata regime {raw_token!r} declares mismatched value {declared_value!r}",
            )
        definitions.append(
            ProrrataRegimeDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                legal_ref=_required(entries, f"{prefix}.legal_ref"),
            ),
        )
    catalogue = ProrrataRegimeCatalogue(definitions=tuple(definitions), default_regime=default_token)
    if default_token not in catalogue.all_regimes:
        raise RegistryValidationError(
            f"prorrata default regime {str(default_token)!r} is not declared in {_ORDER_KEY!r}",
        )
    return catalogue


def require_prorrata_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataRegime:
    """Return one registry-declared opaque regime token or refuse it."""
    return resolve_prorrata_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "ProrrataRegimeCatalogue",
    "ProrrataRegimeDefinition",
    "require_prorrata_regime",
    "resolve_prorrata_regime_catalogue",
]
