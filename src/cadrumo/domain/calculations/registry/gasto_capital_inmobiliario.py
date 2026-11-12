"""Typed projection of the governed rental-expense concept vocabulary.

The vocabulary and the Modelo 100 casilla each concept feeds live in one mapping
fact, so a ledger row, the aggregation and the export read one owner. A concept
that capitalises (an improvement) is marked as such and is never an expense. A
concept whose deduction the law limits to the property's gross income (LIRPF
art. 23.1.a.1.º: financing interest and repair and conservation) is marked as
limited, so the limit reads the vocabulary rather than a list of boxes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ....core.gasto_capital_inmobiliario import GastoCapitalInmobiliario
from .errors import RegistryValidationError
from .facts.envelope_editions import resolve_support_envelope_editions
from .facts.resolution import MappingFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

_FACT_ID = "renta-capital-inmobiliario-gasto-concept-vocabulary"
_ORDER_KEY = "concept_order"
_TREATMENT_EXPENSE = "expense"
_TREATMENT_LIMITED = "expense_limited"
_TREATMENT_CAPITALISED = "capitalised"


@dataclass(frozen=True, slots=True)
class GastoCapitalInmobiliarioConcept:
    """One declared concept with the casilla it feeds and its treatment."""

    token: GastoCapitalInmobiliario
    casilla_id: str
    capitalised: bool
    limited: bool = False
    """Whether the deduction shares the art. 23.1.a.1.º limit of the property's gross income."""


@dataclass(frozen=True, slots=True)
class GastoCapitalInmobiliarioCatalogue:
    """Registry-declared rental-expense concepts for transaction boundaries."""

    concepts: tuple[GastoCapitalInmobiliarioConcept, ...]

    @property
    def all_tokens(self) -> frozenset[GastoCapitalInmobiliario]:
        """Return every declared concept token."""
        return frozenset(concept.token for concept in self.concepts)

    def require(self, value: object) -> GastoCapitalInmobiliario:
        """Return one token only when the selected fact declares it."""
        if isinstance(value, GastoCapitalInmobiliario):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("rental-expense concept token must be non-empty")
            token = GastoCapitalInmobiliario.from_registry(raw)
        else:
            raise RegistryValidationError("rental-expense concept token must be a string token")
        if token not in self.all_tokens:
            raise RegistryValidationError(
                f"rental-expense concept token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def concept_for(self, value: object) -> GastoCapitalInmobiliarioConcept:
        """Return the declared concept for ``value``, refusing an undeclared token."""
        token = self.require(value)
        return next(concept for concept in self.concepts if concept.token == token)


def _entry_text(entries: dict[str, object], key: str) -> str:
    value = entries.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(f"rental-expense concept fact {_FACT_ID!r} has no text entry {key!r}")
    return value.strip()


def _vocabulary_query(effective_date: date) -> MappingFactQuery:
    return MappingFactQuery(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date)


def _edition_entries(resolved: ResolvedGovernedFact) -> dict[str, object]:
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("rental-expense concept vocabulary must resolve as a mapping fact")
    return {str(entry.key): entry.value for entry in resolved.payload.entries}


def _catalogue(entries: dict[str, object]) -> GastoCapitalInmobiliarioCatalogue:
    names = tuple(name.strip() for name in _entry_text(entries, _ORDER_KEY).split(","))
    if not names or len(names) != len(set(names)) or any(not name for name in names):
        raise RegistryValidationError("rental-expense concept vocabulary must contain unique non-empty tokens")
    concepts: list[GastoCapitalInmobiliarioConcept] = []
    for name in names:
        treatment = _entry_text(entries, f"concept.{name}.treatment")
        if treatment not in {_TREATMENT_EXPENSE, _TREATMENT_LIMITED, _TREATMENT_CAPITALISED}:
            raise RegistryValidationError(
                f"rental-expense concept {name!r} declares unknown treatment {treatment!r}",
            )
        concepts.append(
            GastoCapitalInmobiliarioConcept(
                token=GastoCapitalInmobiliario.from_registry(name),
                casilla_id=_entry_text(entries, f"concept.{name}.casilla"),
                capitalised=treatment == _TREATMENT_CAPITALISED,
                limited=treatment == _TREATMENT_LIMITED,
            ),
        )
    return GastoCapitalInmobiliarioCatalogue(concepts=tuple(concepts))


def resolve_gasto_capital_inmobiliario_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> GastoCapitalInmobiliarioCatalogue:
    """Resolve the rental-expense concept vocabulary.

    A dated read takes the vocabulary in force on ``effective_date``. Without a
    date the run date is never substituted: the entries of every edition inside
    the supported filing years are merged, oldest first, so a concept any
    edition declares is admitted and where editions differ the newest edition's
    order, casilla and treatment stand. A caller that decides where an expense
    is declared for a period supplies that period's date.
    """
    selected = require_governed_fact_authority(authority, subject="rental-expense concept catalogue")
    if effective_date is not None:
        return _catalogue(_edition_entries(selected.resolve_governed_fact(_vocabulary_query(effective_date))))
    editions = resolve_support_envelope_editions(selected, _vocabulary_query)
    if not editions:
        raise RegistryValidationError(
            "rental-expense concept vocabulary authors no edition inside the supported filing years"
        )
    merged: dict[str, object] = {}
    for resolved in editions:
        merged.update(_edition_entries(resolved))
    return _catalogue(merged)


def require_gasto_capital_inmobiliario(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> GastoCapitalInmobiliario:
    """Project one rental-expense concept token from the selected facts authority."""
    return resolve_gasto_capital_inmobiliario_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "GastoCapitalInmobiliarioCatalogue",
    "GastoCapitalInmobiliarioConcept",
    "require_gasto_capital_inmobiliario",
    "resolve_gasto_capital_inmobiliario_catalogue",
]
