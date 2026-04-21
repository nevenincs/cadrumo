"""Extraction primitives: text-layer regex + word bbox helpers.

The module is backend-agnostic — it consumes the output of
:mod:`aeat.declaracion._parsers` (a plain string + a list of pdfplumber
word records) and returns casilla-keyed extraction results. Concrete
extractors under :mod:`aeat.declaracion._extractors` compose these
primitives per ``(modelo, template_revision)``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class LabelExtractionHit:
    """A successful label-anchored regex extraction."""

    casilla_id: str
    raw_value: str
    decimal_value: Decimal | None


def parse_spanish_decimal(raw: str) -> Decimal | None:
    """Parse an AEAT-formatted decimal string (``1.234,56`` or ``1234.56``).

    Returns ``None`` on unparseable input — extractor callers treat that
    as "casilla matched its label but value was blank / malformed".
    """
    cleaned = raw.strip().replace(" ", "")
    if not cleaned or cleaned == "-":
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def apply_label_regex(
    text: str,
    label_regex_map: Mapping[str, re.Pattern[str]],
) -> dict[str, LabelExtractionHit]:
    """Run each regex against ``text``; return a map of successful hits.

    Each regex must expose a single capturing group for the value; the
    key in ``label_regex_map`` is the casilla ID the hit maps to.
    """
    hits: dict[str, LabelExtractionHit] = {}
    for casilla_id, pattern in label_regex_map.items():
        match = pattern.search(text)
        if match is None:
            continue
        raw = match.group(1).strip()
        hits[casilla_id] = LabelExtractionHit(
            casilla_id=casilla_id,
            raw_value=raw,
            decimal_value=parse_spanish_decimal(raw),
        )
    return hits
