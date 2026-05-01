"""Computation ledger, discrepancy record, and audit-report models."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import AuditDiscrepancyError
from ._codes import FormulaOp


class LedgerEntry(BaseModel):
    """One row in a :class:`ComputationLedger`."""

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
    """Ordered collection of :class:`LedgerEntry` rows for one evaluation."""

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
    """One mismatch between a user-provided and engine-derived value."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: Annotated[str, Field(min_length=2, max_length=5)]
    user_value: Decimal
    computed_value: Decimal
    delta: Decimal
    formula_id: str
    contributing_casillas: tuple[str, ...] = ()
    ruleset_id: str


class AuditReport(BaseModel):
    """Forward ledger plus any discovered discrepancies."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger: ComputationLedger
    discrepancies: tuple[Discrepancy, ...] = ()

    def is_clean(self) -> bool:
        """Return ``True`` when no discrepancies were detected."""
        return not self.discrepancies

    def assert_clean(self) -> None:
        """Raise :class:`AuditDiscrepancyError` when discrepancies exist."""
        if self.discrepancies:
            summary = "; ".join(
                f"{d.casilla_id}: user={d.user_value} computed={d.computed_value}" for d in self.discrepancies
            )
            raise AuditDiscrepancyError(summary)
