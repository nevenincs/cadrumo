"""The one owner of invoice line figures, invoice totals and the retención and recargo rules.

:class:`~cadrumo.domain.invoices.models.Invoice` validators and every preview read
the rules here, so a figure a preview accepts is the figure acceptance accepts.
A rule answers with a :class:`FigureFinding` carrying a stable code rather than
raising, and :func:`figure_refusal` turns that finding into the refusal the
model raises. The document rules outside the figures answer the same way, with
an :class:`~cadrumo.domain.invoices.rule_findings.InvoiceRuleFinding` and
:func:`~cadrumo.domain.invoices.rule_findings.invoice_rule_refusal`.

Stated figures stay the operator's: a line subtotal or cuota within its cent is
accepted as printed and stored as printed. A computed figure is what the backend
would state when the document states nothing. An absent input yields no figure
at all, which is never the same as zero: the only computed zero is the cuota of
a slot the registry declares nonnumeric.

One cent is the slack for the line products and for a retención, because each is
a rate applied to a base and the recorded figure legitimately differs from the
recomputed product in the last cent depending on where the issuer rounded. The
invoice totals are compared exactly, because each is a sum of line figures that
were themselves already rounded to the cent.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, DecimalException
from enum import StrEnum
from typing import Final

from ...core.money.rounding import CENT, round_to_cents
from ..iva.errors import IvaRateNotFoundError
from .enums import IvaRate, iva_rate_percentage, iva_rate_slots_on
from .errors import InvoiceRetentionFigureError, InvoiceValidationError

_ZERO: Final = Decimal("0")
_ONE: Final = Decimal("1")
_COMPARISON_SCALE: Final = Decimal("0.0001")


class FigureFindingCode(StrEnum):
    """Stable, closed names of what a figure rule found."""

    LINE_QUANTITY_NOT_POSITIVE = "line_quantity_not_positive"
    LINE_AMOUNT_NEGATIVE = "line_amount_negative"
    LINE_SUBTOTAL_MISMATCH = "line_subtotal_mismatch"
    LINE_RATE_UNDECLARED = "line_rate_undeclared"
    LINE_RATE_NOT_IN_FORCE = "line_rate_not_in_force"
    LINE_RATE_COVERAGE_GAP = "line_rate_coverage_gap"
    LINE_IVA_MISMATCH = "line_iva_mismatch"
    LINE_IVA_NOT_ZERO_FOR_NONNUMERIC = "line_iva_not_zero_for_nonnumeric"
    FIGURE_OUT_OF_RANGE = "figure_out_of_range"
    RATE_DATE_UNRESOLVED = "rate_date_unresolved"
    RATE_DATE_PROJECTED = "rate_date_projected"
    TOTAL_NEGATIVE = "total_negative"
    BASE_TOTAL_NOT_LINE_SUM = "base_total_not_line_sum"
    IVA_TOTAL_NOT_LINE_SUM = "iva_total_not_line_sum"
    GRAND_TOTAL_IDENTITY = "grand_total_identity"
    NONNUMERIC_IVA_TOTAL_NOT_ZERO = "nonnumeric_iva_total_not_zero"
    NONNUMERIC_RECARGO_NOT_ZERO = "nonnumeric_recargo_not_zero"
    NONNUMERIC_GRAND_TOTAL_IDENTITY = "nonnumeric_grand_total_identity"
    RECARGO_NEGATIVE = "recargo_negative"
    RECARGO_ABOVE_IVA_TOTAL = "recargo_above_iva_total"
    SUPLIDO_NEGATIVE = "suplido_negative"
    RETENTION_AMOUNT_NEGATIVE = "retention_amount_negative"
    RETENTION_RATE_OUT_OF_RANGE = "retention_rate_out_of_range"
    RETENTION_RATE_WITHOUT_AMOUNT = "retention_rate_without_amount"
    RETENTION_AMOUNT_ABOVE_BASE = "retention_amount_above_base"
    RETENTION_AMOUNT_MISMATCH = "retention_amount_mismatch"
    PRINTED_TOTAL_DIFFERS = "printed_total_differs"


_RETENTION_FINDING_CODES: Final = frozenset(
    {
        FigureFindingCode.RETENTION_AMOUNT_NEGATIVE,
        FigureFindingCode.RETENTION_RATE_OUT_OF_RANGE,
        FigureFindingCode.RETENTION_RATE_WITHOUT_AMOUNT,
        FigureFindingCode.RETENTION_AMOUNT_ABOVE_BASE,
        FigureFindingCode.RETENTION_AMOUNT_MISMATCH,
    }
)


class FigureFindingSeverity(StrEnum):
    """Whether a finding stops acceptance or only informs the person."""

    REFUSAL = "refusal"
    WARNING = "warning"


class StatedFigureVerdict(StrEnum):
    """What the backend's check said about a figure the document states."""

    EQUAL = "equal"
    WITHIN_TOLERANCE = "within_tolerance"
    REFUSED = "refused"
    NOT_CHECKED = "not_checked"


@dataclass(frozen=True, slots=True)
class FigureFinding:
    """One rule's answer, with the fields it concerns and the values it compared."""

    code: FigureFindingCode
    message: str
    fields: tuple[str, ...]
    severity: FigureFindingSeverity = FigureFindingSeverity.REFUSAL
    values: Mapping[str, Decimal | str] = field(default_factory=dict[str, Decimal | str])


def figure_refusal(finding: FigureFinding) -> InvoiceValidationError:
    """Return the refusal a validator raises for ``finding``, carrying its stable code."""
    refusal_type = InvoiceRetentionFigureError if finding.code in _RETENTION_FINDING_CODES else InvoiceValidationError
    return refusal_type(
        finding.message,
        context={"finding_code": finding.code.value, "fields": finding.fields},
    )


def raise_first_figure_finding(findings: Iterable[FigureFinding | None]) -> None:
    """Raise the refusal of the first present finding, in the order given."""
    for finding in findings:
        if finding is not None:
            raise figure_refusal(finding)


def _beyond_a_cent(stated: Decimal, expected: Decimal) -> bool:
    return abs(stated - expected) > CENT


def quantity_finding(quantity: Decimal) -> FigureFinding | None:
    """A line's quantity is strictly positive."""
    if quantity <= _ZERO:
        return FigureFinding(
            FigureFindingCode.LINE_QUANTITY_NOT_POSITIVE,
            "quantity must be strictly positive",
            ("quantity",),
        )
    return None


def line_amount_finding(amount: Decimal, *, field_name: str = "amount") -> FigureFinding | None:
    """A line's price, subtotal and cuota are non-negative magnitudes."""
    if amount < _ZERO:
        return FigureFinding(
            FigureFindingCode.LINE_AMOUNT_NEGATIVE,
            "monetary value must be non-negative",
            (field_name,),
        )
    return None


def expected_line_subtotal(quantity: Decimal, unit_price: Decimal) -> Decimal:
    """Return the product a stated subtotal is compared with."""
    return (quantity * unit_price).quantize(_COMPARISON_SCALE)


def line_subtotal_finding(quantity: Decimal, unit_price: Decimal, subtotal: Decimal) -> FigureFinding | None:
    """A stated subtotal stays within a cent of quantity times unit price."""
    expected = expected_line_subtotal(quantity, unit_price)
    if _beyond_a_cent(subtotal, expected):
        return FigureFinding(
            FigureFindingCode.LINE_SUBTOTAL_MISMATCH,
            "subtotal must equal quantity * unit_price within 1 cent",
            ("subtotal", "quantity", "unit_price"),
            values={"expected": expected, "stated": subtotal},
        )
    return None


def expected_line_iva(subtotal: Decimal, rate: Decimal) -> Decimal:
    """Return the product a stated cuota is compared with."""
    return (subtotal * rate).quantize(_COMPARISON_SCALE)


def line_iva_finding(subtotal: Decimal, iva_amount: Decimal, rate: Decimal | None) -> FigureFinding | None:
    """A stated cuota is zero on a nonnumeric slot and otherwise within a cent of the product."""
    if rate is None:
        if iva_amount != _ZERO:
            return FigureFinding(
                FigureFindingCode.LINE_IVA_NOT_ZERO_FOR_NONNUMERIC,
                "iva_amount must be zero for nonnumeric IVA lines",
                ("iva_amount", "iva_rate"),
                values={"stated": iva_amount},
            )
        return None
    expected = expected_line_iva(subtotal, rate)
    if _beyond_a_cent(iva_amount, expected):
        return FigureFinding(
            FigureFindingCode.LINE_IVA_MISMATCH,
            "iva_amount must equal subtotal * iva_rate within 1 cent",
            ("iva_amount", "subtotal", "iva_rate"),
            values={"expected": expected, "stated": iva_amount},
        )
    return None


def rate_refusal_is_coverage_gap(cause: IvaRateNotFoundError) -> bool:
    """Tell a refusal on our registry's reach from one on the law, by its machine fact."""
    return (cause.context or {}).get("rate_registry_covers_date") is False


def rate_refusal_finding(
    rate: IvaRate,
    on_date: date,
    *,
    coverage_gap: bool,
    cause: IvaRateNotFoundError | None = None,
) -> FigureFinding:
    """Name why a slot yields no rate on a date, keeping our coverage apart from the law.

    A coverage gap says nothing about Spanish law, so it never claims the rate was
    out of force.
    """
    claim = "is not covered by the rate registry on" if coverage_gap else "was not in force on"
    reason = "" if cause is None else f": {cause}"
    return FigureFinding(
        FigureFindingCode.LINE_RATE_COVERAGE_GAP if coverage_gap else FigureFindingCode.LINE_RATE_NOT_IN_FORCE,
        f"line rate {rate.name} {claim} {on_date.isoformat()}{reason}",
        ("iva_rate",),
        values={"slot": str(rate), "on_date": on_date.isoformat()},
    )


def computed_line_subtotal(quantity: Decimal, unit_price: Decimal) -> Decimal:
    """Return the subtotal the backend states for a line, at the cent."""
    return round_to_cents(quantity * unit_price)


def computed_line_iva(base: Decimal, rate: Decimal | None) -> Decimal:
    """Return the cuota the backend states on ``base``, zero only for a nonnumeric slot."""
    return _ZERO if rate is None else round_to_cents(base * rate)


def rounded_line_totals(subtotals: Sequence[Decimal], iva_amounts: Sequence[Decimal]) -> tuple[Decimal, Decimal]:
    """Return the invoice base and cuota totals summed from its lines, at the cent."""
    return round_to_cents(_exact_sum(subtotals)), round_to_cents(_exact_sum(iva_amounts))


def _exact_sum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, start=_ZERO)


def computed_grand_total(base_total: Decimal, iva_total: Decimal, recargo: Decimal | None) -> Decimal:
    """Return the total: recargo rides inside it, and a retención stays outside."""
    return base_total + iva_total + (recargo or _ZERO)


def settlement_amount(grand_total: Decimal, retention_amount: Decimal | None) -> Decimal:
    """Return the cash an invoice settles for.

    A retención is withheld at source, so the cash that moves is the total less
    the withheld figure; the total itself never reaches the bank.
    """
    return grand_total - (retention_amount or _ZERO)


def total_sign_finding(total: Decimal) -> FigureFinding | None:
    """An invoice total is a non-negative magnitude."""
    if total < _ZERO:
        return FigureFinding(
            FigureFindingCode.TOTAL_NEGATIVE,
            "invoice totals must be non-negative",
            ("total",),
        )
    return None


def invoice_total_findings(
    *,
    base_total: Decimal,
    iva_total: Decimal,
    grand_total: Decimal,
    line_subtotals: Sequence[Decimal],
    line_iva_amounts: Sequence[Decimal],
    recargo: Decimal | None,
    suplido: Decimal | None,
) -> tuple[FigureFinding, ...]:
    """Compare each stored total with its exact identity, in the order they are refused."""
    findings: list[FigureFinding] = []
    if base_total != _exact_sum(line_subtotals):
        findings.append(
            FigureFinding(
                FigureFindingCode.BASE_TOTAL_NOT_LINE_SUM,
                "base_total must equal the exact sum of line subtotals",
                ("base_total", "lines"),
            )
        )
    if iva_total != _exact_sum(line_iva_amounts):
        findings.append(
            FigureFinding(
                FigureFindingCode.IVA_TOTAL_NOT_LINE_SUM,
                "iva_total must equal the exact sum of line iva amounts",
                ("iva_total", "lines"),
            )
        )
    if grand_total != base_total + iva_total + (recargo or _ZERO) + (suplido or _ZERO):
        findings.append(
            FigureFinding(
                FigureFindingCode.GRAND_TOTAL_IDENTITY,
                "grand_total must equal base_total + iva_total + recargo_amount + suplido_amount exactly",
                ("grand_total", "base_total", "iva_total", "recargo_amount", "suplido_amount"),
            )
        )
    return tuple(findings)


def nonnumeric_invoice_findings(
    *,
    base_total: Decimal,
    iva_total: Decimal,
    grand_total: Decimal,
    recargo: Decimal | None,
    suplido: Decimal | None,
) -> tuple[FigureFinding, ...]:
    """Name the impossible component when every line is nonnumeric.

    The recargo rides on the cuota of a taxable supply (LIVA art. 161), so a
    supply bearing no cuota by law bears no recargo either. A suplido is
    unrelated to whether the underlying supply is taxable, so it stays permitted.
    """
    findings: list[FigureFinding] = []
    if iva_total != _ZERO:
        findings.append(
            FigureFinding(
                FigureFindingCode.NONNUMERIC_IVA_TOTAL_NOT_ZERO,
                "iva_total must be zero when every line is nonnumeric",
                ("iva_total",),
            )
        )
    if (recargo or _ZERO) != _ZERO:
        findings.append(
            FigureFinding(
                FigureFindingCode.NONNUMERIC_RECARGO_NOT_ZERO,
                "recargo_amount must be zero when every line is nonnumeric",
                ("recargo_amount",),
            )
        )
    if grand_total != base_total + (suplido or _ZERO):
        findings.append(
            FigureFinding(
                FigureFindingCode.NONNUMERIC_GRAND_TOTAL_IDENTITY,
                "grand_total must equal base_total + suplido_amount when every line is nonnumeric",
                ("grand_total", "base_total", "suplido_amount"),
            )
        )
    return tuple(findings)


def recargo_sign_finding(recargo: Decimal | None) -> FigureFinding | None:
    """A stated recargo is a non-negative magnitude; ``None`` states nothing about it."""
    if recargo is not None and recargo < _ZERO:
        return FigureFinding(
            FigureFindingCode.RECARGO_NEGATIVE,
            "recargo_amount must be non-negative",
            ("recargo_amount",),
        )
    return None


def recargo_ceiling_finding(recargo: Decimal | None, iva_total: Decimal) -> FigureFinding | None:
    """A recargo never exceeds the cuota it rides on, under any tier."""
    if recargo is not None and recargo > iva_total:
        return FigureFinding(
            FigureFindingCode.RECARGO_ABOVE_IVA_TOTAL,
            "recargo_amount must not exceed iva_total; every recargo tier is a smaller "
            "percentage than the IVA rate it accompanies (LIVA art. 161)",
            ("recargo_amount", "iva_total"),
            values={"iva_total": iva_total, "stated": recargo},
        )
    return None


def suplido_finding(suplido: Decimal | None) -> FigureFinding | None:
    """A stated suplido is a non-negative magnitude; it carries no rate and no other bound."""
    if suplido is not None and suplido < _ZERO:
        return FigureFinding(
            FigureFindingCode.SUPLIDO_NEGATIVE,
            "suplido_amount must be non-negative",
            ("suplido_amount",),
        )
    return None


def retention_findings(
    rate: Decimal | None,
    amount: Decimal | None,
    base: Decimal | None,
) -> tuple[FigureFinding, ...]:
    """Check the two retención fields, in the order they are refused.

    The base is the base imponible, because RIRPF art. 95.1 withholds on the
    ingresos íntegros. The rate is a fraction, so 15 written for 15 % is refused
    rather than read as 1500 %. An amount may stand alone; a rate may not, since
    inferring the amount from it would manufacture a figure the document never
    stated. An unknown ``base`` leaves the checks that need it unasked.

    A rate is checked only for its shape and its agreement with the amount, not
    against any dated RIRPF rate.
    """
    candidates = (
        _retention_amount_sign(amount),
        _retention_rate_range(rate),
        _retention_rate_needs_amount(rate, amount),
        None if base is None else _retention_within_base(amount, base),
        None if base is None else _retention_agrees_with_rate(rate, amount, base),
    )
    return tuple(finding for finding in candidates if finding is not None)


def _retention_amount_sign(amount: Decimal | None) -> FigureFinding | None:
    if amount is not None and amount < _ZERO:
        return FigureFinding(
            FigureFindingCode.RETENTION_AMOUNT_NEGATIVE,
            "retention_amount must be non-negative",
            ("retention_amount",),
        )
    return None


def _retention_rate_range(rate: Decimal | None) -> FigureFinding | None:
    if rate is not None and (rate < _ZERO or rate > _ONE):
        return FigureFinding(
            FigureFindingCode.RETENTION_RATE_OUT_OF_RANGE,
            "retention_rate must be a fraction between 0 and 1 (0.15 for a 15 % retención), not a percentage",
            ("retention_rate",),
        )
    return None


def _retention_rate_needs_amount(rate: Decimal | None, amount: Decimal | None) -> FigureFinding | None:
    if rate is not None and amount is None:
        return FigureFinding(
            FigureFindingCode.RETENTION_RATE_WITHOUT_AMOUNT,
            "retention_rate requires retention_amount; a rate alone declares no withheld figure",
            ("retention_rate", "retention_amount"),
        )
    return None


def _retention_within_base(amount: Decimal | None, base: Decimal) -> FigureFinding | None:
    if amount is not None and amount > base:
        return FigureFinding(
            FigureFindingCode.RETENTION_AMOUNT_ABOVE_BASE,
            "retention_amount must not exceed base_total; the retención base is the "
            "base imponible (ingresos íntegros), not the IVA-inclusive total",
            ("retention_amount", "base_total"),
            values={"base_total": base, "stated": amount},
        )
    return None


def _retention_agrees_with_rate(rate: Decimal | None, amount: Decimal | None, base: Decimal) -> FigureFinding | None:
    if rate is None or amount is None:
        return None
    expected = (base * rate).quantize(_COMPARISON_SCALE)
    if _beyond_a_cent(amount, expected):
        return FigureFinding(
            FigureFindingCode.RETENTION_AMOUNT_MISMATCH,
            "retention_amount must equal base_total * retention_rate within 1 cent",
            ("retention_rate", "retention_amount", "base_total"),
            values={"expected": expected, "stated": amount},
        )
    return None


def printed_total_finding(printed_total: Decimal | None, total: Decimal | None) -> FigureFinding | None:
    """Warn that the document prints another total; the printed total never blocks."""
    if printed_total is None or total is None or printed_total == total:
        return None
    return FigureFinding(
        FigureFindingCode.PRINTED_TOTAL_DIFFERS,
        "the printed total differs from the computed total",
        ("printed_total",),
        severity=FigureFindingSeverity.WARNING,
        values={"computed": total, "printed": printed_total},
    )


@dataclass(frozen=True, slots=True)
class DatedRateSlot:
    """One slot's standing on a date. ``fraction`` is ``None`` when no rate applies."""

    slot: IvaRate
    fraction: Decimal | None
    in_force: bool
    coverage_gap: bool = False


def dated_rate_slots(on_date: date) -> tuple[DatedRateSlot, ...]:
    """Return every declared slot with its standing, under the authority in scope.

    A nonnumeric slot is in force with no fraction. A registry that cannot answer
    for the date raises its own failure here: this neither substitutes a rate nor
    decides what that failure means to a caller.
    """
    slots: list[DatedRateSlot] = []
    for slot in iva_rate_slots_on(on_date):
        try:
            fraction = iva_rate_percentage(slot, on_date)
        except IvaRateNotFoundError as refused:
            slots.append(DatedRateSlot(slot, None, in_force=False, coverage_gap=rate_refusal_is_coverage_gap(refused)))
        else:
            slots.append(DatedRateSlot(slot, fraction, in_force=True))
    return tuple(slots)


@dataclass(frozen=True, slots=True)
class StatedFigure:
    """A line figure: the backend's, the document's and the one that would be stored."""

    computed: Decimal | None = None
    stated: Decimal | None = None
    verdict: StatedFigureVerdict | None = None
    submitted: Decimal | None = None


@dataclass(frozen=True, slots=True)
class LineFigures:
    """One line's figures and findings. A figure nobody can know yet stays ``None``."""

    subtotal: StatedFigure
    iva_amount: StatedFigure
    findings: tuple[FigureFinding, ...]
    numeric_slot: bool | None = None


def _judged(
    computed: Decimal | None,
    stated: Decimal | None,
    finding: FigureFinding | None,
) -> StatedFigure:
    if stated is None:
        return StatedFigure(computed=computed, submitted=computed)
    if finding is not None:
        return StatedFigure(computed=computed, stated=stated, verdict=StatedFigureVerdict.REFUSED)
    verdict = StatedFigureVerdict.EQUAL if stated == computed else StatedFigureVerdict.WITHIN_TOLERANCE
    return StatedFigure(computed=computed, stated=stated, verdict=verdict, submitted=stated)


def _unchecked(stated: Decimal | None) -> StatedFigure:
    return StatedFigure(stated=stated, verdict=None if stated is None else StatedFigureVerdict.NOT_CHECKED)


def _subtotal_shape_findings(
    quantity: Decimal | None,
    unit_price: Decimal | None,
    stated: Decimal | None,
) -> tuple[FigureFinding, ...]:
    return tuple(
        finding
        for finding in (
            None if quantity is None else quantity_finding(quantity),
            None if unit_price is None else line_amount_finding(unit_price, field_name="unit_price"),
            None if stated is None else line_amount_finding(stated, field_name="subtotal"),
        )
        if finding is not None
    )


def _judged_with(
    computed: Decimal | None,
    stated: Decimal | None,
    finding: FigureFinding | None,
) -> tuple[StatedFigure, tuple[FigureFinding, ...]]:
    return _judged(computed, stated, finding), () if finding is None else (finding,)


def _subtotal_figure(
    quantity: Decimal | None,
    unit_price: Decimal | None,
    stated: Decimal | None,
) -> tuple[StatedFigure, tuple[FigureFinding, ...]]:
    shape = _subtotal_shape_findings(quantity, unit_price, stated)
    if quantity is None or unit_price is None or shape:
        return (
            StatedFigure(
                stated=stated,
                verdict=None if stated is None else _unverified_verdict(stated),
            ),
            shape,
        )
    finding = None if stated is None else line_subtotal_finding(quantity, unit_price, stated)
    computed = computed_line_subtotal(quantity, unit_price)
    return _judged_with(computed, stated, finding)


def _unverified_verdict(stated: Decimal) -> StatedFigureVerdict:
    return StatedFigureVerdict.REFUSED if stated < _ZERO else StatedFigureVerdict.NOT_CHECKED


def _oss_iva_figure(stated: Decimal | None) -> StatedFigure:
    # An OSS line bears the destination state's rate, which the slot does not name.
    return StatedFigure(
        stated=stated,
        verdict=None if stated is None else StatedFigureVerdict.NOT_CHECKED,
        submitted=stated,
    )


def _stated_iva_finding(base: Decimal, stated: Decimal | None, fraction: Decimal | None) -> FigureFinding | None:
    return None if stated is None else line_iva_finding(base, stated, fraction)


def _iva_figure(
    base: Decimal | None,
    stated: Decimal | None,
    slot: DatedRateSlot | None,
    *,
    oss_rate: bool,
) -> tuple[StatedFigure, tuple[FigureFinding, ...]]:
    sign = None if stated is None else line_amount_finding(stated, field_name="iva_amount")
    if sign is not None:
        return StatedFigure(stated=stated, verdict=StatedFigureVerdict.REFUSED), (sign,)
    if slot is None or not slot.in_force:
        return _unchecked(stated), ()
    if oss_rate:
        return _oss_iva_figure(stated), ()
    if slot.fraction is None:
        return _judged_with(_ZERO, stated, _stated_iva_finding(_ZERO, stated, None))
    if base is None:
        return _unchecked(stated), ()
    finding = _stated_iva_finding(base, stated, slot.fraction)
    return _judged_with(computed_line_iva(base, slot.fraction), stated, finding)


def compute_line_figures(
    *,
    quantity: Decimal | None,
    unit_price: Decimal | None,
    stated_subtotal: Decimal | None,
    stated_iva_amount: Decimal | None,
    slot: DatedRateSlot | None,
    oss_rate: bool = False,
) -> LineFigures:
    """Answer one draft line by the rules acceptance applies.

    An incomplete line has no figure for what it cannot determine, a subtotal
    the rule refuses is not used as the base of a cuota, and a magnitude too
    large for decimal arithmetic is a finding rather than a failure.
    """
    try:
        subtotal, subtotal_findings = _subtotal_figure(quantity, unit_price, stated_subtotal)
        iva_amount, iva_findings = _iva_figure(subtotal.submitted, stated_iva_amount, slot, oss_rate=oss_rate)
    except DecimalException:
        return LineFigures(
            subtotal=StatedFigure(stated=stated_subtotal),
            iva_amount=StatedFigure(stated=stated_iva_amount),
            findings=(figure_out_of_range_finding(("quantity", "unit_price", "subtotal", "iva_amount")),),
        )
    return LineFigures(
        subtotal=subtotal,
        iva_amount=iva_amount,
        findings=(*subtotal_findings, *iva_findings),
        numeric_slot=None if slot is None or not slot.in_force else slot.fraction is not None,
    )


def figure_out_of_range_finding(fields: tuple[str, ...]) -> FigureFinding:
    """Name a figure too large for decimal arithmetic at the cent."""
    return FigureFinding(
        FigureFindingCode.FIGURE_OUT_OF_RANGE,
        "the figure is too large to compute at the cent",
        fields,
    )


@dataclass(frozen=True, slots=True)
class InvoiceFigures:
    """The invoice's figures. A total stays ``None`` until every part of it is known."""

    base_total: Decimal | None
    iva_total: Decimal | None
    recargo_amount: Decimal | None
    total: Decimal | None
    net_of_retention: Decimal | None
    retention_rate: Decimal | None
    retention_amount: Decimal | None
    retention_implied: Decimal | None
    findings: tuple[FigureFinding, ...]


def _sum_when_known(figures: Sequence[StatedFigure]) -> tuple[Decimal, ...] | None:
    known = tuple(figure.submitted for figure in figures if figure.submitted is not None)
    return known if figures and len(known) == len(figures) else None


def _line_derived_totals(
    lines: Sequence[LineFigures],
) -> tuple[Decimal | None, Decimal | None, tuple[FigureFinding, ...]]:
    subtotals = _sum_when_known([line.subtotal for line in lines])
    iva_amounts = _sum_when_known([line.iva_amount for line in lines])
    if subtotals is None or iva_amounts is None:
        base = None if subtotals is None else round_to_cents(_exact_sum(subtotals))
        iva = None if iva_amounts is None else round_to_cents(_exact_sum(iva_amounts))
        return base, iva, ()
    base, iva = rounded_line_totals(subtotals, iva_amounts)
    findings = invoice_total_findings(
        base_total=base,
        iva_total=iva,
        grand_total=base + iva,
        line_subtotals=subtotals,
        line_iva_amounts=iva_amounts,
        recargo=None,
        suplido=None,
    )
    return base, iva, findings


def compute_invoice_figures(
    *,
    lines: Sequence[LineFigures],
    stated_base_total: Decimal | None = None,
    recargo_amount: Decimal | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    printed_total: Decimal | None = None,
    stored_grand_total: Decimal | None = None,
) -> InvoiceFigures:
    """Answer one draft's totals, retención and recargo by the rules acceptance applies.

    ``stated_base_total`` stands in for lines where a draft has none. It gives
    the retención a base and leaves the cuota unknown. ``stored_grand_total`` is
    the total a stored invoice already holds: a correction cannot change it, so
    it is what a changed retención settles against.
    """
    try:
        return _compute_invoice_figures(
            lines=lines,
            stated_base_total=stated_base_total,
            stored_grand_total=stored_grand_total,
            recargo_amount=recargo_amount,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
            printed_total=printed_total,
        )
    except DecimalException:
        return InvoiceFigures(
            base_total=None,
            iva_total=None,
            recargo_amount=recargo_amount,
            total=None,
            net_of_retention=None,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
            retention_implied=None,
            findings=(figure_out_of_range_finding(("base_total", "iva_total", "retention_amount")),),
        )


def _compute_invoice_figures(
    *,
    lines: Sequence[LineFigures],
    stated_base_total: Decimal | None,
    stored_grand_total: Decimal | None,
    recargo_amount: Decimal | None,
    retention_rate: Decimal | None,
    retention_amount: Decimal | None,
    printed_total: Decimal | None,
) -> InvoiceFigures:
    if lines:
        base, iva, total_findings = _line_derived_totals(lines)
    else:
        base, iva, total_findings = stated_base_total, None, ()
    retention = retention_findings(retention_rate, retention_amount, base)
    recargo_findings = _recargo_findings(recargo_amount, iva)
    total = _invoice_grand_total(lines, base, iva, recargo_amount, stored_grand_total)
    nonnumeric = _nonnumeric_findings(lines, base, iva, total, recargo_amount)
    printed = printed_total_finding(printed_total, total)
    return InvoiceFigures(
        base_total=base,
        iva_total=iva,
        recargo_amount=recargo_amount,
        total=total,
        net_of_retention=None if total is None or retention else settlement_amount(total, retention_amount),
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        retention_implied=_implied_retention(retention_rate, base),
        findings=(
            *total_findings,
            *nonnumeric,
            *recargo_findings,
            *retention,
            *(() if printed is None else (printed,)),
        ),
    )


def _recargo_findings(recargo_amount: Decimal | None, iva: Decimal | None) -> tuple[FigureFinding, ...]:
    findings: list[FigureFinding | None] = [recargo_sign_finding(recargo_amount)]
    if iva is not None:
        findings.append(recargo_ceiling_finding(recargo_amount, iva))
    return tuple(finding for finding in findings if finding is not None)


def _invoice_grand_total(
    lines: Sequence[LineFigures],
    base: Decimal | None,
    iva: Decimal | None,
    recargo_amount: Decimal | None,
    stored_grand_total: Decimal | None,
) -> Decimal | None:
    if base is not None and iva is not None:
        return computed_grand_total(base, iva, recargo_amount)
    return stored_grand_total if not lines else None


def _nonnumeric_findings(
    lines: Sequence[LineFigures],
    base: Decimal | None,
    iva: Decimal | None,
    total: Decimal | None,
    recargo_amount: Decimal | None,
) -> tuple[FigureFinding, ...]:
    every_line_nonnumeric = bool(lines) and all(line.numeric_slot is False for line in lines)
    if every_line_nonnumeric and base is not None and iva is not None and total is not None:
        return nonnumeric_invoice_findings(
            base_total=base,
            iva_total=iva,
            grand_total=total,
            recargo=recargo_amount,
            suplido=None,
        )
    return ()


def _implied_retention(rate: Decimal | None, base: Decimal | None) -> Decimal | None:
    if rate is None or base is None or rate < _ZERO or rate > _ONE:
        return None
    return round_to_cents(base * rate)


__all__ = [
    "DatedRateSlot",
    "FigureFinding",
    "FigureFindingCode",
    "FigureFindingSeverity",
    "InvoiceFigures",
    "LineFigures",
    "StatedFigure",
    "StatedFigureVerdict",
    "compute_invoice_figures",
    "compute_line_figures",
    "computed_grand_total",
    "computed_line_iva",
    "computed_line_subtotal",
    "dated_rate_slots",
    "expected_line_iva",
    "expected_line_subtotal",
    "figure_out_of_range_finding",
    "figure_refusal",
    "invoice_total_findings",
    "line_amount_finding",
    "line_iva_finding",
    "line_subtotal_finding",
    "nonnumeric_invoice_findings",
    "printed_total_finding",
    "quantity_finding",
    "raise_first_figure_finding",
    "rate_refusal_finding",
    "rate_refusal_is_coverage_gap",
    "recargo_ceiling_finding",
    "recargo_sign_finding",
    "retention_findings",
    "rounded_line_totals",
    "settlement_amount",
    "suplido_finding",
    "total_sign_finding",
]
