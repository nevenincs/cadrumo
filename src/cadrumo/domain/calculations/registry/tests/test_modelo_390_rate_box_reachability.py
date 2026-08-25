"""Production-shaped invoice lines reach every Modelo 390 rate box.

The sibling rate-box tests build :class:`IvaLedgerObservation` rows by hand,
setting ``category``, ``rate_kind`` and ``applied_rate`` directly. Those are the
three fields the classification path is meant to DECIDE, so a hand-built fixture
asserting ``rate_kind=REDUCED`` beside ``applied_rate=0.075`` proves the binding
selectors work over that combination without proving the combination is one
production ever emits. A box that no real invoice line can reach is dormant
capacity wearing a passing test.

This module closes that gap by supplying only what an operator supplies — an
``IvaRate`` slot, a date and two amounts — and letting
``invoice_line_to_iva_observation`` derive the classification triple. Every
assertion below is therefore about a row the ledger→modelo bridge actually
produces.

The bridge is the canonical path for standard-case domestic IVA, and it refuses
a transitional food slot used outside its statutory window rather than recording
it at whatever the tier meant that day. That refusal is exercised here as the
positive control: if it did not fire, the in-window passes would carry far less
weight, because any date would do and the window would be decorative.

Real-behaviour: the committed revision through the real registry authority, the
real classification bridge, and the real ``ledger_iva_aggregation`` resolver. No
mocks, stubs, skips or xfail.

Non-tautology: every base and cuota is distinct across tiers and no cuota is the
base multiplied by its rate, so a resolver that leaked a neighbouring rate or
returned base for cuota fails on value. The 0 % cuota is zero by definition
rather than by arithmetic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .....core.resources import resources
from ....invoices import IvaRate
from ....iva import (
    InvoiceKind,
    IvaCategory,
    IvaRateKind,
    IvaRateNotFoundError,
    invoice_line_to_iva_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# slot, a date inside the slot's statutory window, box suffix, base, cuota.
# Only 21 %, 10 % and 4 % run the whole year. Under RDL 4/2024 art. 1, 5 % and
# 0 % apply 1 Jul - 30 Sep 2024 and 7,5 % and 2 % from 1 Oct, so each windowed
# slot is exercised on a day it was actually in force.
#
# The 0 % row is deliberately dated inside July-September rather than in Q1. The
# zero window was corrected to the span the bundled corpus actually supports, and
# a Q1 date now refuses at the bridge. That refusal is the CORRECT behaviour and
# this fixture follows the law rather than pinning the date it used to accept.
_LINES = (
    (IvaRate.RATE_21, date(2024, 3, 10), "21", "4000.00", "817.00"),
    (IvaRate.RATE_10, date(2024, 3, 11), "10", "2500.00", "241.00"),
    (IvaRate.RATE_7_5, date(2024, 11, 12), "7-5", "1600.00", "127.00"),
    (IvaRate.RATE_5, date(2024, 8, 13), "5", "1400.00", "73.00"),
    (IvaRate.RATE_4, date(2024, 3, 14), "4", "1200.00", "51.00"),
    (IvaRate.RATE_2, date(2024, 11, 15), "2", "900.00", "19.00"),
    (IvaRate.RATE_0, date(2024, 8, 16), "0", "700.00", "0.00"),
)

# The rate each slot must resolve to, and the tier the classifier must pick. The
# tiers are deliberately NOT one-to-one with the rates: 10/7,5/5 all classify
# REDUCED and 4/2 both classify SUPER_REDUCED, which is precisely why a per-tier
# casilla cannot serve a per-rate box.
_EXPECTED_CLASSIFICATION = {
    "21": (Decimal("0.21"), IvaRateKind.GENERAL, IvaCategory.DOMESTIC_GENERAL),
    "10": (Decimal("0.10"), IvaRateKind.REDUCED, IvaCategory.DOMESTIC_REDUCED),
    "7-5": (Decimal("0.075"), IvaRateKind.REDUCED, IvaCategory.DOMESTIC_REDUCED),
    "5": (Decimal("0.05"), IvaRateKind.REDUCED, IvaCategory.DOMESTIC_REDUCED),
    "4": (Decimal("0.04"), IvaRateKind.SUPER_REDUCED, IvaCategory.DOMESTIC_SUPER_REDUCED),
    "2": (Decimal("0.02"), IvaRateKind.SUPER_REDUCED, IvaCategory.DOMESTIC_SUPER_REDUCED),
    "0": (Decimal("0"), IvaRateKind.ZERO, IvaCategory.DOMESTIC_ZERO),
}

# A transitional slot paired with a date OUTSIDE its statutory window.
_OUT_OF_WINDOW = (
    (IvaRate.RATE_7_5, date(2024, 3, 10)),
    (IvaRate.RATE_5, date(2024, 11, 12)),
    (IvaRate.RATE_2, date(2024, 8, 13)),
)

# RATE_0 is deliberately ABSENT from the set above, and must stay absent. It is
# the one slot exempted from the in-force check, because the registry's zero
# authority is knowingly incomplete: rates.toml registers only the RD-ley 4/2024
# window and deliberately does NOT register the indefinite art. 91.Cuatro 0 %
# (entregas de donativos), since a flat `kind = "zero"` record cannot express a
# tipo bounded to donativos and an open one would apply 0 % to every domestic
# supply. A missing zero record therefore means "this registry cannot say", not
# "no zero-rated supply was lawful that day", and refusing on it made every
# zero-rated invoice unrecordable at every date.
#
# Adding RATE_0 here looks like tightening a gap and is actually asserting a
# refusal the code intentionally does not perform.


def _m390_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("390", filing_year=2024, period="0A").revision


def _issued_lines() -> tuple[IvaLedgerObservation, ...]:
    """Observations built the way production builds them, from operator inputs only."""
    return tuple(
        invoice_line_to_iva_observation(
            invoice_id=f"inv-m390-{suffix}",
            issued_at=on,
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=slot,
            base_amount=Decimal(base),
            iva_amount=Decimal(cuota),
            deduction_fact_kind=None,
            deduction_provenance=None,
        )
        for slot, on, suffix, base, cuota in _LINES
    )


def _resolved() -> dict[str, Decimal]:
    return dict(resolve_ledger_iva_aggregation_binding_values(_m390_revision(), _issued_lines()))


@pytest.mark.parametrize(("suffix", "base", "cuota"), tuple((t[2], t[3], t[4]) for t in _LINES))
def test_a_production_built_line_reaches_its_official_rate_box(
    suffix: str,
    base: str,
    cuota: str,
) -> None:
    """Each rate box is reachable from an invoice line, not merely from a fixture.

    The test supplies an ``IvaRate`` slot and a date; the classification triple
    that the selectors match on is derived by the production bridge. A box that
    only a hand-built observation could reach would fail here.
    """
    resolved = _resolved()
    assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-base"] == Decimal(base)
    assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-cuota"] == Decimal(cuota)


@pytest.mark.parametrize(("slot", "on", "suffix"), tuple((t[0], t[1], t[2]) for t in _LINES))
def test_the_bridge_decides_the_classification_the_selectors_match_on(
    slot: IvaRate,
    on: date,
    suffix: str,
) -> None:
    """The rate, tier and category are derived from the slot, never supplied here.

    This is what makes the sibling suite's hand-built fixtures trustworthy: it
    confirms the combinations they assert are the combinations production emits.
    Note the tier is many-to-one with the rate -- 10 %, 7,5 % and 5 % are all
    REDUCED -- which is the whole reason the box layer exists.
    """
    expected_rate, expected_tier, expected_category = _EXPECTED_CLASSIFICATION[suffix]
    observation = invoice_line_to_iva_observation(
        invoice_id=f"inv-classify-{suffix}",
        issued_at=on,
        invoice_kind=InvoiceKind.ISSUED,
        iva_rate=slot,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("1.00"),
        deduction_fact_kind=None,
        deduction_provenance=None,
    )
    assert observation.applied_rate == expected_rate
    assert observation.rate_kind is expected_tier
    assert observation.category is expected_category


@pytest.mark.parametrize(("slot", "on"), _OUT_OF_WINDOW)
def test_a_transitional_slot_outside_its_window_is_refused(slot: IvaRate, on: date) -> None:
    """The positive control for every in-window assertion in this module.

    A line claiming 7,5 % in March asserts a rate the statute did not offer that
    day. The bridge refuses it rather than recording it at whatever its tier
    meant, so the dates above are load-bearing rather than decorative. If this
    stopped raising, every other test here would still pass while the window had
    become meaningless.
    """
    with pytest.raises(IvaRateNotFoundError):
        invoice_line_to_iva_observation(
            invoice_id="inv-out-of-window",
            issued_at=on,
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=slot,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("7.50"),
            deduction_fact_kind=None,
            deduction_provenance=None,
        )


def test_the_transitional_boxes_are_not_reachable_only_in_theory() -> None:
    """Each transitional box draws a non-zero amount from a real line.

    A binding that can only ever resolve zero is dormant capacity. The three
    transitional rates are the ones at risk, because each is in force for only
    part of the year and a fixture confined to one quarter would miss them.
    """
    resolved = _resolved()
    for suffix in ("7-5", "5", "2"):
        assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-cuota"] > 0
        assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-base"] > 0
