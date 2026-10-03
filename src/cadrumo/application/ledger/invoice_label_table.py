"""Recognize printed tax-table headers and rows in invoice transcriptions."""

from __future__ import annotations

import re

from . import invoice_label_vocabulary as vocabulary
from .invoice_label_models import InvoiceLabelTier, PrintedValue
from .invoice_label_value_parsing import parse_amount, parse_invoice_rate


def invoice_table_header(folded: str) -> list[str] | None:
    """Return recognized tax-table columns when the header is structurally usable."""
    if vocabulary.AMOUNT_RE.search(folded):
        return None
    columns = [
        name
        for match in vocabulary.TABLE_HEADER_RE.finditer(folded)
        for name, value in match.groupdict().items()
        if value
    ]
    if "base" not in columns or "iva" not in columns or len(set(columns)) != len(columns):
        return None
    return columns


def invoice_table_row(line: str, columns: list[str]) -> InvoiceLabelTier | None:
    """Parse one row whose tokens match the supplied tax-table columns."""
    tokens = _table_tokens(line)
    if tokens is None or len(tokens) != len(columns):
        return None
    return _table_tier(columns, tokens)


def _table_tokens(line: str) -> list[tuple[str, str]] | None:
    tokens: list[tuple[str, str]] = []
    position = 0
    for match in re.finditer(
        rf"(?P<rate>\d{{1,2}}(?:[.,]\d{{1,2}})?\s?%)|(?P<amount>[{vocabulary.MINUS_SIGNS}]?\d[\d{vocabulary.NUMBER_JOINERS}]*\d|\d)",
        line,
    ):
        if line[position : match.start()].strip(" \t|€:") and re.search(r"[A-Za-z]", line[position : match.start()]):
            return None
        tokens.append(("rate", match.group("rate")) if match.group("rate") else ("amount", match.group("amount")))
        position = match.end()
    if re.search(r"[A-Za-z]{2,}", line[position:].replace("EUR", "")):
        return None
    return tokens


def _table_tier(columns: list[str], tokens: list[tuple[str, str]]) -> InvoiceLabelTier | None:
    tier = InvoiceLabelTier()
    for column, (shape, printed) in zip(columns, tokens, strict=True):
        if column in {"rate", "re_rate"}:
            number = printed.rstrip("% ") if shape == "rate" else printed
            if not re.fullmatch(r"\d{1,2}(?:[.,]\d{1,2})?", number):
                return None
            setattr(tier, column, PrintedValue(parse_invoice_rate(number), printed))
        elif column == "total":
            continue
        else:
            magnitude = printed.lstrip(vocabulary.MINUS_SIGNS)
            value, _ = parse_amount(magnitude)
            if value is None:
                return None
            negative = magnitude != printed
            setattr(
                tier, column, PrintedValue(-value if negative else value, f"-{magnitude}" if negative else magnitude)
            )
    return tier


__all__ = ["invoice_table_header", "invoice_table_row"]
