"""Typed projections for the cross-cutting Renta residency catalogues."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from ....core.time.clock import today_madrid
from ...contribuyente.renta_codes import FiscalResidency
from .errors import RegistryValidationError
from .facts.resolution import (
    EntitySetFactQuery,
    ResolvedEntitySetFact,
    required_mapping_entry,
    unique_mapping_tokens,
)
from .facts.string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    required_mapping_boolean,
)
from .governed_fact_scope import (
    GovernedFactSource,
    require_governed_fact_authority,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "fiscal-residency catalogue"

_FISCAL_RESIDENCY_FACT_ID = "renta-fiscal-residency-vocabulary"
_EU_EEA_COUNTRY_FACT_ID = "eu-eea-country-membership"
_FISCAL_RESIDENCY_ORDER_KEY = "fiscal_residency.order"
_FISCAL_RESIDENCY_DEFAULT_KEY = "fiscal_residency.default_token"
_FISCAL_RESIDENCY_PREFIX = "fiscal_residency."


@dataclass(frozen=True, slots=True)
class FiscalResidencyDefinition:
    """One registry-declared fiscal-residency token and its semantics."""

    token: FiscalResidency
    description: str
    tax_regime: str
    requires_country: bool
    is_default: bool


@dataclass(frozen=True, slots=True)
class FiscalResidencyCatalogue:
    """Typed projection of the dated fiscal-residency vocabulary."""

    definitions: tuple[FiscalResidencyDefinition, ...]
    default_token: FiscalResidency

    @property
    def all_residencies(self) -> frozenset[FiscalResidency]:
        """Return every residency token declared by this catalogue."""
        return frozenset(definition.token for definition in self.definitions)

    @property
    def choices(self) -> tuple[FiscalResidency, ...]:
        """Return declared residency tokens in authored choice order."""
        return tuple(definition.token for definition in self.definitions)

    def require(self, value: object) -> FiscalResidency:
        """Project one token only when the selected fact declares it."""
        if isinstance(value, FiscalResidency):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("fiscal-residency token must be non-empty")
            if raw not in {str(item) for item in self.all_residencies}:
                raise RegistryValidationError(f"fiscal-residency token {raw!r} is not declared by the facts registry")
            token = FiscalResidency.from_registry(raw)
        else:
            raise RegistryValidationError("fiscal-residency token must be a string token")
        if token not in self.all_residencies:
            raise RegistryValidationError(
                f"fiscal-residency token {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> FiscalResidencyDefinition:
        """Return the declaration for a required residency token."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(
    fact_id=_FISCAL_RESIDENCY_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY
)


def resolve_fiscal_residency_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> FiscalResidencyCatalogue:
    """Resolve the dated fiscal-residency vocabulary through fact 0122."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    definitions: list[FiscalResidencyDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _FISCAL_RESIDENCY_ORDER_KEY, subject=_ENTRY_SUBJECT):
        prefix = f"{_FISCAL_RESIDENCY_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"fiscal-residency token {raw_token!r} declares a mismatched value")
        definitions.append(
            FiscalResidencyDefinition(
                token=FiscalResidency.from_registry(raw_token),
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                tax_regime=required_mapping_entry(entries, f"{prefix}tax_regime", subject=_ENTRY_SUBJECT),
                requires_country=required_mapping_boolean(
                    entries, f"{prefix}requires_country", subject=_ENTRY_SUBJECT, case=BooleanTokenCase.EXACT
                ),
                is_default=required_mapping_boolean(
                    entries, f"{prefix}default", subject=_ENTRY_SUBJECT, case=BooleanTokenCase.EXACT
                ),
            ),
        )
    catalogue = FiscalResidencyCatalogue(
        definitions=tuple(definitions),
        default_token=FiscalResidency.from_registry(
            required_mapping_entry(entries, _FISCAL_RESIDENCY_DEFAULT_KEY, subject=_ENTRY_SUBJECT)
        ),
    )
    if len(catalogue.all_residencies) != len(catalogue.definitions):
        raise RegistryValidationError("fiscal-residency catalogue has duplicate tokens")
    if catalogue.default_token not in catalogue.all_residencies:
        raise RegistryValidationError("fiscal-residency default token is not declared in the order")
    if sum(definition.is_default for definition in catalogue.definitions) != 1:
        raise RegistryValidationError("fiscal-residency catalogue must declare exactly one default token")
    if (
        next(definition for definition in catalogue.definitions if definition.is_default).token
        != catalogue.default_token
    ):
        raise RegistryValidationError("fiscal-residency default declaration disagrees with default_token")
    return catalogue


def require_fiscal_residency(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> FiscalResidency:
    """Project one registry-governed fiscal-residency token."""
    return resolve_fiscal_residency_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def fiscal_residency_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[FiscalResidency, ...]:
    """Return fiscal-residency choices in authored order."""
    return resolve_fiscal_residency_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def default_fiscal_residency(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> FiscalResidency:
    """Return the registry-declared default residency token."""
    return resolve_fiscal_residency_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).default_token


def fiscal_residency_requires_country(
    value: FiscalResidency | str | None,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return the registry-declared country requirement for one token."""
    if value is None or value == "":
        return False
    return (
        resolve_fiscal_residency_catalogue(
            effective_date=effective_date,
            authority=authority,
        )
        .definition(value)
        .requires_country
    )


def _resolve_country_entities(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> frozenset[str]:
    resolved = authority.resolve_governed_fact(
        EntitySetFactQuery(
            fact_id=_EU_EEA_COUNTRY_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise RegistryValidationError("EU/EEA country membership must resolve as an entity-set fact")
    entities = tuple(str(entity).strip().upper() for entity in resolved.payload.entities)
    if not entities or len(entities) != len(set(entities)) or any(len(entity) != 2 for entity in entities):
        raise RegistryValidationError("EU/EEA country membership must contain unique two-letter country codes")
    return frozenset(entities)


def ue_eea_country_codes(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[str]:
    """Return the selected EU/EEA country-code entity set from fact 0123."""
    selected = require_governed_fact_authority(authority, subject="EU/EEA country-entity set")
    return _resolve_country_entities(effective_date=effective_date or today_madrid(), authority=selected)


def is_ue_eea_country_code(
    country_code: str | None,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return whether a country token is in the selected EU/EEA entity set."""
    if country_code is None:
        return False
    return country_code.strip().upper() in ue_eea_country_codes(
        effective_date=effective_date,
        authority=authority,
    )


__all__ = [
    "FiscalResidencyCatalogue",
    "FiscalResidencyDefinition",
    "default_fiscal_residency",
    "fiscal_residency_choices",
    "fiscal_residency_requires_country",
    "is_ue_eea_country_code",
    "require_fiscal_residency",
    "resolve_fiscal_residency_catalogue",
    "ue_eea_country_codes",
]
