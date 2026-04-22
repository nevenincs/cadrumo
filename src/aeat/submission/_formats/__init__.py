"""Fichero-BOE export formats per modelo (EPIC #201, wave 75d).

This package houses per-modelo serialisers for the AEAT "importar
datos" fixed-width fichero-BOE format. See
`.vault/adr/2026-04-22-aeat-fichero-boe-export-adr.md` for the
architecture.

Each ``modelo_{N}_{year}.py`` module exports:

- ``_RECORD_SPECS: tuple[RecordFieldSpec, ...]`` — field layout pinned
  to the BOE *Diseño de registros* version.
- ``serialise(draft: FilingDraft) -> bytes`` — produces the
  ISO-8859-15 byte string Kent uploads to the AEAT portal.
- ``parse(payload: bytes) -> FilingDraft`` — round-trip inverse.

Waves 76+ populate Modelo 130 / 303 / 390 schemas from their
respective Órdenes ministeriales; this wave ships only the shared
``_record_spec.py`` primitives.
"""

from __future__ import annotations

from ._record_spec import (
    DEFAULT_ENCODING,
    DateFmt,
    FicheroBoeEncoding,
    FieldKind,
    Justification,
    RecordFieldSpec,
    SegmentSpec,
    encode_currency,
    encode_date,
    encode_text,
    record_field,
    validate_record_specs,
    validate_segment_specs,
)

__all__ = [
    "DEFAULT_ENCODING",
    "DateFmt",
    "FicheroBoeEncoding",
    "FieldKind",
    "Justification",
    "RecordFieldSpec",
    "SegmentSpec",
    "encode_currency",
    "encode_date",
    "encode_text",
    "record_field",
    "validate_record_specs",
    "validate_segment_specs",
]
