"""Spanish, Catalan, and English labels recognized in printed invoices."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .invoice_label_models import InvoiceLabelKind

CURRENCY_CODES = frozenset(
    {
        "EUR", "USD", "GBP", "CHF", "SEK", "DKK", "NOK", "PLN", "CZK",
        "HUF", "RON", "BGN", "JPY", "CNY", "CAD", "AUD", "MXN",
    },
)  # fmt: skip


CURRENCY_SYMBOLS: Mapping[str, str] = {"€": "EUR"}


MONTHS: Mapping[str, int] = {
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


SUPPLIER_HEADING = (
    r"proveedor(?:es)?|proveidor|emisor(?:/a)?|emissor|expedidor(?:/a)?|vendedor|venedor|"
    r"datos del emisor|dades de l'?emissor|supplier|seller|vendor|issued by|issuer|from"
)


CUSTOMER_HEADING = (
    r"destinatario|destinatari|cliente|client|customer|comprador|buyer|bill(?:ed)? to|invoice to|"
    r"facturar a|receptor|datos del cliente|dades del client"
)


HEADING_RE = re.compile(
    rf"^\s*(?P<label>(?P<supplier>{SUPPLIER_HEADING})|(?P<customer>{CUSTOMER_HEADING}))\s*(?::|$)",
)


TAX_LABEL = (
    r"n\.?\s?i\.?\s?f\.?[- ]iva|nif[- ]iva|vat (?:reg(?:istration)?\.? )?(?:no\.?|number|id)|vat|"
    r"tax id|c\.?\s?i\.?\s?f\.?|n\.?\s?i\.?\s?f\.?|n\.?\s?i\.?\s?e\.?|d\.?\s?n\.?\s?i\.?"
)


SUPPLIER_QUALIFIER = r"supplier|seller|vendor|emisor|emissor|proveedor|proveidor|del emisor|de l'?emissor"


CUSTOMER_QUALIFIER = r"customer|buyer|client|cliente|comprador|del cliente|del client|destinatario|destinatari"


TAX_ID_RE = re.compile(
    rf"(?<![a-z])(?:(?:(?P<supplier_before>{SUPPLIER_QUALIFIER})|(?P<customer_before>{CUSTOMER_QUALIFIER})) )?"
    rf"(?:{TAX_LABEL})"
    rf"(?: (?:(?P<supplier_after>{SUPPLIER_QUALIFIER})|(?P<customer_after>{CUSTOMER_QUALIFIER})))?"
    rf"\s*[:#.]?\s*(?P<token>(?:[a-z]{{2}} )?[a-z0-9](?:[.\-]?[a-z0-9]){{7,13}})(?![a-z0-9])",
)


HEADING_WORD_RE = re.compile(rf"(?<![a-z])(?:{SUPPLIER_HEADING}|{CUSTOMER_HEADING})(?![a-z])")


NUMBER_LABEL = (
    r"numero de (?:la )?factura|num\.? de factura|n[ºo°]\.? de factura|n\.?\s?[ºo°]\.? factura|"
    r"num\.? factura|factura (?:n[ºo°]\.?|num\.?|numero)|invoice (?:number|no\.?|nr\.?|#)|"
    # Bare words label a number only at the start of a line, before a colon;
    # elsewhere "Total factura:" would read its total as an invoice number.
    r"^\s*(?:numero|num\.|n[ºo°]\.?|invoice|factura)(?=\s*:)"
)


NUMBER_RE = re.compile(
    rf"(?<![a-z])(?:{NUMBER_LABEL})\s*[:#]?\s*(?P<token>[a-z0-9][a-z0-9/\-_.]*[a-z0-9]|[0-9])(?![a-z0-9])",
)


SERIES_RE = re.compile(r"(?<![a-z])(?:serie|series)\s*:\s*(?P<token>[a-z0-9][a-z0-9\-]*)(?![a-z0-9])")


DATE_LABEL = (
    r"fecha de (?:expedicion|emision|la factura|factura)|fecha factura|fecha|"
    r"data d'?(?:expedicio|emissio)|data de (?:la )?factura|data factura|data|"
    r"invoice date|date of issue|issue date|date"
)


DATE_VALUE = (
    r"(?P<dmy>\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})|(?P<iso>\d{4}-\d{2}-\d{2})|"
    r"(?P<dnamey>\d{1,2}(?:st|nd|rd|th)?\s+(?:de\s+|d')?[a-z]+\.?\s+(?:de\s+|del\s+)?\d{4})|"
    r"(?P<namedy>[a-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
)


DATE_RE = re.compile(rf"(?<![a-z])(?:{DATE_LABEL})\s*:?\s*(?:{DATE_VALUE})")


NOT_ISSUE_DATE_RE = re.compile(
    r"(?:due|vencimiento|venciment|pago|pagament|payment|operacion|operacio|supply|entrega)\s*$"
)


AMOUNT_LABELS: tuple[tuple[InvoiceLabelKind, str], ...] = (
    (InvoiceLabelKind.INCLUDED, r"(?:iva|vat|impuestos?) incl(?:uidos?|\.)?|incl\.? (?:iva|vat)"),
    (
        InvoiceLabelKind.PAYABLE,
        r"total a pagar|total a percibir|total a cobrar|liquido a (?:percibir|pagar)|importe a pagar|"
        r"import a pagar|total a abonar|amount due|total due|balance due|net to pay|a pagar",
    ),
    (
        InvoiceLabelKind.IVA_TOTAL,
        r"total (?:cuotas? )?(?:iva|vat)|total cuotas?|total quotes?|(?:iva|vat|cuota) ?\(total\)",
    ),
    (InvoiceLabelKind.BASE_TOTAL, r"total bases? (?:imponibles?|imposables?)|total bases?|total net"),
    (
        InvoiceLabelKind.GRAND_TOTAL,
        r"total factura|importe total|import total|total (?:invoice|amount)|invoice total|total general|total",
    ),
    (InvoiceLabelKind.RECARGO, r"recargo (?:de )?equivalencia|recarrec (?:d'?)?equivalencia|equivalence surcharge"),
    (InvoiceLabelKind.RETENCION, r"retencion(?: (?:de )?irpf)?|retencio(?: (?:d'?)?irpf)?|irpf|withholding(?: tax)?"),
    (InvoiceLabelKind.SUPLIDOS, r"(?:gastos )?suplidos?|despeses suplertes|disbursements?"),
    (
        InvoiceLabelKind.BASE,
        r"base imponible|base imposable|taxable (?:base|amount)|tax base|net amount|importe neto|base",
    ),
    (InvoiceLabelKind.RATE, r"tipo (?:de )?iva|tipus (?:d'?)?iva|tipo impositivo|vat rate|% ?iva|tipo|tipus"),
    (
        InvoiceLabelKind.IVA,
        r"cuota (?:de )?iva|quota (?:d'?)?iva|importe iva|import iva|vat amount|cuota|quota|i\.v\.a\.?|iva|vat",
    ),
)


AMOUNT_LABEL_RE = re.compile(
    "(?<![a-z])(?:" + "|".join(f"(?P<{kind.value}>{pattern})" for kind, pattern in AMOUNT_LABELS) + ")(?![a-z])",
)


RATE_RE = re.compile(r"(?<![\d.,])(?P<number>\d{1,2}(?:[.,]\d{1,2})?)\s?%")


NUMBER_JOINERS = ".,\u00a0\u202f"


GROUP_SEPARATORS = f"{NUMBER_JOINERS} "


MINUS_SIGNS = "-\u2212"


AMOUNT_RE = re.compile(
    rf"(?<![\w.,])(?P<sign>[{MINUS_SIGNS}]\s?)?"
    rf"(?P<number>\d{{1,3}}(?:[{GROUP_SEPARATORS}]\d{{3}})+(?:[.,]\d{{1,2}})?|\d+(?:[.,]\d{{1,3}})?)"
    r"(?![\w]|[.,]\d)",
)


TABLE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("re_rate", r"% ?r\.?\s?e\.?|tipo r\.?\s?e\.?"),
    ("re_amount", r"(?:cuota )?r\.\s?e\.?|recargo(?: equivalencia)?|recarrec"),
    ("base", r"base(?: imponible| imposable)?|taxable base|net amount|net"),
    ("rate", r"% ?iva|iva ?%|vat ?%|tipo(?: iva)?|tipus(?: iva)?|rate|%"),
    ("iva", r"cuota(?: iva)?|quota(?: iva)?|import iva|importe iva|vat amount|iva|vat"),
    ("total", r"total"),
)


TABLE_HEADER_RE = re.compile(
    "(?<![a-z])(?:" + "|".join(f"(?P<{name}>{pattern})" for name, pattern in TABLE_COLUMNS) + ")(?![a-z])",
)


FILLER_WORDS = frozenset(
    {"sobre", "on", "de", "del", "iva", "vat", "incluido", "incluidos", "incl", "included", "total"}
)
