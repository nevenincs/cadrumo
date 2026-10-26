"""Numeric display policy shared by form, scenario and saved-review workbooks.

Patterns use spreadsheet grammar, not localized separators. Sheets renders them
under the Spanish workbook locale; XLSX adds the Spanish locale qualifier.
Formatting never changes the stored magnitude or turns missing values into zero.
"""

from typing import Final, Literal

WORKBOOK_LOCALE: Final[str] = "es_ES"
XLSX_NUMBER_LOCALE: Final[str] = "[$-C0A]"

type NumericFormatKind = Literal["money", "integer", "decimal", "percentage"]


def numeric_format(data_type: str, *, currency: str | None = "EUR") -> tuple[NumericFormatKind, str] | None:
    """Select display by declared semantics, never by Python numeric type.

    Registry ratios have mixed scales, so they deliberately receive no percent
    multiplier. Only an explicitly fractional percentage uses spreadsheet `%`.
    An unknown currency must not acquire an invented euro denomination.
    """
    if data_type == "money":
        return "money", '#,##0.00" €"' if currency == "EUR" else "#,##0.00"
    if data_type == "integer":
        return "integer", "#,##0"
    if data_type == "year":
        return "integer", "0"
    if data_type == "ratio":
        return "decimal", "0.00####"
    if data_type in {"decimal", "float"}:
        return "decimal", "#,##0.############"
    if data_type == "percentage":
        return "percentage", "0.00####%"
    return None
