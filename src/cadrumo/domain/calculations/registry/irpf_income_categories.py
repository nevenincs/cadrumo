"""Typed projections for the IRPF income-category vocabulary fact (0128)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.time.clock import today_madrid
from ...deadlines.models import IrpfIncomeCategory
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "IRPF income-category vocabulary"

_FACT_ID = "irpf-income-category-vocabulary"
_ORDER_KEY = "irpf_income_category.order"
_ACTIVITY_CATEGORY_ENTRY = "irpf_income_category.activity_token"
_PREFIX = "irpf_income_category."


@dataclass(frozen=True, slots=True)
class IrpfIncomeCategoryDefinition:
    """One registry-declared IRPF income category and its semantics."""

    token: IrpfIncomeCategory
    description: str
    tax_regime: str
    activity_gate_modelos: tuple[str, ...]
    payment_modelos: tuple[str, ...]
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IrpfIncomeCategoryCatalogue:
    """Typed projection of the dated IRPF income-category vocabulary."""

    definitions: tuple[IrpfIncomeCategoryDefinition, ...]
    activity_token: IrpfIncomeCategory

    @property
    def all_categories(self) -> frozenset[IrpfIncomeCategory]:
        """Return the complete declared category membership."""
        return frozenset(item.token for item in self.definitions)

    @property
    def choices(self) -> tuple[IrpfIncomeCategory, ...]:
        """Return categories in their declared presentation order."""
        return tuple(item.token for item in self.definitions)

    def require(self, value: object) -> IrpfIncomeCategory:
        """Return one declared category or refuse an unknown value."""
        if isinstance(value, IrpfIncomeCategory):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IRPF income-category token must be non-empty")
            try:
                token = IrpfIncomeCategory(raw, _registry_validated=True)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("IRPF income-category token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("IRPF income-category token must be a string token")
        if token not in self.all_categories:
            raise RegistryValidationError(
                f"IRPF income-category token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> IrpfIncomeCategoryDefinition:
        """Return the declaration for one admitted category."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)


def _csv(entries: Mapping[str, str], key: str, *, required: bool = True) -> tuple[str, ...]:
    value = entries.get(key)
    if value is None or not value.strip():
        if required:
            raise RegistryValidationError(f"IRPF income-category vocabulary is missing {key!r}")
        return ()
    values = tuple(token.strip() for token in value.split(",") if token.strip())
    if len(values) != len(set(values)):
        raise RegistryValidationError(f"IRPF income-category vocabulary {key!r} must contain unique tokens")
    return values


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = _csv(entries, key)
    if not values:
        raise RegistryValidationError(f"IRPF income-category vocabulary {key!r} must contain legal references")
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IRPF income-category entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IRPF income-category key {entry.key!r}")
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
        raise RegistryValidationError("IRPF income-category vocabulary must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError("IRPF income-category catalogue requires an explicit authority operation or scope")


def _selected_mapping_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    coordinate = effective_date or today_madrid()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(coordinate)
    return _resolve_mapping_entries(effective_date=coordinate, authority=selected)


def resolve_irpf_income_category_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfIncomeCategoryCatalogue:
    """Resolve all six income categories from fact 0128."""
    entries = _selected_mapping_entries(effective_date=effective_date, authority=authority)
    definitions: list[IrpfIncomeCategoryDefinition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        token = IrpfIncomeCategory(raw_token, _registry_validated=True)
        prefix = f"{_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"IRPF income-category token {raw_token!r} declares a mismatched value")
        definitions.append(
            IrpfIncomeCategoryDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                tax_regime=required_mapping_entry(entries, f"{prefix}tax_regime", subject=_ENTRY_SUBJECT),
                activity_gate_modelos=_csv(entries, f"{prefix}activity_gate_modelos", required=False),
                payment_modelos=_csv(entries, f"{prefix}payment_modelos", required=False),
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    activity_token = IrpfIncomeCategory(
        required_mapping_entry(entries, _ACTIVITY_CATEGORY_ENTRY, subject=_ENTRY_SUBJECT), _registry_validated=True
    )
    catalogue = IrpfIncomeCategoryCatalogue(
        definitions=tuple(definitions),
        activity_token=activity_token,
    )
    if len(catalogue.all_categories) != len(definitions):
        raise RegistryValidationError("IRPF income-category vocabulary has duplicate tokens")
    if catalogue.activity_token not in catalogue.all_categories:
        raise RegistryValidationError("IRPF income-category activity token is not declared in the order")
    activity_definition = catalogue.definition(catalogue.activity_token)
    if not activity_definition.activity_gate_modelos:
        raise RegistryValidationError("IRPF income-category activity token must declare activity-gate modelos")
    if not activity_definition.payment_modelos:
        raise RegistryValidationError("IRPF income-category activity token must declare payment modelos")
    return catalogue


def require_irpf_income_category(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfIncomeCategory:
    """Return one registry-declared IRPF income category."""
    return resolve_irpf_income_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def irpf_income_category_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[IrpfIncomeCategory, ...]:
    """Return the registry-declared IRPF income categories in order."""
    return resolve_irpf_income_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def irpf_income_category_actividad_economica_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfIncomeCategory:
    """Return the category designated for economic-activity income."""
    return resolve_irpf_income_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).activity_token


__all__ = [
    "IrpfIncomeCategoryCatalogue",
    "IrpfIncomeCategoryDefinition",
    "irpf_income_category_actividad_economica_token",
    "irpf_income_category_choices",
    "require_irpf_income_category",
    "resolve_irpf_income_category_catalogue",
]
