"""Fichero-BOE record spec for Modelo 130 ejercicio 2024.

 (scaffold) + (BOE-accurate rewrite). Source: AEAT
*Diseño de Registro* ``dr130.09.pdf`` + ``DR130e15v12.xls`` (2015
revision, last-modified 2021-07-13). The Modelo 130 layout has NOT
been superseded since the 2015 revision; Orden EHA/672/2007
(BOE-A-2007-6032) remains the governing norma. Orden HAC/819/2024 is
IVA-scoped (Modelo 303), not 130.

## Record shape

- Total on-wire size: **880 bytes** per filing (positions 1-878 for
  field content + positions 879-880 for the CRLF terminator).
- Encoding: Windows-1252 (CP1252). Filename: ``{NIF}{ejercicio}{periodo}.130``.
- ``RECORD_LENGTH = 878`` below counts ONLY the field content
  (positions 1-878). The serialiser owns the 2-byte CRLF terminator
  — it is not represented as a field in ``RECORD_SPECS``.

## Sign convention

No separate SIGNO field. A negative declaration is indicated via
``tipo_declaracion = "N"``. Amount fields emit the absolute magnitude
with 2 implicit decimals (13 digits zero-padded, no decimal point).

## History of prior miscites (tracked for auditability)

- draft used Stream D's offsets which did not match
  dr130.09.pdf for the header block — TIPO_DECLARACION at 79 (wrong;
  real is 7), NIF at 10 (real 13), EJERCICIO at 4 (real 71), PERIODO
  at 8 (real 75). All casillas shifted +3. IBAN was a single 20-byte
  field; real is 4 sub-fields. FIRMA_MES was length 8; real is 10.
   (this file) aligns with dr130.09.pdf verbatim.

## References

- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_100_199/archivos/dr130.09.pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos/DR130e15v12.xls
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
#: (positions 1-878). On-wire stream adds 2-byte CRLF terminator
#: at positions 879-880 (serialiser-owned; not in ``RECORD_SPECS``).
RECORD_LENGTH = 878

#: Wire encoding for Modelo 130 fichero-BOE output.
ENCODING: FicheroBoeEncoding = "cp1252"

#: Width of every currency (amount) field: 11 integer + 2 implicit
#: decimals = 13 digits zero-padded.
_AMOUNT_LEN = 13

#: Header-field identifiers every draft MUST provide. Consumed by
#: :mod:`aeat.submission._formats._serialise` to fail-fast on missing
#: required inputs before emitting any bytes.
REQUIRED_HEADER_FIELDS: frozenset[str] = frozenset(
    {
        "EJERCICIO",
        "PERIODO",
        "NIF_DECLARANTE",
        "APELLIDOS",
        "NOMBRE",
        "TIPO_DECLARACION",
    }
)

RECORD_SPECS: tuple[RecordFieldSpec, ...] = (
    # ---- Record header (positions 1-76) ----
    record_field(
        offset=1,
        length=3,
        field_id="MODELO",
        kind=FieldKind.RESERVED,
        literal_value="130",
    ),
    record_field(
        offset=4,
        length=2,
        field_id="PAGINA",
        kind=FieldKind.RESERVED,
        literal_value="01",
    ),
    record_field(
        offset=6,
        length=1,
        field_id="IND_COMPLEMENTARIA",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=7,
        length=1,
        field_id="TIPO_DECLARACION",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=8,
        length=5,
        field_id="COD_ADMINISTRACION",
        kind=FieldKind.NUMERIC,
    ),
    record_field(
        offset=13,
        length=9,
        field_id="NIF_DECLARANTE",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=22,
        length=4,
        field_id="COMIENZO_APELLIDO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=26,
        length=30,
        field_id="APELLIDOS",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=56,
        length=15,
        field_id="NOMBRE",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=71,
        length=4,
        field_id="EJERCICIO",
        kind=FieldKind.NUMERIC,
    ),
    record_field(
        offset=75,
        length=2,
        field_id="PERIODO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Apartado I: actividades en estimación directa ----
    record_field(
        offset=77,
        length=_AMOUNT_LEN,
        field_id="INGRESOS_COMPUTABLES",
        casilla_id="01",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=90,
        length=_AMOUNT_LEN,
        field_id="GASTOS_DEDUCIBLES",
        casilla_id="02",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=103,
        length=_AMOUNT_LEN,
        field_id="RENDIMIENTO_NETO",
        casilla_id="03",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=116,
        length=_AMOUNT_LEN,
        field_id="VEINTE_PCT_CASILLA_03",
        casilla_id="04",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=129,
        length=_AMOUNT_LEN,
        field_id="DEDUCIR_TRIMESTRES_ANT",
        casilla_id="05",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=142,
        length=_AMOUNT_LEN,
        field_id="RETENCIONES_INGR_CUENTA",
        casilla_id="06",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=155,
        length=_AMOUNT_LEN,
        field_id="RESULTADO_APARTADO_I",
        casilla_id="07",
        kind=FieldKind.CURRENCY,
    ),
    # ---- Apartado II: actividades agrícolas/ganaderas ----
    record_field(
        offset=168,
        length=_AMOUNT_LEN,
        field_id="INGRESOS_AGRARIOS",
        casilla_id="08",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=181,
        length=_AMOUNT_LEN,
        field_id="DOS_PCT_CASILLA_08",
        casilla_id="09",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=194,
        length=_AMOUNT_LEN,
        field_id="RETENCIONES_AGRARIAS",
        casilla_id="10",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=207,
        length=_AMOUNT_LEN,
        field_id="RESULTADO_APARTADO_II",
        casilla_id="11",
        kind=FieldKind.CURRENCY,
    ),
    # ---- Liquidación total ----
    record_field(
        offset=220,
        length=_AMOUNT_LEN,
        field_id="SUMA_PARCIALES",
        casilla_id="12",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=233,
        length=_AMOUNT_LEN,
        field_id="MINORACION_RD_LEY",
        casilla_id="13",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=246,
        length=_AMOUNT_LEN,
        field_id="NETO_TRAS_MINORACION",
        casilla_id="14",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=259,
        length=_AMOUNT_LEN,
        field_id="NEGATIVOS_ANTERIORES",
        casilla_id="15",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=272,
        length=_AMOUNT_LEN,
        field_id="DEDUCCION_VIVIENDA",
        casilla_id="16",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=285,
        length=_AMOUNT_LEN,
        field_id="DIFERENCIA",
        casilla_id="17",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=298,
        length=_AMOUNT_LEN,
        field_id="A_DEDUCIR_AUTOLIQ_ANT",
        casilla_id="18",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=311,
        length=_AMOUNT_LEN,
        field_id="RESULTADO_FINAL",
        casilla_id="19",
        kind=FieldKind.CURRENCY,
    ),
    # ---- Ingreso / devolución + IBAN block (4 sub-fields) ----
    record_field(
        offset=324,
        length=_AMOUNT_LEN,
        field_id="IMPORTE_INGRESO",
        kind=FieldKind.CURRENCY,
    ),
    record_field(
        offset=337,
        length=1,
        field_id="FORMA_PAGO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=338,
        length=4,
        field_id="IBAN_ENTIDAD",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=342,
        length=4,
        field_id="IBAN_SUCURSAL",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=346,
        length=2,
        field_id="IBAN_DC",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=348,
        length=10,
        field_id="IBAN_NUM",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=358,
        length=1,
        field_id="A_DEDUCIR_FLAG",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Complementaria block ----
    record_field(
        offset=359,
        length=16,
        field_id="COMPLEMENTARIA_CODIGO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=375,
        length=13,
        field_id="COMPLEMENTARIA_JUSTIFICANTE",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Contact + observaciones ----
    record_field(
        offset=388,
        length=100,
        field_id="CONTACTO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=488,
        length=9,
        field_id="TELEFONO",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=497,
        length=350,
        field_id="OBSERVACIONES",
        kind=FieldKind.ALPHANUMERIC,
    ),
    # ---- Firma block ----
    record_field(
        offset=847,
        length=16,
        field_id="FIRMA_LOCALIDAD",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=863,
        length=2,
        field_id="FIRMA_DIA",
        kind=FieldKind.NUMERIC,
    ),
    record_field(
        offset=865,
        length=10,
        field_id="FIRMA_MES",
        kind=FieldKind.ALPHANUMERIC,
    ),
    record_field(
        offset=875,
        length=4,
        field_id="FIRMA_ANO",
        kind=FieldKind.NUMERIC,
    ),
)

# Enforce monotonic contiguity at import time. Any off-by-one in the
# hand-authored specs above will fail-fast at collection.
validate_record_specs(RECORD_SPECS, total_length=RECORD_LENGTH)


__all__ = [
    "ENCODING",
    "RECORD_LENGTH",
    "RECORD_SPECS",
    "REQUIRED_HEADER_FIELDS",
]
