"""Modelo 369 corrections, coexisting destination rates and undated rate coverage.

Worked by hand, in the Union regime against France's published 20 and 10:

* F-1 1.000,00 + 200,00 corrected by R-1 100,00 + 20,00 in the same quarter leaves one
  general row of 900,00 and 180,00, because a correction takes off its invoice's row.
* France also publishes a reduced 5,5, so 100,00 + 5,50 is a row of its own at 5,5.

Each second reduced rate comes from the EPRS table of the rates in force on 1 July 2025,
typed here by hand so it does not repeat the registry.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.money.rounding import round_to_cents
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.invoice_legal_classification import invoice_class_rectificativa
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_revision
from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.invoices.models import Invoice
from ....domain.iva.errors import IvaRateNotFoundError
from ....domain.iva.lookup import coexisting_tier_rates, lookup_rate
from ....domain.iva.rates import IVA_RATE_FACT_ID
from ....domain.iva.schema import EUMemberState, IvaRateKind
from ...exchange_rate_provider import bind_exchange_rate_provider_factory
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..errors import AggregationValidationError
from ..oss_ioss_resolver import OssIossLedgerSourceResolver
from ..oss_ioss_wire_geometry import record_row_slots
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .oss_rate_change_support import ordinary_general_variants, rate_change_inside_a_quarter, variant_pct
from .test_oss_detail_sections import (
    BUCKET,
    EXTERIOR,
    IMPORT,
    UNION,
    Reader,
    Regime,
    Transactions,
    oss_detail_sections_invoice,
    oss_detail_sections_row,
    resolve,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = filing_year_envelope().horizon
_SUPPLY = date(_YEAR, 2, 17)
_CUSTOMER = "FR40303265045"
_LATER_QUARTER = date(_YEAR, 5, 4)
_RETURN_AGE_LIMIT = 3
_CORRECTION_RECORD = {
    EXTERIOR: "modelo-369-exterior-t36902",
    UNION: "modelo-369-union-t36908",
    IMPORT: "modelo-369-importacion-t36911",
}


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
    return oss_detail_sections_invoice(
        UNION, number, country=country, tier=tier, base=base, cuota=cuota, supply_date=supply_date
    ).model_copy(
        update={
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "counterparty_tax_id": _CUSTOMER,
            "rectifies_invoice_number": rectifies,
        }
    )


def _first() -> Invoice:
    return oss_detail_sections_invoice(UNION, "F-1", country="FR", tier="general", base="1000.00", cuota="200.00")


def _refusal(operation: PinnedAuthorityOperation, *invoices: Invoice, on: date = _SUPPLY) -> str:
    with pytest.raises(AggregationValidationError) as refused:
        resolve(operation, UNION, invoices, period=UNION.period(on))
    return str(refused.value.translated_message)


def test_a_same_period_correction_nets_its_invoices_row(operation: PinnedAuthorityOperation) -> None:
    resolution = resolve(operation, UNION, (_first(), _correction()))
    assert oss_detail_sections_row(resolution, UNION, 1) == (
        "FR",
        "S",
        Decimal("20"),
        Decimal("900.00"),
        Decimal("180.00"),
    )


def test_a_correction_cancelling_its_invoice_leaves_no_row(operation: PinnedAuthorityOperation) -> None:
    resolution = resolve(operation, UNION, (_first(), _correction(base="1000.00", cuota="200.00")))
    closed = {row_set.record_id: row_set for row_set in resolution.closed_record_row_sets}
    assert [row.row_index for row in closed[UNION.record].rows if row.occupied] == []


def test_a_correction_nets_at_the_rate_of_the_invoice_it_corrects(operation: PinnedAuthorityOperation) -> None:
    """Art. 90.Dos fixes the rate at the operation's devengo, so the correction joins the older row."""
    change = rate_change_inside_a_quarter(operation)
    code = change.member_state.upper()
    period = UNION.period(change.first_day_after)
    cuota = round_to_cents(Decimal("100.00") * change.pct_before / Decimal("100"))
    original = oss_detail_sections_invoice(
        UNION, "F-1", country=code, tier="general", base="100.00", cuota=str(cuota), supply_date=change.last_day_before
    )
    half = round_to_cents(cuota / 2)
    corrected = _correction(country=code, base="50.00", cuota=str(half), supply_date=change.first_day_after)
    resolution = resolve(operation, UNION, (original, corrected), period=period)
    assert oss_detail_sections_row(resolution, UNION, 1) == (
        code,
        "S",
        change.pct_before,
        Decimal("50.00"),
        cuota - half,
    )


def _correction_rows(
    resolution: CalculationSourceResolution, regime: Regime
) -> list[tuple[str, int, str, str, Decimal]]:
    revision = published_revision("369", regime.revision_id)
    rows = []
    for country, year, period_type, period, cuota in record_row_slots(revision, _CORRECTION_RECORD[regime]):
        if country in resolution.enum_binding_values:
            rows.append(
                (
                    resolution.enum_binding_values[country],
                    int(resolution.binding_values[year]),
                    resolution.enum_binding_values[period_type],
                    resolution.enum_binding_values[period],
                    resolution.binding_values[cuota],
                )
            )
    return rows


def _resolve_corrections(
    operation: PinnedAuthorityOperation, regime: Regime, *invoices: Invoice, on: date
) -> CalculationSourceResolution:
    return resolve(operation, regime, invoices, period=regime.period(on))


def _regime_first(regime: Regime, day: date) -> Invoice:
    return oss_detail_sections_invoice(
        regime, "F-1", country="FR", tier="general", base="1000.00", cuota="200.00", supply_date=day
    )


def _regime_correction(regime: Regime, day: date, *, number: str = "R-1", cuota: str = "20.00") -> Invoice:
    base = str(Decimal(cuota) * 5)
    return oss_detail_sections_invoice(
        regime, number, country="FR", tier="general", base=base, cuota=cuota, supply_date=day
    ).model_copy(
        update={
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "counterparty_tax_id": _CUSTOMER,
            "rectifies_invoice_number": "F-1",
        }
    )


@pytest.mark.parametrize(
    ("regime", "later", "period_type", "period"),
    [
        (EXTERIOR, _LATER_QUARTER, "T", "1"),
        (UNION, _LATER_QUARTER, "T", "1"),
        (IMPORT, date(_YEAR, 3, 4), "M", "2"),
    ],
    ids=["exterior", "union", "import"],
)
def test_a_correction_of_an_earlier_period_takes_a_row_of_that_period_below_zero(
    operation: PinnedAuthorityOperation, regime: Regime, later: date, period_type: str, period: str
) -> None:
    """F-1's 200,00 is filed; R-1 takes 20,00 off it, so the later return states -20,00 for the earlier period."""
    resolution = _resolve_corrections(
        operation, regime, _regime_first(regime, _SUPPLY), _regime_correction(regime, later), on=later
    )
    assert _correction_rows(resolution, regime) == [("FR", _YEAR, period_type, period, Decimal("-20.00"))]


def test_corrections_of_one_period_net_into_one_row_and_of_another_take_their_own(
    operation: PinnedAuthorityOperation,
) -> None:
    """R-1 -20,00 and R-2 -5,00 name F-1 of 1T; R-3 -10,00 names F-3 of 4T of the year before."""
    previous = date(_YEAR - 1, 11, 17)
    resolution = _resolve_corrections(
        operation,
        UNION,
        _regime_first(UNION, _SUPPLY),
        _regime_correction(UNION, _LATER_QUARTER),
        _regime_correction(UNION, _LATER_QUARTER, number="R-2", cuota="5.00"),
        oss_detail_sections_invoice(
            UNION, "F-3", country="FR", tier="general", base="100.00", cuota="20.00", supply_date=previous
        ),
        _regime_correction(UNION, _LATER_QUARTER, number="R-3", cuota="10.00").model_copy(
            update={"rectifies_invoice_number": "F-3"}
        ),
        on=_LATER_QUARTER,
    )
    assert _correction_rows(resolution, UNION) == [
        ("FR", _YEAR - 1, "T", "4", Decimal("-10.00")),
        ("FR", _YEAR, "T", "1", Decimal("-25.00")),
    ]


def test_a_correction_issued_in_the_period_of_its_invoice_stays_on_the_row(operation: PinnedAuthorityOperation) -> None:
    resolution = _resolve_corrections(
        operation, UNION, _regime_first(UNION, _SUPPLY), _regime_correction(UNION, _SUPPLY), on=_SUPPLY
    )
    assert _correction_rows(resolution, UNION) == []


def test_a_correction_issued_before_its_invoice_refuses(operation: PinnedAuthorityOperation) -> None:
    assert (
        _refusal(operation, _regime_first(UNION, _LATER_QUARTER), _regime_correction(UNION, _SUPPLY), on=_SUPPLY)
        == "aggregation.oss_ioss.errors.rectificativa_target_later"
    )


def test_corrections_of_one_invoice_refuse_together_above_what_it_declared(operation: PinnedAuthorityOperation) -> None:
    """150,00 and 60,00 each fit F-1's 200,00; together they do not."""
    assert (
        _refusal(
            operation,
            _regime_first(UNION, _SUPPLY),
            _regime_correction(UNION, _LATER_QUARTER, cuota="150.00"),
            _regime_correction(UNION, _LATER_QUARTER, number="R-2", cuota="60.00"),
            on=_LATER_QUARTER,
        )
        == "aggregation.oss_ioss.errors.rectificativa_above_row"
    )


@pytest.mark.parametrize(
    ("regime", "corrected", "last_inside", "first_outside"),
    [
        # 1T closed on 30 April, so the limit three years on is 30 April: 1T is filed from 1 April, 2T from 1 July.
        (UNION, date(_YEAR - _RETURN_AGE_LIMIT, 2, 17), date(_YEAR, 2, 17), date(_YEAR, 5, 4)),
        # February closed on 31 March, so the limit three years on is 31 March: 02 is filed from 1 March, 03 from 1 April.
        (IMPORT, date(_YEAR - _RETURN_AGE_LIMIT, 2, 17), date(_YEAR, 2, 17), date(_YEAR, 3, 4)),
    ],
    ids=["quarter", "month"],
)
def test_the_three_year_limit_counts_from_the_close_of_the_corrected_return(
    operation: PinnedAuthorityOperation, regime: Regime, corrected: date, last_inside: date, first_outside: date
) -> None:
    resolution = _resolve_corrections(
        operation, regime, _regime_first(regime, corrected), _regime_correction(regime, last_inside), on=last_inside
    )
    assert _correction_rows(resolution, regime)[0][4] == Decimal("-20.00")
    with pytest.raises(AggregationValidationError) as refused:
        _resolve_corrections(
            operation,
            regime,
            _regime_first(regime, corrected),
            _regime_correction(regime, first_outside),
            on=first_outside,
        )
    assert str(refused.value.translated_message) == "aggregation.oss_ioss.errors.correction_beyond_limit"


def test_a_foreign_currency_correction_of_an_earlier_period_refuses(operation: PinnedAuthorityOperation) -> None:
    corrected = _regime_correction(UNION, _LATER_QUARTER).model_copy(update={"currency": "PLN"})
    assert (
        _refusal(operation, _regime_first(UNION, _SUPPLY), corrected, on=_LATER_QUARTER)
        == "aggregation.oss_ioss.errors.correction_currency_unsourced"
    )


def _entered_row(
    operation: PinnedAuthorityOperation, regime: Regime, *, year: int, period_type: str, period: str
) -> CalculationSourceResolution:
    revision = published_revision("369", regime.revision_id)
    country_slot, year_slot, type_slot, period_slot, cuota_slot = record_row_slots(
        revision, _CORRECTION_RECORD[regime]
    )[0]
    filed = regime.period(_LATER_QUARTER)
    return OssIossLedgerSourceResolver(
        ports=InvoiceCatalogueReadPorts(invoice_reader=Reader(()), transaction_reader=Transactions())
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET,
            work_unit_id="a" * 64,
            modelo="369",
            filing_year=filed.filing_year,
            period=filed,
            revision=revision,
            operation=operation,
            caller_binding_values={year_slot: Decimal(year), cuota_slot: Decimal("15.00")},
            caller_enum_binding_values={country_slot: "PL", type_slot: period_type, period_slot: period},
        )
    )


@pytest.mark.parametrize(
    ("year", "period_type", "period", "reason"),
    [
        (_YEAR, "T", "2", "correction_row_invalid"),
        (_YEAR, "M", "1", "correction_row_invalid"),
        (_YEAR, "T", "9", "correction_row_invalid"),
        (_YEAR - _RETURN_AGE_LIMIT, "T", "1", "correction_beyond_limit"),
    ],
    ids=["same-period", "wrong-type", "no-such-period", "beyond-limit"],
)
def test_an_entered_row_the_return_cannot_file_refuses(
    operation: PinnedAuthorityOperation, year: int, period_type: str, period: str, reason: str
) -> None:
    with pytest.raises(AggregationValidationError) as refused:
        _entered_row(operation, UNION, year=year, period_type=period_type, period=period)
    assert str(refused.value.translated_message) == f"aggregation.oss_ioss.errors.{reason}"


def test_an_entered_row_of_an_earlier_period_stands(operation: PinnedAuthorityOperation) -> None:
    resolution = _entered_row(operation, UNION, year=_YEAR, period_type="T", period="1")
    assert _correction_rows(resolution, UNION) == []


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
    period = IMPORT.period(_SUPPLY)
    first = oss_detail_sections_invoice(IMPORT, "F-1", country="FR", tier="general", base="150.00", cuota="30.00")
    corrected = oss_detail_sections_invoice(
        IMPORT, "R-1", country="FR", tier="general", base="50.00", cuota="10.00"
    ).model_copy(
        update={
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "counterparty_tax_id": _CUSTOMER,
            "rectifies_invoice_number": "F-1",
        }
    )
    resolution = resolve(operation, IMPORT, (first, corrected), period=period)
    assert oss_detail_sections_row(resolution, IMPORT, 1) == (
        "FR",
        "S",
        Decimal("20"),
        Decimal("100.00"),
        Decimal("20.00"),
    )


def test_frances_second_reduced_rate_takes_its_own_reduced_row(operation: PinnedAuthorityOperation) -> None:
    resolution = resolve(
        operation,
        UNION,
        (
            oss_detail_sections_invoice(UNION, "F-1", country="FR", tier="reduced", base="100.00", cuota="5.50"),
            oss_detail_sections_invoice(UNION, "F-2", country="FR", tier="reduced", base="200.00", cuota="20.00"),
        ),
    )
    assert {oss_detail_sections_row(resolution, UNION, row) for row in (1, 2)} == {
        ("FR", "R", Decimal("10"), Decimal("200.00"), Decimal("20.00")),
        ("FR", "R", Decimal("5.5"), Decimal("100.00"), Decimal("5.50")),
    }


def test_frances_super_reduced_rate_is_written_as_reduced(operation: PinnedAuthorityOperation) -> None:
    """DR369's code is binary, S:Estandar or R:Reducido, and 2,1 is not the standard rate."""
    on = date(_YEAR, 7, 20)
    resolution = resolve(
        operation,
        UNION,
        (
            oss_detail_sections_invoice(
                UNION, "F-1", country="FR", tier="super_reduced", base="100.00", cuota="2.10", supply_date=on
            ),
        ),
        period=UNION.period(on),
    )
    assert oss_detail_sections_row(resolution, UNION, 1) == (
        "FR",
        "R",
        Decimal("2.1"),
        Decimal("100.00"),
        Decimal("2.10"),
    )


def test_a_cuota_matching_no_rate_of_the_tier_still_refuses(operation: PinnedAuthorityOperation) -> None:
    invoice = oss_detail_sections_invoice(UNION, "F-1", country="FR", tier="reduced", base="100.00", cuota="7.00")
    assert _refusal(operation, invoice) == "aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate"


def test_a_cuota_two_rates_of_the_tier_both_explain_refuses(operation: PinnedAuthorityOperation) -> None:
    """0,10 at 5,5 and at 10 both round to 0,01, so the row's rate is not known."""
    invoice = oss_detail_sections_invoice(UNION, "F-1", country="FR", tier="reduced", base="0.10", cuota="0.01")
    assert _refusal(operation, invoice) == "aggregation.oss_ioss.errors.rate_tier_ambiguous"


def _eprs_table_day(operation: PinnedAuthorityOperation) -> date:
    """The day the typed table is dated: the registry publishes it from the day Germany's ordinary rate starts."""
    return min(
        variant.valid_from for variant in ordinary_general_variants(operation)["de"] if variant.valid_from is not None
    )


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
def test_every_reduced_rate_of_the_eprs_table_is_held(
    operation: PinnedAuthorityOperation, state: str, rates: set[str]
) -> None:
    on = _eprs_table_day(operation)
    member, tier = EUMemberState.from_registry(state), IvaRateKind("reduced")
    held = {lookup_rate(member, tier, on, operation=operation).pct}
    held |= {rate.pct for rate in coexisting_tier_rates(member, tier, on, operation=operation)}
    assert held == {Decimal(rate) for rate in rates}


@pytest.mark.parametrize(
    ("state", "tier", "pct"),
    [
        ("ee", "general", "22"),
        ("fi", "general", "25.5"),
        ("ee", "reduced", "13"),
    ],
)
def test_a_rate_the_national_pages_date_earlier_is_published_from_that_date(
    operation: PinnedAuthorityOperation, state: str, tier: str, pct: str
) -> None:
    on = _first_day_of_rate(operation, state, tier, pct)
    assert on < _eprs_table_day(operation), "the rate predates the table, so only the national pages date it"
    record = lookup_rate(EUMemberState.from_registry(state), IvaRateKind(tier), on, operation=operation)
    assert record.pct == Decimal(pct)
    assert record.published_on_date


def _first_day_of_rate(operation: PinnedAuthorityOperation, state: str, tier: str, pct: str) -> date:
    """The first day the registry publishes ``pct`` as ``state``'s rate of ``tier``."""
    starts = [
        variant.valid_from
        for variant in operation.governed_fact(IVA_RATE_FACT_ID).variants
        if {selector.name: selector.value for selector in variant.selectors}.get("member_state") == state
        and {selector.name: selector.value for selector in variant.selectors}.get("kind") == tier
        and variant_pct(variant) == Decimal(pct)
        and variant.valid_from is not None
    ]
    return min(starts)


def _before_french_general(operation: PinnedAuthorityOperation) -> date:
    earliest = min(
        variant.valid_from for variant in ordinary_general_variants(operation)["fr"] if variant.valid_from is not None
    )
    return earliest - timedelta(days=1)


def test_a_figure_matching_a_projected_rate_is_accepted_with_a_warning(operation: PinnedAuthorityOperation) -> None:
    uncovered = _before_french_general(operation)
    resolution = resolve(
        operation,
        UNION,
        (
            oss_detail_sections_invoice(
                UNION, "F-1", country="FR", tier="general", base="100.00", cuota="20.00", supply_date=uncovered
            ),
        ),
        period=UNION.period(uncovered),
    )
    assert oss_detail_sections_row(resolution, UNION, 1) == (
        "FR",
        "S",
        Decimal("20"),
        Decimal("100.00"),
        Decimal("20.00"),
    )
    warnings = [item for item in resolution.diagnostics if item.source_ref == "rate_date_projected"]
    assert len(warnings) == 1
    assert warnings[0].reason == "source_issue"


def test_a_figure_differing_from_a_projected_rate_is_a_coverage_gap_not_a_mismatch(
    operation: PinnedAuthorityOperation,
) -> None:
    uncovered = _before_french_general(operation)
    with pytest.raises(IvaRateNotFoundError) as refused:
        resolve(
            operation,
            UNION,
            (
                oss_detail_sections_invoice(
                    UNION, "F-1", country="FR", tier="general", base="100.00", cuota="19.60", supply_date=uncovered
                ),
            ),
            period=UNION.period(uncovered),
        )
    assert refused.value.context is not None
    assert refused.value.context["rate_registry_covers_date"] is False


def test_a_correction_two_invoices_could_answer_refuses(operation: PinnedAuthorityOperation) -> None:
    """Two F-1 in different series could each be the one named, and the record cannot say which."""
    other = oss_detail_sections_invoice(UNION, "F-1", country="FR", tier="general", base="500.00", cuota="100.00")
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
    return oss_detail_sections_invoice(
        UNION, f"N-{number}", country="NL", tier="general", base=base, cuota=cuota
    ).model_copy(update={"currency": currency})


def test_a_foreign_currency_row_converts_at_the_level_of_the_row(operation: PinnedAuthorityOperation) -> None:
    """1.000 x USD 1,00 + 0,21 at 0,9195 and 21: base 919,50, cuota 919,50 x 0,21 = 193,095, so 193,10.

    Rounding each line first gives 0,92 and 0,19, so 920,00 and 190,00, a cuota that is not
    21 of its own base.
    """
    invoices = tuple(_dutch(number, currency="USD", base="1.00", cuota="0.21") for number in range(1000))
    with bind_exchange_rate_provider_factory(_Quote):
        resolution = resolve(operation, UNION, invoices)
    assert oss_detail_sections_row(resolution, UNION, 1) == (
        "NL",
        "S",
        Decimal("21"),
        Decimal("919.50"),
        Decimal("193.10"),
    )


def test_a_euro_row_declares_its_cuota_at_its_own_rate(operation: PinnedAuthorityOperation) -> None:
    """100 x 0,99 + 0,21: base 99,00, cuota 99,00 x 0,21 = 20,79, where the lines would add up to 21,00."""
    invoices = tuple(_dutch(number, currency="EUR", base="0.99", cuota="0.21") for number in range(100))
    resolution = resolve(operation, UNION, invoices)
    assert oss_detail_sections_row(resolution, UNION, 1) == (
        "NL",
        "S",
        Decimal("21"),
        Decimal("99.00"),
        Decimal("20.79"),
    )
