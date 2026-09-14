"""Typed projection of the registry-owned LIVA art. 104.Tres vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.prorrata_exclusions import Art104TresExclusion
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority

_FACT_ID = "renta-iva-deduction-ratio-policy"
_ORDER_KEY = "art104_tres.exclusion_order"
_OPERATOR_KEY = "art104_tres.operator_declared"
_AUTO_KEY = "art104_tres.auto_derived"


@dataclass(frozen=True, slots=True)
class Art104TresExclusionDefinition:
    """One registry-projected exclusion token and its legal metadata."""

    token: Art104TresExclusion
    article: str
    legal_ref: str
    description: str
    kind: str


@dataclass(frozen=True, slots=True)
class Art104TresExclusionCatalogue:
    """Typed projection of the dated art. 104.Tres mapping fact."""

    definitions: tuple[Art104TresExclusionDefinition, ...]

    @property
    def all_exclusions(self) -> frozenset[Art104TresExclusion]:
        """Return every registry-declared exclusion token."""
        return frozenset(definition.token for definition in self.definitions)

    @property
    def operator_declared(self) -> frozenset[Art104TresExclusion]:
        """Return tokens the registry permits an operator to declare."""
        return frozenset(definition.token for definition in self.definitions if definition.kind == "operator_declared")

    @property
    def auto_derived(self) -> frozenset[Art104TresExclusion]:
        """Return tokens the registry marks as structurally derived."""
        return frozenset(definition.token for definition in self.definitions if definition.kind == "auto_derived")

    def require(self, value: object) -> Art104TresExclusion:
        """Validate one opaque token against this projection, failing closed."""
        if isinstance(value, Art104TresExclusion):
            token = value
        elif isinstance(value, str):
            token = Art104TresExclusion(value.strip())
        else:
            raise RegistryValidationError("art. 104.Tres exclusion must be a string token")
        if not str(token):
            raise RegistryValidationError("art. 104.Tres exclusion token must not be blank")
        if token not in self.all_exclusions:
            raise RegistryValidationError(
                f"art. 104.Tres exclusion {str(token)!r} is not declared by the facts registry",
            )
        return token


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow a resolved mapping payload to a unique string-to-string map."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("art. 104.Tres mapping entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate art. 104.Tres mapping key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"art. 104.Tres mapping is missing {key!r}")
    return value.strip()


def _csv_tokens(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not tokens or len(set(tokens)) != len(tokens):
        raise RegistryValidationError(f"art. 104.Tres mapping {key!r} must declare unique non-empty tokens")
    return tokens


def resolve_art104_tres_exclusion_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> Art104TresExclusionCatalogue:
    """Resolve the complete art. 104.Tres catalogue through facts authority."""
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
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
    operator_tokens = _csv_tokens(entries, _OPERATOR_KEY)
    auto_tokens = _csv_tokens(entries, _AUTO_KEY)
    ordered = tuple(Art104TresExclusion(token) for token in ordered_tokens)
    operator = frozenset(Art104TresExclusion(token) for token in operator_tokens)
    auto = frozenset(Art104TresExclusion(token) for token in auto_tokens)
    all_tokens = frozenset(ordered)
    if operator & auto or operator | auto != all_tokens:
        raise RegistryValidationError(
            "art. 104.Tres operator and auto-derived partitions must be disjoint and cover the exclusion order",
        )

    definitions: list[Art104TresExclusionDefinition] = []
    for token in ordered:
        prefix = f"art104_tres.exclusion.{token}"
        kind = _required(entries, f"{prefix}.kind")
        expected_kind = "operator_declared" if token in operator else "auto_derived"
        if kind != expected_kind:
            raise RegistryValidationError(
                f"art. 104.Tres token {str(token)!r} has kind {kind!r}, expected {expected_kind!r}",
            )
        definitions.append(
            Art104TresExclusionDefinition(
                token=token,
                article=_required(entries, f"{prefix}.article"),
                legal_ref=_required(entries, f"{prefix}.legal_ref"),
                description=_required(entries, f"{prefix}.description"),
                kind=kind,
            ),
        )
    return Art104TresExclusionCatalogue(definitions=tuple(definitions))


def require_art104_tres_exclusion(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> Art104TresExclusion:
    """Return one registry-declared opaque token or refuse it."""
    catalogue = resolve_art104_tres_exclusion_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    return catalogue.require(value)


__all__ = [
    "Art104TresExclusionCatalogue",
    "Art104TresExclusionDefinition",
    "require_art104_tres_exclusion",
    "resolve_art104_tres_exclusion_catalogue",
]
