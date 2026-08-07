"""Can an invoice-only bucket reach a filed Modelo 390? (P05.S22)

The rest of `P05` assumes it can. That assumption is load-bearing: if an
invoice-only bucket could NOT reach a filed M390, adding an M390-scoped
invoice-versus-ledger screen would be guarding a path nobody can walk, and the
Step that adds one would need re-scoping rather than executing.

The answer is YES, and this module encodes it structurally rather than as prose,
so it reddens if any of the three facts that make it true stops holding.

Three facts, together sufficient:

1. The existing invoice-versus-ledger screen is scoped to M303 and returns
   immediately for every other modelo. There is no M390 equivalent.
2. M390 declares no invoice-sourced binding at all, so a bucket's invoices
   contribute nothing to its values and their absence cannot show up there.
3. Both sides of the `390`-to-`303` reconciliation BLOCKING_RULE root in the
   same transaction ledger. The annual total is a formula over
   `ledger_iva_aggregation` casillas. The reconciliation figures arrive by two
   different wirings -- a `relation_prefill` fold of the quarterly totals, and
   an `iva_compensation_annual_partition` FIFO over the filed M303s -- and both
   originate in filed M303 state, which is itself ledger-derived. Neither
   wiring gives the reconciliation an origin independent of that ledger.

Point 3 is why the blocking rule cannot substitute for a screen. It compares
the ledger against itself, aggregated two ways. That catches a period
attribution error -- a transaction booked into the wrong quarter -- and cannot
catch consistent under-population: a transaction that was never recorded is
absent from both sides equally, so the rule sees zero equals zero and passes
while the bucket's invoices describe real operations.
"""

from __future__ import annotations

import pytest

from ....core import Modelo, Period
from ....core.resources import resources
from .. import CalculationSourceContext
from .._modelo_bindings import _raise_if_m303_invoice_domestic_iva_would_be_silent

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39393939-3939-4393-8393-393939393939"

_INVOICE_SOURCES = frozenset({"collectible_invoice", "payable_invoice"})


def _revision(modelo_id: str, period: str):
    return resources().modelos.authority.snapshot(modelo_id, filing_year=2026, period=period).revision


def test_the_invoice_versus_ledger_screen_does_not_apply_to_m390() -> None:
    """Fact 1: the screen is M303-scoped, so M390 has no equivalent guard.

    Called with an M390 context and no invoice repository at all. The screen
    returns empty before it reaches anything it could fail on, which is the
    early return that makes M390 unguarded rather than an accident of this
    call's arguments.
    """
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M390.value,
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_revision("390", "0A"),
    )

    compared = _raise_if_m303_invoice_domestic_iva_would_be_silent(
        context=context,
        period=Period.from_year_and_code(2026, "0A"),
        transaction_binding_values={},
        invoice_repository=None,
        prorrata_apportionment=None,
    )

    assert compared == ()


def test_m390_declares_no_invoice_sourced_binding() -> None:
    """Fact 2: a bucket's invoices contribute nothing to M390's values.

    So their absence from the ledger cannot surface in M390's own figures --
    there is no invoice-derived number there to disagree with anything.
    """
    revision = _revision("390", "0A")

    invoice_sourced = [binding for binding in revision.bindings if str(binding.source) in _INVOICE_SOURCES]

    assert invoice_sourced == []


def test_both_sides_of_the_390_to_303_reconciliation_root_in_the_ledger() -> None:
    """Fact 3: the blocking rule compares the ledger against itself.

    The reconciliation figure is a relation fold of M303's own total, and M303
    sources that total from the transaction ledger. The annual side is a
    formula over ledger-sourced casillas. Neither side has an independent
    origin, so a transaction that was never recorded is missing from both.

    This is the fact that makes an M390-scoped screen necessary rather than
    redundant, and it is asserted on the registry's declared sources rather
    than on a computed outcome, because the point is structural: no bucket
    fixture could show that the rule is INCAPABLE of detecting something.
    """
    revision = _revision("390", "0A")

    reconciliation = [
        binding for binding in revision.bindings if "prev-303" in str(binding.id) or "reconciliacion" in str(binding.id)
    ]
    assert reconciliation, "the 390 revision must declare the 303 reconciliation fold"
    # Two mechanisms carry these figures, not one: the ordinary totals arrive
    # as a relation fold of the quarterly casillas, and the compensation boxes
    # as an annual FIFO partition over the filed M303s. They are different
    # wirings and the distinction matters -- but BOTH originate in filed M303
    # state, so neither gives the reconciliation an origin independent of the
    # ledger those filings were computed from. That is what the argument needs,
    # and asserting the narrower "all relation_prefill" would be false.
    assert {str(binding.source) for binding in reconciliation} == {
        "relation_prefill",
        "iva_compensation_annual_partition",
    }

    ledger_sourced = [binding for binding in revision.bindings if str(binding.source) == "ledger_iva_aggregation"]
    assert ledger_sourced, "the 390 annual totals must be ledger-sourced for this argument to hold"
