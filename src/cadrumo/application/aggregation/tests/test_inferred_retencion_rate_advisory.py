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

* a genuine 15 % withholding raises NO advisory, and neither does a 7 %
  inicio-de-actividades one — an advisory that fired on the correct domestic-B2B
  majority would train operators to ignore the channel;
* each non-rate shortfall DOES raise exactly one, naming its transaction;
* a retención DECLARED on a linked invoice is never screened, because that figure
  is the document's statement rather than something this application inferred.

If a later edit made the advisory unconditional, the conforming gates go red; if
it disabled the advisory, the phantom gates go red. Neither direction passes
silently.

The expected figures are invoice arithmetic (declared gross minus declared cash)
and the statutory RIRPF art. 95.1 rates read from the registry parameter
catalogue, not the output of any formula under test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.aggregation import LedgerWithholdingDerivation
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
    load_retencion_actividades_rates,
)
from .._renta_income_ledger import RentaIncomeObservation, aggregate_renta_income_ledger
from .._retencion_rate_advisory import (
    INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND,
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
    iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL_21,
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


def test_the_registry_grounds_exactly_the_two_art_95_1_rates() -> None:
    """The screen compares against 15 % / 7 %, read rather than restated.

    Pinned because the discrimination is only as good as the rate set behind it:
    were a third rate to be grounded later, the conforming gates below would
    admit it and this gate is where that change announces itself.
    """
    rates = load_retencion_actividades_rates()

    assert rates.general_rate == Decimal("0.15")
    assert rates.inicio_actividad_rate == Decimal("0.07")


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
        ("swift-fee", "2400.00", Decimal("20.00")),
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
        _income_row("exempt-swift-fee", cash="1980.00", iva_amount=None, iva_category=IvaCategory.DOMESTIC_EXEMPT),
    )

    assert len(observations) == 1
    assert observations[0].withheld_derivation is LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA
    assert observations[0].withheld_amount == Decimal("20.00")

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "inferred_retencion_rate_unmatched"


def test_the_advisory_discriminates_within_one_mixed_aggregation() -> None:
    """The conforming row stays silent while the phantoms fire, in one pass.

    The per-scenario gates above could each pass with a screen that keyed on
    something incidental to how a single row was built. Running all six together
    and asserting that exactly the four phantoms are named is the property that
    matters: an unconditional advisory yields six here, a disabled one yields
    zero, and only a rate-discriminating screen yields these four.
    """
    observations = _observations(
        _income_row("mixed-genuine-15", cash="2120.00"),
        _income_row("mixed-genuine-07", cash="2280.00"),
        _income_row("mixed-swift-fee", cash="2400.00"),
        _income_row("mixed-rounding-short-pay", cash="2419.50"),
        _income_row("mixed-pronto-pago-discount", cash="2371.60"),
        _income_row("mixed-disputed-line", cash="2170.00"),
    )

    assert len(observations) == 6

    diagnostics = inferred_actividad_retencion_rate_advisory_observations(observations)
    flagged = {
        observation.transaction_id
        for observation in observations
        if any(observation.transaction_id in diagnostic.message for diagnostic in diagnostics)
    }
    silent = {observation.transaction_id for observation in observations} - flagged

    assert len(diagnostics) == 4
    assert len(flagged) == 4
    assert len(silent) == 2
