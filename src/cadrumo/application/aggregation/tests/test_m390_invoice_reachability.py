"""Can an invoice-only bucket reach a filed Modelo 390?

Generalising the invoice-versus-ledger screen to cover every applicable modelo
assumes it can. That assumption is load-bearing: if an invoice-only bucket
could NOT reach a filed M390, adding an M390-scoped invoice-versus-ledger
screen would be guarding a path nobody can walk, and the work adding one would
need re-scoping rather than executing.

The answer is YES, and this module encodes it structurally rather than as prose,
so it reddens if any of the three facts that make it true stops holding.

Three facts, together sufficient:

1. The invoice-versus-ledger screen was scoped to M303 and returned
   immediately for every other modelo, leaving M390 unguarded. **Generalising
   the screen closed that**, and the first assertion below now pins the screen
   as covering M390 rather than skipping it -- this module reddened when the
   gap was closed, which is what encoding the answer as a test is for.
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

from ....core.modelo import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from .._modelo_bindings_invoice_iva import INVOICE_LEDGER_SCREEN_BINDINGS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39393939-3939-4393-8393-393939393939"

_INVOICE_SOURCES = frozenset({"collectible_invoice", "payable_invoice"})


#: The ejercicio these structural assertions read a revision for. They are
#: claims about a revision's DECLARED binding sources, not about any year's
#: figures, so the ejercicio only has to be one AEAT has published: modelo 390's
#: annual design for an ejercicio appears late in that same year, so 2026 is not
#: published yet and 2025 is the latest that is.
_STRUCTURAL_EJERCICIO = 2025


def _revision(modelo_id: str, period: str):
    return bundled_authority().snapshot(modelo_id, filing_year=_STRUCTURAL_EJERCICIO, period=period).revision


def test_the_invoice_versus_ledger_screen_now_covers_m390() -> None:
    """Fact 1, as closed by generalising the screen: M390 is screened, not skipped.

    This assertion is the inverse of the one this module first carried. It
    asserted the screen returned immediately for M390 -- the gap that made the
    reachability answer yes. Closing that gap reddened this test, which is the
    behaviour an encoded answer is supposed to have: the fact changed, so the
    test that stated it failed rather than quietly staying green.

    Asserted against the screened-binding table rather than by calling the
    screen, because what matters is that M390 has an ENTRY -- a screen that ran
    but compared an empty binding set would pass this call and guard nothing.
    """
    assert Modelo.M390.value in INVOICE_LEDGER_SCREEN_BINDINGS
    assert INVOICE_LEDGER_SCREEN_BINDINGS[Modelo.M390.value]


def test_the_two_screened_modelos_cover_the_same_concepts() -> None:
    """One screen, one comparison: the two entries must not drift apart.

    M390 declares the same seven cuota concepts M303 does under its own id
    prefix. Comparing the tables with the prefix stripped is what makes a
    widening applied to one and not the other fail here rather than surface as
    a wrong filing -- which is how the ES-only counterparty filter and the
    missing recargo tiers survived on the M303 side for as long as they did.
    """
    stripped = {
        modelo: sorted(str(binding).removeprefix(f"modelo-{modelo}-").removeprefix("iva-") for binding in bindings)
        for modelo, bindings in INVOICE_LEDGER_SCREEN_BINDINGS.items()
    }

    assert stripped[Modelo.M303.value] == stripped[Modelo.M390.value]


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
