"""Sede G313 (Mis Datos Censales) read-only censo adapter — data layer.

Owns the strict pydantic envelope (:class:`CensoFactSet`) and the pure
HTML parser (:func:`parse_g313_html`) that lift the AEAT G313 result
page into a typed boundary value. The live Playwright driver, the raw-
HTML persistence path, and the
:class:`aeat.domain.user_profile._values.UserProfileFact` provenance
wiring are separate concerns that compose with this module; nothing in
here performs I/O.

The fact-set covers every field on the G313 (Mis Datos Censales)
projection:

* fiscal address: cadastral reference + habitual-vivienda flag
* censo section: activity start / end dates, establecimiento type,
  elected withholding pct (LIRPF Art. 101.5 + RIRPF Art. 95.1/95.2)
* vivienda_office: total / office m² (LIRPF Art. 30.2 rule 5)
* activities: IAE epigraph

Every field is optional at the envelope level because G313 returns a
sparse projection: a brand-new alta may not have a habitual-vivienda
flag yet, an operator who never deducted suministros has no
vivienda_office row, etc. The CensoSyncService layer above is where
"missing-when-required" is adjudicated, not here.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.decimal import normalize_decimal_separators
from .....core.parsing import parse_bool as _parse_bool
from .....core.parsing import parse_date as _parse_date_canonical
from ._errors import SedeError, SedeFailureMode

# G313 publishes the operator's elected withholding rate as a percentage
# string. The closed enum {15, 7, 1} is enforced at the CensoSyncService
# layer (per the ADR amendment); here the parser accepts any well-formed
# decimal-as-string and lets the application layer adjudicate.
_WITHHOLDING_RE: Final = re.compile(r"^\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*%?\s*$")
_M2_RE: Final = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:m²|m2)?\s*$")
_CADASTRAL_RE: Final = re.compile(r"^[0-9A-Z]{20}$")


class CensoFactSet(BaseModel):
    """Typed projection of one G313 (Mis Datos Censales) page read.

    Every field is optional because G313 returns whatever subset of the
    censo the operator's NIF actually has registered. The
    CensoSyncService layer above is responsible for refusing a partial
    capture that contradicts a required calculation; the adapter never
    fabricates a default to fill a hole.
    """

    model_config = _STRICT_FROZEN

    fiscal_address_cadastral_reference: str | None = Field(
        default=None,
        max_length=64,
        description="Catastral reference of the fiscal domicilio (RDLeg 1/2004).",
    )
    fiscal_address_is_habitual_vivienda: bool | None = Field(
        default=None,
        description="Whether the fiscal domicilio coincides with the operator's habitual vivienda.",
    )
    activity_start_date: date | None = Field(
        default=None,
        description="RGAT Art. 9 censo activity start date.",
    )
    activity_end_date: date | None = Field(
        default=None,
        description="RGAT Art. 11 censo activity end date (None while still active).",
    )
    establecimiento_type: str | None = Field(
        default=None,
        max_length=64,
        description="Tipo de establecimiento (propio / arrendado / cedido_gratuitamente).",
    )
    elected_withholding_pct: str | None = Field(
        default=None,
        max_length=8,
        description="Elected withholding percentage as published by AEAT (validated against {15, 7, 1} above).",
    )
    vivienda_office_total_m2: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="Total m² of the habitual vivienda when partially afecta to the activity.",
    )
    vivienda_office_office_m2: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="m² of the habitual vivienda dedicated to the activity.",
    )
    iae_epigraph: str | None = Field(
        default=None,
        max_length=16,
        description="IAE epigraph the operator is censado under (RDLeg 1175/1990).",
    )


class CensoParseError(SedeError):
    """Raised when a value on the G313 page does not parse against the schema."""

    def __init__(self, message: str, *, field: str, raw: str) -> None:
        super().__init__(
            message,
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"field": field, "raw_value": raw},
        )


_G313_LABELS: Final[dict[str, str]] = {
    "fiscal_address_cadastral_reference": "Referencia catastral",
    "fiscal_address_is_habitual_vivienda": "Vivienda habitual",
    "activity_start_date": "Fecha de alta de la actividad",
    "activity_end_date": "Fecha de baja de la actividad",
    "establecimiento_type": "Tipo de establecimiento",
    "elected_withholding_pct": "Porcentaje de retención",
    "vivienda_office_total_m2": "Superficie total de la vivienda",
    "vivienda_office_office_m2": "Superficie afecta a la actividad",
    "iae_epigraph": "Epígrafe IAE",
}


def parse_g313_html(html: str) -> CensoFactSet:
    """Parse a G313 (Mis Datos Censales) result page into a :class:`CensoFactSet`.

    The parser is deliberately label-driven rather than DOM-structural:
    AEAT re-shapes the surrounding ZK markup periodically without
    changing the Spanish field labels, so anchoring on labels gives the
    longest-lived contract. Each label maps to one field; missing labels
    yield ``None`` on the corresponding attribute.

    Raises :exc:`CensoParseError` when a label is present but its
    value does not parse against the field schema — that is a shape
    change and must surface to the operator rather than silently drop
    the value.
    """
    extracted = _label_value_table(html)
    return CensoFactSet(
        fiscal_address_cadastral_reference=_parse_cadastral(
            extracted.get(_G313_LABELS["fiscal_address_cadastral_reference"]),
        ),
        fiscal_address_is_habitual_vivienda=_parse_bool(
            extracted.get(_G313_LABELS["fiscal_address_is_habitual_vivienda"]),
        ),
        activity_start_date=_parse_date(
            extracted.get(_G313_LABELS["activity_start_date"]),
            field="activity_start_date",
        ),
        activity_end_date=_parse_date(
            extracted.get(_G313_LABELS["activity_end_date"]),
            field="activity_end_date",
        ),
        establecimiento_type=_normalise_token(
            extracted.get(_G313_LABELS["establecimiento_type"]),
        ),
        elected_withholding_pct=_parse_withholding(
            extracted.get(_G313_LABELS["elected_withholding_pct"]),
        ),
        vivienda_office_total_m2=_parse_m2(
            extracted.get(_G313_LABELS["vivienda_office_total_m2"]),
            field="vivienda_office_total_m2",
        ),
        vivienda_office_office_m2=_parse_m2(
            extracted.get(_G313_LABELS["vivienda_office_office_m2"]),
            field="vivienda_office_office_m2",
        ),
        iae_epigraph=_normalise_token(
            extracted.get(_G313_LABELS["iae_epigraph"]),
        ),
    )


_TAG_RE: Final = re.compile(r"<[^>]+>")
_WS_RE: Final = re.compile(r"\s+")


def _label_value_table(html: str) -> dict[str, str]:
    """Flatten HTML to a label → value mapping.

    Strips tags, collapses whitespace, then sweeps the text for each
    known G313 label and captures the immediately-following non-empty
    fragment as the value. Tolerates labels rendered with or without a
    trailing colon.
    """
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()
    table: dict[str, str] = {}
    for label in _G313_LABELS.values():
        for pattern in (f"{label}:", label):
            index = text.find(pattern)
            if index == -1:
                continue
            after = text[index + len(pattern) :].strip()
            value = _take_value_token(after)
            if value:
                table[label] = value
                break
    return table


def _take_value_token(after: str) -> str:
    """Return the first value token following a label.

    Stops at the next known label so a value-less label cell does not
    swallow the next field's value.
    """
    other_labels = sorted(_G313_LABELS.values(), key=lambda label: len(label), reverse=True)
    cutoff = len(after)
    for other in other_labels:
        for needle in (f"{other}:", other):
            position = after.find(needle)
            if position != -1 and position < cutoff:
                cutoff = position
    return after[:cutoff].strip().rstrip(":").strip()


def _normalise_token(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    return cleaned or None


def _parse_cadastral(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip().upper().replace(" ", "")
    if not cleaned:
        return None
    if not _CADASTRAL_RE.match(cleaned):
        raise CensoParseError(
            f"cadastral reference {cleaned!r} is not 20 alphanumerics",
            field="fiscal_address_cadastral_reference",
            raw=raw,
        )
    return cleaned


def _parse_date(raw: str | None, *, field: str) -> date | None:
    try:
        return _parse_date_canonical(raw, fmt="ddmmyyyy", on_error="raise")
    except ValueError as exc:
        raise CensoParseError(
            f"{field} value {raw!r}: {exc}",
            field=field,
            raw=raw or "",
        ) from exc


def _parse_withholding(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    match = _WITHHOLDING_RE.match(cleaned)
    if match is None:
        raise CensoParseError(
            f"withholding percentage {cleaned!r} is not a valid percentage literal",
            field="elected_withholding_pct",
            raw=raw,
        )
    return normalize_decimal_separators(match.group(1), strip_thousands=False)


def _parse_m2(raw: str | None, *, field: str) -> Decimal | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    match = _M2_RE.match(cleaned)
    if match is None:
        raise CensoParseError(
            f"{field} value {cleaned!r} is not a valid m² literal",
            field=field,
            raw=raw,
        )
    decimal_str = normalize_decimal_separators(match.group(1), strip_thousands=False)
    try:
        return Decimal(decimal_str)
    except InvalidOperation as exc:
        raise CensoParseError(
            f"{field} value {cleaned!r} is not a valid decimal",
            field=field,
            raw=raw,
        ) from exc


__all__ = [
    "CensoFactSet",
    "CensoParseError",
    "parse_g313_html",
]
