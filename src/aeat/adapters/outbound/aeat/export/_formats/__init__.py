"""Fichero-BOE export formats per modelo.

Per-modelo serialisers for the AEAT "importar datos" fixed-width
fichero-BOE format. The shared primitives live in
:mod:`._record_spec`; concrete modelo modules
(``modelo_{n}_{year}.py``) declare the on-wire layout as constants.

Each ``modelo_{n}_{year}.py`` module exports:

- ``RECORD_SPECS: tuple[RecordFieldSpec, ...]`` — field layout pinned
  to the BOE *Diseño de registros* version.
- A ``serialise`` callable produced by
  :func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise`
  — emits the wire-encoding byte string the AEAT portal accepts.
- A ``parse`` callable produced by
  :func:`aeat.adapters.outbound.aeat.export._formats._deserialise.deserialise`
  — round-trip inverse.

This module re-exports the shared primitives needed to author or
consume per-modelo specs:
:class:`RecordFieldSpec`, :class:`SegmentSpec`, :class:`FieldKind`,
:class:`Justification`, :class:`DateFmt`, :class:`SignedMode`,
:func:`record_field`, :func:`encode_currency`, :func:`encode_date`,
:func:`encode_text`, :func:`validate_record_specs`, and
:func:`validate_segment_specs`.
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
    SignedMode,
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
    "SignedMode",
    "encode_currency",
    "encode_date",
    "encode_text",
    "record_field",
    "validate_record_specs",
    "validate_segment_specs",
]
