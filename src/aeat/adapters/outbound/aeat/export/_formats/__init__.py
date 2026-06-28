"""Low-level fixed-width fichero-BOE primitives.

This package contains explicit-spec byte helpers for fichero-BOE records
and envelopes. The active modelo export flow is registry-driven through
:func:`aeat.application.filing.export_draft`, which renders
:class:`aeat.domain.calculations.registry.ExportLayoutDefinition`
records directly; export verification re-reads files through
:func:`aeat.domain.calculations.registry.parse_export_payload`.

The primitives here remain useful when a caller already has adapter-local
:class:`RecordFieldSpec` or :class:`SegmentSpec` tuples and needs to
validate byte-level round trips. This module re-exports:
:class:`RecordFieldSpec`, :class:`SegmentSpec`, :class:`FieldKind`,
:class:`Justification`, :class:`DateFmt`, :class:`SignedMode`,
:func:`record_field`, :func:`encode_currency`, :func:`encode_date`,
:func:`encode_text`, :func:`validate_record_specs`, and
:func:`validate_segment_specs`.

See Also:
    :mod:`aeat.adapters.outbound.aeat.export`
        Supported outbound export package root and error import surface.
    :func:`aeat.application.filing.export_draft`
        Application entry point that writes approved drafts from registry
        export layouts.
    :func:`aeat.domain.calculations.registry.parse_export_payload`
        Registry parser used by export verification.
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
