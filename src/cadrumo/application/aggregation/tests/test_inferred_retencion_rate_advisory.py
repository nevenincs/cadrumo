"""Inferred actividad-económica retención: the advisory discriminates by rate.

The Modelo 130 income ledger derives retención practicada as declared invoice
gross minus cash received, bounded ABOVE by the RIRPF art. 95.1 general rate and
not at all below. A cash shortfall from something that is not a retención — a
correspondent-bank fee, a rounding short-pay, a pronto-pago discount, a disputed
line the client deducted — therefore lands in the same subtraction and is credited
as a pago a cuenta nobody withheld and AEAT never received.

The inference is deliberately left alone; what these gates pin is that it becomes
VISIBLE without becoming noisy. The whole value of the advisory is the
discrimination, so that is what is asserted here rather than the weaker "an
advisory was raised":

* a withholding at an art. 95.1 PROFESSIONAL rate (15 % or 7 %) raises nothing —
  those figures are too large for a fee or rounding gap to reach by accident, so
  the match is a strong claim and an advisory there would train operators to
  ignore the channel;
* a match on a SECTORAL rate only (2 % or 1 %) raises the weaker
  ``inferred_retencion_sectoral_rate_unconfirmed``, never the unmatched reason —
  those rates are small enough that a bank fee lands on one by coincidence;
* each non-rate shortfall raises ``inferred_retencion_rate_unmatched``, naming
  its transaction;
* a retención DECLARED on a linked invoice is never screened, because that figure
  is the document's statement rather than something this application inferred;
* the active profile WORDS the sectoral advisory and never suppresses it.

The two reason codes are asserted structurally rather than by prose, because the
operator driving this CLI routes on fields. If a later edit made the screen
unconditional the professional gates go red; if it disabled the screen the
phantom gates go red; if it merged the two reasons the split gate goes red; and
if it promoted the profile hint into a filter, the no-profile gate goes red.

The expected figures are invoice arithmetic (declared gross minus declared cash)
and the statutory RIRPF art. 95 rates read from the registry parameter catalogue,
not the output of any formula under test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.aggregation import LedgerWithholdingDerivation
from ....domain.iva import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.retencion_parameters import load_retencion_actividades_rates, statutory_activity_retencion_rates
from .._renta_income_ledger import RentaIncomeObservation, aggregate_renta_income_ledger
from .._retencion_rate_advisory import (
    INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND,
    INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND,
    inferred_actividad_retencion_rate_advisory_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Every scenario invoices the same 2.000,00 EUR base at 21 % IVA, so the rows
#: differ only in what reached the bank. Holding the invoice fixed is what makes
#: the cash figure the single variable the advisory reacts to.
_BASE = Decimal("2000.00")
_IVA = Decimal("420.00")
_GROSS = _BASE + _IVA


def _raw(provider_id: str, *, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 3, 15),
        value_date=date(2024, 3, 15),
        amount=amount,
        currency="EUR",
        counterparty="Cliente SA",
        description=f"income row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _income_row(
    provider_id: str,
    *,
    cash: str,
    iva_amount: str | None = "420.00",
    iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, amount=Decimal(cash)),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _BASE,
            "iva_amount": None if iva_amount is None else Decimal(iva_amount),
            "iva_rate": None if iva_amount is None else Decimal("0.21"),
            "iva_category": iva_category,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _observations(*rows: Transaction) -> tuple[RentaIncomeObservation, ...]:
    """Run rows through the REAL aggregation, so the figures are production's.

    Constructing observations by hand would let the test assert against amounts
    the test itself chose, which proves nothing about the inference that actually
    runs. These come out of ``aggregate_renta_income_ledger``.
    """
    aggregation = aggregate_renta_income_ledger(
        TransactionCatalogue.from_transactions(rows),
        bucket_id="test",
        period=Period.from_year_and_code(2024, "1T"),
    )
    return tuple(aggregation.observations)


def test_the_registry_grounds_every_art_95_rate() -> None:
    """The screen compares against the whole grounded set, read not restated.

    Pinned per apartado because the discrimination is only as good as the rate
    set behind it, and because art. 95.4 is deliberately two figures rather than
    one: the 2 % general agrícola/ganadera rate carries an express 1 % carve-out
    for engorde de porcino y avicultura. Grounding only the general figure would
    have left that carve-out false-firing.

    The distinct-value set is what the advisory consumes; six declared
    parameters collapse to four figures because 95.4.2.º/95.5 both fix 2 % and
    95.4.1.º/95.6.1.º both fix 1 %.
    """
    rates = load_retencion_actividades_rates()

    assert rates.general_rate == Decimal("0.15")
    assert rates.inicio_actividad_rate == Decimal("0.07")
    assert rates.agricola_ganadera_rate == Decimal("0.02")
    assert rates.ganadera_engorde_rate == Decimal("0.01")
    assert rates.forestal_rate == Decimal("0.02")
    assert rates.estimacion_objetiva_rate == Decimal("0.01")
    assert statutory_activity_retencion_rates() == {
        Decimal("0.15"),
        Decimal("0.07"),
        Decimal("0.02"),
        Decimal("0.01"),
    }


@pytest.mark.parametrize(
    ("provider_id", "cash", "withheld", "apartado"),
    [
        ("sectoral-agricola-2pct", "2380.00", Decimal("40.00"), "95.4.2.º agrícola/ganadera general"),
        ("sectoral-forestal-2pct", "2380.00", Decimal("40.00"), "95.5 forestal"),
        ("sectoral-engorde-1pct", "2400.00", Decimal("20.00"), "95.4.1.º engorde porcino/avicultura"),
        ("sectoral-objetiva-1pct", "2400.00", Decimal("20.00"), "95.6.1.º estimación objetiva"),
    ],
)
def test_a_genuine_sectoral_rate_never_raises_the_unmatched_advisory(
    provider_id: str,
    cash: str,
    withheld: Decimal,
    apartado: str,
) -> None:
    """A sectoral rate is a real rate: it must never be called unmatched.

    Before art. 95.4/95.5/95.6 were in the registry the screen knew only 15 %
    and 7 %, so an agricultural, forestry or módulos filer withholding at their
    correct statutory rate raised the STRONG advisory on a perfectly correct
    filing. That misclassification is what grounding closed. These rows may
    still raise the weaker sectoral-coincidence advisory — asserted separately
    below — but never the unmatched one.
    """
    assert _GROSS - Decimal(cash) == withheld
    assert apartado

    observations = _observations(_income_row(provider_id, cash=cash))

    assert len(observations) == 1
    assert observations[0].withheld_amount == withheld
    reasons = {
        diagnostic.reason for diagnostic in inferred_actividad_retencion_rate_advisory_observations(observations)
    }
    assert "inferred_retencion_rate_unmatched" not in reasons


def test_a_shortfall_coinciding_with_a_sectoral_rate_raises_the_soft_advisory() -> None:
    """The €20 catch, recovered as a weaker claim instead of as silence.

    A 20,00 EUR correspondent-bank fee on a 2.000,00 base is exactly 1 % — the
    art. 95.4.1.º / 95.6.1.º figure — so it is arithmetically indistinguishable
    from a genuine engorde or módulos withholding. Grounding the sectoral rates
    made this row silent; the sectoral reason code makes it visible again
    WITHOUT asserting the certainty the unmatched advisory carries.

    Keyed on the reason, not the prose: the operator is an autonomous agent that
    routes on fields, so the two advisories must be separable structurally.
    """
    observations = _observations(_income_row("swift-fee-coincides-with-1pct", cash="2400.00"))

    assert observations[0].withheld_amount == Decimal("20.00")

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "inferred_retencion_sectoral_rate_unconfirmed"
    assert diagnostics[0].source_kind == INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND


@pytest.mark.parametrize(
    ("provider_id", "cash", "shortfall", "quoted_on"),
    [
        ("pronto-pago-1pct-of-base", "2400.00", Decimal("20.00"), "base"),
        ("pronto-pago-2pct-of-base", "2380.00", Decimal("40.00"), "base"),
    ],
)
def test_a_percentage_quoted_discount_still_speaks_through_the_sectoral_reason(
    provider_id: str,
    cash: str,
    shortfall: Decimal,
    quoted_on: str,
) -> None:
    """The class the rate set absorbs wholesale, pinned as audible.

    A pronto-pago descuento is quoted as a percentage and 1 % / 2 % are its
    standard values, so a base-quoted discount equals a sectoral rate at EVERY
    base — by construction, not by the one-base arithmetic luck the flat-fee
    case represents. Screening on the rate set alone would make this phantom
    cause invisible at its two commonest values at every invoice size.

    These rows must therefore raise the SECTORAL advisory. If a later edit
    dropped that reason and kept only the unmatched one, this class would go
    silent and this gate is what catches it.
    """
    assert quoted_on == "base"
    assert _GROSS - Decimal(cash) == shortfall

    observations = _observations(_income_row(provider_id, cash=cash))

    assert observations[0].withheld_amount == shortfall

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "inferred_retencion_sectoral_rate_unconfirmed"


def test_a_discount_quoted_on_the_invoice_total_raises_the_strong_advisory() -> None:
    """Quoted on the gross, the same discount collides with nothing.

    2 % of the 2.420,00 invoice total is 48,40, which is 2,42 % of the base and
    matches no statutory rate — so the commercially conventional quoting
    convention lands in the strong bucket. Pinned beside the base-quoted case
    because the two differ only by the 1,21 IVA factor, and a reader who saw
    only one would draw the wrong conclusion about which discounts are audible.
    """
    observations = _observations(_income_row("pronto-pago-2pct-of-gross", cash="2371.60"))

    assert observations[0].withheld_amount == Decimal("48.40")

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "inferred_retencion_rate_unmatched"


def test_a_professional_rate_match_stays_silent_while_a_sectoral_one_speaks() -> None:
    """The severity split, asserted as one comparison rather than two beliefs.

    300,00 is 15 % of the base and 20,00 is 1 %; both are statutory products, and
    the screen treats them differently ONLY because a fee can reach 1 % by
    accident and cannot reach 15 %. If a later edit collapsed the two branches,
    one side of this assertion fails whichever way it collapsed.
    """
    professional = _observations(_income_row("prof-15pct", cash="2120.00"))
    sectoral = _observations(_income_row("sect-1pct", cash="2400.00"))

    assert inferred_actividad_retencion_rate_advisory_observations(professional) == ()
    assert len(inferred_actividad_retencion_rate_advisory_observations(sectoral)) == 1


def test_the_sectoral_advisory_fires_even_when_no_profile_is_available() -> None:
    """Absent profile changes the WORDING and never suppresses the diagnostic.

    This is the gate against the obvious future "improvement": promoting the
    profile hint into a filter. With no bucket the hint is unavailable, and the
    advisory must still fire, saying only that it could not be checked.
    """
    observations = _observations(_income_row("sect-no-profile", cash="2400.00"))

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations, bucket_id=None)

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "inferred_retencion_sectoral_rate_unconfirmed"
    assert "could not be checked" in diagnostics[0].message


def test_a_genuine_fifteen_percent_retencion_raises_no_advisory() -> None:
    """2.420,00 invoiced, 2.120,00 banked: the 300,00 gap IS 15 % of the base."""
    observations = _observations(_income_row("genuine-15", cash="2120.00"))

    assert len(observations) == 1
    assert observations[0].withheld_amount == _BASE * Decimal("0.15")
    assert observations[0].withheld_derivation is LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA
    assert inferred_actividad_retencion_rate_advisory_observations(observations) == ()


def test_a_genuine_seven_percent_inicio_retencion_raises_no_advisory() -> None:
    """The reduced inicio-de-actividades rate is equally conforming.

    2.420,00 invoiced, 2.280,00 banked: the 140,00 gap is 7 % of the base. The
    engine cannot know which rate a row is entitled to, so either statutory
    figure must pass — screening only the general rate would false-fire on every
    filer in their first three years of activity.
    """
    observations = _observations(_income_row("genuine-07", cash="2280.00"))

    assert len(observations) == 1
    assert observations[0].withheld_amount == _BASE * Decimal("0.07")
    assert inferred_actividad_retencion_rate_advisory_observations(observations) == ()


@pytest.mark.parametrize(
    ("provider_id", "cash", "shortfall"),
    [
        ("swift-fee", "2401.50", Decimal("18.50")),
        ("rounding-short-pay", "2419.50", Decimal("0.50")),
        ("pronto-pago-discount", "2371.60", Decimal("48.40")),
        ("disputed-line", "2170.00", Decimal("250.00")),
    ],
)
def test_a_non_rate_shortfall_raises_exactly_one_advisory(
    provider_id: str,
    cash: str,
    shortfall: Decimal,
) -> None:
    """Each phantom credit is disclosed, and names the row an operator must fix.

    True retención is ZERO in every one of these: the payer withheld nothing. The
    gap is a bank fee, a rounding difference, a discount, or a disputed amount,
    and none of them is a product of the base and a statutory rate.
    """
    assert _GROSS - Decimal(cash) == shortfall

    observations = _observations(_income_row(provider_id, cash=cash))

    assert len(observations) == 1
    assert observations[0].withheld_amount == shortfall

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "inferred_retencion_rate_unmatched"
    assert diagnostics[0].source_kind == INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND
    assert observations[0].transaction_id in diagnostics[0].message
    assert diagnostics[0].remedy is not None


def test_a_cuota_less_exempt_row_is_screened_on_the_same_rate_basis() -> None:
    """The zero-cuota route reaches the screen too, not only the declared-cuota one.

    An IVA-exempt professional service (LIVA art. 20) has no cuota to record, so
    its invoice gross is the bare base and it derives through a different marker.
    2.000,00 invoiced, 1.980,00 banked after a 20,00 transfer fee: still no
    statutory rate, still a phantom credit.
    """
    observations = _observations(
        _income_row("exempt-swift-fee", cash="1981.50", iva_amount=None, iva_category=IvaCategory.DOMESTIC_EXEMPT),
    )

    assert len(observations) == 1
    assert observations[0].withheld_derivation is LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA
    assert observations[0].withheld_amount == Decimal("18.50")

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "inferred_retencion_rate_unmatched"


def test_the_advisory_splits_one_mixed_aggregation_three_ways() -> None:
    """All three outcomes in one pass, keyed on reason rather than on count.

    The per-scenario gates above could each pass with a screen that keyed on
    something incidental to how a single row was built. Running every shape
    together and asserting WHICH bucket each lands in is the property that
    matters, and it fails whichever way a later edit collapses the branches:
    an unconditional screen puts the two professional rows in a bucket, a
    disabled one empties both, and merging the reason codes moves the sectoral
    row into the unmatched set.
    """
    observations = _observations(
        _income_row("mixed-genuine-15", cash="2120.00"),
        _income_row("mixed-genuine-07", cash="2280.00"),
        _income_row("mixed-sectoral-2pct", cash="2380.00"),
        _income_row("mixed-swift-fee", cash="2401.50"),
        _income_row("mixed-rounding-short-pay", cash="2419.50"),
        _income_row("mixed-pronto-pago-discount", cash="2371.60"),
        _income_row("mixed-disputed-line", cash="2170.00"),
    )

    assert len(observations) == 7

    # Keyed on the withheld amount rather than the provider id: transaction_id is
    # a derived hash, and the amount is both stable and the quantity the screen
    # actually reasons about.
    amount_by_id = {observation.transaction_id: observation.withheld_amount for observation in observations}
    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)
    by_reason: dict[str, set[Decimal]] = {}
    for diagnostic in diagnostics:
        named = {amount for transaction_id, amount in amount_by_id.items() if transaction_id in diagnostic.message}
        by_reason.setdefault(diagnostic.reason, set()).update(named)
    spoken = set().union(*by_reason.values()) if by_reason else set()
    silent = set(amount_by_id.values()) - spoken

    assert by_reason["inferred_retencion_rate_unmatched"] == {
        Decimal("18.50"),
        Decimal("0.50"),
        Decimal("48.40"),
        Decimal("250.00"),
    }
    assert by_reason["inferred_retencion_sectoral_rate_unconfirmed"] == {Decimal("40.00")}
    assert silent == {Decimal("300.00"), Decimal("140.00")}
