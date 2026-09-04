"""Pure carry-forward logic for bases imponibles negativas (Modelo 200).

This module owns the typed per-cohort stock record for losses a company
carries between exercises, and the shape rules the Modelo 200 detalle cuadro
imposes on it. All logic here is pure: it depends only on :mod:`decimal`,
pydantic, and :data:`STRICT_FROZEN_CONFIG` from :mod:`cadrumo.core`.
Persistence, registry resolution, and the arithmetic that applies stock
against a period's base imponible live outside this module.

Two regulatory facts shape the records below, both from Ley 27/2014 art. 26:

* **Carry-forward is indefinite.** Art. 26.1 permits compensation against
  ``las rentas positivas de los períodos impositivos siguientes`` with no term.
  There is deliberately no expiry field on a cohort. The ten-year period in
  art. 26.5 is the Administration's window to *inspect* a compensated loss, not
  a limit on the right to compensate it, and it is modelled nowhere here.
* **A current-period loss cannot be applied against its own period.** Art. 26.1
  compensates losses ``procedentes de períodos anteriores``, so the cohort whose
  generation year is the filing year carries no ``aplicado`` leg at all. The
  official cuadro reflects this: that one cohort has two legs where every other
  has three.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .errors import BinCohortShapeError

_ZERO = Decimal("0")


class BinCohortStock(BaseModel):
    """One generation year's stock of base imponible negativa.

    ``generation_year`` is the exercise in which the loss arose, and is the
    cohort key in the Modelo 200 detalle cuadro. The three amounts are the
    cuadro's three legs, in its own order: what was pending at the start of the
    period, what is applied in this liquidación, and what remains pending for
    future periods.

    ``applied_amount`` is ``None`` — not zero — for the cohort generated in the
    filing year itself, because art. 26.1 forbids applying it. ``None`` here
    means *legally not applicable*; a genuine decision to apply nothing is
    ``Decimal("0")``. Collapsing the two would let a forbidden value reach
    casilla ``[00547]`` and change the tax.
    """

    model_config = _STRICT_FROZEN

    generation_year: FilingYear
    pending_opening_amount: Decimal = Field(ge=_ZERO)
    applied_amount: Decimal | None = Field(default=None, ge=_ZERO)
    pending_future_amount: Decimal = Field(ge=_ZERO)

    @property
    def is_current_period_cohort(self) -> bool:
        """Whether this cohort carries no ``aplicado`` leg."""
        return self.applied_amount is None

    @model_validator(mode="after")
    def _legs_balance(self) -> BinCohortStock:
        applied = _ZERO if self.applied_amount is None else self.applied_amount
        if applied + self.pending_future_amount != self.pending_opening_amount:
            raise BinCohortShapeError(
                "applied_amount + pending_future_amount must equal pending_opening_amount"
            )
        return self


class BinStock(BaseModel):
    """A filer's whole base-imponible-negativa position for one filing year.

    Cohorts are held by generation year and are unique on it. The cohort whose
    generation year equals ``filing_year`` is the current-period one and is the
    only cohort permitted to omit its ``aplicado`` leg; any other cohort
    omitting it, or that cohort carrying it, is refused.
    """

    model_config = _STRICT_FROZEN

    filing_year: FilingYear
    cohorts: tuple[BinCohortStock, ...]

    @model_validator(mode="after")
    def _cohort_shapes(self) -> BinStock:
        years = [c.generation_year for c in self.cohorts]
        if len(set(years)) != len(years):
            raise BinCohortShapeError("cohorts must be unique on generation_year")
        for cohort in self.cohorts:
            if cohort.generation_year > self.filing_year:
                raise BinCohortShapeError(
                    "a cohort cannot be generated after the filing year"
                )
            is_current = cohort.generation_year == self.filing_year
            if is_current and cohort.applied_amount is not None:
                raise BinCohortShapeError(
                    "the current-period cohort cannot carry an applied_amount "
                    "(LIS art. 26.1 compensates only losses from earlier periods)"
                )
            if not is_current and cohort.applied_amount is None:
                raise BinCohortShapeError(
                    "a prior-period cohort must state its applied_amount, "
                    "using Decimal('0') where nothing was applied"
                )
        return self

    @property
    def total_applied_amount(self) -> Decimal:
        """The sum reported in the cuadro's TOTAL ``aplicado`` leg."""
        return sum(
            (c.applied_amount for c in self.cohorts if c.applied_amount is not None),
            _ZERO,
        )

    @property
    def total_pending_future_amount(self) -> Decimal:
        """The sum reported in the cuadro's TOTAL ``pendiente futuro`` leg."""
        return sum((c.pending_future_amount for c in self.cohorts), _ZERO)

    @property
    def total_pending_opening_amount(self) -> Decimal:
        """The sum reported in the cuadro's TOTAL opening leg."""
        return sum((c.pending_opening_amount for c in self.cohorts), _ZERO)
