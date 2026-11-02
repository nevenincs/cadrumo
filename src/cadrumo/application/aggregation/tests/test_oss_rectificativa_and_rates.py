"""Modelo 369 corrections, coexisting destination rates and undated rate coverage.

Worked by hand, in the Union regime against France's published 20 and 10:

* F-1 1.000,00 + 200,00 corrected by R-1 100,00 + 20,00 in the same quarter leaves one
  general row of 900,00 and 180,00, because a correction takes off its invoice's row.
* France also publishes a reduced 5,5, so 100,00 + 5,50 is a row of its own at 5,5.

Each second reduced rate comes from the table of EPRS "VAT rates", 1 July 2025, typed
here by hand so it does not repeat the registry.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.money.rounding import round_to_cents
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.invoice_legal_classification import invoice_class_rectificativa
from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.invoices.models import Invoice
from ....domain.iva.errors import IvaRateNotFoundError
from ....domain.iva.lookup import coexisting_tier_rates, lookup_rate
from ....domain.iva.schema import EUMemberState, IvaRateKind
from ...exchange_rate_provider import bind_exchange_rate_provider_factory
from ..errors import AggregationValidationError
from .oss_rate_change_support import ordinary_general_variants, rate_change_inside_a_quarter
from .test_oss_detail_sections import _IMPORT, _UNION, _invoice, _resolve, _row

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_SUPPLY = date(2026, 2, 17)
_CUSTOMER = "FR40303265045"
_LATER_QUARTER = date(2026, 5, 4)


def _correction(
    number: str = "R-1",
    *,
    rectifies: str = "F-1",
    country: str = "FR",
    tier: str = "general",
    base: str = "100.00",
    cuota: str = "20.00",
    supply_date: date = _SUPPLY,
) -> Invoice:
    return _invoice(
        _UNION, number, country=country, tier=tier, base=base, cuota=cuota, supply_date=supply_date
    ).model_copy(
        update={
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "counterparty_tax_id": _CUSTOMER,
            "rectifies_invoice_number": rectifies,
        }
    )


def _first() -> Invoice:
    return _invoice(_UNION, "F-1", country="FR", tier="general", base="1000.00", cuota="200.00")


def _refusal(operation: PinnedAuthorityOperation, *invoices: Invoice, on: date = _SUPPLY) -> str:
    with pytest.raises(AggregationValidationError) as refused:
        _resolve(operation, _UNION, invoices, period=_UNION.period(on))
    return str(refused.value.translated_message)


def test_a_same_period_correction_nets_its_invoices_row(operation: PinnedAuthorityOperation) -> None:
    resolution = _resolve(operation, _UNION, (_first(), _correction()))
    assert _row(resolution, _UNION, 1) == ("FR", "S", Decimal("20"), Decimal("900.00"), Decimal("180.00"))


def test_a_correction_cancelling_its_invoice_leaves_no_row(operation: PinnedAuthorityOperation) -> None:
    resolution = _resolve(operation, _UNION, (_first(), _correction(base="1000.00", cuota="200.00")))
    closed = {row_set.record_id: row_set for row_set in resolution.closed_record_row_sets}
    assert [row.row_index for row in closed[_UNION.record].rows if row.occupied] == []


def test_a_correction_nets_at_the_rate_of_the_invoice_it_corrects(operation: PinnedAuthorityOperation) -> None:
    """Art. 90.Dos fixes the rate at the operation's devengo, so the correction joins the older row."""
    change = rate_change_inside_a_quarter(operation)
    code = change.member_state.upper()
    period = _UNION.period(change.first_day_after)
    cuota = round_to_cents(Decimal("100.00") * change.pct_before / Decimal("100"))
    original = _invoice(
        _UNION, "F-1", country=code, tier="general", base="100.00", cuota=str(cuota), supply_date=change.last_day_before
    )
    half = round_to_cents(cuota / 2)
    corrected = _correction(country=code, base="50.00", cuota=str(half), supply_date=change.first_day_after)
    resolution = _resolve(operation, _UNION, (original, corrected), period=period)
    assert _row(resolution, _UNION, 1) == (code, "S", change.pct_before, Decimal("50.00"), cuota - half)


def test_a_correction_of_an_earlier_period_refuses_because_section_4_cannot_write_it(
    operation: PinnedAuthorityOperation,
) -> None:
    """DR369 section 4 holds it, but its cuota field is unsigned, so the renderer cannot write the reduction."""
    assert (
        _refusal(operation, _first(), _correction(supply_date=_LATER_QUARTER), on=_LATER_QUARTER)
        == "aggregation.oss_ioss.errors.rectificativa_outside_period"
    )


def test_a_correction_whose_invoice_is_not_recorded_refuses(operation: PinnedAuthorityOperation) -> None:
    assert _refusal(operation, _correction()) == "aggregation.oss_ioss.errors.rectificativa_target_unknown"


def test_a_correction_for_another_destination_refuses(operation: PinnedAuthorityOperation) -> None:
    assert (
        _refusal(operation, _first(), _correction(country="PL", base="100.00", cuota="23.00"))
        == "aggregation.oss_ioss.errors.rectificativa_target_differs"
    )


def test_a_correction_above_its_row_refuses(operation: PinnedAuthorityOperation) -> None:
    assert (
        _refusal(operation, _first(), _correction(base="1100.00", cuota="220.00"))
        == "aggregation.oss_ioss.errors.rectificativa_above_row"
    )


def test_a_consignment_within_the_ceiling_is_still_read_with_its_correction(
    operation: PinnedAuthorityOperation,
) -> None:
    period = _IMPORT.period(_SUPPLY)
    first = _invoice(_IMPORT, "F-1", country="FR", tier="general", base="150.00", cuota="30.00")
    corrected = _invoice(_IMPORT, "R-1", country="FR", tier="general", base="50.00", cuota="10.00").model_copy(
        update={
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "counterparty_tax_id": _CUSTOMER,
            "rectifies_invoice_number": "F-1",
        }
    )
    resolution = _resolve(operation, _IMPORT, (first, corrected), period=period)
    assert _row(resolution, _IMPORT, 1) == ("FR", "S", Decimal("20"), Decimal("100.00"), Decimal("20.00"))


def test_frances_second_reduced_rate_takes_its_own_reduced_row(operation: PinnedAuthorityOperation) -> None:
    resolution = _resolve(
        operation,
        _UNION,
        (
            _invoice(_UNION, "F-1", country="FR", tier="reduced", base="100.00", cuota="5.50"),
            _invoice(_UNION, "F-2", country="FR", tier="reduced", base="200.00", cuota="20.00"),
        ),
    )
    assert {_row(resolution, _UNION, row) for row in (1, 2)} == {
        ("FR", "R", Decimal("10"), Decimal("200.00"), Decimal("20.00")),
        ("FR", "R", Decimal("5.5"), Decimal("100.00"), Decimal("5.50")),
    }


def test_frances_super_reduced_rate_is_written_as_reduced(operation: PinnedAuthorityOperation) -> None:
    """DR369's code is binary, S:Estandar or R:Reducido, and 2,1 is not the standard rate."""
    on = date(2026, 7, 20)
    resolution = _resolve(
        operation,
        _UNION,
        (_invoice(_UNION, "F-1", country="FR", tier="super_reduced", base="100.00", cuota="2.10", supply_date=on),),
        period=_UNION.period(on),
    )
    assert _row(resolution, _UNION, 1) == ("FR", "R", Decimal("2.1"), Decimal("100.00"), Decimal("2.10"))


def test_a_cuota_matching_no_rate_of_the_tier_still_refuses(operation: PinnedAuthorityOperation) -> None:
    invoice = _invoice(_UNION, "F-1", country="FR", tier="reduced", base="100.00", cuota="7.00")
    assert _refusal(operation, invoice) == "aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate"


def test_a_cuota_two_rates_of_the_tier_both_explain_refuses(operation: PinnedAuthorityOperation) -> None:
    """0,10 at 5,5 and at 10 both round to 0,01, so the row's rate is not known."""
    invoice = _invoice(_UNION, "F-1", country="FR", tier="reduced", base="0.10", cuota="0.01")
    assert _refusal(operation, invoice) == "aggregation.oss_ioss.errors.rate_tier_ambiguous"


@pytest.mark.parametrize(
    ("state", "rates"),
    [
        ("at", {"10", "13"}),
        ("be", {"6", "12"}),
        ("bg", {"9"}),
        ("hr", {"5", "13"}),
        ("cy", {"5", "9"}),
        ("cz", {"12"}),
        ("ee", {"9", "13"}),
        ("fi", {"10", "14"}),
        ("fr", {"5.5", "10"}),
        ("de", {"7"}),
        ("gr", {"6", "13"}),
        ("hu", {"5", "18"}),
        ("ie", {"9", "13.5"}),
        ("it", {"5", "10"}),
        ("lv", {"5", "12"}),
        ("lt", {"5", "9"}),
        ("mt", {"5", "7"}),
        ("nl", {"9"}),
        ("pl", {"5", "8"}),
        ("pt", {"6", "13"}),
        ("ro", {"5", "9"}),
        ("sk", {"5", "19"}),
        ("si", {"5", "9.5"}),
        ("se", {"6", "12"}),
    ],
)
def test_every_reduced_rate_of_the_1_july_2025_table_is_held(
    operation: PinnedAuthorityOperation, state: str, rates: set[str]
) -> None:
    on = date(2025, 7, 1)
    member, tier = EUMemberState.from_registry(state), IvaRateKind("reduced")
    held = {lookup_rate(member, tier, on, operation=operation).pct}
    held |= {rate.pct for rate in coexisting_tier_rates(member, tier, on, operation=operation)}
    assert held == {Decimal(rate) for rate in rates}


@pytest.mark.parametrize(
    ("state", "tier", "on", "pct"),
    [
        ("ee", "general", date(2024, 1, 1), "22"),
        ("fi", "general", date(2024, 9, 1), "25.5"),
        ("ee", "reduced", date(2025, 1, 1), "13"),
    ],
)
def test_a_rate_the_national_pages_date_earlier_is_published_from_that_date(
    operation: PinnedAuthorityOperation, state: str, tier: str, on: date, pct: str
) -> None:
    record = lookup_rate(EUMemberState.from_registry(state), IvaRateKind(tier), on, operation=operation)
    assert record.pct == Decimal(pct)
    assert record.published_on_date


def _before_french_general(operation: PinnedAuthorityOperation) -> date:
    earliest = min(
        variant.valid_from for variant in ordinary_general_variants(operation)["fr"] if variant.valid_from is not None
    )
    return earliest - timedelta(days=1)


def test_a_figure_matching_a_projected_rate_is_accepted_with_a_warning(operation: PinnedAuthorityOperation) -> None:
    uncovered = _before_french_general(operation)
    resolution = _resolve(
        operation,
        _UNION,
        (_invoice(_UNION, "F-1", country="FR", tier="general", base="100.00", cuota="20.00", supply_date=uncovered),),
        period=_UNION.period(uncovered),
    )
    assert _row(resolution, _UNION, 1) == ("FR", "S", Decimal("20"), Decimal("100.00"), Decimal("20.00"))
    warnings = [item for item in resolution.diagnostics if item.source_ref == "rate_date_projected"]
    assert len(warnings) == 1
    assert warnings[0].reason == "source_issue"


def test_a_figure_differing_from_a_projected_rate_is_a_coverage_gap_not_a_mismatch(
    operation: PinnedAuthorityOperation,
) -> None:
    uncovered = _before_french_general(operation)
    with pytest.raises(IvaRateNotFoundError) as refused:
        _resolve(
            operation,
            _UNION,
            (
                _invoice(
                    _UNION, "F-1", country="FR", tier="general", base="100.00", cuota="19.60", supply_date=uncovered
                ),
            ),
            period=_UNION.period(uncovered),
        )
    assert refused.value.context is not None
    assert refused.value.context["rate_registry_covers_date"] is False


def test_a_correction_two_invoices_could_answer_refuses(operation: PinnedAuthorityOperation) -> None:
    """Two F-1 in different series could each be the one named, and the record cannot say which."""
    other = _invoice(_UNION, "F-1", country="FR", tier="general", base="500.00", cuota="100.00")
    other = Invoice.model_validate({**other.model_dump(exclude={"invoice_id"}), "series": "B"})
    assert _refusal(operation, _first(), other, _correction()) == (
        "aggregation.oss_ioss.errors.rectificativa_target_ambiguous"
    )


class _Quote:
    """A rate authority publishing one rate; the lookup's parsing has its own tests."""

    rate_source_id = "ecb_reference"

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        del currency
        return EurRateLookup(
            status=EurRateLookupStatus.FOUND,
            rate_date=rate_date,
            source=self.rate_source_id,
            rate=Decimal("0.9195"),
            observation_date=rate_date,
        )


def _dutch(number: int, *, currency: str, base: str, cuota: str) -> Invoice:
    return _invoice(_UNION, f"N-{number}", country="NL", tier="general", base=base, cuota=cuota).model_copy(
        update={"currency": currency}
    )


def test_a_foreign_currency_row_converts_at_the_level_of_the_row(operation: PinnedAuthorityOperation) -> None:
    """1.000 x USD 1,00 + 0,21 at 0,9195 and 21: base 919,50, cuota 919,50 x 0,21 = 193,095, so 193,10.

    Rounding each line first gives 0,92 and 0,19, so 920,00 and 190,00, a cuota that is not
    21 of its own base.
    """
    invoices = tuple(_dutch(number, currency="USD", base="1.00", cuota="0.21") for number in range(1000))
    with bind_exchange_rate_provider_factory(_Quote):
        resolution = _resolve(operation, _UNION, invoices)
    assert _row(resolution, _UNION, 1) == ("NL", "S", Decimal("21"), Decimal("919.50"), Decimal("193.10"))


def test_a_euro_row_declares_its_cuota_at_its_own_rate(operation: PinnedAuthorityOperation) -> None:
    """100 x 0,99 + 0,21: base 99,00, cuota 99,00 x 0,21 = 20,79, where the lines would add up to 21,00."""
    invoices = tuple(_dutch(number, currency="EUR", base="0.99", cuota="0.21") for number in range(100))
    resolution = _resolve(operation, _UNION, invoices)
    assert _row(resolution, _UNION, 1) == ("NL", "S", Decimal("21"), Decimal("99.00"), Decimal("20.79"))
