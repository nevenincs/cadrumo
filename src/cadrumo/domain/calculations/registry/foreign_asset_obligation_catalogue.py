"""Typed projection of the foreign-asset obligation taxonomy fact (0132)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.aggregation import ForeignAssetClass
from ....core.foreign_asset_obligation import ForeignAssetObligationGroup
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "foreign-asset-obligation-taxonomy"
_GROUP_ORDER_KEY = "group.order"
_GROUP_PREFIX = "group."
_ASSET_CLASS_PREFIX = "asset_class."


@dataclass(frozen=True, slots=True)
class ForeignAssetObligationDefinition:
    """One registry-declared RGAT obligation group."""

    token: ForeignAssetObligationGroup
    description: str
    establishing_legal_ref: str


@dataclass(frozen=True, slots=True)
class ForeignAssetObligationCatalogue:
    """Complete typed projection of fact 0132 for one filing date."""

    declarations: Mapping[str, str]
    groups: tuple[ForeignAssetObligationDefinition, ...]

    @property
    def group_choices(self) -> tuple[ForeignAssetObligationGroup, ...]:
        return tuple(item.token for item in self.groups)

    def require(self, value: object) -> ForeignAssetObligationGroup:
        """Project a group only when the selected fact declares it."""
        if isinstance(value, ForeignAssetObligationGroup):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("foreign-asset obligation group must be a non-empty string token")
            try:
                token = ForeignAssetObligationGroup._from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    "foreign-asset obligation group must be a non-empty string token",
                ) from exc
        else:
            raise RegistryValidationError("foreign-asset obligation group must be a string token")
        if token not in self.group_choices:
            raise RegistryValidationError(
                f"foreign-asset obligation group {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def group_for_asset_class(self, asset_class: ForeignAssetClass) -> ForeignAssetObligationGroup:
        """Resolve the registry-declared obligation group for one asset class."""
        try:
            asset_class_member = ForeignAssetClass(asset_class)
        except ValueError as exc:
            raise RegistryValidationError(f"unknown foreign-asset class {asset_class!r}") from exc
        key = f"{_ASSET_CLASS_PREFIX}{asset_class_member.value}.group"
        return self.require(_required(self.declarations, key))

    def groups_established_by_legal_refs(
        self,
        legal_refs: tuple[str, ...] | list[str] | set[str] | frozenset[str],
    ) -> frozenset[ForeignAssetObligationGroup]:
        """Return groups whose registry citation appears in selected legal refs."""
        cited = set(legal_refs)
        return frozenset(
            definition.token
            for definition in self.groups
            if definition.establishing_legal_ref in cited
        )


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"foreign-asset obligation taxonomy is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"foreign-asset obligation taxonomy {key!r} must contain unique tokens")
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("foreign-asset obligation taxonomy entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate foreign-asset obligation taxonomy key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("foreign-asset obligation taxonomy must resolve as a mapping fact")
    return _mapping_entries(resolved)


@lru_cache(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_entries(effective_date=effective_date, authority=bundled_authority())


def _selected_mapping_entries(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None,
) -> Mapping[str, str]:
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(effective_date)
    return _resolve_entries(effective_date=effective_date, authority=selected)


def _catalogue(entries: Mapping[str, str]) -> ForeignAssetObligationCatalogue:
    definitions: list[ForeignAssetObligationDefinition] = []
    for raw_token in _csv(entries, _GROUP_ORDER_KEY):
        token = ForeignAssetObligationGroup._from_registry(raw_token)
        prefix = f"{_GROUP_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"foreign-asset obligation group {raw_token!r} declares a mismatched value")
        definitions.append(
            ForeignAssetObligationDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                establishing_legal_ref=_required(entries, f"{prefix}establishing_legal_ref"),
            ),
        )
    if len({item.token for item in definitions}) != len(definitions):
        raise RegistryValidationError("foreign-asset obligation taxonomy contains duplicate groups")

    catalogue = ForeignAssetObligationCatalogue(
        declarations=entries,
        groups=tuple(definitions),
    )
    declared_groups = set(catalogue.group_choices)
    mapped_groups: set[ForeignAssetObligationGroup] = set()
    for key in entries:
        if not key.startswith(_ASSET_CLASS_PREFIX) or not key.endswith(".group"):
            continue
        raw_asset_class = key[len(_ASSET_CLASS_PREFIX) : -len(".group")]
        try:
            ForeignAssetClass(raw_asset_class)
        except ValueError as exc:
            raise RegistryValidationError(
                f"foreign-asset obligation taxonomy has an unknown asset class key {raw_asset_class!r}",
            ) from exc
        group = catalogue.require(entries[key])
        mapped_groups.add(group)
    if mapped_groups != declared_groups:
        raise RegistryValidationError(
            "foreign-asset obligation taxonomy must map every declared group from an asset class",
        )
    return catalogue


@lru_cache(maxsize=64)
def _bundled_catalogue(effective_date: date) -> ForeignAssetObligationCatalogue:
    return _catalogue(_bundled_mapping_entries(effective_date))


def resolve_foreign_asset_obligation_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> ForeignAssetObligationCatalogue:
    """Resolve the dated foreign-asset obligation taxonomy."""
    coordinate = effective_date or date.today()
    if authority is None and governed_facts_in_scope() is None:
        return _bundled_catalogue(coordinate)
    return _catalogue(_selected_mapping_entries(effective_date=coordinate, authority=authority))


__all__ = [
    "ForeignAssetObligationCatalogue",
    "ForeignAssetObligationDefinition",
    "resolve_foreign_asset_obligation_catalogue",
]
