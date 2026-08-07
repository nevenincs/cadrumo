"""The closed vocabulary a tabular column's meaning is mapped onto.

A CSV or spreadsheet arrives with header names the product does not control:
a real libro registro carries every field the invoice importer needs under
Spanish names it has never seen, plus a retención column it has no slot for at
all. The mapping step answers "what does this column MEAN", once per file,
against this closed set — never per row, and never over a cell value.

That closedness is the anti-fabrication control. Role assignment is an
allow-list selection over these members, so the only thing the mapping step can
emit is a member; deterministic code then copies each cell under the chosen
mapping. A column whose meaning cannot be established maps to
:attr:`FieldRole.UNMAPPED` and is reported, so a file is never refused whole for
carrying a column the product does not know, and an unknown column is never
quietly copied into a field it does not belong to.

Member values are byte-identical to the column tokens the tabular importers
already accept, so a role resolves against an existing importer column without a
second translation table in between. The set is deliberately WIDER than those
importers: retención and the suplido/recargo/total terms of the arithmetic
closure are roles the product must be able to recognise in a source table even
where no importer column exists for them yet.

The axis lives in ``core`` because its producers, the deterministic copy step
and the operator-facing report of unmapped columns sit in different packages,
and ``core`` is the only home all of them reach without depending on each other.

See Also:
    :class:`FieldOrigin`
        The companion axis recording HOW a value was obtained; a cell copied
        under a role mapping is :attr:`FieldOrigin.TABULAR_MAPPED`.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["FieldRole"]


class FieldRole(StrEnum):
    """What one column of a source table means.

    Closed by construction: an unrecognised header resolves to
    :attr:`UNMAPPED` rather than widening the set at read time.
    """

    UNMAPPED = "unmapped"
    """The column's meaning was not established. Reported, never copied."""

    TRANSACTION_ID = "transaction_id"
    """Identifier addressing an existing ledger transaction."""

    COUNTERPARTY_NIF = "counterparty_nif"
    """The other party's Spanish tax identifier."""

    COUNTERPARTY_NAME = "counterparty_name"
    """The other party's name as printed."""

    INVOICE_NUMBER = "invoice_number"
    """The issuer's invoice series and number."""

    INVOICE_DATE = "invoice_date"
    """Date of issue."""

    TAXABLE_BASE = "taxable_base"
    """Base imponible, before cuota."""

    IVA_RATE = "iva_rate"
    """The IVA rate the line was charged at."""

    IVA_AMOUNT = "iva_amount"
    """Cuota de IVA."""

    IVA_CATEGORY = "iva_category"
    """The IVA treatment the row falls under."""

    IRPF_CATEGORY = "irpf_category"
    """The IRPF treatment the row falls under."""

    RETENCION_AMOUNT = "retencion_amount"
    """IRPF withheld at source; subtracted from the total to reach cash."""

    RECARGO_AMOUNT = "recargo_amount"
    """Recargo de equivalencia charged alongside the cuota."""

    SUPLIDO_AMOUNT = "suplido_amount"
    """Suplidos: sums advanced on the customer's behalf, outside the base."""

    GRAND_TOTAL = "grand_total"
    """The printed total the arithmetic closure is checked against."""

    CURRENCY = "currency"
    """ISO-4217 currency of the row's amounts."""

    COUNTRY_CODE = "country_code"
    """Counterparty country, which decides domestic versus not."""

    NOTES = "notes"
    """Free-text description carried through without interpretation."""

    CLASSIFICATION = "classification"
    """Business-versus-personal decision for the row."""

    CATEGORY_ID = "category_id"
    """Spending category the row is assigned to."""

    BUSINESS_PCT = "business_pct"
    """Business-use percentage for a mixed-use row."""

    USAGE_RATIO_ID = "usage_ratio_id"
    """Named usage ratio supplying the business percentage."""
