"""Computation ledger, discrepancy record, and audit-report models.

The ledger is the engine's only output channel: every derivation produces a
:class:`ComputationLedger` of :class:`LedgerEntry` rows, and every audit
produces an :class:`AuditReport` carrying that ledger plus zero or more
:class:`Discrepancy` rows. All four types are strict, frozen pydantic v2
models so they round-trip cleanly to JSON for offline verification.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import AuditDiscrepancyError
from ._codes import FormulaOp


class LedgerEntry(BaseModel):
    """One row in a :class:`ComputationLedger`.

    Attributes:
        casilla_id: The computed casilla this row stores.
        value: The derived :class:`decimal.Decimal` value.
        op: The :class:`aeat.domain.formulas.FormulaOp` used at the
            outermost node of the formula tree.
        formula_id: The stable id of the
            :class:`aeat.domain.formulas.FormulaDefinition` applied.
        operand_refs: Casilla ids referenced by the formula tree (in
            traversal order).
        operand_values: Values for each entry in :attr:`operand_refs`.
        ruleset_id: Identifier of the
            :class:`aeat.domain.formulas.Ruleset` that produced this row.
        notes: Optional free-form annotation; never consumed by the
            engine.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: Annotated[str, Field(min_length=2, max_length=5)]
    value: Decimal
    op: FormulaOp
    formula_id: str
    operand_refs: tuple[str, ...] = ()
    operand_values: tuple[Decimal, ...] = ()
    ruleset_id: str
    notes: str = ""


class ComputationLedger(BaseModel):
    """Ordered collection of :class:`LedgerEntry` rows for one evaluation.

    Attributes:
        ruleset_id: Identifier of the
            :class:`aeat.domain.formulas.Ruleset` that produced the
            ledger.
        entries: Tuple of :class:`LedgerEntry`, ordered by topological
            evaluation.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ruleset_id: str
    entries: tuple[LedgerEntry, ...] = ()

    def value(self, casilla_id: str) -> Decimal | None:
        """Return the derived value for ``casilla_id`` or ``None`` if absent."""
        for entry in self.entries:
            if entry.casilla_id == casilla_id:
                return entry.value
        return None


class Discrepancy(BaseModel):
    """One mismatch between a user-provided and engine-derived value.

    Attributes:
        casilla_id: The casilla where the mismatch surfaced.
        user_value: The caller-supplied :class:`decimal.Decimal`.
        computed_value: The engine-derived :class:`decimal.Decimal`.
        delta: ``user_value - computed_value`` (signed).
        formula_id: The formula whose evaluation produced
            ``computed_value``.
        contributing_casillas: Upstream casilla ids the formula
            referenced.
        ruleset_id: Identifier of the
            :class:`aeat.domain.formulas.Ruleset`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: Annotated[str, Field(min_length=2, max_length=5)]
    user_value: Decimal
    computed_value: Decimal
    delta: Decimal
    formula_id: str
    contributing_casillas: tuple[str, ...] = ()
    ruleset_id: str


class AuditReport(BaseModel):
    """Forward ledger plus any discovered discrepancies.

    Attributes:
        ledger: The :class:`ComputationLedger` produced from
            ``provided``'s user inputs.
        discrepancies: Tuple of :class:`Discrepancy` rows, one per
            casilla where the caller's value diverged from the engine's
            derivation beyond tolerance.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger: ComputationLedger
    discrepancies: tuple[Discrepancy, ...] = ()

    def is_clean(self) -> bool:
        """Return ``True`` when no discrepancies were detected."""
        return not self.discrepancies

    def assert_clean(self) -> None:
        """Raise :exc:`aeat.core.errors.AuditDiscrepancyError` when discrepancies exist."""
        if self.discrepancies:
            summary = "; ".join(
                f"{d.casilla_id}: user={d.user_value} computed={d.computed_value}" for d in self.discrepancies
            )
            raise AuditDiscrepancyError(summary)
