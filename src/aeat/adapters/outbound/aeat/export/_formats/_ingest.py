"""DR *Diseño de Registros* ingestion library.

Converts a JSON representation of an AEAT *Diseño de Registros*
specification into a tuple of
:class:`aeat.adapters.outbound.aeat.export._formats._record_spec.SegmentSpec`
objects ready for the multi-segment envelope serialiser. Isolates the
xlsx-parsing work (which agents perform externally with ``openpyxl``)
from the schema-generation work (which is pure pydantic construction).

A DR spec document is a JSON object keyed by ``segment_id``. Each
segment carries its ``total_length`` plus an ordered list of fields:

.. code-block:: json

    {
      "source": {
        "modelo": "303",
        "ejercicio": "2024",
        "orden": "Orden HAC/819/2024",
        "boe_id": "BOE-A-2024-16129",
        "xlsx": "DR303e24.xlsx",
        "retrieval_date": "2026-04-22"
      },
      "encoding": "iso-8859-1",
      "segments": {
        "DP30300": {
          "total_length": 329,
          "fields": [
            {"offset": 1, "length": 2, "field_id": "OPEN_ENV",
             "kind": "RESERVED", "literal": "<T"},
            ...
          ]
        },
        "DP30301": { ... }
      }
    }

This format is hand-authored (or research-agent-authored from the
xlsx) and committed to ``tests/fixtures/dr_specs/`` for auditability
and deterministic schema regeneration.

Security note: this library parses JSON only — no binary xlsx parsing
lives here. Agents that download xlsx files and translate to JSON are
out of the production codebase; their output is committed as plain
text.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict, cast

from ._record_spec import (
    DateFmt,
    FicheroBoeEncoding,
    FieldKind,
    Justification,
    RecordFieldSpec,
    SegmentSpec,
    SignedMode,
    record_field,
    validate_segment_specs,
)


class IngestSourceMeta(TypedDict, total=False):
    """Provenance metadata written into the generated module docstring.

    Every key is optional; only the fields that the underlying JSON
    spec carries are surfaced. ``extra_required_fields`` is an optional
    list of field IDs to force-merge into ``REQUIRED_HEADER_FIELDS`` so
    the heuristic in
    :func:`aeat.adapters.outbound.aeat.export._formats._generate._collect_required_field_ids`
    can be extended for modelos whose header spans multiple segments
    (for example Modelo 303's per-page identification fields in
    DP30301).
    """

    modelo: str
    ejercicio: str
    orden: str
    boe_id: str
    xlsx: str
    retrieval_date: str
    notes: str
    extra_required_fields: list[str]


class IngestedSpec(TypedDict):
    """Parsed output of :func:`ingest_dr_spec_document`.

    Attributes:
        source: Provenance metadata copied from the JSON document's
            ``source`` block.
        encoding: Validated wire encoding for the modelo (one of the
            allowed values in
            :data:`aeat.adapters.outbound.aeat.export._formats._record_spec.FicheroBoeEncoding`).
        segments: Ordered tuple of segment specifications ready for the
            envelope serialiser.
    """

    source: IngestSourceMeta
    encoding: FicheroBoeEncoding
    segments: tuple[SegmentSpec, ...]


# Maps the JSON string literal (case-insensitive) to the enum.
_KIND_MAP: Mapping[str, FieldKind] = {
    "ALPHANUMERIC": FieldKind.ALPHANUMERIC,
    "NUMERIC": FieldKind.NUMERIC,
    "CURRENCY": FieldKind.CURRENCY,
    "DATE": FieldKind.DATE,
    "RESERVED": FieldKind.RESERVED,
}

_JUSTIFICATION_MAP: Mapping[str, Justification] = {
    "LEFT": Justification.LEFT,
    "RIGHT": Justification.RIGHT,
}

_DATE_FMT_MAP: Mapping[str, DateFmt] = {
    "YYYYMMDD": DateFmt.YYYYMMDD,
    "DDMMYYYY": DateFmt.DDMMYYYY,
}

_SIGNED_MODE_MAP: Mapping[str, SignedMode] = {
    "UNSIGNED": SignedMode.UNSIGNED,
    "INLINE_SIGN": SignedMode.INLINE_SIGN,
}


def _parse_field(entry: Mapping[str, Any]) -> RecordFieldSpec:
    """Construct a :class:`RecordFieldSpec` from a single JSON field entry."""
    kind_raw = str(entry["kind"]).upper()
    kind = _KIND_MAP.get(kind_raw)
    if kind is None:
        raise ValueError(f"unknown FieldKind {kind_raw!r}")

    justification_raw = entry.get("justification")
    justification = _JUSTIFICATION_MAP[str(justification_raw).upper()] if justification_raw is not None else None

    date_fmt_raw = entry.get("date_fmt")
    date_fmt = _DATE_FMT_MAP[str(date_fmt_raw).upper()] if date_fmt_raw is not None else None

    signed_mode_raw = entry.get("signed_mode", "UNSIGNED")
    signed_mode = _SIGNED_MODE_MAP[str(signed_mode_raw).upper()]

    return record_field(
        offset=int(entry["offset"]),
        length=int(entry["length"]),
        field_id=str(entry["field_id"]),
        casilla_id=entry.get("casilla_id"),
        kind=kind,
        justification=justification,
        pad_char=entry.get("pad_char"),
        literal_value=entry.get("literal"),
        date_fmt=date_fmt,
        signed_mode=signed_mode,
    )


def ingest_dr_spec_document(document: Mapping[str, Any]) -> IngestedSpec:
    """Parse a DR JSON spec document into an :class:`IngestedSpec`.

    Runs
    :func:`aeat.adapters.outbound.aeat.export._formats._record_spec.validate_segment_specs`
    on the assembled tuple so any offset, contiguity, or duplication
    error in the source JSON surfaces at ingestion time with the
    offending ``segment_id`` named.

    Args:
        document: Decoded JSON object loaded from a DR spec fixture.

    Returns:
        An :class:`IngestedSpec` ready for the serialiser or generator.

    Raises:
        KeyError: On missing required top-level keys.
        ValueError: On unknown enum values, unsupported encoding, or
            spec-invariant violations.
    """
    source_raw = document.get("source", {})
    source_dict: dict[str, Any] = dict(source_raw) if isinstance(source_raw, Mapping) else {}
    source = cast(IngestSourceMeta, source_dict)
    encoding_raw = str(document["encoding"]).lower()
    allowed_encodings = {"cp1252", "iso-8859-1", "iso-8859-15"}
    if encoding_raw not in allowed_encodings:
        raise ValueError(f"encoding {encoding_raw!r} not in allowed set {allowed_encodings}")
    encoding = cast(FicheroBoeEncoding, encoding_raw)

    segments_raw = document["segments"]
    if not isinstance(segments_raw, Mapping):
        raise ValueError("'segments' must be a mapping of segment_id to spec")

    segments_list: list[SegmentSpec] = []
    for segment_id, body in segments_raw.items():
        if not isinstance(body, Mapping):
            raise ValueError(f"segment {segment_id!r} body must be a mapping")
        fields_raw = body.get("fields", [])
        specs = tuple(_parse_field(entry) for entry in fields_raw)
        segments_list.append(
            SegmentSpec(
                segment_id=str(segment_id),
                specs=specs,
                total_length=int(body["total_length"]),
            )
        )

    segments = tuple(segments_list)
    validate_segment_specs(segments)
    return IngestedSpec(
        source=source,
        encoding=encoding,
        segments=segments,
    )


def ingest_dr_spec_path(path: Path | str) -> IngestedSpec:
    """Load and ingest a DR spec document from a JSON file.

    Thin convenience wrapper over :func:`ingest_dr_spec_document` that
    handles file IO and JSON decoding.

    Raises:
        ValueError: If the file does not contain a JSON object at the
            top level, or any error raised by
            :func:`ingest_dr_spec_document`.
    """
    payload = Path(path).read_text(encoding="utf-8")
    document = json.loads(payload)
    if not isinstance(document, Mapping):
        raise ValueError(f"{path!s} must contain a JSON object at the top level")
    return ingest_dr_spec_document(document)


__all__ = [
    "IngestedSpec",
    "ingest_dr_spec_document",
    "ingest_dr_spec_path",
]
