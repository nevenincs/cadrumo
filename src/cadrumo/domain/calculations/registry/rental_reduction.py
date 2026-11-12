"""Typed projections of the governed art. 23.2 LIRPF rental-reduction facts.

Two facts govern the reduction: the regime fact, which dates the move from the
single legacy rate to the tiers and names the legacy token, and the tier
catalogue, which declares each tier of the tiered regime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...renta.rental_reduction import RentalReductionArt232Tier
from ...renta.rental_reduction_derivation import RentalReductionArt232Rules
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .formula_runtime_ops import read_parameter
from .governed_fact_scope import GovernedFactSource
from .ids import ModeloId, RevisionId
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import PinnedAuthorityOperation

_ENTRY_SUBJECT: Final = "rental reduction mapping"
_UNIQUE_TOKENS_REQUIREMENT: Final = "must declare unique non-empty tokens"

_FACT_ID = "renta-rental-reduccion-art-23-2-tier-catalogue"
_ORDER_KEY = "tier_order"
_TIER_PREFIX = "tier."


@dataclass(frozen=True, slots=True)
class RentalReductionArt232TierDefinition:
    """One registry-declared tier and its legal selection metadata."""

    token: RentalReductionArt232Tier
    description: str
    legal_ref: str
    parameter_id: str


@dataclass(frozen=True, slots=True)
class RentalReductionArt232TierCatalogue:
    """Typed projection of the dated rental-reduction mapping fact."""

    definitions: tuple[RentalReductionArt232TierDefinition, ...]

    @property
    def all_tiers(self) -> frozenset[RentalReductionArt232Tier]:
        """Return every registry-declared tier token."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> RentalReductionArt232Tier:
        """Validate one opaque tier token against the selected authority."""
        if isinstance(value, RentalReductionArt232Tier):
            token = value
        elif isinstance(value, str):
            token = RentalReductionArt232Tier(value.strip())
        else:
            raise RegistryValidationError("rental reduction tier must be a string token")
        if not str(token):
            raise RegistryValidationError("rental reduction tier token must not be blank")
        if token not in self.all_tiers:
            raise RegistryValidationError(
                f"rental reduction tier {str(token)!r} is not declared by the facts registry",
            )
        return token


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)

_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_rental_reduction_art232_tier_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> RentalReductionArt232TierCatalogue:
    """Resolve the dated rental-reduction tier catalogue through authority."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    definitions: list[RentalReductionArt232TierDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _ORDER_KEY, subject=_ENTRY_SUBJECT, requirement=_UNIQUE_TOKENS_REQUIREMENT
    ):
        token = RentalReductionArt232Tier(raw_token)
        prefix = f"{_TIER_PREFIX}{raw_token}"
        declared_value = required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"rental reduction tier {raw_token!r} declares mismatched value {declared_value!r}",
            )
        definitions.append(
            RentalReductionArt232TierDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
                parameter_id=required_mapping_entry(entries, f"{prefix}.parameter_id", subject=_ENTRY_SUBJECT),
            ),
        )
    return RentalReductionArt232TierCatalogue(definitions=tuple(definitions))


_REGIME_FACT_ID: Final = "renta-rental-reduccion-art-23-2-regime"


def _regime_date(entries: dict[str, object], key: str) -> date:
    value = entries.get(key)
    if not isinstance(value, date):
        raise RegistryValidationError(f"rental reduction regime fact {_REGIME_FACT_ID!r} has no date entry {key!r}")
    return value


def _regime_text(entries: dict[str, object], key: str) -> str:
    value = entries.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(f"rental reduction regime fact {_REGIME_FACT_ID!r} has no text entry {key!r}")
    return value.strip()


def _whole_years(value: Decimal) -> int:
    if value != value.to_integral_value() or value < 0:
        raise RegistryValidationError("the rehabilitation look-back must be a whole number of years")
    return int(value)


def resolve_rental_reduction_art232_rules(
    *,
    modelo_id: ModeloId,
    revision_id: RevisionId,
    devengo: date,
    operation: PinnedAuthorityOperation,
) -> RentalReductionArt232Rules:
    """Resolve the dated regime fact and the two tier thresholds at a devengo date.

    ``modelo_id`` and ``revision_id`` name the annual return edition whose parameters the
    calculation pins; the regime fact is read on the filing-period axis at ``devengo``.
    """
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(fact_id=_REGIME_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=devengo),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("rental reduction regime fact must resolve as a mapping fact")
    entries: dict[str, object] = {str(entry.key): entry.value for entry in resolved.payload.entries}
    date_context = {DateAxis.FILING_PERIOD.value: devengo}
    return RentalReductionArt232Rules(
        regime_start=_regime_date(entries, "regime_start"),
        contract_cut_off=_regime_date(entries, "contract_cut_off"),
        legacy_tier=RentalReductionArt232Tier(_regime_text(entries, "legacy_tier")),
        rebaja_threshold=read_parameter(
            modelo_id,
            revision_id,
            "renta-rental-prior-rent-rebaja-threshold",
            date_context=date_context,
            operation=operation,
        ),
        rehabilitation_lookback_years=_whole_years(
            read_parameter(
                modelo_id,
                revision_id,
                "renta-rental-rehab-lookback-years",
                date_context=date_context,
                operation=operation,
            )
        ),
    )


__all__ = [
    "RentalReductionArt232TierCatalogue",
    "RentalReductionArt232TierDefinition",
    "resolve_rental_reduction_art232_rules",
    "resolve_rental_reduction_art232_tier_catalogue",
]
