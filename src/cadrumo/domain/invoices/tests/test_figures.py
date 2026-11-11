"""The figures owner and the Invoice validators give one answer.

Expected figures are worked by hand in the comments or come from the statute a
rate slot names, never from a run of the code under test.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...iva.schema import InvoiceKind
from ..enums import IvaRate, PaymentStatus
from ..errors import InvoiceValidationError
from ..figures import (
    DatedRateSlot,
    FigureFinding,
    FigureFindingCode,
    FigureFindingSeverity,
    StatedFigureVerdict,
    compute_invoice_figures,
    compute_line_figures,
    dated_rate_slots,
    figure_refusal,
    line_iva_finding,
    line_subtotal_finding,
    printed_total_finding,
    retention_findings,
    settlement_amount,
)
from ..models import Invoice, InvoiceLine
from .invoice_catalogue_seed import STANDING_DEVENGO, window_middle

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _slot(token: str, fraction: str | None) -> DatedRateSlot:
    return DatedRateSlot(IvaRate.from_registry(token), None if fraction is None else Decimal(fraction), in_force=True)


def _codes(findings: tuple[FigureFinding, ...]) -> list[FigureFindingCode]:
    return [finding.code for finding in findings]


def _refusal_context(error: ValidationError) -> Mapping[str, object]:
    for detail in error.errors():
        cause = getattr(detail.get("ctx", {}).get("error"), "__cause__", None)
        if isinstance(cause, InvoiceValidationError) and cause.context is not None:
            return cause.context
    raise AssertionError("the refusal carries no registered invoice failure")


def _line(
    *,
    subtotal: str = "100.00",
    iva_amount: str = "21.00",
    slot: str = "RATE_21",
    quantity: str = "1",
    unit_price: str = "100.00",
) -> InvoiceLine:
    return InvoiceLine(
        description="Synthetic service",
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        subtotal=Decimal(subtotal),
        iva_rate=IvaRate.from_registry(slot),
        iva_amount=Decimal(iva_amount),
    )


def _invoice(lines: tuple[InvoiceLine, ...], **overrides: object) -> Invoice:
    base = sum((line.subtotal for line in lines), Decimal("0"))
    iva = sum((line.iva_amount for line in lines), Decimal("0"))
    recargo = overrides.get("recargo_amount")
    payload: dict[str, object] = {
        "bucket_id": None,
        "kind": InvoiceKind.RECEIVED.value,
        "invoice_number": "SYN-1",
        "issued_at": STANDING_DEVENGO.isoformat(),
        "counterparty_name": "Synthetic supplier",
        "counterparty_tax_id": "B00010157",
        "counterparty_country": "ES",
        "base_total": str(base),
        "iva_total": str(iva),
        "grand_total": str(base + iva + (Decimal(str(recargo)) if recargo is not None else Decimal("0"))),
        "currency": "EUR",
        "payment_status": PaymentStatus.PENDING.value,
        "lines": [line.model_dump(mode="json") for line in lines],
    }
    payload.update(overrides)
    return Invoice.model_validate(payload)


@pytest.mark.parametrize(
    ("subtotal", "accepted"),
    (
        ("100.00", True),
        ("100.01", True),  # exactly one cent above 1 x 100.00
        ("99.99", True),  # exactly one cent below
        ("100.02", False),
        ("99.98", False),
        ("100.0100", True),
        ("100.0101", False),  # one hundredth of a cent beyond the slack
    ),
)
def test_line_subtotal_boundary_at_one_cent(subtotal: str, accepted: bool) -> None:
    rule = line_subtotal_finding(Decimal("1"), Decimal("100.00"), Decimal(subtotal))
    assert (rule is None) is accepted
    if accepted:
        assert _line(subtotal=subtotal, iva_amount="21.00").subtotal == Decimal(subtotal)
        return
    assert rule is not None
    assert rule.code is FigureFindingCode.LINE_SUBTOTAL_MISMATCH
    with pytest.raises(ValidationError) as refused:
        _line(subtotal=subtotal, iva_amount="21.00")
    assert _refusal_context(refused.value)["finding_code"] == FigureFindingCode.LINE_SUBTOTAL_MISMATCH.value


@pytest.mark.parametrize(
    ("iva_amount", "accepted"),
    (
        ("21.00", True),
        ("21.01", True),  # one cent above 100.00 x 0.21 = 21.00
        ("20.99", True),
        ("21.02", False),
        ("20.98", False),
    ),
)
def test_line_iva_boundary_at_one_cent_on_a_real_invoice(iva_amount: str, accepted: bool) -> None:
    rule = line_iva_finding(Decimal("100.00"), Decimal(iva_amount), Decimal("0.21"))
    assert (rule is None) is accepted
    line = _line(iva_amount=iva_amount)
    if accepted:
        assert _invoice((line,)).lines[0].iva_amount == Decimal(iva_amount)
        return
    with pytest.raises(ValidationError) as refused:
        _invoice((line,))
    assert _refusal_context(refused.value)["finding_code"] == FigureFindingCode.LINE_IVA_MISMATCH.value


@pytest.mark.parametrize(
    ("amount", "accepted"),
    (
        # 100.50 x 0.155 = 15.5 + 0.0775 = 15.5775, compared unrounded.
        ("15.58", True),  # 0.0025 away
        ("15.5875", True),  # exactly 0.0100 away
        ("15.5675", True),  # exactly 0.0100 away on the other side
        ("15.59", False),  # 0.0125 away: a window comparing with a rounded 15.58 would pass it
        ("15.56", False),  # 0.0175 away
    ),
)
def test_retention_is_compared_with_the_unrounded_product(amount: str, accepted: bool) -> None:
    findings = retention_findings(Decimal("0.155"), Decimal(amount), Decimal("100.50"))
    assert (not findings) is accepted
    # 1 x 100.50 at 21 %: 21.105, which a stated 21.11 keeps within its cent.
    line = _line(subtotal="100.50", unit_price="100.50", iva_amount="21.11")
    if accepted:
        assert _invoice((line,), retention_rate="0.155", retention_amount=amount).retention_amount == Decimal(amount)
        return
    assert _codes(findings) == [FigureFindingCode.RETENTION_AMOUNT_MISMATCH]
    with pytest.raises(ValidationError) as refused:
        _invoice((line,), retention_rate="0.155", retention_amount=amount)
    assert _refusal_context(refused.value)["fields"] == ("retention_rate", "retention_amount", "base_total")


@pytest.mark.parametrize(
    ("rate", "amount", "base", "codes"),
    (
        (None, "99", "100", []),  # an amount may stand alone
        (None, "100", "100", []),
        (None, "100.01", "100", [FigureFindingCode.RETENTION_AMOUNT_ABOVE_BASE]),
        (None, "-1", "100", [FigureFindingCode.RETENTION_AMOUNT_NEGATIVE]),
        ("0.15", None, "100", [FigureFindingCode.RETENTION_RATE_WITHOUT_AMOUNT]),
        (
            "15",
            "15",
            "100",
            [FigureFindingCode.RETENTION_RATE_OUT_OF_RANGE, FigureFindingCode.RETENTION_AMOUNT_MISMATCH],
        ),
        (
            "-0.01",
            "0",
            "100",
            [FigureFindingCode.RETENTION_RATE_OUT_OF_RANGE, FigureFindingCode.RETENTION_AMOUNT_MISMATCH],
        ),
        ("1", "100", "100", []),
        ("0.33", "33", "100", []),  # shape and agreement only: no dated RIRPF rate is consulted
    ),
)
def test_retention_rules_in_refusal_order(
    rate: str | None, amount: str | None, base: str, codes: list[FigureFindingCode]
) -> None:
    findings = retention_findings(
        None if rate is None else Decimal(rate),
        None if amount is None else Decimal(amount),
        Decimal(base),
    )
    assert _codes(findings) == codes


def test_an_unknown_base_leaves_only_the_checks_that_need_no_base() -> None:
    assert retention_findings(Decimal("0.15"), Decimal("99"), None) == ()
    assert _codes(retention_findings(Decimal("15"), None, None)) == [
        FigureFindingCode.RETENTION_RATE_OUT_OF_RANGE,
        FigureFindingCode.RETENTION_RATE_WITHOUT_AMOUNT,
    ]


@pytest.mark.parametrize(
    ("recargo", "accepted", "code"),
    (
        ("5.20", True, None),  # 5.2 % of 100.00 against a 21.00 cuota
        ("21.00", True, None),  # the generic ceiling is the cuota itself
        ("21.01", False, FigureFindingCode.RECARGO_ABOVE_IVA_TOTAL),
        ("-0.01", False, FigureFindingCode.RECARGO_NEGATIVE),
    ),
)
def test_recargo_ceiling_and_sign_through_the_model(
    recargo: str, accepted: bool, code: FigureFindingCode | None
) -> None:
    figures = compute_invoice_figures(
        lines=(
            compute_line_figures(
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                stated_subtotal=None,
                stated_iva_amount=None,
                slot=_slot("RATE_21", "0.21"),
            ),
        ),
        recargo_amount=Decimal(recargo),
    )
    if accepted:
        assert figures.findings == ()
        assert figures.total == Decimal("121.00") + Decimal(recargo)
        assert _invoice((_line(),), recargo_amount=recargo).grand_total == figures.total
        return
    assert _codes(figures.findings) == [code]
    assert code is not None
    with pytest.raises(ValidationError) as refused:
        _invoice((_line(),), recargo_amount=recargo)
    assert _refusal_context(refused.value)["finding_code"] == code.value


def test_a_nonnumeric_invoice_bears_no_cuota_and_no_recargo() -> None:
    line = compute_line_figures(
        quantity=Decimal("2"),
        unit_price=Decimal("50.00"),
        stated_subtotal=None,
        stated_iva_amount=None,
        slot=_slot("EXEMPT", None),
    )
    # A proven zero, distinct from the None an unknown cuota carries.
    assert line.iva_amount.computed == Decimal("0")
    assert line.subtotal.computed == Decimal("100.00")
    assert compute_invoice_figures(lines=(line,)).total == Decimal("100.00")

    # A recargo above the zero cuota breaches both the ceiling and the nonnumeric rule.
    refused = compute_invoice_figures(lines=(line,), recargo_amount=Decimal("1"))
    assert FigureFindingCode.NONNUMERIC_RECARGO_NOT_ZERO in _codes(refused.findings)
    exempt = _line(slot="EXEMPT", iva_amount="0")
    with pytest.raises(ValidationError):
        _invoice((exempt,), recargo_amount="1")
    assert _codes(
        compute_line_figures(
            quantity=Decimal("1"),
            unit_price=Decimal("1"),
            stated_subtotal=None,
            stated_iva_amount=Decimal("0.01"),
            slot=_slot("EXEMPT", None),
        ).findings
    ) == [FigureFindingCode.LINE_IVA_NOT_ZERO_FOR_NONNUMERIC]


@pytest.mark.parametrize(
    ("quantity", "unit_price", "slot", "subtotal", "iva"),
    (
        (None, "100.00", _slot, None, None),
        ("1", None, _slot, None, None),
        ("1", "100.00", None, "100.00", None),
        (None, None, None, None, None),
    ),
)
def test_an_incomplete_line_has_null_figures_never_zero(quantity, unit_price, slot, subtotal, iva) -> None:
    line = compute_line_figures(
        quantity=None if quantity is None else Decimal(quantity),
        unit_price=None if unit_price is None else Decimal(unit_price),
        stated_subtotal=None,
        stated_iva_amount=None,
        slot=None if slot is None else _slot("RATE_21", "0.21"),
    )
    assert line.subtotal.computed == (None if subtotal is None else Decimal(subtotal))
    assert line.iva_amount.computed is None
    assert line.iva_amount.submitted is None
    totals = compute_invoice_figures(lines=(line,))
    assert totals.iva_total is None
    assert totals.total is None
    assert totals.net_of_retention is None


def test_half_cent_rounds_up_and_a_stated_figure_keeps_its_own_value() -> None:
    # 1 x 100.50 at 21 % is 21.105, half up 21.11. Half-even would state 21.10.
    computed = compute_line_figures(
        quantity=Decimal("1"),
        unit_price=Decimal("100.50"),
        stated_subtotal=None,
        stated_iva_amount=None,
        slot=_slot("RATE_21", "0.21"),
    )
    assert computed.iva_amount.computed == Decimal("21.11")

    # A printed 21.10 is 0.005 from the product: accepted, stored as printed, and reported with both figures.
    stated = compute_line_figures(
        quantity=Decimal("1"),
        unit_price=Decimal("100.50"),
        stated_subtotal=Decimal("100.51"),
        stated_iva_amount=Decimal("21.10"),
        slot=_slot("RATE_21", "0.21"),
    )
    assert stated.subtotal.verdict is StatedFigureVerdict.WITHIN_TOLERANCE
    assert stated.subtotal.submitted == Decimal("100.51")
    # The cuota is judged on the subtotal that would be stored: 100.51 x 0.21 = 21.1071.
    assert stated.iva_amount.computed == Decimal("21.11")
    assert stated.iva_amount.verdict is StatedFigureVerdict.WITHIN_TOLERANCE
    assert stated.iva_amount.submitted == Decimal("21.10")
    assert compute_invoice_figures(lines=(stated,)).total == Decimal("121.61")


def test_a_refused_stated_figure_keeps_the_backend_figure_and_withholds_the_total() -> None:
    line = compute_line_figures(
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        stated_subtotal=Decimal("100.02"),
        stated_iva_amount=None,
        slot=_slot("RATE_21", "0.21"),
    )
    assert line.subtotal.computed == Decimal("100.00")
    assert line.subtotal.stated == Decimal("100.02")
    assert line.subtotal.verdict is StatedFigureVerdict.REFUSED
    assert line.subtotal.submitted is None
    assert compute_invoice_figures(lines=(line,)).total is None


def test_a_magnitude_beyond_decimal_arithmetic_is_a_finding() -> None:
    line = compute_line_figures(
        quantity=Decimal("1E+30"),
        unit_price=Decimal("100.00"),
        stated_subtotal=None,
        stated_iva_amount=None,
        slot=_slot("RATE_21", "0.21"),
    )
    assert _codes(line.findings) == [FigureFindingCode.FIGURE_OUT_OF_RANGE]
    assert line.subtotal.computed is None


def test_several_rates_sum_exactly_and_settlement_nets_the_retention() -> None:
    # 100.00 at 21 % is 21.00 and 50.00 at 10 % is 5.00: base 150.00, cuota 26.00, total 176.00.
    lines = (
        compute_line_figures(
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            stated_subtotal=None,
            stated_iva_amount=None,
            slot=_slot("RATE_21", "0.21"),
        ),
        compute_line_figures(
            quantity=Decimal("2"),
            unit_price=Decimal("25.00"),
            stated_subtotal=None,
            stated_iva_amount=None,
            slot=_slot("RATE_10", "0.10"),
        ),
    )
    # 150.00 x 0.15 = 22.50 retención, so 176.00 - 22.50 = 153.50 reaches the bank.
    figures = compute_invoice_figures(lines=lines, retention_rate=Decimal("0.15"), retention_amount=Decimal("22.50"))
    assert (figures.base_total, figures.iva_total, figures.total) == (
        Decimal("150.00"),
        Decimal("26.00"),
        Decimal("176.00"),
    )
    assert figures.retention_implied == Decimal("22.50")
    assert figures.net_of_retention == Decimal("153.50")
    assert settlement_amount(Decimal("121.00"), None) == Decimal("121.00")


def test_a_stated_base_gives_the_retention_a_base_and_leaves_the_cuota_unknown() -> None:
    figures = compute_invoice_figures(
        lines=(),
        stated_base_total=Decimal("100.50"),
        retention_rate=Decimal("0.155"),
        retention_amount=Decimal("15.59"),
    )
    assert figures.base_total == Decimal("100.50")
    assert figures.iva_total is None
    assert figures.total is None
    assert figures.retention_implied == Decimal("15.58")
    assert _codes(figures.findings) == [FigureFindingCode.RETENTION_AMOUNT_MISMATCH]


def test_a_differing_printed_total_only_warns() -> None:
    finding = printed_total_finding(Decimal("121.01"), Decimal("121.00"))
    assert finding is not None
    assert finding.code is FigureFindingCode.PRINTED_TOTAL_DIFFERS
    assert finding.severity is FigureFindingSeverity.WARNING
    assert printed_total_finding(Decimal("121.00"), Decimal("121.00")) is None
    assert printed_total_finding(Decimal("121.00"), None) is None


# The fractions are the statutory rates: LIVA art. 90 (21 %) and art. 91 (10 %, 4 %);
# RDL 20/2022 (5 % food, from 2023); RDL 4/2024 (2 % and 7.5 %, second half of 2024).
_STANDING = {"RATE_0": "0", "RATE_4": "0.04", "RATE_10": "0.1", "RATE_21": "0.21"}
_NONNUMERIC = {"EXEMPT", "NOT_SUBJECT"}


@pytest.mark.parametrize(
    ("on_date", "transitional_in_force", "transitional_out"),
    (
        (window_middle("RATE_5"), {"RATE_5": "0.05"}, {"RATE_2", "RATE_7.5"}),
        (window_middle("RATE_2"), {"RATE_2": "0.02", "RATE_7.5": "0.075"}, {"RATE_5"}),
        (STANDING_DEVENGO, {}, {"RATE_2", "RATE_5", "RATE_7.5"}),
    ),
)
def test_each_rate_slot_in_and_out_of_force_through_the_real_authority(
    on_date: date,
    transitional_in_force: dict[str, str],
    transitional_out: set[str],
) -> None:
    slots = {str(slot.slot): slot for slot in dated_rate_slots(on_date)}

    assert set(slots) == set(_STANDING) | _NONNUMERIC | set(transitional_in_force) | transitional_out
    for token, fraction in {**_STANDING, **transitional_in_force}.items():
        assert slots[token].in_force
        assert slots[token].fraction == Decimal(fraction)
    for token in _NONNUMERIC:
        assert slots[token].in_force
        assert slots[token].fraction is None
    for token in transitional_out:
        assert not slots[token].in_force
        assert slots[token].fraction is None
        assert not slots[token].coverage_gap

    for token in transitional_out:
        line = _line(slot=token, iva_amount="0")
        with pytest.raises(ValidationError) as refused:
            _invoice((line,), issued_at=on_date.isoformat())
        assert _refusal_context(refused.value)["finding_code"] == FigureFindingCode.LINE_RATE_NOT_IN_FORCE.value
    for token, fraction in {**_STANDING, **transitional_in_force}.items():
        cuota = str(Decimal("100.00") * Decimal(fraction))
        accepted = _invoice((_line(slot=token, iva_amount=cuota),), issued_at=on_date.isoformat())
        assert accepted.iva_total == Decimal(cuota)


def test_a_date_before_the_filing_years_still_has_its_ordinary_rates_and_no_temporary_ones(
    _authority_operation: PinnedAuthorityOperation,
) -> None:
    envelope = _authority_operation.supported_filing_years().date_envelope()
    before_floor = envelope.floor - timedelta(days=1)
    assert not envelope.admits_coordinate(before_floor)
    slots = {str(slot.slot): slot for slot in dated_rate_slots(before_floor)}
    assert slots["RATE_21"].fraction == Decimal("0.21")
    assert not slots["RATE_5"].in_force


def test_a_finding_becomes_a_refusal_with_its_message_code_and_fields() -> None:
    finding = line_subtotal_finding(Decimal("1"), Decimal("100.00"), Decimal("100.02"))
    assert finding is not None
    refusal = figure_refusal(finding)
    assert str(refusal) == "subtotal must equal quantity * unit_price within 1 cent"
    assert refusal.context == {
        "finding_code": "line_subtotal_mismatch",
        "fields": ("subtotal", "quantity", "unit_price"),
    }


def test_the_totals_identity_is_exact_on_the_model() -> None:
    with pytest.raises(ValidationError) as refused:
        _invoice((_line(),), grand_total="121.01")
    assert _refusal_context(refused.value)["finding_code"] == FigureFindingCode.GRAND_TOTAL_IDENTITY.value
    with pytest.raises(ValidationError) as refused:
        _invoice((_line(),), base_total="100.01", grand_total="121.01")
    assert _refusal_context(refused.value)["finding_code"] == FigureFindingCode.BASE_TOTAL_NOT_LINE_SUM.value
    with pytest.raises(ValidationError) as refused:
        _invoice((_line(),), iva_total="21.01", grand_total="121.01")
    assert _refusal_context(refused.value)["finding_code"] == FigureFindingCode.IVA_TOTAL_NOT_LINE_SUM.value
