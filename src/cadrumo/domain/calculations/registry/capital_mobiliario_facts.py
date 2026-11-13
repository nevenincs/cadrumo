"""Typed projections for the capital-mobiliario concept vocabulary and withholding rate.

The vocabulary (fact 0187) says which Modelo 100 detail record a capital-mobiliario
ledger concept feeds; the rate (fact 0188) is the governed withholding percentage on
that income. Neither the tokens, the record names nor the rate is held in Python.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final

from ....core.concepto_capital_mobiliario import ConceptoCapitalMobiliario
from .errors import RegistryValidationError
from .facts.resolution import (
    ResolvedScalarFact,
    ScalarFactQuery,
    required_mapping_entry,
    unique_mapping_tokens,
)
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

_SUBJECT: Final = "capital-mobiliario concept vocabulary"
_FACT_ID: Final = "capital-mobiliario-concept-vocabulary"
_ORDER_KEY: Final = "catalogue.ids"
_PREFIX: Final = "concept."

_RATE_SUBJECT: Final = "capital-mobiliario withholding rate"
_RATE_FACT_ID: Final = "capital-mobiliario-withholding-rate"
_RATE_UNIT: Final = "fraction"

_VOCABULARY_FACT = StringMappingFact(
    fact_id=_FACT_ID,
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(subject=_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE),
)


class CapitalMobiliarioAmountRole(StrEnum):
    """What a linked row's amount is on its detail record, as the vocabulary declares it."""

    GROSS_INCOME = "gross_income"
    """Net cash credited, from which the record's gross is rebuilt with the payer's withholding."""
    DEDUCTIBLE_EXPENSE = "deductible_expense"
    """An expense the record carries beside its gross and withholding."""


def _amount_role(entries: Mapping[str, str], key: str) -> CapitalMobiliarioAmountRole:
    raw = required_mapping_entry(entries, key, subject=_SUBJECT)
    try:
        return CapitalMobiliarioAmountRole(raw)
    except ValueError as error:
        raise RegistryValidationError(f"{_SUBJECT} entry {key!r} names an unknown amount role {raw!r}") from error


@dataclass(frozen=True, slots=True)
class CapitalMobiliarioConcept:
    """One ledger concept and the Modelo 100 detail record it feeds."""

    token: str
    detail_record: str
    amount_element: str
    casilla_semantic_role: str
    requires_position_kind: str | None
    amount_role: CapitalMobiliarioAmountRole


@dataclass(frozen=True, slots=True)
class CapitalMobiliarioConceptCatalogue:
    """The declared concepts in their registry order."""

    concepts: tuple[CapitalMobiliarioConcept, ...]

    @property
    def tokens(self) -> tuple[str, ...]:
        """Return the declared concept tokens in order."""
        return tuple(item.token for item in self.concepts)

    def require(self, value: object) -> CapitalMobiliarioConcept:
        """Return the declaration of one concept or refuse an unknown token."""
        if not isinstance(value, str) or not value.strip():
            raise RegistryValidationError(f"{_SUBJECT} token must be a non-empty string")
        token = value.strip()
        for item in self.concepts:
            if item.token == token:
                return item
        raise RegistryValidationError(f"{_SUBJECT} token {token!r} is not declared by fact {_FACT_ID!r}")


def resolve_capital_mobiliario_concept_vocabulary(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> CapitalMobiliarioConceptCatalogue:
    """Resolve the concept vocabulary from fact 0187."""
    entries = _VOCABULARY_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    concepts: list[CapitalMobiliarioConcept] = []
    for token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_SUBJECT):
        prefix = f"{_PREFIX}{token}."
        position_kind = entries.get(f"{prefix}requires_position_kind", "").strip()
        concepts.append(
            CapitalMobiliarioConcept(
                token=token,
                detail_record=required_mapping_entry(entries, f"{prefix}detail_record", subject=_SUBJECT),
                amount_element=required_mapping_entry(entries, f"{prefix}amount_element", subject=_SUBJECT),
                casilla_semantic_role=required_mapping_entry(
                    entries, f"{prefix}casilla_semantic_role", subject=_SUBJECT
                ),
                requires_position_kind=position_kind or None,
                amount_role=_amount_role(entries, f"{prefix}amount_role"),
            ),
        )
    return CapitalMobiliarioConceptCatalogue(concepts=tuple(concepts))


def require_concepto_capital_mobiliario(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ConceptoCapitalMobiliario:
    """Project one concept token from the selected dated vocabulary, refusing an undeclared one."""
    catalogue = resolve_capital_mobiliario_concept_vocabulary(effective_date=effective_date, authority=authority)
    return ConceptoCapitalMobiliario.from_registry(catalogue.require(value).token)


def resolve_capital_mobiliario_withholding_rate(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> Decimal:
    """Return the governed withholding rate on rendimientos del capital mobiliario.

    Raises:
        InternalInvariantError: When no authority is supplied and no scope is active.
        RegistryValidationError: When the fact does not resolve to a fraction in (0, 1).
    """
    selected = require_governed_fact_authority(authority, subject=_RATE_SUBJECT)
    resolved = selected.resolve_governed_fact(
        ScalarFactQuery(fact_id=_RATE_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date)
    )
    if not isinstance(resolved, ResolvedScalarFact) or resolved.payload.unit != _RATE_UNIT:
        raise RegistryValidationError(f"{_RATE_SUBJECT} must resolve as a scalar {_RATE_UNIT}")
    value = resolved.payload.value
    if not isinstance(value, Decimal) or not Decimal(0) < value < Decimal(1):
        raise RegistryValidationError(f"{_RATE_SUBJECT} must be a decimal fraction between zero and one")
    return value


__all__ = [
    "CapitalMobiliarioAmountRole",
    "CapitalMobiliarioConcept",
    "CapitalMobiliarioConceptCatalogue",
    "require_concepto_capital_mobiliario",
    "resolve_capital_mobiliario_concept_vocabulary",
    "resolve_capital_mobiliario_withholding_rate",
]
