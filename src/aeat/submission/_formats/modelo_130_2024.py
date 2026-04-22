"""Fichero-BOE record spec for Modelo 130 ejercicio 2024.

Wave 77c (EPIC #201 / EPIC #305). Source: AEAT *Diseño de Registro*
DR130e15v12.xls (revised 2015-02, last-modified 2021-07-13). The
Modelo 130 layout has NOT been superseded since the 2015 revision;
Orden EHA/672/2007 (BOE-A-2007-6032) remains the governing norma.
Wave 68 audit confirmed Orden HAC/819/2024 is IVA-only, not 130.

Record shape: single record per filing. Field content fills 879
bytes (positions 1-879); the serialiser appends a 2-byte CRLF
terminator as line-ending (positions 880-881 in the on-wire
stream). Encoding: Windows-1252 (CP1252). Filename convention:
``{NIF}{ejercicio}{periodo}.130``.

``RECORD_LENGTH`` below measures the field-content byte count
(879) — NOT the on-wire byte count including CRLF (881). The
serialiser handles terminator bytes separately.

Sign convention: no separate SIGNO field. A negative filing is
indicated via ``tipo_declaracion = "N"``. Currency fields encode
the absolute magnitude with 2 implicit decimals (no decimal point,
13 digits zero-padded).

References:
    - https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos/DR130e15v12.xls
    - https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_100_199/archivos/dr130.09.pdf
    - https://www.boe.es/buscar/act.php?id=BOE-A-2007-6032
"""

from __future__ import annotations

from ._record_spec import (
    FicheroBoeEncoding,
    FieldKind,
    RecordFieldSpec,
    record_field,
    validate_record_specs,
)

#: Field-content byte length per the 2015+ Diseño de Registro
#: (positions 1-879). On-wire stream adds 2-byte CRLF terminator.
RECORD_LENGTH = 879

#: Wire encoding for Modelo 130 fichero-BOE output.
ENCODING: FicheroBoeEncoding = "cp1252"

#: Width of every currency (amount) field: 11 integer + 2 implicit
#: decimals = 13 digits zero-padded.
_AMOUNT_LEN = 13

_RECORD_SPECS: tuple[RecordFieldSpec, ...] = (
    # ---- Record header (positions 1-75) ----
    record_field(
        offset=1,
        length=3,
        field_id="MODELO",
        kind=FieldKind.RESERVED,
        literal_value="130",
    ),
    record_field(
        offset=4,
        length=4,
        field_id="EJERCICIO",
        kind=FieldKind.NUMERIC,
    ),
    record_field(
        offset=8,
        length=2,
        field_id="PERIODO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=10,
        length=9,
        field_id="NIF_DECLARANTE",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=19,
        length=60,
        field_id="APELLIDOS_NOMBRE",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=79,
        length=1,
        field_id="TIPO_DECLARACION",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Apartado I: actividades en estimación directa ----
    record_field(
        offset=80,
        length=_AMOUNT_LEN,
        field_id="INGRESOS_COMPUTABLES",
        casilla_id="01",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=93,
        length=_AMOUNT_LEN,
        field_id="GASTOS_DEDUCIBLES",
        casilla_id="02",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=106,
        length=_AMOUNT_LEN,
        field_id="RENDIMIENTO_NETO",
        casilla_id="03",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=119,
        length=_AMOUNT_LEN,
        field_id="VEINTE_PCT_CASILLA_03",
        casilla_id="04",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=132,
        length=_AMOUNT_LEN,
        field_id="DEDUCIR_TRIMESTRES_ANT",
        casilla_id="05",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=145,
        length=_AMOUNT_LEN,
        field_id="RETENCIONES_INGR_CUENTA",
        casilla_id="06",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=158,
        length=_AMOUNT_LEN,
        field_id="RESULTADO_APARTADO_I",
        casilla_id="07",
        kind=FieldKind.CURRENCY,
    ),
    # ---- Apartado II: actividades agrícolas/ganaderas ----
    record_field(
        offset=171,
        length=_AMOUNT_LEN,
        field_id="INGRESOS_AGRARIOS",
        casilla_id="08",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=184,
        length=_AMOUNT_LEN,
        field_id="DOS_PCT_CASILLA_08",
        casilla_id="09",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=197,
        length=_AMOUNT_LEN,
        field_id="RETENCIONES_AGRARIAS",
        casilla_id="10",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=210,
        length=_AMOUNT_LEN,
        field_id="RESULTADO_APARTADO_II",
        casilla_id="11",
        kind=FieldKind.CURRENCY,
    ),
    # ---- Liquidación total ----
    record_field(
        offset=223,
        length=_AMOUNT_LEN,
        field_id="SUMA_PARCIALES",
        casilla_id="12",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=236,
        length=_AMOUNT_LEN,
        field_id="MINORACION_RD_LEY",
        casilla_id="13",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=249,
        length=_AMOUNT_LEN,
        field_id="NETO_TRAS_MINORACION",
        casilla_id="14",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=262,
        length=_AMOUNT_LEN,
        field_id="NEGATIVOS_ANTERIORES",
        casilla_id="15",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=275,
        length=_AMOUNT_LEN,
        field_id="DEDUCCION_VIVIENDA",
        casilla_id="16",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=288,
        length=_AMOUNT_LEN,
        field_id="DIFERENCIA",
        casilla_id="17",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=301,
        length=_AMOUNT_LEN,
        field_id="A_DEDUCIR_AUTOLIQ_ANT",
        casilla_id="18",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=314,
        length=_AMOUNT_LEN,
        field_id="RESULTADO_FINAL",
        casilla_id="19",
        kind=FieldKind.CURRENCY,
    ),
    # ---- Ingreso / devolución block ----
    record_field(
        offset=327,
        length=_AMOUNT_LEN,
        field_id="IMPORTE_INGRESO",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=340,
        length=1,
        field_id="FORMA_PAGO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=341,
        length=20,
        field_id="IBAN_CCC",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=361,
        length=1,
        field_id="A_DEDUCIR_FLAG",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Complementaria block ----
    record_field(
        offset=362,
        length=16,
        field_id="COMPLEMENTARIA_CODIGO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=378,
        length=13,
        field_id="COMPLEMENTARIA_JUSTIFICANTE",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Contact + observaciones ----
    record_field(
        offset=391,
        length=100,
        field_id="CONTACTO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=491,
        length=9,
        field_id="TELEFONO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=500,
        length=350,
        field_id="OBSERVACIONES",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Firma block ----
    record_field(
        offset=850,
        length=16,
        field_id="FIRMA_LOCALIDAD",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=866,
        length=2,
        field_id="FIRMA_DIA",
        kind=FieldKind.NUMERIC,
    ),
    record_field(
        offset=868,
        length=8,
        field_id="FIRMA_MES",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=876,
        length=4,
        field_id="FIRMA_ANO",
        kind=FieldKind.NUMERIC,
    ),
)

# Enforce monotonic contiguity at import time. Any off-by-one in the
# hand-authored specs above will fail-fast at collection.
validate_record_specs(_RECORD_SPECS, total_length=RECORD_LENGTH)


__all__ = [
    "ENCODING",
    "RECORD_LENGTH",
    "_RECORD_SPECS",
]
