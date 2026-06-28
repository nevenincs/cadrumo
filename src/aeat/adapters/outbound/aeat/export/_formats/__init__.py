"""Shared fichero-BOE export primitives.

The package contains only reusable fixed-width encoding primitives.
Reviewed registry-backed export definitions provide the concrete field
and segment declarations after legal-source validation. This module
re-exports the shared primitives needed to validate and use those
declarations:
:class:`RecordFieldSpec`, :class:`SegmentSpec`, :class:`FieldKind`,
:class:`Justification`, :class:`DateFmt`, :class:`SignedMode`,
:func:`record_field`, :func:`encode_currency`, :func:`encode_date`,
:func:`encode_text`, :func:`validate_record_specs`, and
:func:`validate_segment_specs`.
"""

from __future__ import annotations

from ._record_spec import (
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
