"""Spanish-locale decimal parser for filing-history payloads (#168).

AEAT's portal renders monetary values with a mix of Spanish-locale
thousands separators and comma decimals (``1.234,56``) and plain
English-locale decimals depending on the surface and the campaign.
This module translates either shape into a :class:`decimal.Decimal`
preserving the printed precision.

The implementation is deliberately duplicated from
``aeat.justificante._extract._parse_decimal`` (ADR D12). Cross-
importing a private module from a sibling subpackage is forbidden by
the project's public-API discipline; the 15-line Spanish locale
parser is low enough churn to live twice. If a third consumer
appears, promote to a shared ``aeat._decimal`` module.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ._errors import HistoryParseError


def parse_decimal(raw: str) -> Decimal:
    """Parse a portal-rendered decimal string into :class:`Decimal`.

    Accepts Spanish locale (``"1.234,56"`` → ``1234.56``), English
    locale (``"1234.56"``), or comma-only (``"1234,56"``). Preserves
    the printed precision via :class:`Decimal` — never floats.

    Args:
        raw: The numeric substring captured from an AEAT page.

    Returns:
        A :class:`decimal.Decimal` exactly representing the input.

    Raises:
        HistoryParseError: If ``raw`` is empty or not a recognisable
            number.
    """
    cleaned = raw.strip().replace(" ", "")
    if not cleaned:
        raise HistoryParseError(f"empty decimal string: {raw!r}")
    if "," in cleaned and "." in cleaned:
        # Mixed separators. AEAT always renders thousands-separator
        # first and decimal-separator last, so the rightmost wins.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise HistoryParseError(f"unparseable decimal string: {raw!r}") from exc
