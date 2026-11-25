"""Scenario bodies for test_unrouted_renta_quantity_screen, called by its authored-source and published-authority tests."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from .....core.aggregation import LedgerIncomeGrounding, LedgerWithholdingDerivation
from ..ledger_renta_income_bindings import (
    unrouted_ledger_renta_income_quantities,
    unsupported_ledger_renta_income_observations,
)
from ..schema import ModeloRevision


class Row:
    """Minimal ``RentaIncomeObservationProtocol`` instance.

    Hand-rolled per-site rather than shared: every screen test in this package
    builds its own, which keeps each test's substrate visible at the assertion
    instead of behind a fixture that later grows fields nobody here reads.
    """

    def __init__(self, *, gross: str, withheld: str, base: str | None = None) -> None:
        self.transaction_id = f"tx-{gross}-{withheld}"
        self.target_casilla_id = "01"
        self.gross_amount = Decimal(gross)
        self.withheld_amount = Decimal(withheld)
        self.taxable_base_amount = None if base is None else Decimal(base)
        # Derived from the base exactly as the real projection derives it: a
        # declared taxable base is substrate, its absence leaves only the raw
        # bank-credited figure. Hard-coding one member instead would let a row
        # claim substrate it does not carry.
        self.grounding = (
            LedgerIncomeGrounding.CASH_FALLBACK if base is None else LedgerIncomeGrounding.SUBSTRATE_DECLARED
        )
        # Derived from the same substrate, for the same reason: no base leaves
        # the retencion undeterminable rather than absent, and a figure a base
        # made determinable was reconstructed rather than read off a document.
        # This screen reads the quantity whatever its marker, so the marker is
        # here to keep the row a legitimate observation, not to steer the result.
        if base is None:
            self.withheld_derivation = LedgerWithholdingDerivation.NO_SUBSTRATE
        elif self.withheld_amount == Decimal("0"):
            self.withheld_derivation = LedgerWithholdingDerivation.NONE_WITHHELD
        else:
            self.withheld_derivation = LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA


def revision_without_fact(revision: ModeloRevision, fact: str) -> ModeloRevision:
    """Return ``revision`` with every binding drawing ``fact`` removed.

    Models the regression under test: a revision that never declared the
    retenciones binding, or one from which it was dropped.
    """
    kept = [
        binding
        for binding in revision.bindings
        if not (
            binding.source.value == "ledger_renta_income_aggregation"
            and getattr(binding.provider, "fact", None) == fact
        )
    ]
    return revision.model_copy(update={"bindings": tuple(kept)})


def check_the_committed_revision_draws_every_quantity_its_rows_carry(
    modelo_130_revision: Callable[[], ModeloRevision],
) -> None:
    """The real M130 revision routes both income and retención -- no advisory."""
    revision = modelo_130_revision()
    rows = [Row(gross="1000.00", withheld="150.00", base="1000.00")]

    assert unrouted_ledger_renta_income_quantities(revision, rows) == ()


def check_a_dropped_retenciones_binding_is_surfaced(modelo_130_revision: Callable[[], ModeloRevision]) -> None:
    """Removing the retenciones binding surfaces the whole suffered credit."""
    revision = revision_without_fact(modelo_130_revision(), "declared_withheld_amount_sum")
    rows = [
        Row(gross="1000.00", withheld="150.00", base="1000.00"),
        Row(gross="2000.00", withheld="300.00", base="2000.00"),
    ]

    unrouted = unrouted_ledger_renta_income_quantities(revision, rows)

    assert len(unrouted) == 1
    assert unrouted[0].fact == "declared_withheld_amount_sum"
    assert unrouted[0].total == Decimal("450.00")
    assert len(unrouted[0].observations) == 2


def check_the_row_screen_stays_silent_on_the_same_defect(modelo_130_revision: Callable[[], ModeloRevision]) -> None:
    """The blindness this screen exists for, proved rather than asserted.

    Same revision and rows as the test above. The row screen reports nothing,
    because both rows are still consumed by the income bindings on
    ``target_casilla_id = "01"`` -- so without the quantity screen the dropped
    retención has a clean screen on both sides.
    """
    revision = revision_without_fact(modelo_130_revision(), "declared_withheld_amount_sum")
    rows = [Row(gross="1000.00", withheld="150.00", base="1000.00")]

    assert unsupported_ledger_renta_income_observations(revision, rows) == ()
    assert unrouted_ledger_renta_income_quantities(revision, rows) != ()


def check_a_taxpayer_who_suffered_no_retencion_raises_nothing(
    modelo_130_revision: Callable[[], ModeloRevision],
) -> None:
    """A legitimate zero is not a modelling gap.

    Anti-false-fire control: the binding is absent AND the rows carry no
    retención, so there is no dropped quantity to report. Without this the
    screen could fire on every taxpayer who is simply not subject to
    withholding.
    """
    revision = revision_without_fact(modelo_130_revision(), "declared_withheld_amount_sum")
    rows = [Row(gross="1000.00", withheld="0.00", base="1000.00")]

    assert unrouted_ledger_renta_income_quantities(revision, rows) == ()


def check_an_omitted_alternative_income_measure_raises_nothing(
    modelo_130_revision: Callable[[], ModeloRevision], fact: str
) -> None:
    """Dropping one income measure is a modelling choice, not a lost quantity.

    A revision picks one measure of income; the other two are deliberately
    omitted. Screening them would fire on every revision and train the operator
    to ignore the advisory, so only genuinely independent quantities qualify.
    """
    revision = revision_without_fact(modelo_130_revision(), fact)
    rows = [Row(gross="1000.00", withheld="150.00", base="1000.00")]

    assert unrouted_ledger_renta_income_quantities(revision, rows) == ()


def check_the_screen_reads_the_revision_it_is_given(modelo_130_revision: Callable[[], ModeloRevision]) -> None:
    """Guards against a screen that ignores its revision argument.

    An implementation hardcoding "M130 draws declared_withheld_amount_sum" would pass
    every test above. This one fails it: the same rows must report differently
    against a revision that draws the fact and one that does not.
    """
    committed = modelo_130_revision()
    stripped = revision_without_fact(committed, "declared_withheld_amount_sum")
    rows = [Row(gross="1000.00", withheld="150.00", base="1000.00")]

    assert unrouted_ledger_renta_income_quantities(committed, rows) == ()
    assert unrouted_ledger_renta_income_quantities(stripped, rows) != ()
