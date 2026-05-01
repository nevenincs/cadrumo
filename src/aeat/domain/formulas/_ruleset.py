"""Ruleset + parameter-table models.

A :class:`Ruleset` is the unit of period-versioned legislation. It
bundles the full casilla set, every computed casilla's formula, the
date-keyed parameter table, and the legal citations grounding the
rules. Structural invariants (DAG acyclicity, casilla/param closure,
single-rounding) are enforced at load time in ``model_post_init``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from graphlib import CycleError, TopologicalSorter
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.errors import (
    AmbiguousPeriodError,
    CasillaNotDefinedError,
    FormulaCycleError,
    MissingRulesetError,
    RulesetValidationError,
)
from ..modelos import LegalCitation, ModeloCode
from ._casilla import CasillaDefinition
from ._formula import (
    Bracket,
    FormulaDefinition,
    iter_casilla_refs,
    iter_param_refs,
)

__all__ = [
    "Bracket",
    "ParameterTable",
    "ParameterValue",
    "Ruleset",
]


class ParameterValue(BaseModel):
    """One date-keyed value for a named ruleset parameter."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    effective_from: date
    effective_to: date | None = None
    value: Decimal

    @model_validator(mode="after")
    def _validate_span(self) -> ParameterValue:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class ParameterTable(BaseModel):
    """Named parameters (rates, thresholds, ...) grouped by id."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    entries: Mapping[str, tuple[ParameterValue, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_entries(self) -> ParameterTable:
        for param_id, values in self.entries.items():
            if not values:
                raise ValueError(f"parameter {param_id!r} has no values")
            ordered = sorted(values, key=lambda v: v.effective_from)
            for idx, current in enumerate(ordered):
                if idx == 0:
                    continue
                previous = ordered[idx - 1]
                if previous.effective_to is None or previous.effective_to >= current.effective_from:
                    raise ValueError(f"parameter {param_id!r} has overlapping spans at {current.effective_from}")
        return self

    def resolve(self, name: str, *, on: date) -> Decimal:
        """Return the parameter value active on the supplied date."""
        if name not in self.entries:
            raise MissingRulesetError(f"parameter {name!r} not declared")
        matches = [
            v for v in self.entries[name] if v.effective_from <= on and (v.effective_to is None or v.effective_to >= on)
        ]
        if not matches:
            raise MissingRulesetError(f"parameter {name!r} has no value on {on.isoformat()}")
        if len(matches) > 1:
            raise AmbiguousPeriodError(f"parameter {name!r} has {len(matches)} overlapping values on {on.isoformat()}")
        return matches[0].value


class Ruleset(BaseModel):
    """A period-versioned formula ruleset for one modelo."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ruleset_id: Annotated[str, Field(min_length=1, max_length=128)]
    modelo: ModeloCode
    variant: Annotated[str, Field(min_length=1, max_length=32)] = "default"
    """Disambiguates partial / alternate / regional encodings of the same
    ``(modelo, period)``. Wave 47 implements the key-axis extension
    committed in ``2026-04-22-ruleset-architecture-adr.md``. Existing
    canonical rulesets (130.2024, 303.2025, etc.) are ``variant="default"``;
    partials (``modelo_100.summary.2025``) and future regional variants
    (``modelo_303.canarias.2025``) carry their own variant slug.
    """
    effective_from: date
    effective_to: date | None = None
    casillas: tuple[CasillaDefinition, ...] = Field(min_length=1)
    formulas: tuple[FormulaDefinition, ...] = ()
    parameters: ParameterTable = ParameterTable()
    legal_citations: tuple[LegalCitation, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> Ruleset:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise RulesetValidationError(f"ruleset {self.ruleset_id!r}: effective_to precedes effective_from")

        casilla_ids: set[str] = set()
        for casilla in self.casillas:
            if casilla.casilla_id in casilla_ids:
                raise RulesetValidationError(f"ruleset {self.ruleset_id!r}: duplicate casilla {casilla.casilla_id!r}")
            casilla_ids.add(casilla.casilla_id)

        computed_ids = {c.casilla_id for c in self.casillas if c.computed}
        formula_ids: set[str] = set()
        formula_by_casilla: dict[str, FormulaDefinition] = {}

        for formula_def in self.formulas:
            if formula_def.casilla_id not in casilla_ids:
                raise CasillaNotDefinedError(
                    f"ruleset {self.ruleset_id!r}: formula references undeclared casilla {formula_def.casilla_id!r}"
                )
            if formula_def.casilla_id not in computed_ids:
                raise RulesetValidationError(
                    f"ruleset {self.ruleset_id!r}: formula bound to non-computed casilla {formula_def.casilla_id!r}"
                )
            if formula_def.casilla_id in formula_by_casilla:
                raise RulesetValidationError(
                    f"ruleset {self.ruleset_id!r}: duplicate formula for casilla {formula_def.casilla_id!r}"
                )
            if formula_def.formula_id in formula_ids:
                raise RulesetValidationError(
                    f"ruleset {self.ruleset_id!r}: duplicate formula_id {formula_def.formula_id!r}"
                )
            formula_ids.add(formula_def.formula_id)
            formula_by_casilla[formula_def.casilla_id] = formula_def

            for ref in iter_casilla_refs(formula_def.formula):
                if ref not in casilla_ids:
                    raise CasillaNotDefinedError(
                        f"ruleset {self.ruleset_id!r}: formula {formula_def.formula_id!r} "
                        f"references undeclared casilla {ref!r}"
                    )
            for param_ref in iter_param_refs(formula_def.formula):
                if param_ref not in self.parameters.entries:
                    raise RulesetValidationError(
                        f"ruleset {self.ruleset_id!r}: formula {formula_def.formula_id!r} "
                        f"references undeclared parameter {param_ref!r}"
                    )

        missing_formulas = computed_ids - formula_by_casilla.keys()
        if missing_formulas:
            raise RulesetValidationError(
                f"ruleset {self.ruleset_id!r}: computed casillas without formulas: {sorted(missing_formulas)!r}"
            )

        ts: TopologicalSorter[str] = TopologicalSorter()
        for casilla in self.casillas:
            ts.add(casilla.casilla_id)
        for formula_def in self.formulas:
            refs = iter_casilla_refs(formula_def.formula)
            ts.add(formula_def.casilla_id, *refs)
        try:
            ts.prepare()
        except CycleError as exc:
            cycle = tuple(str(node) for node in exc.args[1])
            raise FormulaCycleError(ruleset_id=self.ruleset_id, cycle=cycle) from exc

        return self

    def covers(self, period_start: date, period_end: date) -> bool:
        """Return ``True`` when the ruleset span covers the entire period."""
        if period_start < self.effective_from:
            return False
        return not (self.effective_to is not None and period_end > self.effective_to)

    def formula_for(self, casilla_id: str) -> FormulaDefinition | None:
        """Return the formula binding for a casilla id, or ``None``."""
        for formula_def in self.formulas:
            if formula_def.casilla_id == casilla_id:
                return formula_def
        return None

    def casilla(self, casilla_id: str) -> CasillaDefinition:
        """Return the casilla definition for ``casilla_id``."""
        for casilla in self.casillas:
            if casilla.casilla_id == casilla_id:
                return casilla
        raise CasillaNotDefinedError(f"ruleset {self.ruleset_id!r} does not declare casilla {casilla_id!r}")

    def evaluation_order(self) -> tuple[str, ...]:
        """Return the deterministic topological evaluation order."""
        ts: TopologicalSorter[str] = TopologicalSorter()
        for casilla in self.casillas:
            ts.add(casilla.casilla_id)
        for formula_def in self.formulas:
            refs = iter_casilla_refs(formula_def.formula)
            ts.add(formula_def.casilla_id, *refs)
        return tuple(ts.static_order())
