"""Shared fichero-BOE export primitives.

The package intentionally does not commit per-modelo generated Python
layouts. Registry-backed modelo definitions must provide the concrete
field and segment declarations at runtime after legal-source validation.
This module re-exports the shared primitives needed to validate and use
those declarations:
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
