"""BOE-PDF extraction and source-fetch adapters for AEAT modelo schemas."""

from __future__ import annotations

from ._boe_extractor import BoeOrdenExtractor
from ._fetch import (
    BOE_ORDEN_SOURCES,
    BoeOrdenSource,
    FetchedSchemaSource,
    fetch_boe_pdf,
)

__all__ = (
    "BOE_ORDEN_SOURCES",
    "BoeOrdenExtractor",
    "BoeOrdenSource",
    "FetchedSchemaSource",
    "fetch_boe_pdf",
)
