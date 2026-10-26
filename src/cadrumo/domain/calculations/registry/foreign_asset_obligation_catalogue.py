"""Typed projection of the foreign-asset obligation taxonomy fact (0132)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ....core.aggregation import ForeignAssetClass
from ....core.foreign_asset_obligation import ForeignAssetObligationGroup
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "foreign-asset obligation taxonomy"

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
        """Return obligation groups in registry-authored order."""
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
                token = ForeignAssetObligationGroup.from_registry(raw)
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
        return self.require(required_mapping_entry(self.declarations, key, subject=_ENTRY_SUBJECT))

    def groups_established_by_legal_refs(
        self,
        legal_refs: tuple[str, ...] | list[str] | set[str] | frozenset[str],
    ) -> frozenset[ForeignAssetObligationGroup]:
        """Return groups whose registry citation appears in selected legal refs."""
        cited = set(legal_refs)
        return frozenset(definition.token for definition in self.groups if definition.establishing_legal_ref in cited)


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _catalogue(entries: Mapping[str, str]) -> ForeignAssetObligationCatalogue:
    definitions: list[ForeignAssetObligationDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _GROUP_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = ForeignAssetObligationGroup.from_registry(raw_token)
        prefix = f"{_GROUP_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"foreign-asset obligation group {raw_token!r} declares a mismatched value")
        definitions.append(
            ForeignAssetObligationDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                establishing_legal_ref=required_mapping_entry(
                    entries, f"{prefix}establishing_legal_ref", subject=_ENTRY_SUBJECT
                ),
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


def resolve_foreign_asset_obligation_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> ForeignAssetObligationCatalogue:
    """Resolve the dated foreign-asset obligation taxonomy.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


__all__ = [
    "ForeignAssetObligationCatalogue",
    "ForeignAssetObligationDefinition",
    "resolve_foreign_asset_obligation_catalogue",
]
