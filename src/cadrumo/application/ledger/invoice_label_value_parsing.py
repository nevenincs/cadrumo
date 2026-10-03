"""Parse amounts, dates, and label segments from invoice text."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

from . import invoice_label_vocabulary as vocabulary
from .closure_findings import within_rounding_allowance
from .invoice_label_models import HUNDRED, InvoiceLabelCollection, InvoiceLabelKind, PrintedValue


def fold_invoice_text(text: str) -> str:
    """Lowercase and strip accents without changing the string's length.

    Length is preserved so a match position in the folded text addresses the
    same characters in the printed line, which is where anchors are cut from.
    """
    folded: list[str] = []
    for character in text:
        base = unicodedata.normalize("NFD", character)[0].lower()
        folded.append(base if len(base) == 1 else character)
    return "".join(folded)


def parse_amount(printed: str) -> tuple[Decimal | None, tuple[str, ...]]:
    """Return the amount *printed* states, or ``None`` with the competing readings.

    A dot or comma followed by exactly three digits and no other separator is
    either a thousands separator or a three-place decimal; both readings are
    returned and no value is chosen.
    """
    # `\s` covers the plain, no-break and narrow no-break space separators.
    text = re.sub(r"\s", "", printed)
    mixed = _parse_mixed_separators(text)
    if mixed is not None:
        return mixed
    for mark in (",", "."):
        if mark in text:
            return _parse_single_separator(text, mark)
    return Decimal(text), ()


def _parse_mixed_separators(text: str) -> tuple[Decimal | None, tuple[str, ...]] | None:
    if "," not in text or "." not in text:
        return None
    decimal_mark = "," if text.rfind(",") > text.rfind(".") else "."
    group_mark = "." if decimal_mark == "," else ","
    whole, fraction = text.rsplit(decimal_mark, 1)
    groups = whole.split(group_mark)
    if len(fraction) not in {1, 2}:
        return None, ()
    if decimal_mark in whole:
        return None, ()
    if not _valid_grouping(groups):
        return None, ()
    return Decimal(f"{''.join(groups)}.{fraction}"), ()


def _valid_grouping(groups: list[str]) -> bool:
    if not groups[0]:
        return False
    if len(groups[0]) > 3:
        return False
    return all(len(group) == 3 for group in groups[1:])


def _parse_single_separator(text: str, mark: str) -> tuple[Decimal | None, tuple[str, ...]]:
    parts = text.split(mark)
    if len(parts) > 2:
        return _parse_repeated_separator(parts)
    whole, fraction = parts
    if len(fraction) == 3:
        return None, (f"{whole}{fraction}", f"{whole}.{fraction}")
    return Decimal(f"{whole}.{fraction}"), ()


def _parse_repeated_separator(parts: list[str]) -> tuple[Decimal | None, tuple[str, ...]]:
    if all(len(part) == 3 for part in parts[1:]) and len(parts[0]) <= 3:
        return Decimal("".join(parts)), ()
    return None, ()


def parse_invoice_rate(printed: str) -> Decimal:
    """Parse a printed percentage using comma or dot as its decimal mark."""
    return Decimal(printed.replace(",", "."))


def parse_invoice_date(match: re.Match[str], printed: str) -> str | None:
    """Return a validated ISO date for a matched printed invoice date."""
    folded = fold_invoice_text(printed)
    if match.group("iso") is not None:
        year, month, day = (int(part) for part in printed.split("-"))
    elif match.group("dmy") is not None:
        day, month, year = (int(part) for part in re.split(r"[/.\-]", printed))
    else:
        words = re.findall(r"[a-z]+", re.sub(r"\b(?:de|del|d')\b|(?<=\d)(?:st|nd|rd|th)", " ", folded))
        numbers = [int(number) for number in re.findall(r"\d+", folded)]
        if len(words) != 1 or words[0] not in vocabulary.MONTHS or len(numbers) != 2:
            return None
        month = vocabulary.MONTHS[words[0]]
        day, year = numbers
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _amount_label_kind(match: re.Match[str]) -> InvoiceLabelKind:
    for kind in InvoiceLabelKind:
        if match.group(kind.value) is not None:
            return kind
    raise AssertionError("the label pattern matched no named kind")


def invoice_amount_segments(line: str, folded: str) -> list[tuple[InvoiceLabelKind, str, str]]:
    """Split one line at each amount label, keeping the text each label governs."""
    matches = [
        m for m in vocabulary.AMOUNT_LABEL_RE.finditer(folded) if _amount_label_kind(m) is not InvoiceLabelKind.INCLUDED
    ]
    segments: list[tuple[InvoiceLabelKind, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        segments.append((_amount_label_kind(match), line[match.end() : end], folded[match.end() : end]))
    return segments


def _rate_and_amounts(
    text: str,
) -> tuple[PrintedValue[Decimal] | None, list[PrintedValue[Decimal]], list[str]]:
    """Return the first printed rate, the printed amounts and any ambiguous amounts."""
    rate_match = vocabulary.RATE_RE.search(text)
    rate = None
    remainder = text
    if rate_match is not None:
        rate = PrintedValue(parse_invoice_rate(rate_match.group("number")), rate_match.group(0))
        remainder = text[: rate_match.start()] + " " * len(rate_match.group(0)) + text[rate_match.end() :]
    # OCR glues a unit to its figure ("708,60EUR"); the figure alone is the anchor.
    remainder = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", remainder)
    amounts: list[PrintedValue[Decimal]] = []
    ambiguous: list[str] = []
    previous_end = 0
    for match in vocabulary.AMOUNT_RE.finditer(remainder):
        # Only the first run of figures directly after the label belongs to it;
        # a figure inside prose ("Art. 196 Directive 2006/112/EC") is not an amount.
        if _is_prose(remainder[previous_end : match.start()]):
            break
        previous_end = match.end()
        printed = match.group("number")
        value, candidates = parse_amount(printed)
        if value is not None:
            if match.group("sign"):
                value, printed = -value, f"-{printed}"
            amounts.append(PrintedValue(value, printed))
        elif candidates:
            ambiguous.append(printed)
    return rate, amounts, ambiguous


def _is_prose(gap: str) -> bool:
    words = re.findall(r"[^\W\d_]{2,}", gap)
    return any(
        word.upper() not in vocabulary.CURRENCY_CODES and fold_invoice_text(word) not in vocabulary.FILLER_WORDS
        for word in words
    )


def _is_bare_amount_line(line: str) -> bool:
    words = re.findall(r"[^\W\d_]+", line)
    return all(word.upper() in vocabulary.CURRENCY_CODES for word in words) and bool(vocabulary.AMOUNT_RE.search(line))


def collect_invoice_amount_segment(
    collected: InvoiceLabelCollection,
    kind: InvoiceLabelKind,
    text: str,
    following: str | None,
) -> None:
    """Record the amount and rate candidates belonging to one printed label."""
    rate, amounts, ambiguous = _rate_and_amounts(text)
    if not amounts and not ambiguous and following is not None and _is_bare_amount_line(following):
        rate_next, amounts, ambiguous = _rate_and_amounts(following)
        rate = rate or rate_next
    _store_amount_segment(collected, kind, rate, amounts, ambiguous)


def _store_amount_segment(
    collected: InvoiceLabelCollection,
    kind: InvoiceLabelKind,
    rate: PrintedValue[Decimal] | None,
    amounts: list[PrintedValue[Decimal]],
    ambiguous: list[str],
) -> None:
    if kind is InvoiceLabelKind.RATE:
        if rate is not None:
            collected.rates.append(rate)
        return
    if ambiguous:
        collected.ambiguous_amounts.setdefault(kind, []).extend(ambiguous)
        return
    if not amounts:
        _store_unpaired_rate(collected, kind, rate)
        return
    amount = amounts[-1]
    collected.amounts.setdefault(kind, []).append((amount, rate))
    _store_paired_base(collected, kind, rate, amounts, amount)


def _store_unpaired_rate(
    collected: InvoiceLabelCollection,
    kind: InvoiceLabelKind,
    rate: PrintedValue[Decimal] | None,
) -> None:
    if kind is InvoiceLabelKind.IVA and rate is not None:
        collected.rates.append(rate)


def _store_paired_base(
    collected: InvoiceLabelCollection,
    kind: InvoiceLabelKind,
    rate: PrintedValue[Decimal] | None,
    amounts: list[PrintedValue[Decimal]],
    amount: PrintedValue[Decimal],
) -> None:
    if kind is not InvoiceLabelKind.IVA or rate is None or len(amounts) < 2:
        return
    # "IVA 21 % s/ 1.000,00: 210,00" prints the tier's base beside its cuota.
    base = amounts[-2]
    if within_rounding_allowance(base.value * rate.value / HUNDRED - amount.value, term_count=2):
        collected.amounts.setdefault(InvoiceLabelKind.BASE, []).append((base, rate))


def is_invoice_name_line(line: str) -> bool:
    """Return whether a line can be accepted as an unlabelled party name."""
    folded = fold_invoice_text(line)
    return (
        bool(re.search(r"[a-z]{2}", folded))
        and vocabulary.TAX_ID_RE.search(folded) is None
        and vocabulary.AMOUNT_LABEL_RE.search(folded) is None
        and vocabulary.HEADING_WORD_RE.search(folded) is None
        and ":" not in line
    )


def collect_invoice_currency(collected: InvoiceLabelCollection, line: str) -> None:
    """Record recognized ISO currency codes and symbols from one line."""
    for match in re.finditer(r"(?<![A-Za-z])([A-Z]{3})(?![A-Za-z])", line):
        if match.group(1) in vocabulary.CURRENCY_CODES:
            collected.add_value("currency", match.group(1), match.group(1))
    for symbol, code in vocabulary.CURRENCY_SYMBOLS.items():
        if symbol in line:
            collected.add_value("currency", code, symbol)


__all__ = [
    "collect_invoice_amount_segment",
    "collect_invoice_currency",
    "fold_invoice_text",
    "invoice_amount_segments",
    "is_invoice_name_line",
    "parse_amount",
    "parse_invoice_date",
    "parse_invoice_rate",
]
