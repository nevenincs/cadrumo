"""**DRAFT / PREVIEW** Modelo 303 fichero-BOE schema for ejercicio 2024.

.. warning::

   This module is a proof-of-concept skeleton, NOT a production schema.
   Verification against DR303e24.xlsx / DR303e25.xlsx revealed that
   the prior research offsets were off-by-one on 3 of 5 spot-checks
   and miscategorised casilla 01's semantics. A full schema requires
   xlsx-ingestion tooling to avoid hand-transcription errors across
   the ~2600 DP30301 fields alone.

   This skeleton exists to exercise the multi-segment
   envelope architecture + inline-sign encoder END-TO-END,
   proving the primitives work for Modelo 303's shape without
   committing to specific casilla offsets. It is NOT wired into the
   CLI schema registry (see ``src/aeat/entrypoints/cli/submission/export.py``).

## Record shape (verified from DR303e25.xlsx)

- Multi-segment XML-tagged envelope, NOT a flat record.
- Envelope has SEVEN segments: ``DP30300`` (header) + ``DP30301``
  (identification + devengado) + ``DP30302`` (simplificado) +
  ``DP30303`` (resultado + rectificativa) + ``DP30304`` (annual
  exonerados) + ``DP30305`` (prorratas) + ``DP303DID`` (trailer).
- Encoding: ISO-8859-1 (Latin-1), NOT CP1252 and NOT ISO-8859-15.
  Confirmed via AEAT portal error-message docs explicitly
  specifying Latin-1.
- Signed numeric fields (casillas 69, 71, others) use INLINE 'N'
  prefix convention (byte 0 = 'N' for negatives / ' ' for
  non-negatives; remaining bytes = zero-padded |value|). Different
  from Modelo 130's TIPO_DECLARACION flag.
- Casilla widths: 17 bytes each (15 int + 2 decimal implicit),
  NOT 13 like Modelo 130.

## Skeleton contents

This file ships the MINIMAL shape to prove the architecture:

- DP30300 envelope (opener/closer + ejercicio + período + NIF).
- DP30301 page with a single casilla placeholder at a verified
  offset (14 for NIF — the one offset stream D got right).
- DP30303 page with casilla 69 at offset 323 (the ONLY offset both
  stream D and the audit agreed on), using ``inline_sign=True``.

Every other DP30301 / DP30302 / DP30304 / DP30305 / DP303DID field
is OUT OF SCOPE for this preview. + will populate them from
the xlsx ingestion output.

## References

- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos_24/DR303e24.xlsx
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos_25/DR303e25.xlsx
- https://www.boe.es/buscar/doc.php?id=BOE-A-2024-16129 (Orden HAC/819/2024)
"""

from __future__ import annotations

from ._record_spec import (
    FicheroBoeEncoding,
    FieldKind,
    SegmentSpec,
    SignedMode,
    record_field,
)

ENCODING: FicheroBoeEncoding = "iso-8859-1"

# DP30300 envelope header — minimal: just enough to carry the
# ejercicio/período/NIF trio. Real envelope also has programa ED,
# AUX block, and closer tag — deferred to the production schema.
_DP30300_MINI = SegmentSpec(
    segment_id="DP30300_PREVIEW",
    specs=(
        record_field(
            offset=1,
            length=2,
            field_id="OPEN_ENV",
            kind=FieldKind.RESERVED,
            literal_value="<T",
        ),
        record_field(
            offset=3,
            length=3,
            field_id="MODELO",
            kind=FieldKind.RESERVED,
            literal_value="303",
        ),
        record_field(
            offset=6,
            length=1,
            field_id="DISCRIMINANTE",
            kind=FieldKind.RESERVED,
            literal_value="0",
        ),
        record_field(
            offset=7,
            length=4,
            field_id="EJERCICIO",
            kind=FieldKind.NUMERIC,
        ),
        record_field(
            offset=11,
            length=2,
            field_id="PERIODO",
            kind=FieldKind.ALPHANUMERIC,
        ),
    ),
    total_length=12,
)

# DP30301 preview: only NIF — at offset 14 per xlsx verification.
# Positions 1-13 filled with filler RESERVED for now; DP30301 is
# actually 1581 bytes total but this preview stops at position 22
# (NIF end) to prove the architecture without committing to
# unverified offsets.
_DP30301_MINI = SegmentSpec(
    segment_id="DP30301_PREVIEW",
    specs=(
        record_field(
            offset=1,
            length=2,
            field_id="OPEN_PAGE_BEGIN",
            kind=FieldKind.RESERVED,
            literal_value="<T",
        ),
        record_field(
            offset=3,
            length=3,
            field_id="PAGE_MODELO",
            kind=FieldKind.RESERVED,
            literal_value="303",
        ),
        record_field(
            offset=6,
            length=5,
            field_id="PAGE_ID",
            kind=FieldKind.RESERVED,
            literal_value="01000",
        ),
        record_field(
            offset=11,
            length=1,
            field_id="PAGE_CLOSE_ANGLE",
            kind=FieldKind.RESERVED,
            literal_value=">",
        ),
        record_field(
            offset=12,
            length=1,
            field_id="PAGE_PREFIX_FILLER",
            kind=FieldKind.RESERVED,
            literal_value=" ",
        ),
        record_field(
            offset=13,
            length=1,
            field_id="TIPO_DECLARACION",
            kind=FieldKind.ALPHANUMERIC,
        ),
        record_field(
            offset=14,
            length=9,
            field_id="NIF_DECLARANTE",
            kind=FieldKind.ALPHANUMERIC,
        ),
    ),
    total_length=22,
)

# DP30303 preview: casilla 69 at offset 323 (only offset both
# stream D and agreed on). The 320 bytes before it
# are filled as a single ALPHANUMERIC placeholder — the real
# layout has many intermediate fields that + will
# populate from xlsx.
_DP30303_MINI = SegmentSpec(
    segment_id="DP30303_PREVIEW",
    specs=(
        record_field(
            offset=1,
            length=322,
            field_id="DP30303_PREFIX_FILLER",
            kind=FieldKind.ALPHANUMERIC,
        ),
        record_field(
            offset=323,
            length=17,
            field_id="CASILLA_69_RESULTADO",
            casilla_id="69",
            kind=FieldKind.CURRENCY,
            signed_mode=SignedMode.INLINE_SIGN,
        ),
    ),
    total_length=339,
)

ENVELOPE_PREVIEW: tuple[SegmentSpec, ...] = (
    _DP30300_MINI,
    _DP30301_MINI,
    _DP30303_MINI,
)

REQUIRED_HEADER_FIELDS: frozenset[str] = frozenset({"EJERCICIO", "PERIODO", "NIF_DECLARANTE", "TIPO_DECLARACION"})

__all__ = ["ENCODING", "ENVELOPE_PREVIEW", "REQUIRED_HEADER_FIELDS"]
