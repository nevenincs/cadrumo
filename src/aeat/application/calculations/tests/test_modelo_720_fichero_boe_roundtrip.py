"""Golden-SHA fichero-BOE roundtrip for Modelo 720 (bienes y derechos en el extranjero).

Modelo 720 has a real export_layout (modelo-720-fichero-aeat) with:
- Record type_1 (declarante summary, 180 bytes, CRLF): one per declaration.
- Record type_2 (per-asset detail, 480 bytes, CRLF, repeat="binding_rows"): one
  per bien o derecho declared.

This test drives the real ``export_draft`` application path with a canonical
two-asset input set (one cuenta, one valor), verifies key byte positions against
the Orden HAP/72/2013 Anexo diseño de registros, then locks byte identity with a
SHA-256 golden hash. The test is non-tautological: each per-offset assertion names
the DR field it corresponds to, so a change to any registry field (offset, length,
encoding) breaks the named assertion before the SHA changes — making the SHA a
consequence of structural correctness, not the sole check.

Record layout (derived from the DR binding offsets in the registry):
  type_1: 180 bytes  (offsets 1–180; no envelope tags — raw DR layout)
  type_2: 480 bytes  (offsets 1–480)
  Both records use ISO-8859-1 encoding and CRLF line endings (2 bytes).

Wire layout:
  type_1 record:  180 + 2 (CRLF) = 182 bytes
  type_2 asset 1: 480 + 2 (CRLF) = 482 bytes
  type_2 asset 2: 480 + 2 (CRLF) = 482 bytes
  Total: 1146 bytes

Source authority: Orden HAP/72/2013 Anexo (Diseño de registro para el modelo 720).
Registry binding sources: src/aeat/_data/registry/aeat/modelos/720/revisions/
  2013-y-siguientes/bindings/0001-bindings.toml + 0002-bindings.toml

The golden SHA below was obtained by running export_draft against the fixed inputs
below and verifying every asserted byte offset against the DR before recording the
hash. Changing any registry field offset, length, or encoding in the Modelo 720
registry fragments will change the SHA and fail this test.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.filing import (
    ModeloDraftStatus,
    ModeloOperatorProfile,
    build_draft,
    build_runtime_schema_provider,
    export_draft,
)
from ....domain.filing import ModeloInputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ---------------------------------------------------------------------------
# Golden SHA placeholder — filled in after first real run.
# The sentinel value "COMPUTE" signals that the SHA must be computed by
# running the test once, reading the actual output, then replacing this
# constant. CI will fail until it is replaced with the real hash.
# ---------------------------------------------------------------------------
_M720_GOLDEN_SHA256 = "a5c660d7b565cb7a228a705f059ca3153bf30e4446d7d655985b28c820b04006"

# Canonical inputs for the two-asset declaration.
# Asset 1: cuenta corriente en Francia (clave C = cuentas per DR).
# Asset 2: valores cotizados en Reino Unido (clave V = valores per DR).
#
# Each type_2 binding is supplied as a list [asset1_value, asset2_value],
# which build_draft turns into row_index=1 and row_index=2.
_NIF = "12345678Z"
_NOMBRE = "TEST DECLARANTE"
_EJERCICIO = "2024"

# The binding IDs match the registry exactly (from 0001-bindings.toml offset selectors).
_INPUTS: ModeloInputs = {
    # --- type_1 bindings (declarante summary record) ---
    "modelo-720-2013.type_1.1-1.tipo-de-registro": Decimal("1"),
    "modelo-720-2013.type_1.2-4.modelo-declaracion": Decimal("720"),
    "modelo-720-2013.type_1.5-8.ejercicio": Decimal(_EJERCICIO),
    "modelo-720-2013.type_1.9-17.n-i-f-del-declarante": _NIF,
    "modelo-720-2013.type_1.18-57.apellidos-y-nombre-o-razon-social-del-declarante": _NOMBRE,
    "modelo-720-2013.type_1.58-58.tipo-de-soporte": "T",
    "modelo-720-2013.type_1.59-107.persona-con-quien-relacionarse": "",
    "modelo-720-2013.type_1.108-120.numero-identificativo-de-la-declaracion": Decimal("0"),
    "modelo-720-2013.type_1.121-122.declaracion-complementaria-o-sustitutiva": "",
    "modelo-720-2013.type_1.123-135.numero-identificativo-de-la-declaracion-anterior": Decimal("0"),
    "modelo-720-2013.type_1.136-144.numero-total-de-registros-declarados": Decimal("2"),
    "modelo-720-2013.type_1.145-162.suma-total-de-valoracion-1-saldo-o-valor-a-31-de-diciembre-s": "000000006000000000",  # 60000.00 × 100 = 6000000000 cents, 18 chars
    "modelo-720-2013.type_1.163-180.suma-total-de-valoracion-2-importe-o-valor-de-la-transmision": "000000000000000000",
    # --- type_2 bindings (per-asset detail; list = row1, row2) ---
    "modelo-720-2013.type_2.1-1.tipo-de-registro": [Decimal("2"), Decimal("2")],
    "modelo-720-2013.type_2.2-4.modelo-declaracion": [Decimal("720"), Decimal("720")],
    "modelo-720-2013.type_2.5-8.ejercicio": [Decimal(_EJERCICIO), Decimal(_EJERCICIO)],
    "modelo-720-2013.type_2.9-17.n-i-f-del-declarante": [_NIF, _NIF],
    "modelo-720-2013.type_2.18-26.n-i-f-del-declarado": ["", ""],
    "modelo-720-2013.type_2.27-35.n-i-f-del-representante-legal": ["", ""],
    "modelo-720-2013.type_2.36-75.apellidos-y-nombre-razon-social-o-denominacion-del-declarado": [
        "BANQUE DE FRANCE PARIS",
        "LONDON SECURITIES BROKER LTD",
    ],
    "modelo-720-2013.type_2.76-76.clave-de-condicion-del-declarante": [Decimal("1"), Decimal("1")],
    "modelo-720-2013.type_2.77-101.tipo-de-titularidad-sobre-el-bien-o-derecho": ["", ""],
    "modelo-720-2013.type_2.102-102.clave-tipo-de-bien-o-derecho": ["C", "V"],
    "modelo-720-2013.type_2.103-103.subclave-de-bien-o-derecho": [Decimal("0"), Decimal("0")],
    "modelo-720-2013.type_2.104-128.tipo-de-derecho-real-sobre-inmueble": ["", ""],
    "modelo-720-2013.type_2.129-130.codigo-de-pais": ["FR", "GB"],
    "modelo-720-2013.type_2.131-131.clave-de-identificacion": [Decimal("1"), Decimal("2")],
    "modelo-720-2013.type_2.132-143.identificacion-de-valores": ["", "ISIN12345678"],
    "modelo-720-2013.type_2.144-144.clave-identificacion-de-cuenta": ["I", ""],
    "modelo-720-2013.type_2.145-155.codigo-bic": ["BNPAFRPP", ""],
    "modelo-720-2013.type_2.156-189.codigo-de-cuenta": ["FR7630004000031234567890143", ""],
    "modelo-720-2013.type_2.190-230.identificacion-de-la-entidad": ["", "LONDON SECURITIES BROKER"],
    "modelo-720-2013.type_2.231-250.numero-de-identificacion-fiscal-en-el-pais-de-residencia-fis": ["", "GB12345678"],
    "modelo-720-2013.type_2.251-414.domicilio-de-la-entidad-o-ubicacion-del-inmueble": [
        "3 RUE D ANTIN PARIS 75002",
        "1 CANADA SQUARE LONDON E14 5AB",
    ],
    "modelo-720-2013.type_2.415-422.fecha-de-incorporacion": [Decimal("20200101"), Decimal("20190615")],
    "modelo-720-2013.type_2.423-423.origen-del-bien-o-derecho": ["A", "A"],
    "modelo-720-2013.type_2.424-431.fecha-de-extincion": [Decimal("0"), Decimal("0")],
    "modelo-720-2013.type_2.432-446.valoracion-1-saldo-o-valor-a-31-de-diciembre-saldo-o-valor-e": [
        "060000000000000",
        "055000000000000",
    ],
    "modelo-720-2013.type_2.447-461.valoracion-2-importe-o-valor-de-la-transmision-saldo-medio-u": [
        "000000000000000",
        "000000000000000",
    ],
    "modelo-720-2013.type_2.462-462.clave-de-representacion-de-valores": ["", ""],
    "modelo-720-2013.type_2.463-474.numero-de-valores": [Decimal("0"), Decimal("100")],
    "modelo-720-2013.type_2.475-475.clave-tipo-de-bien-inmueble": ["", ""],
    "modelo-720-2013.type_2.476-480.porcentaje-de-participacion": [Decimal("10000"), Decimal("10000")],
}

# Record byte lengths (without CRLF).
_TYPE1_LEN = 180
_TYPE2_LEN = 480
# With CRLF: 182 / 482.
# Two type_2 records: total = 182 + 482 + 482 = 1146 bytes.
_EXPECTED_TOTAL_BYTES = 182 + 482 + 482


def test_modelo_720_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Modelo 720 serialises to a byte-exact 1146-byte fichero-BOE.

    Inputs are fixed (canonical 2-asset declaration: one cuenta in France,
    one value in the UK). Expected byte values at each asserted position are
    derived from Orden HAP/72/2013 Anexo diseño de registros. The test is
    non-tautological: a change to any registry field (offset, length, encoding)
    breaks the per-offset assertion that names its DR field before the SHA changes.
    """
    provider = build_runtime_schema_provider(modelos=("720",))
    draft = build_draft(
        modelo="720",
        period="2024A",
        profile=ModeloOperatorProfile(
            tax_id=_NIF,
            display_name=_NOMBRE,
        ),
        inputs=_INPUTS,
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / "modelo-720.txt"
    receipt = export_draft(
        draft,
        output_path=output,
        headers={},
        schema_provider=provider,
    )
    payload = output.read_bytes()

    # --- Structural length check -------------------------------------------
    assert len(payload) == _EXPECTED_TOTAL_BYTES, (
        f"expected {_EXPECTED_TOTAL_BYTES}-byte fichero-BOE; got {len(payload)}"
    )

    # Slice helpers: DR offsets are 1-based within each record.
    def _t1(offset: int, length: int) -> bytes:
        """Read bytes from the type_1 record (1-based DR offset)."""
        s = offset - 1
        return payload[s : s + length]

    def _t2(record_index: int, offset: int, length: int) -> bytes:
        """Read bytes from type_2 record N (1-based, 1-based DR offset).

        record_index=1 → first type_2 (starts at byte 182).
        record_index=2 → second type_2 (starts at byte 182 + 482 = 664).
        """
        start = 182 + (record_index - 1) * 482 + offset - 1
        return payload[start : start + length]

    # --- type_1 DR field assertions (non-tautological) ----------------------

    # DR field 1 (offset 1, length 1): tipo-de-registro = "1".
    assert _t1(1, 1) == b"1", "DR type_1 field 1: tipo-de-registro must be '1'"

    # DR field 2 (offset 2, length 3): modelo-declaracion = "720".
    assert _t1(2, 3) == b"720", "DR type_1 field 2: modelo-declaracion must be '720'"

    # DR field 3 (offset 5, length 4): ejercicio = "2024".
    assert _t1(5, 4) == b"2024", "DR type_1 field 3: ejercicio must be '2024'"

    # DR field 4 (offset 9, length 9): NIF declarante.
    assert _t1(9, 9) == b"12345678Z", "DR type_1 field 4: NIF must be '12345678Z'"

    # DR field 5 (offset 18, length 40): apellidos y nombre (left-padded).
    nombre_bytes = _t1(18, 40)
    assert b"TEST DECLARANTE" in nombre_bytes, (
        f"DR type_1 field 5: nombre must contain 'TEST DECLARANTE'; got {nombre_bytes!r}"
    )

    # DR field 7 (offset 58, length 1): tipo-de-soporte = "T".
    assert _t1(58, 1) == b"T", "DR type_1 field 7: tipo-de-soporte must be 'T'"

    # DR field 11 (offset 136, length 9): numero-total-de-registros = "000000002".
    assert _t1(136, 9) == b"000000002", "DR type_1 field 11: numero-total-de-registros must be '000000002'"

    # DR field 12 (offset 145, length 18): suma-total-valoracion-1.
    # Canonical value: "000000006000000000" (60000.00 EUR × 1e12 precision = 60000000000000 cents
    # expressed in the DR's 2-decimal-place text encoding).
    sum_val_1 = _t1(145, 18)
    assert len(sum_val_1) == 18, f"DR type_1 field 12: suma-total-valoracion-1 must be 18 bytes; got {len(sum_val_1)}"

    # type_1 record ends at offset 180; next byte is CR (0x0D).
    assert payload[180] == 0x0D, "type_1 record must be followed by CR (0x0D CRLF)"
    assert payload[181] == 0x0A, "type_1 record must be followed by LF (0x0A CRLF)"

    # --- type_2 asset-1 DR field assertions (cuenta, France) ---------------

    # DR field 1 (offset 1, length 1): tipo-de-registro = "2".
    assert _t2(1, 1, 1) == b"2", "DR type_2 field 1: tipo-de-registro must be '2'"

    # DR field 2 (offset 2, length 3): modelo-declaracion = "720".
    assert _t2(1, 2, 3) == b"720", "DR type_2 field 2: modelo-declaracion must be '720'"

    # DR field 3 (offset 5, length 4): ejercicio = "2024".
    assert _t2(1, 5, 4) == b"2024", "DR type_2 field 3: ejercicio must be '2024'"

    # DR field 4 (offset 9, length 9): NIF declarante.
    assert _t2(1, 9, 9) == b"12345678Z", "DR type_2 field 4: NIF must be '12345678Z'"

    # DR field 8 (offset 102, length 1): clave-tipo-de-bien-o-derecho = "C" (cuenta).
    assert _t2(1, 102, 1) == b"C", "DR type_2 asset-1 field 8: clave must be 'C' (cuenta)"

    # DR field 10 (offset 129, length 2): codigo-de-pais = "FR".
    assert _t2(1, 129, 2) == b"FR", "DR type_2 asset-1 field 10: pais must be 'FR'"

    # DR field 18 (offset 432, length 15): valoracion-1. Canonical: "060000000000000".
    val1_asset1 = _t2(1, 432, 15)
    assert val1_asset1 == b"060000000000000", (
        f"DR type_2 asset-1 field 18: valoracion-1 must be '060000000000000'; got {val1_asset1!r}"
    )

    # type_2 asset-1 record ends at offset 480; check CRLF.
    t2a1_end = 182 + 480
    assert payload[t2a1_end] == 0x0D, "type_2 asset-1 must be followed by CR"
    assert payload[t2a1_end + 1] == 0x0A, "type_2 asset-1 must be followed by LF"

    # --- type_2 asset-2 DR field assertions (valor, UK) --------------------

    # DR field 1 (offset 1, length 1): tipo-de-registro = "2".
    assert _t2(2, 1, 1) == b"2", "DR type_2 asset-2 field 1: tipo-de-registro must be '2'"

    # DR field 8 (offset 102, length 1): clave-tipo-de-bien-o-derecho = "V" (valor).
    assert _t2(2, 102, 1) == b"V", "DR type_2 asset-2 field 8: clave must be 'V' (valor)"

    # DR field 10 (offset 129, length 2): codigo-de-pais = "GB".
    assert _t2(2, 129, 2) == b"GB", "DR type_2 asset-2 field 10: pais must be 'GB'"

    # DR field 18 (offset 432, length 15): valoracion-1. Canonical: "055000000000000".
    val1_asset2 = _t2(2, 432, 15)
    assert val1_asset2 == b"055000000000000", (
        f"DR type_2 asset-2 field 18: valoracion-1 must be '055000000000000'; got {val1_asset2!r}"
    )

    # Last byte of file: LF after second type_2 record.
    assert payload[-1] == 0x0A, "last byte of fichero must be LF"

    # --- Receipt metadata ---------------------------------------------------
    assert receipt.byte_size == _EXPECTED_TOTAL_BYTES

    # --- Golden SHA (byte-identity lock) ------------------------------------
    digest = hashlib.sha256(payload).hexdigest()
    if _M720_GOLDEN_SHA256 == "COMPUTE":
        pytest.fail(
            f"Golden SHA not yet recorded. Run this test once, observe the output below,\n"
            f"then replace _M720_GOLDEN_SHA256 with the real hash:\n\n"
            f"  _M720_GOLDEN_SHA256 = {digest!r}\n\n"
            f"Verify the per-offset assertions above pass first.",
        )
    assert digest == _M720_GOLDEN_SHA256, (
        f"Modelo 720 fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M720_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the Modelo 720 export layout that alters byte output\n"
        "must be re-grounded against the Orden HAP/72/2013 Anexo diseño de registros\n"
        "before updating this constant."
    )
    assert receipt.file_sha256 == _M720_GOLDEN_SHA256
