"""Ledger transactions reach every Modelo 390 rate box, through the real aggregator.

:class:`IvaLedgerObservation` has two production producers: the invoice-line
bridge, and this one — the ledger aggregator, which projects classified
:class:`Transaction` rows and sets ``applied_rate`` from ``transaction.iva_rate``.
A sibling module in the registry tests covers the invoice-line producer. This
covers the ledger producer, which carries imported bank and statement rows and is
the higher-volume path in practice.

Why it is worth covering separately rather than assuming: the rate boxes select
on ``category``, ``rate_kind`` and ``applied_rate`` together, and only the first
of those comes from the operator. The tier is DERIVED here, and it is
deliberately many-to-one with the rate — 10 %, 7,5 % and 5 % all classify
``REDUCED``, 4 % and 2 % both classify ``SUPER_REDUCED``. That collapse is the
entire reason a per-tier casilla cannot serve a per-rate box, so a test that
supplied the tier by hand would assume away the thing under test.

Real-behaviour: real :class:`Transaction` models through the real
``aggregate_iva_ledger_observations``, resolved against the committed Modelo 390
revision by the real registry resolver. No mocks, stubs, skips or xfail.

Non-tautology: no cuota equals its base multiplied by its rate (the 0 % cuota is
zero by definition, not by arithmetic), and every tier carries a distinct base
and a distinct cuota, so a row routed to a neighbouring rate's box fails on
value. The transaction model independently enforces that base + cuota
reconstitutes the gross cash movement, so these triples are internally
consistent rather than arbitrary.

Mutation evidence, recorded here rather than in a commit message because catch-all
sweeps in this tree routinely land work under an unrelated message, and evidence
that lives only in a commit nobody can find is evidence nobody has. Both
mutations were applied as runtime monkeypatches from outside the repository, so
nothing under ``src`` changed and no window existed for a sweep to capture.

Dropping ``applied_rate`` from every observation empties ``tipo-7-5`` and
``tipo-5`` — 1600.00 and 1400.00 both fall to 0 — while the rate-blind
``modelo-390-iva-repercutido-reducido-base`` holds 5500.00 unchanged. That is the
silent-drop signature the two-layer split exists to expose: the rate boxes go
empty, the declared total stays whole, and nothing raises. It is also the exact
regression this producer once shipped, when it left ``applied_rate`` unset on the
reasoning that an invoice line carries a rate slot rather than a number.

Mis-deriving the tier for the 7,5 % row reddens the derivation test alone. The
unmutated aggregation passes as control, so both bites are attributable to the
mutation rather than to the patching.

The window dates are load-bearing, not decorative: 0 % and 5 % are transitional
food rates confined to 1 July - 30 September 2024, and a 0 % sale booked in Q1 is
refused. That refusal is correct, and this fixture follows the statute rather
than pinning a date it once accepted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.ledger_bindings import resolve_ledger_iva_aggregation_binding_values
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ....core import Period
from ....core.resources import resources
from ....domain.iva import IvaCategory, IvaRateKind
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLASSIFIED_AT = datetime(2025, 1, 6, 12, 0, tzinfo=UTC)
_ANNUAL_2024 = Period.from_year_and_code(2024, "0A")

# box suffix, operator-declared category, operator-declared rate, a date inside
# that rate's 2024 window, base, cuota. Only 21 %, 10 % and 4 % run the whole
# year: under RDL 4/2024 art. 1, 5 % and 0 % apply 1 Jul - 30 Sep 2024 and 7,5 %
# and 2 % from 1 Oct. Each windowed rate is booked on a day it was in force, and
# an annual return spans all of those windows -- which is why one return needs
# boxes for rates that never coexisted.
#
# The 0 % row sits in July-September rather than Q1 on purpose: the zero window
# is a transitional food rate, not a permanent tier, and a Q1 0 % sale is now
# correctly refused by the aggregator.
_LEDGER_ROWS = (
    ("21", IvaCategory.DOMESTIC_GENERAL, "0.21", date(2024, 3, 10), "4000.00", "817.00"),
    ("10", IvaCategory.DOMESTIC_REDUCED, "0.10", date(2024, 3, 11), "2500.00", "241.00"),
    ("7-5", IvaCategory.DOMESTIC_REDUCED, "0.075", date(2024, 11, 12), "1600.00", "127.00"),
    ("5", IvaCategory.DOMESTIC_REDUCED, "0.05", date(2024, 8, 13), "1400.00", "73.00"),
    ("4", IvaCategory.DOMESTIC_SUPER_REDUCED, "0.04", date(2024, 3, 14), "1200.00", "51.00"),
    ("2", IvaCategory.DOMESTIC_SUPER_REDUCED, "0.02", date(2024, 11, 15), "900.00", "19.00"),
    ("0", IvaCategory.DOMESTIC_ZERO, "0.00", date(2024, 8, 16), "700.00", "0.00"),
)

# The tier the aggregator must DERIVE for each rate. Many-to-one on purpose.
_EXPECTED_TIER = {
    "21": IvaRateKind.GENERAL,
    "10": IvaRateKind.REDUCED,
    "7-5": IvaRateKind.REDUCED,
    "5": IvaRateKind.REDUCED,
    "4": IvaRateKind.SUPER_REDUCED,
    "2": IvaRateKind.SUPER_REDUCED,
    "0": IvaRateKind.ZERO,
}


def _m390_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("390", filing_year=2024, period="0A").revision


def _sale(
    *,
    tag: str,
    category: IvaCategory,
    rate: str,
    booked: date,
    base: str,
    cuota: str,
) -> Transaction:
    """One issued domestic sale, carrying only what an operator records."""
    raw = RawTransaction(
        provider_transaction_id=f"m390-rate-box-{tag}",
        booked_date=booked,
        value_date=booked,
        amount=Decimal(base) + Decimal(cuota),
        currency="EUR",
        counterparty="Cliente",
        description=f"venta tipo {tag}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_CLASSIFIED_AT,
            provider_name="manual",
        ),
        raw_fields={"tag": tag},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            # INCOMING is what makes this a repercutido sale rather than a
            # soportado purchase; the flow direction is derived, not declared.
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal(base),
            "iva_rate": Decimal(rate),
            "iva_amount": Decimal(cuota),
            "iva_category": category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _CLASSIFIED_AT,
            "classified_by": "manual",
        },
    )


def _catalogue() -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(
        tuple(
            _sale(tag=tag, category=category, rate=rate, booked=booked, base=base, cuota=cuota)
            for tag, category, rate, booked, base, cuota in _LEDGER_ROWS
        )
    )


def _aggregation():
    return aggregate_iva_ledger_observations(_catalogue(), period=_ANNUAL_2024)


def _resolved() -> dict[str, Decimal]:
    aggregation = _aggregation()
    return dict(resolve_ledger_iva_aggregation_binding_values(_m390_revision(), aggregation.observations))


@pytest.mark.parametrize(
    ("suffix", "base", "cuota"),
    tuple((row[0], row[4], row[5]) for row in _LEDGER_ROWS),
)
def test_a_ledger_sale_reaches_its_official_rate_box(suffix: str, base: str, cuota: str) -> None:
    """A booked sale lands in the box for the rate it was charged at.

    The whole chain runs: transaction -> aggregator -> observation -> registry
    selector -> box binding. Nothing between the operator's input and the
    official box is supplied by this test.
    """
    resolved = _resolved()
    assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-base"] == Decimal(base)
    assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-cuota"] == Decimal(cuota)


@pytest.mark.parametrize(("suffix", "rate"), tuple((row[0], row[2]) for row in _LEDGER_ROWS))
def test_the_aggregator_derives_the_tier_and_carries_the_rate(suffix: str, rate: str) -> None:
    """The tier is derived from the rate; the rate is carried, not re-derived.

    Both halves matter. If the tier were wrong the row would land in another
    rate's tier entirely; if ``applied_rate`` were dropped — which is what the
    aggregator did before it was corrected — the row would match no rate-specific
    binding at all and leave every box while staying in the rate-blind total.
    """
    observations = {
        obs.applied_rate: obs for obs in _aggregation().observations if obs.flow_direction.value == "repercutido"
    }
    observation = observations[Decimal(rate)]
    assert observation.rate_kind is _EXPECTED_TIER[suffix]
    assert observation.applied_rate == Decimal(rate)


def test_the_tier_is_many_to_one_with_the_rate() -> None:
    """The collapse that makes a per-tier casilla unable to serve a per-rate box.

    Stated as its own assertion because it is the premise of the whole box
    layer. If a future rate table gave each rate its own tier, the two-layer
    split would still be correct but this justification would have changed, and
    that deserves to be noticed rather than silently outlived.
    """
    tiers_by_rate = {
        obs.applied_rate: obs.rate_kind
        for obs in _aggregation().observations
        if obs.flow_direction.value == "repercutido"
    }
    assert tiers_by_rate[Decimal("0.10")] is tiers_by_rate[Decimal("0.075")]
    assert tiers_by_rate[Decimal("0.10")] is tiers_by_rate[Decimal("0.05")]
    assert tiers_by_rate[Decimal("0.04")] is tiers_by_rate[Decimal("0.02")]


def test_no_sale_is_silently_gated_out_of_the_aggregation() -> None:
    """The control for every assertion above.

    The aggregator drops rows it cannot classify and records an issue rather
    than raising. Without this, a fixture whose rows were all quietly gated would
    produce an empty observation set, and every value assertion would fail
    loudly — but a fixture where only SOME rows were gated could still look
    partially green. Assert the full count and an empty issue list.
    """
    aggregation = _aggregation()
    assert len(aggregation.observations) == len(_LEDGER_ROWS)
    assert aggregation.issues == ()
