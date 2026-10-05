"""Parse labelled values from invoice text without inferring missing facts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...core.identity.documents import IdentityError
from ...core.identity.nif_iva import normalise_nif_iva
from ...domain.calculations.registry.nif_iva_catalogue import nif_iva_format_for_country
from ...domain.calculations.registry.tax_id_runtime import validate_runtime_spanish_tax_id
from . import invoice_label_vocabulary as vocabulary
from .invoice_label_models import InvoiceLabelCollection, InvoiceLabelParty
from .invoice_label_table import invoice_table_header, invoice_table_row
from .invoice_label_value_parsing import (
    collect_invoice_amount_segment,
    collect_invoice_currency,
    fold_invoice_text,
    invoice_amount_segments,
    is_invoice_name_line,
    parse_invoice_date,
)


def _grounded_tax_id(token: str) -> str | None:
    """Return *token* as a checksum-valid Spanish or EU-structured identifier."""
    try:
        return validate_runtime_spanish_tax_id(token)
    except IdentityError:
        normalised = normalise_nif_iva(token)
        if len(normalised) < 2:
            return None
        spec = nif_iva_format_for_country(normalised[:2])
        if spec is None or not spec.pattern.match(normalised):
            return None
        return normalised


@dataclass
class _CollectionContext:
    lines: list[str]
    party: InvoiceLabelParty | None = None
    party_heading: str | None = None
    headings_seen: set[InvoiceLabelParty] = field(default_factory=set)
    preamble_tax_ids: list[tuple[str, str]] = field(default_factory=list)
    table_columns: list[str] | None = None


def collect_label_occurrences(text: str) -> InvoiceLabelCollection:
    """Collect printed invoice identity, date, and amount labels in text order."""
    collected = InvoiceLabelCollection()
    context = _CollectionContext(text.splitlines())
    for index, line in enumerate(context.lines):
        following = context.lines[index + 1] if index + 1 < len(context.lines) else None
        if _collect_table_line(collected, context, line):
            continue
        _collect_document_line(collected, context, line, following)
    heading_words_printed = any(vocabulary.HEADING_WORD_RE.search(fold_invoice_text(line)) for line in context.lines)
    _assign_letterhead_issuer(
        collected,
        context.preamble_tax_ids,
        context.headings_seen,
        heading_words_printed=heading_words_printed,
    )
    return collected


def _collect_table_line(collected: InvoiceLabelCollection, context: _CollectionContext, line: str) -> bool:
    folded = fold_invoice_text(line)
    if context.table_columns is not None:
        row = invoice_table_row(line, context.table_columns)
        if row is not None:
            collected.table_tiers.append(row)
            return True
        context.table_columns = None
    header = invoice_table_header(folded)
    if header is None:
        return False
    context.table_columns = header
    return True


def _collect_document_line(
    collected: InvoiceLabelCollection,
    context: _CollectionContext,
    line: str,
    following: str | None,
) -> None:
    folded = fold_invoice_text(line)
    heading = _collect_party_heading(collected, context, line, folded, following)
    tax_start = _collect_tax_ids(collected, context, line, folded)
    _collect_invoice_number(collected, line, folded)
    _collect_invoice_dates(collected, line, folded)
    amount_text = line[:tax_start] if heading is None else ""
    for kind, segment, _ in invoice_amount_segments(amount_text, folded[: len(amount_text)]):
        collect_invoice_amount_segment(collected, kind, segment, following)
    collect_invoice_currency(collected, line)


def _collect_party_heading(
    collected: InvoiceLabelCollection,
    context: _CollectionContext,
    line: str,
    folded: str,
    following: str | None,
) -> re.Match[str] | None:
    heading = vocabulary.HEADING_RE.match(folded)
    if heading is None:
        return None
    context.party = InvoiceLabelParty.SUPPLIER if heading.group("supplier") else InvoiceLabelParty.CUSTOMER
    context.party_heading = line[heading.start("label") : heading.end("label")]
    context.headings_seen.add(context.party)
    rest = line[heading.end() :]
    first_tax = vocabulary.TAX_ID_RE.search(fold_invoice_text(rest))
    name = (rest[: first_tax.start()] if first_tax else rest).strip(" ,;-|")
    if not name and following is not None and is_invoice_name_line(following):
        name = following.strip()
    if name:
        collected.add_value(f"{context.party.value}_name", name, name)
    return heading


def _collect_tax_ids(
    collected: InvoiceLabelCollection,
    context: _CollectionContext,
    line: str,
    folded: str,
) -> int:
    tax_start = len(line)
    for match in vocabulary.TAX_ID_RE.finditer(folded):
        tax_start = min(tax_start, match.start())
        printed = line[match.start("token") : match.end("token")]
        grounded = _grounded_tax_id(printed)
        qualified = _qualified_party(match)
        owner = qualified or context.party
        if owner is None:
            if grounded is not None:
                context.preamble_tax_ids.append((grounded, printed))
            continue
        role = f"{owner.value}_tax_id"
        if grounded is None:
            collected.rejected_tax_ids.setdefault(role, printed)
            continue
        collected.add_value(role, grounded, printed)
        evidence = line[match.start() : match.start("token")].strip(" :#.") if qualified else context.party_heading
        if evidence:
            collected.role_evidence[role] = evidence
    return tax_start


def _collect_invoice_number(collected: InvoiceLabelCollection, line: str, folded: str) -> None:
    for pattern, name in ((vocabulary.NUMBER_RE, "invoice_number"), (vocabulary.SERIES_RE, "invoice_series")):
        for match in pattern.finditer(folded):
            token = line[match.start("token") : match.end("token")]
            if name == "invoice_number" and not re.search(r"\d", token):
                continue
            collected.add_value(name, token, token)


def _collect_invoice_dates(collected: InvoiceLabelCollection, line: str, folded: str) -> None:
    for match in vocabulary.DATE_RE.finditer(folded):
        if vocabulary.NOT_ISSUE_DATE_RE.search(folded[: match.start()]):
            continue
        span = next(match.span(group) for group in ("dmy", "iso", "dnamey", "namedy") if match.group(group))
        printed = line[span[0] : span[1]]
        parsed = parse_invoice_date(match, printed)
        if parsed is not None:
            collected.add_value("invoice_date", parsed, printed)


def _qualified_party(match: re.Match[str]) -> InvoiceLabelParty | None:
    if match.group("supplier_before") or match.group("supplier_after"):
        return InvoiceLabelParty.SUPPLIER
    if match.group("customer_before") or match.group("customer_after"):
        return InvoiceLabelParty.CUSTOMER
    return None


def _assign_letterhead_issuer(
    collected: InvoiceLabelCollection,
    preamble_tax_ids: list[tuple[str, str]],
    headings_seen: set[InvoiceLabelParty],
    *,
    heading_words_printed: bool,
) -> None:
    """Assign the one identifier of a heading-free document to its issuer.

    Only when the document prints no party heading word anywhere and exactly one
    distinct unqualified identifier: RD 1619/2012 art. 7.1 requires the issuer's
    NIF on a factura simplificada and not the recipient's. A document printing a
    heading word the rules could not attribute (two party columns on one line)
    is left unread rather than assigned by position. The issuer's name is never
    read from a letterhead, which prints addresses in the same shape.
    """
    distinct = {grounded for grounded, _ in preamble_tax_ids}
    if headings_seen or heading_words_printed or len(distinct) != 1:
        return
    if "supplier_tax_id" in collected.values or "customer_tax_id" in collected.values:
        return
    grounded, printed = preamble_tax_ids[0]
    collected.add_value("supplier_tax_id", grounded, printed)


__all__ = ["collect_label_occurrences"]
