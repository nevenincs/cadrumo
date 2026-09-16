"""Read invoice fields from a text-layer transcription by fixed label rules.

The deterministic rung of the text lane. It runs before any model, over the same
:class:`~application.ledger.document_transcription.DocumentTranscription` the
semantic reader would receive, and recovers only what a printed label assigns:
``Base imponible: 1.200,00``, ``IVA 21 %: 252,00``, ``Total factura``, ``NIF`` under
a party heading. Labels are matched in Spanish, Catalan and English.

Nothing is inferred. A value no label introduces is not read; a label that
introduces two different values is recorded as an ambiguity and left empty; an
amount whose thousands separator could be read two ways is left empty with both
readings recorded. Every monetary figure is then cross-checked:

- each rate tier: ``base * rate / 100 == cuota`` (and the recargo tier alike);
- the invoice: ``base + cuota + recargo + suplidos == total``;
- the retención: ``base * rate / 100 == amount``, and it sits outside the total,
  so a printed amount payable must equal ``total - retención``.

A figure that does not reconcile is cleared and a
:class:`~application.ledger.invoice_draft_records.DraftDiscrepancyFinding` of the
same kinds the shared closure check emits is recorded in its place, so a
non-closing document never yields a plausible-looking draft.

Envelopes leave this module ``UNANCHORED`` with the printed form as their
anchor, exactly as the semantic reader's do; the grounding pass that follows
checks every anchor against the transcription.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from ...core.identity.documents import IdentityError
from ...core.identity.nif_iva import normalise_nif_iva
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.nif_iva_catalogue import nif_iva_format_for_country
from ...domain.calculations.registry.tax_id_runtime import validate_runtime_spanish_tax_id
from .closure_findings import within_rounding_allowance
from .document_transcription import DocumentTranscription
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .evidence_textlayer import text_layer_transcriber_identity
from .evidence_textlayer_ports import EvidenceTextLayerPorts
from .invoice_draft_records import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftRateBreakdown,
)

__all__ = [
    "LABEL_READER_REQUIRED_FIELDS",
    "LabelReading",
    "merge_label_reading_with_model_draft",
    "read_invoice_fields_by_labels",
    "text_layer_reads_completely_by_labels",
]

LABEL_READER_REQUIRED_FIELDS = frozenset(
    {
        "invoice_number",
        "invoice_date",
        "supplier_tax_id",
        "supplier_name",
        "taxable_base",
        "iva_amount",
        "grand_total",
        "currency",
    },
)
"""Fields that must be read for the label reading to stand without a model.

``iva_rate`` is added for a single-rate document; a multi-rate document carries
its rates in the per-rate breakdown instead. The customer is not required: a
factura simplificada legitimately names none.
"""

_HUNDRED = Decimal(100)
_PROVENANCE_NOTE = "read by label rules from the text layer; not yet checked against the document"

_CURRENCY_CODES = frozenset(
    {
        "EUR", "USD", "GBP", "CHF", "SEK", "DKK", "NOK", "PLN", "CZK",
        "HUF", "RON", "BGN", "JPY", "CNY", "CAD", "AUD", "MXN",
    },
)  # fmt: skip
_CURRENCY_SYMBOLS: Mapping[str, str] = {"€": "EUR"}
"""Symbols that name exactly one currency. ``$`` and ``£`` name several and are not read."""

_MONTHS: Mapping[str, int] = {
    **dict.fromkeys(("enero", "gener", "january", "jan"), 1),
    **dict.fromkeys(("febrero", "febrer", "february", "feb"), 2),
    **dict.fromkeys(("marzo", "marc", "march", "mar"), 3),
    **dict.fromkeys(("abril", "april", "apr"), 4),
    **dict.fromkeys(("mayo", "maig", "may"), 5),
    **dict.fromkeys(("junio", "juny", "june", "jun"), 6),
    **dict.fromkeys(("julio", "juliol", "july", "jul"), 7),
    **dict.fromkeys(("agosto", "agost", "august", "aug"), 8),
    **dict.fromkeys(("septiembre", "setiembre", "setembre", "september", "sep", "sept"), 9),
    **dict.fromkeys(("octubre", "october", "oct"), 10),
    **dict.fromkeys(("noviembre", "novembre", "november", "nov"), 11),
    **dict.fromkeys(("diciembre", "desembre", "december", "dec"), 12),
}


def _fold(text: str) -> str:
    """Lowercase and strip accents without changing the string's length.

    Length is preserved so a match position in the folded text addresses the
    same characters in the printed line, which is where anchors are cut from.
    """
    folded: list[str] = []
    for character in text:
        base = unicodedata.normalize("NFD", character)[0].lower()
        folded.append(base if len(base) == 1 else character)
    return "".join(folded)


class _Party(StrEnum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"


_SUPPLIER_HEADING = (
    r"proveedor(?:es)?|proveidor|emisor(?:/a)?|emissor|expedidor(?:/a)?|vendedor|venedor|"
    r"datos del emisor|dades de l'?emissor|supplier|seller|vendor|issued by|issuer|from"
)
_CUSTOMER_HEADING = (
    r"destinatario|destinatari|cliente|client|customer|comprador|buyer|bill(?:ed)? to|invoice to|"
    r"facturar a|receptor|datos del cliente|dades del client"
)
_HEADING_RE = re.compile(
    rf"^\s*(?P<label>(?P<supplier>{_SUPPLIER_HEADING})|(?P<customer>{_CUSTOMER_HEADING}))\s*(?::|$)",
)

_TAX_LABEL = (
    r"n\.?\s?i\.?\s?f\.?[- ]iva|nif[- ]iva|vat (?:reg(?:istration)?\.? )?(?:no\.?|number|id)|vat|"
    r"tax id|c\.?\s?i\.?\s?f\.?|n\.?\s?i\.?\s?f\.?|n\.?\s?i\.?\s?e\.?|d\.?\s?n\.?\s?i\.?"
)
_SUPPLIER_QUALIFIER = r"supplier|seller|vendor|emisor|emissor|proveedor|proveidor|del emisor|de l'?emissor"
_CUSTOMER_QUALIFIER = r"customer|buyer|client|cliente|comprador|del cliente|del client|destinatario|destinatari"
_TAX_ID_RE = re.compile(
    rf"(?<![a-z])(?:(?:(?P<supplier_before>{_SUPPLIER_QUALIFIER})|(?P<customer_before>{_CUSTOMER_QUALIFIER})) )?"
    rf"(?:{_TAX_LABEL})"
    rf"(?: (?:(?P<supplier_after>{_SUPPLIER_QUALIFIER})|(?P<customer_after>{_CUSTOMER_QUALIFIER})))?"
    rf"\s*[:#.]?\s*(?P<token>(?:[a-z]{{2}} )?[a-z0-9](?:[.\-]?[a-z0-9]){{7,13}})(?![a-z0-9])",
)
_HEADING_WORD_RE = re.compile(rf"(?<![a-z])(?:{_SUPPLIER_HEADING}|{_CUSTOMER_HEADING})(?![a-z])")

_NUMBER_LABEL = (
    r"numero de (?:la )?factura|num\.? de factura|n[ºo°]\.? de factura|n\.?\s?[ºo°]\.? factura|"
    r"num\.? factura|factura (?:n[ºo°]\.?|num\.?|numero)|invoice (?:number|no\.?|nr\.?|#)|"
    # Bare words label a number only at the start of a line, before a colon;
    # elsewhere "Total factura:" would read its total as an invoice number.
    r"^\s*(?:numero|num\.|n[ºo°]\.?|invoice|factura)(?=\s*:)"
)
_NUMBER_RE = re.compile(
    rf"(?<![a-z])(?:{_NUMBER_LABEL})\s*[:#]?\s*(?P<token>[a-z0-9][a-z0-9/\-_.]*[a-z0-9]|[0-9])(?![a-z0-9])",
)
_SERIES_RE = re.compile(r"(?<![a-z])(?:serie|series)\s*:\s*(?P<token>[a-z0-9][a-z0-9\-]*)(?![a-z0-9])")

_DATE_LABEL = (
    r"fecha de (?:expedicion|emision|la factura|factura)|fecha factura|fecha|"
    r"data d'?(?:expedicio|emissio)|data de (?:la )?factura|data factura|data|"
    r"invoice date|date of issue|issue date|date"
)
_DATE_VALUE = (
    r"(?P<dmy>\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})|(?P<iso>\d{4}-\d{2}-\d{2})|"
    r"(?P<dnamey>\d{1,2}(?:st|nd|rd|th)?\s+(?:de\s+|d')?[a-z]+\.?\s+(?:de\s+|del\s+)?\d{4})|"
    r"(?P<namedy>[a-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
)
_DATE_RE = re.compile(rf"(?<![a-z])(?:{_DATE_LABEL})\s*:?\s*(?:{_DATE_VALUE})")
_NOT_ISSUE_DATE_RE = re.compile(
    r"(?:due|vencimiento|venciment|pago|pagament|payment|operacion|operacio|supply|entrega)\s*$"
)


class _Kind(StrEnum):
    PAYABLE = "payable"
    IVA_TOTAL = "iva_total"
    BASE_TOTAL = "base_total"
    GRAND_TOTAL = "grand_total"
    RECARGO = "recargo"
    RETENCION = "retencion"
    SUPLIDOS = "suplidos"
    BASE = "base"
    RATE = "rate"
    IVA = "iva"
    INCLUDED = "included"


_AMOUNT_LABELS: tuple[tuple[_Kind, str], ...] = (
    (_Kind.INCLUDED, r"(?:iva|vat|impuestos?) incl(?:uidos?|\.)?|incl\.? (?:iva|vat)"),
    (
        _Kind.PAYABLE,
        r"total a pagar|total a percibir|total a cobrar|liquido a (?:percibir|pagar)|importe a pagar|"
        r"import a pagar|total a abonar|amount due|total due|balance due|net to pay|a pagar",
    ),
    (_Kind.IVA_TOTAL, r"total (?:cuotas? )?(?:iva|vat)|total cuotas?|total quotes?|(?:iva|vat|cuota) ?\(total\)"),
    (_Kind.BASE_TOTAL, r"total bases? (?:imponibles?|imposables?)|total bases?|total net"),
    (
        _Kind.GRAND_TOTAL,
        r"total factura|importe total|import total|total (?:invoice|amount)|invoice total|total general|total",
    ),
    (_Kind.RECARGO, r"recargo (?:de )?equivalencia|recarrec (?:d'?)?equivalencia|equivalence surcharge"),
    (_Kind.RETENCION, r"retencion(?: (?:de )?irpf)?|retencio(?: (?:d'?)?irpf)?|irpf|withholding(?: tax)?"),
    (_Kind.SUPLIDOS, r"(?:gastos )?suplidos?|despeses suplertes|disbursements?"),
    (
        _Kind.BASE,
        r"base imponible|base imposable|taxable (?:base|amount)|tax base|net amount|importe neto|base",
    ),
    (_Kind.RATE, r"tipo (?:de )?iva|tipus (?:d'?)?iva|tipo impositivo|vat rate|% ?iva|tipo|tipus"),
    (
        _Kind.IVA,
        r"cuota (?:de )?iva|quota (?:d'?)?iva|importe iva|import iva|vat amount|cuota|quota|i\.v\.a\.?|iva|vat",
    ),
)
_AMOUNT_LABEL_RE = re.compile(
    "(?<![a-z])(?:" + "|".join(f"(?P<{kind.value}>{pattern})" for kind, pattern in _AMOUNT_LABELS) + ")(?![a-z])",
)

_RATE_RE = re.compile(r"(?<![\d.,])(?P<number>\d{1,2}(?:[.,]\d{1,2})?)\s?%")
_NUMBER_JOINERS = ".,\u00a0\u202f"
"""Characters that join the digits of one printed number: dot, comma, no-break and narrow no-break space."""
_GROUP_SEPARATORS = f"{_NUMBER_JOINERS} "
"""Thousands separators, which may also be a plain space inside a labelled amount."""
_MINUS_SIGNS = "-\u2212"
_AMOUNT_RE = re.compile(
    rf"(?<![\w.,])(?P<sign>[{_MINUS_SIGNS}]\s?)?"
    rf"(?P<number>\d{{1,3}}(?:[{_GROUP_SEPARATORS}]\d{{3}})+(?:[.,]\d{{1,2}})?|\d+(?:[.,]\d{{1,3}})?)"
    r"(?![\w]|[.,]\d)",
)

_TABLE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("re_rate", r"% ?r\.?\s?e\.?|tipo r\.?\s?e\.?"),
    ("re_amount", r"(?:cuota )?r\.\s?e\.?|recargo(?: equivalencia)?|recarrec"),
    ("base", r"base(?: imponible| imposable)?|taxable base|net amount|net"),
    ("rate", r"% ?iva|iva ?%|vat ?%|tipo(?: iva)?|tipus(?: iva)?|rate|%"),
    ("iva", r"cuota(?: iva)?|quota(?: iva)?|import iva|importe iva|vat amount|iva|vat"),
    ("total", r"total"),
)
_TABLE_HEADER_RE = re.compile(
    "(?<![a-z])(?:" + "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TABLE_COLUMNS) + ")(?![a-z])",
)


class LabelReading(BaseModel):
    """What the label rules recovered from one transcription.

    Attributes:
        draft: The rule-read draft: values, ``TEXT_RULES`` envelopes and the
            findings the rules raised.
        read_fields: The draft fields that carry a rule-read value.
    """

    model_config = STRICT_FROZEN_CONFIG

    draft: InvoiceDraft
    read_fields: frozenset[str]

    @property
    def required_fields(self) -> frozenset[str]:
        """The fields this document needs before the rules can stand alone.

        A single rate is required only where cuota was charged: a multi-rate
        document states its rates per tier, and a zero cuota states none.
        """
        if len(self.draft.iva_breakdown) > 1 or self.draft.iva_amount == 0:
            return LABEL_READER_REQUIRED_FIELDS
        return LABEL_READER_REQUIRED_FIELDS | {"iva_rate"}

    @property
    def missing_required_fields(self) -> frozenset[str]:
        """Required fields the rules did not read."""
        return self.required_fields - self.read_fields

    @property
    def complete(self) -> bool:
        """Whether every required field was read, so no model is needed."""
        return not self.missing_required_fields


@dataclass
class _Printed[T]:
    value: T
    anchor: str


@dataclass
class _Tier:
    rate: _Printed[Decimal] | None = None
    base: _Printed[Decimal] | None = None
    iva: _Printed[Decimal] | None = None
    re_rate: _Printed[Decimal] | None = None
    re_amount: _Printed[Decimal] | None = None


@dataclass
class _Collected:
    """Every labelled occurrence, before any is accepted."""

    values: dict[str, list[_Printed[str]]] = field(default_factory=dict)
    amounts: dict[_Kind, list[tuple[_Printed[Decimal], _Printed[Decimal] | None]]] = field(default_factory=dict)
    rates: list[_Printed[Decimal]] = field(default_factory=list)
    ambiguous_amounts: dict[_Kind, list[str]] = field(default_factory=dict)
    table_tiers: list[_Tier] = field(default_factory=list)
    role_evidence: dict[str, str] = field(default_factory=dict)
    rejected_tax_ids: dict[str, str] = field(default_factory=dict)

    def add_value(self, name: str, value: str, anchor: str) -> None:
        self.values.setdefault(name, []).append(_Printed(value, anchor))


def _parse_amount(printed: str) -> tuple[Decimal | None, tuple[str, ...]]:
    """Return the amount *printed* states, or ``None`` with the competing readings.

    A dot or comma followed by exactly three digits and no other separator is
    either a thousands separator or a three-place decimal; both readings are
    returned and no value is chosen.
    """
    # `\s` covers the plain, no-break and narrow no-break space separators.
    text = re.sub(r"\s", "", printed)
    if "," in text and "." in text:
        decimal_mark = "," if text.rfind(",") > text.rfind(".") else "."
        group_mark = "." if decimal_mark == "," else ","
        whole, fraction = text.rsplit(decimal_mark, 1)
        groups = whole.split(group_mark)
        if len(fraction) not in {1, 2} or decimal_mark in whole:
            return None, ()
        if not groups[0] or len(groups[0]) > 3 or any(len(group) != 3 for group in groups[1:]):
            return None, ()
        return Decimal(f"{''.join(groups)}.{fraction}"), ()
    for mark in (",", "."):
        if mark not in text:
            continue
        parts = text.split(mark)
        if len(parts) > 2:
            if all(len(part) == 3 for part in parts[1:]) and len(parts[0]) <= 3:
                return Decimal("".join(parts)), ()
            return None, ()
        whole, fraction = parts
        if len(fraction) == 3:
            return None, (f"{whole}{fraction}", f"{whole}.{fraction}")
        return Decimal(f"{whole}.{fraction}"), ()
    return Decimal(text), ()


def _parse_rate(printed: str) -> Decimal:
    return Decimal(printed.replace(",", "."))


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


def _parse_date(match: re.Match[str], printed: str) -> str | None:
    folded = _fold(printed)
    if match.group("iso") is not None:
        year, month, day = (int(part) for part in printed.split("-"))
    elif match.group("dmy") is not None:
        day, month, year = (int(part) for part in re.split(r"[/.\-]", printed))
    else:
        words = re.findall(r"[a-z]+", re.sub(r"\b(?:de|del|d')\b|(?<=\d)(?:st|nd|rd|th)", " ", folded))
        numbers = [int(number) for number in re.findall(r"\d+", folded)]
        if len(words) != 1 or words[0] not in _MONTHS or len(numbers) != 2:
            return None
        month = _MONTHS[words[0]]
        day, year = numbers
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _amount_label_kind(match: re.Match[str]) -> _Kind:
    for kind in _Kind:
        if match.group(kind.value) is not None:
            return kind
    raise AssertionError("the label pattern matched no named kind")


def _segments(line: str, folded: str) -> list[tuple[_Kind, str, str]]:
    """Split one line at each amount label, keeping the text each label governs."""
    matches = [m for m in _AMOUNT_LABEL_RE.finditer(folded) if _amount_label_kind(m) is not _Kind.INCLUDED]
    segments: list[tuple[_Kind, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        segments.append((_amount_label_kind(match), line[match.end() : end], folded[match.end() : end]))
    return segments


def _rate_and_amounts(
    text: str,
) -> tuple[_Printed[Decimal] | None, list[_Printed[Decimal]], list[str]]:
    """Return the first printed rate, the printed amounts and any ambiguous amounts."""
    rate_match = _RATE_RE.search(text)
    rate = None
    remainder = text
    if rate_match is not None:
        rate = _Printed(_parse_rate(rate_match.group("number")), rate_match.group(0))
        remainder = text[: rate_match.start()] + " " * len(rate_match.group(0)) + text[rate_match.end() :]
    # OCR glues a unit to its figure ("708,60EUR"); the figure alone is the anchor.
    remainder = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", remainder)
    amounts: list[_Printed[Decimal]] = []
    ambiguous: list[str] = []
    previous_end = 0
    for match in _AMOUNT_RE.finditer(remainder):
        # Only the first run of figures directly after the label belongs to it;
        # a figure inside prose ("Art. 196 Directive 2006/112/EC") is not an amount.
        if _is_prose(remainder[previous_end : match.start()]):
            break
        previous_end = match.end()
        printed = match.group("number")
        value, candidates = _parse_amount(printed)
        if value is not None:
            if match.group("sign"):
                value, printed = -value, f"-{printed}"
            amounts.append(_Printed(value, printed))
        elif candidates:
            ambiguous.append(printed)
    return rate, amounts, ambiguous


_FILLER_WORDS = frozenset(
    {"sobre", "on", "de", "del", "iva", "vat", "incluido", "incluidos", "incl", "included", "total"}
)


def _is_prose(gap: str) -> bool:
    words = re.findall(r"[^\W\d_]{2,}", gap)
    return any(word.upper() not in _CURRENCY_CODES and _fold(word) not in _FILLER_WORDS for word in words)


def _is_bare_amount_line(line: str) -> bool:
    words = re.findall(r"[^\W\d_]+", line)
    return all(word.upper() in _CURRENCY_CODES for word in words) and bool(_AMOUNT_RE.search(line))


def _collect_amount_segment(
    collected: _Collected,
    kind: _Kind,
    text: str,
    following: str | None,
) -> None:
    rate, amounts, ambiguous = _rate_and_amounts(text)
    if not amounts and not ambiguous and following is not None and _is_bare_amount_line(following):
        rate_next, amounts, ambiguous = _rate_and_amounts(following)
        rate = rate or rate_next
    if kind is _Kind.RATE:
        if rate is not None:
            collected.rates.append(rate)
        return
    if ambiguous:
        collected.ambiguous_amounts.setdefault(kind, []).extend(ambiguous)
        return
    if not amounts:
        if kind is _Kind.IVA and rate is not None:
            collected.rates.append(rate)
        return
    amount = amounts[-1]
    collected.amounts.setdefault(kind, []).append((amount, rate))
    if kind is _Kind.IVA and rate is not None and len(amounts) >= 2:
        # "IVA 21 % s/ 1.000,00: 210,00" prints the tier's base beside its cuota.
        base = amounts[-2]
        if within_rounding_allowance(base.value * rate.value / _HUNDRED - amount.value, term_count=2):
            collected.amounts.setdefault(_Kind.BASE, []).append((base, rate))


def _table_header(folded: str) -> list[str] | None:
    if _AMOUNT_RE.search(folded):
        return None
    columns = [
        name for match in _TABLE_HEADER_RE.finditer(folded) for name, value in match.groupdict().items() if value
    ]
    if "base" not in columns or "iva" not in columns or len(set(columns)) != len(columns):
        return None
    return columns


def _table_row(line: str, columns: list[str]) -> _Tier | None:
    tokens: list[tuple[str, str]] = []
    position = 0
    for match in re.finditer(
        rf"(?P<rate>\d{{1,2}}(?:[.,]\d{{1,2}})?\s?%)|(?P<amount>[{_MINUS_SIGNS}]?\d[\d{_NUMBER_JOINERS}]*\d|\d)", line
    ):
        if line[position : match.start()].strip(" \t|€:") and re.search(r"[A-Za-z]", line[position : match.start()]):
            return None
        tokens.append(("rate", match.group("rate")) if match.group("rate") else ("amount", match.group("amount")))
        position = match.end()
    if re.search(r"[A-Za-z]{2,}", line[position:].replace("EUR", "")) or len(tokens) != len(columns):
        return None
    tier = _Tier()
    for column, (shape, printed) in zip(columns, tokens, strict=True):
        if column in {"rate", "re_rate"}:
            number = printed.rstrip("% ") if shape == "rate" else printed
            if not re.fullmatch(r"\d{1,2}(?:[.,]\d{1,2})?", number):
                return None
            setattr(tier, column, _Printed(_parse_rate(number), printed))
        elif column == "total":
            continue
        else:
            magnitude = printed.lstrip(_MINUS_SIGNS)
            value, _ = _parse_amount(magnitude)
            if value is None:
                return None
            negative = magnitude != printed
            setattr(tier, column, _Printed(-value if negative else value, f"-{magnitude}" if negative else magnitude))
    return tier


def _collect(text: str) -> _Collected:
    collected = _Collected()
    lines = text.splitlines()
    party: _Party | None = None
    party_heading: str | None = None
    headings_seen: set[_Party] = set()
    preamble_tax_ids: list[tuple[str, str]] = []
    table_columns: list[str] | None = None

    for index, line in enumerate(lines):
        folded = _fold(line)
        following = lines[index + 1] if index + 1 < len(lines) else None

        if table_columns is not None:
            row = _table_row(line, table_columns)
            if row is not None:
                collected.table_tiers.append(row)
                continue
            table_columns = None
        header = _table_header(folded)
        if header is not None:
            table_columns = header
            continue

        heading = _HEADING_RE.match(folded)
        tax_start = len(line)
        if heading is not None:
            party = _Party.SUPPLIER if heading.group("supplier") else _Party.CUSTOMER
            party_heading = line[heading.start("label") : heading.end("label")]
            headings_seen.add(party)
            rest = line[heading.end() :]
            first_tax = _TAX_ID_RE.search(_fold(rest))
            name = (rest[: first_tax.start()] if first_tax else rest).strip(" ,;-|")
            if not name and following is not None and _is_name_line(following):
                name = following.strip()
            if name:
                collected.add_value(f"{party.value}_name", name, name)

        for match in _TAX_ID_RE.finditer(folded):
            tax_start = min(tax_start, match.start())
            printed = line[match.start("token") : match.end("token")]
            grounded = _grounded_tax_id(printed)
            qualified = _qualified_party(match)
            owner = qualified or party
            if owner is None:
                if grounded is not None:
                    preamble_tax_ids.append((grounded, printed))
                continue
            role = f"{owner.value}_tax_id"
            if grounded is None:
                collected.rejected_tax_ids.setdefault(role, printed)
                continue
            collected.add_value(role, grounded, printed)
            evidence = line[match.start() : match.start("token")].strip(" :#.") if qualified else party_heading
            if evidence:
                collected.role_evidence[role] = evidence

        for pattern, name in ((_NUMBER_RE, "invoice_number"), (_SERIES_RE, "invoice_series")):
            for match in pattern.finditer(folded):
                token = line[match.start("token") : match.end("token")]
                if name == "invoice_number" and not re.search(r"\d", token):
                    continue
                collected.add_value(name, token, token)

        for match in _DATE_RE.finditer(folded):
            if _NOT_ISSUE_DATE_RE.search(folded[: match.start()]):
                continue
            span = next(match.span(group) for group in ("dmy", "iso", "dnamey", "namedy") if match.group(group))
            printed = line[span[0] : span[1]]
            parsed = _parse_date(match, printed)
            if parsed is not None:
                collected.add_value("invoice_date", parsed, printed)

        amount_text = line[:tax_start] if heading is None else ""
        for kind, segment, _ in _segments(amount_text, folded[: len(amount_text)]):
            _collect_amount_segment(collected, kind, segment, following)

        _collect_currency(collected, line)

    heading_words_printed = any(_HEADING_WORD_RE.search(_fold(line)) for line in lines)
    _assign_letterhead_issuer(collected, preamble_tax_ids, headings_seen, heading_words_printed=heading_words_printed)
    return collected


def _qualified_party(match: re.Match[str]) -> _Party | None:
    if match.group("supplier_before") or match.group("supplier_after"):
        return _Party.SUPPLIER
    if match.group("customer_before") or match.group("customer_after"):
        return _Party.CUSTOMER
    return None


def _is_name_line(line: str) -> bool:
    folded = _fold(line)
    return (
        bool(re.search(r"[a-z]{2}", folded))
        and _TAX_ID_RE.search(folded) is None
        and _AMOUNT_LABEL_RE.search(folded) is None
        and _HEADING_WORD_RE.search(folded) is None
        and ":" not in line
    )


def _collect_currency(collected: _Collected, line: str) -> None:
    for match in re.finditer(r"(?<![A-Za-z])([A-Z]{3})(?![A-Za-z])", line):
        if match.group(1) in _CURRENCY_CODES:
            collected.add_value("currency", match.group(1), match.group(1))
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in line:
            collected.add_value("currency", code, symbol)


def _assign_letterhead_issuer(
    collected: _Collected,
    preamble_tax_ids: list[tuple[str, str]],
    headings_seen: set[_Party],
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


@dataclass
class _Assembly:
    values: dict[str, object] = field(default_factory=dict)
    anchors: dict[str, str] = field(default_factory=dict)
    role_evidence: dict[str, str] = field(default_factory=dict)
    ambiguities: dict[str, tuple[FieldAmbiguityCandidate, ...]] = field(default_factory=dict)
    derived: dict[str, tuple[str, ...]] = field(default_factory=dict)
    findings: list[DraftDiscrepancyFinding] = field(default_factory=list)

    def put(self, name: str, printed: _Printed[str] | _Printed[Decimal] | None) -> None:
        if printed is None:
            return
        self.values[name] = printed.value
        self.anchors[name] = printed.anchor

    def clear(self, *names: str) -> None:
        for name in names:
            self.values.pop(name, None)
            self.anchors.pop(name, None)
            self.derived.pop(name, None)

    def value(self, name: str) -> Decimal | None:
        value = self.values.get(name)
        return value if isinstance(value, Decimal) else None


def _single[T](name: str, occurrences: Iterable[_Printed[T]], assembly: _Assembly) -> _Printed[T] | None:
    """Return the one value every occurrence agrees on, or record the disagreement."""
    items = list(occurrences)
    distinct: dict[T, _Printed[T]] = {}
    for item in items:
        distinct.setdefault(item.value, item)
    if len(distinct) == 1:
        return items[0]
    if len(distinct) > 1:
        assembly.ambiguities[name] = tuple(
            FieldAmbiguityCandidate(value=str(value), anchor=item.anchor, note="another label prints a different value")
            for value, item in distinct.items()
        )
    return None


def _tiers(collected: _Collected, assembly: _Assembly) -> list[_Tier]:
    if collected.table_tiers:
        return collected.table_tiers
    by_rate: dict[Decimal, _Tier] = {}
    unrated = _Tier()
    unrated_bases: list[_Printed[Decimal]] = []
    unrated_ivas: list[_Printed[Decimal]] = []
    for amount, rate in collected.amounts.get(_Kind.BASE, []):
        if rate is None:
            unrated_bases.append(amount)
        else:
            tier = by_rate.setdefault(rate.value, _Tier(rate=rate))
            tier.base = tier.base or amount
    for amount, rate in collected.amounts.get(_Kind.IVA, []):
        if rate is None:
            unrated_ivas.append(amount)
        else:
            tier = by_rate.setdefault(rate.value, _Tier(rate=rate))
            tier.iva = tier.iva or amount
    for amount, rate in collected.amounts.get(_Kind.RECARGO, []):
        if len(by_rate) == 1 or not by_rate:
            target = next(iter(by_rate.values())) if by_rate else unrated
            target.re_amount = amount
            target.re_rate = rate
    if len(by_rate) > 1:
        return list(by_rate.values())
    single = next(iter(by_rate.values())) if by_rate else unrated
    if single.base is None:
        single.base = _single("taxable_base", unrated_bases, assembly)
    if single.iva is None:
        single.iva = _single("iva_amount", unrated_ivas, assembly)
    if single.rate is None:
        single.rate = _single("iva_rate", collected.rates, assembly)
    if single.re_amount is None and unrated.re_amount is not None:
        single.re_amount, single.re_rate = unrated.re_amount, unrated.re_rate
    return [single]


def _tier_reconciles(tier: _Tier, assembly: _Assembly) -> bool:
    checks = ((tier.base, tier.rate, tier.iva, "iva"), (tier.base, tier.re_rate, tier.re_amount, "recargo"))
    for base, rate, amount, label in checks:
        if base is None or rate is None or amount is None:
            continue
        expected = base.value * rate.value / _HUNDRED
        if not within_rounding_allowance(amount.value - expected, term_count=2):
            assembly.findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
                    field="iva_rate" if label == "iva" else "recargo_amount",
                    detail=(
                        f"the printed {label} {amount.anchor!r} is not {rate.anchor} of the printed base "
                        f"{base.anchor!r}; the figures were left empty rather than one of them chosen"
                    ),
                    expected=expected,
                    observed=amount.value,
                ),
            )
            return False
    return True


def _printed_total(
    collected: _Collected,
    total_kind: _Kind,
    tier_kind: _Kind,
    name: str,
    tiers: list[_Tier],
    assembly: _Assembly,
) -> _Printed[Decimal] | None:
    """Return the document's printed total for *name*.

    On a multi-rate document an unrated ``Base imponible`` or ``IVA`` line
    beside the per-rate lines is that total, so it is kept as a cross-check
    rather than dropped.
    """
    totals = [amount for amount, _ in collected.amounts.get(total_kind, [])]
    if len(tiers) > 1 and not collected.table_tiers:
        totals.extend(amount for amount, rate in collected.amounts.get(tier_kind, []) if rate is None)
    return _single(name, totals, assembly)


_TAX_FIGURES = ("taxable_base", "iva_rate", "iva_amount", "recargo_amount", "iva_breakdown")


def _assemble_tax_figures(collected: _Collected, assembly: _Assembly) -> None:
    tiers = [tier for tier in _tiers(collected, assembly) if tier.base or tier.iva or tier.rate]
    if not all(_tier_reconciles(tier, assembly) for tier in tiers):
        return
    printed_base_total = _printed_total(collected, _Kind.BASE_TOTAL, _Kind.BASE, "taxable_base", tiers, assembly)
    printed_iva_total = _printed_total(collected, _Kind.IVA_TOTAL, _Kind.IVA, "iva_amount", tiers, assembly)
    recargos = [tier.re_amount for tier in tiers if tier.re_amount is not None]
    if len(tiers) == 1 and len(collected.table_tiers) <= 1:
        tier = tiers[0]
        base = tier.base or printed_base_total
        if base is None:
            # A cuota or rate with no base has nothing to be checked against.
            return
        assembly.put("taxable_base", base)
        # A printed 0 % charges no rate; the draft's single rate stays empty.
        assembly.put("iva_rate", tier.rate if tier.rate is None or tier.rate.value != 0 else None)
        assembly.put("iva_amount", tier.iva or printed_iva_total)
        assembly.put("recargo_amount", tier.re_amount)
        return
    if not tiers or any(tier.base is None or tier.rate is None or tier.iva is None for tier in tiers):
        return
    assembly.values["iva_breakdown"] = tuple(
        InvoiceDraftRateBreakdown(
            iva_rate=tier.rate.value if tier.rate else None,
            taxable_base=tier.base.value if tier.base else None,
            iva_amount=tier.iva.value if tier.iva else None,
            recargo_rate=tier.re_rate.value if tier.re_rate else None,
            recargo_amount=tier.re_amount.value if tier.re_amount else None,
        )
        for tier in tiers
    )
    assembly.anchors["iva_breakdown"] = " / ".join(
        f"{tier.base.anchor} {tier.rate.anchor} {tier.iva.anchor}"
        for tier in tiers
        if tier.base and tier.rate and tier.iva
    )
    for name, printed, parts in (
        ("taxable_base", printed_base_total, [tier.base for tier in tiers]),
        ("iva_amount", printed_iva_total, [tier.iva for tier in tiers]),
        ("recargo_amount", None, recargos),
    ):
        total = sum((part.value for part in parts if part is not None), Decimal(0))
        if printed is not None:
            if not within_rounding_allowance(printed.value - total, term_count=len(parts)):
                assembly.findings.append(
                    DraftDiscrepancyFinding(
                        kind=DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT,
                        field=name,
                        detail=f"the per-rate figures sum to {total} while the document prints {printed.anchor!r}",
                        expected=total,
                        observed=printed.value,
                    ),
                )
                assembly.clear(*_TAX_FIGURES)
                return
            assembly.put(name, printed)
        elif parts:
            assembly.values[name] = total
            assembly.derived[name] = ("iva_breakdown",)


def _assemble_totals(collected: _Collected, assembly: _Assembly) -> None:
    grand_total = _single("grand_total", (a for a, _ in collected.amounts.get(_Kind.GRAND_TOTAL, [])), assembly)
    suplidos = _single("suplidos_amount", (a for a, _ in collected.amounts.get(_Kind.SUPLIDOS, [])), assembly)
    assembly.put("suplidos_amount", suplidos)
    base = assembly.value("taxable_base")
    if grand_total is not None and base is not None:
        terms = [
            base,
            assembly.value("iva_amount"),
            assembly.value("recargo_amount"),
            assembly.value("suplidos_amount"),
        ]
        stated = [term for term in terms if term is not None]
        computed = sum(stated, Decimal(0))
        if not within_rounding_allowance(grand_total.value - computed, term_count=len(stated)):
            assembly.findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                    field="grand_total",
                    detail=(
                        f"the printed total {grand_total.anchor!r} is not base plus cuota plus recargo plus "
                        f"suplidos ({computed}); the figures were left empty rather than one of them chosen"
                    ),
                    expected=computed,
                    observed=grand_total.value,
                ),
            )
            assembly.clear(*_TAX_FIGURES, "suplidos_amount")
            grand_total = None
    if base is not None:
        # A total with no base has nothing to be checked against.
        assembly.put("grand_total", grand_total)

    retention_entries = collected.amounts.get(_Kind.RETENCION, [])
    retention = _single("retencion_amount", (a for a, _ in retention_entries), assembly)
    if retention is not None:
        # A retención prints negative because it is subtracted; its sign in the
        # draft is the invoice's own, which a rectificativa makes negative.
        magnitude = abs(retention.value)
        anchor = retention.anchor.lstrip("-")
        total_sign = assembly.value("grand_total")
        if total_sign is not None and total_sign < 0:
            retention = _Printed(-magnitude, f"-{anchor}")
        else:
            retention = _Printed(magnitude, anchor)
    retention_rate = _single(
        "retencion_rate",
        (rate for _, rate in retention_entries if rate is not None),
        assembly,
    )
    base = assembly.value("taxable_base")
    if retention is not None and retention_rate is not None and base is not None:
        expected = base * retention_rate.value / _HUNDRED
        if not within_rounding_allowance(retention.value - expected, term_count=2):
            assembly.findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
                    field="retencion_amount",
                    detail=(
                        f"the printed retención {retention.anchor!r} is not {retention_rate.anchor} of the "
                        f"taxable base ({expected}); both were left empty"
                    ),
                    expected=expected,
                    observed=retention.value,
                ),
            )
            retention = retention_rate = None
    payable = _single("grand_total", (a for a, _ in collected.amounts.get(_Kind.PAYABLE, [])), assembly)
    total = assembly.value("grand_total")
    if payable is not None and total is not None:
        withheld = retention.value if retention is not None else Decimal(0)
        if not within_rounding_allowance(total - withheld - payable.value, term_count=2):
            assembly.findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                    field="retencion_amount",
                    detail=(
                        f"the printed amount payable {payable.anchor!r} is not the total less the retención "
                        f"({total - withheld}); the retención was left empty"
                    ),
                    expected=total - withheld,
                    observed=payable.value,
                ),
            )
            retention = retention_rate = None
    assembly.put("retencion_amount", retention)
    assembly.put("retencion_rate", retention_rate)


def _record_ambiguous_amounts(collected: _Collected, assembly: _Assembly) -> None:
    targets = {
        _Kind.BASE: "taxable_base",
        _Kind.BASE_TOTAL: "taxable_base",
        _Kind.IVA: "iva_amount",
        _Kind.IVA_TOTAL: "iva_amount",
        _Kind.GRAND_TOTAL: "grand_total",
        _Kind.RECARGO: "recargo_amount",
        _Kind.RETENCION: "retencion_amount",
        _Kind.SUPLIDOS: "suplidos_amount",
    }
    for kind, printed_forms in collected.ambiguous_amounts.items():
        name = targets.get(kind)
        if name is None or name in assembly.values:
            continue
        printed = printed_forms[0]
        _, readings = _parse_amount(printed)
        assembly.ambiguities[name] = tuple(
            FieldAmbiguityCandidate(value=reading, anchor=printed, note="the separator may mark thousands or decimals")
            for reading in readings
        )


def _provenance(assembly: _Assembly) -> tuple[FieldProvenance, ...]:
    envelopes: list[FieldProvenance] = []
    for name in InvoiceDraft.model_fields:
        if name in assembly.derived and name in assembly.values:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.DERIVED,
                    grounding=FieldGroundingOutcome.RECONCILED,
                    derived_from=assembly.derived[name],
                    note="summed from the per-rate figures the document prints",
                ),
            )
        elif name == "iva_breakdown" and name in assembly.values:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.TEXT_RULES,
                    grounding=FieldGroundingOutcome.RECONCILED,
                    anchor=assembly.anchors[name],
                    note="every printed tier satisfies base x rate = cuota",
                ),
            )
        elif name in assembly.values:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.TEXT_RULES,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    anchor=assembly.anchors[name],
                    role_evidence=assembly.role_evidence.get(name),
                    note=_PROVENANCE_NOTE,
                ),
            )
        elif name in assembly.ambiguities and len(assembly.ambiguities[name]) >= 2:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.TEXT_RULES,
                    grounding=FieldGroundingOutcome.AMBIGUOUS,
                    candidates=assembly.ambiguities[name],
                    note="the document prints competing values; none was chosen",
                ),
            )
    return tuple(envelopes)


def read_invoice_fields_by_labels(
    transcription: DocumentTranscription,
    *,
    operation: PinnedAuthorityOperation,
) -> LabelReading:
    """Read every labelled invoice field the transcription prints.

    Args:
        transcription: A text-layer transcription, printed forms intact.
        operation: The pinned authority the tax-identifier checks resolve
            their format declarations from.

    Returns:
        The rule-read draft and the set of fields it populated. Deterministic:
        the same text always yields the same reading.
    """
    with validating_governed_facts(operation):
        collected = _collect(transcription.text)
    assembly = _Assembly()
    for name in (
        "invoice_number",
        "invoice_series",
        "invoice_date",
        "supplier_name",
        "customer_name",
        "supplier_tax_id",
        "customer_tax_id",
        "currency",
    ):
        assembly.put(name, _single(name, collected.values.get(name, []), assembly))
        if name in assembly.values and name in collected.role_evidence:
            assembly.role_evidence[name] = collected.role_evidence[name]
    for role, printed in collected.rejected_tax_ids.items():
        if role in assembly.values:
            continue
        assembly.findings.append(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.IDENTITY_UNVERIFIED,
                field=role,
                detail=(
                    f"the document prints {printed!r} as this party's tax identifier, but it fails its "
                    f"control-character check, so it was not accepted as a verified identity"
                ),
            ),
        )
    _assemble_tax_figures(collected, assembly)
    _assemble_totals(collected, assembly)
    _record_ambiguous_amounts(collected, assembly)

    draft = InvoiceDraft.model_validate(
        {
            **assembly.values,
            "provenance": _provenance(assembly),
            "discrepancies": tuple(assembly.findings),
            "raw_text_length": len(transcription.text),
            "transcription_sha256": transcription.source_content_sha256,
        },
    )
    return LabelReading(draft=draft, read_fields=frozenset(assembly.values))


def text_layer_reads_completely_by_labels(
    data: bytes,
    *,
    text_layer_ports: EvidenceTextLayerPorts,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether a PDF's text layer reads completely without a model.

    The same predicate the extraction router applies before calling the text
    model, exposed for callers that must decide ahead of extraction whether a
    document needs the inference lane at all. A document without a usable text
    layer answers ``False``.
    """
    try:
        pages = text_layer_ports.extract_pages_text(data)
    except PurchaseInvoiceEvidenceInputError:
        return False
    text = "\n".join(page for page in pages if page)
    if not text.strip():
        return False
    transcription = DocumentTranscription(
        text=text,
        page_count=len(pages),
        source_content_sha256=hashlib.sha256(data).hexdigest(),
        transcriber=text_layer_transcriber_identity(),
    )
    return read_invoice_fields_by_labels(transcription, operation=operation).complete


_ARITHMETIC_KINDS = frozenset(
    {
        DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
        DraftDiscrepancyKind.RATE_INCONSISTENT,
        DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT,
    },
)


def merge_label_reading_with_model_draft(reading: LabelReading, model_draft: InvoiceDraft) -> InvoiceDraft:
    """Fill the fields the rules could not read from a model's draft.

    Every field the rules read keeps its rule value and envelope; the model
    contributes only the rest. The rules' arithmetic findings are dropped once
    the model has supplied figures, because the shared closure check re-runs on
    the merged figures and would otherwise report the same identity twice.
    Identity findings are kept once per field.
    """
    rule_draft = reading.draft
    bookkeeping = {"provenance", "discrepancies", "raw_text_length", "transcription_sha256"}
    rule_owned = set(reading.read_fields)
    if "iva_breakdown" in rule_owned:
        # A multi-rate document has no single rate; a model's pick of one tier
        # must not re-enter beside the breakdown.
        rule_owned.add("iva_rate")
    merged_values = {
        name: getattr(rule_draft if name in rule_owned else model_draft, name)
        for name in type(rule_draft).model_fields
        if name not in bookkeeping
    }
    rule_envelopes = {envelope.field: envelope for envelope in rule_draft.provenance}
    model_envelopes = {envelope.field: envelope for envelope in model_draft.provenance}
    envelopes: list[FieldProvenance] = []
    for name in type(rule_draft).model_fields:
        source = model_envelopes if name not in rule_owned and name in model_envelopes else rule_envelopes
        if name in source:
            envelopes.append(source[name])

    findings: dict[tuple[DraftDiscrepancyKind, str | None], DraftDiscrepancyFinding] = {}
    for finding in rule_draft.discrepancies:
        # Superseded once the model filled the cleared figure: the shared
        # closure check judges the merged figures instead.
        if finding.kind in _ARITHMETIC_KINDS and merged_values.get(finding.field or "") not in (None, ()):
            continue
        findings.setdefault((finding.kind, finding.field), finding)
    for finding in model_draft.discrepancies:
        if finding.field in rule_owned:
            continue
        findings.setdefault((finding.kind, finding.field), finding)
    return rule_draft.model_copy(
        update={
            **merged_values,
            "provenance": tuple(envelopes),
            "discrepancies": tuple(findings.values()),
        },
    )
