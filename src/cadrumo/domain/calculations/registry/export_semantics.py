"""Canonical semantic producer vocabulary for registry export fields."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from .._export_field_kind import CasillaFieldKind

__all__ = [
    "ExportComputedKey",
    "ExportDraftAttribute",
    "ExportSemanticPayloadAxis",
    "export_semantic_payload_axis",
]


class ExportDraftAttribute(StrEnum):
    """Closed draft values the filing renderer may project directly."""

    FILING_YEAR = "filing_year"
    PERIOD_CODE = "period_code"
    PERIOD_START_DATE = "period_start_date"
    PERIOD_END_DATE = "period_end_date"


class ExportComputedKey(StrEnum):
    """Closed export values computed by the filing renderer."""

    ENVELOPE_CLOSING_TAG = "envelope_closing_tag"
    SEPA_MARCA = "sepa_marca"
    #: Renders the official ``C`` page marker from amendment evidence alone.
    #: Modelo-neutral: any modelo whose design admits ``"C"`` on a
    #: complementaria page slot resolves it through this one key.
    COMPLEMENTARIA_PAGE_MARKER = "complementaria_page_marker"
    M303_COMPLEMENTARIA_MARKER = "m303_complementaria_marker"
    M303_NO_ACTIVITY_MARKER = "m303_no_activity_marker"


class ExportSemanticPayloadAxis(StrEnum):
    """The one payload field permitted for each semantic export kind."""

    CASILLA_ID = "casilla_id"
    BINDING = "binding"
    LITERAL = "literal"
    PRODUCER_KEY = "producer_key"
    PROJECTION_REF = "projection_ref"
    DRAFT_ATTRIBUTE = "draft_attribute"
    COMPUTED_KEY = "computed_key"


_PAYLOAD_AXIS_BY_KIND: Final[dict[CasillaFieldKind, ExportSemanticPayloadAxis | None]] = {
    CasillaFieldKind.CASILLA: ExportSemanticPayloadAxis.CASILLA_ID,
    CasillaFieldKind.BINDING: ExportSemanticPayloadAxis.BINDING,
    CasillaFieldKind.LITERAL: ExportSemanticPayloadAxis.LITERAL,
    CasillaFieldKind.HEADER: ExportSemanticPayloadAxis.PRODUCER_KEY,
    CasillaFieldKind.PROJECTION: ExportSemanticPayloadAxis.PROJECTION_REF,
    CasillaFieldKind.DRAFT: ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE,
    CasillaFieldKind.COMPUTED: ExportSemanticPayloadAxis.COMPUTED_KEY,
    CasillaFieldKind.FILLER: None,
    CasillaFieldKind.CHECKSUM: None,
}


def export_semantic_payload_axis(kind: CasillaFieldKind) -> ExportSemanticPayloadAxis | None:
    """Return the sole semantic payload axis admitted for ``kind``."""
    return _PAYLOAD_AXIS_BY_KIND[kind]
