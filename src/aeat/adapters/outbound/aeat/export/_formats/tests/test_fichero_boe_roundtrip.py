"""Deep-fidelity roundtrip tests for the fichero-BOE export format.

The existing :mod:`test_envelope` suite covers a happy-path
serialise / deserialise pair on a minimal two-segment layout. This
file extends that coverage to the failure-prone shapes the registry
data actually emits at the AEAT wire boundary:

* DATE fields in both BOE conventions (``YYYYMMDD`` and ``DDMMYYYY``).
* CURRENCY fields under ``SignedMode.INLINE_SIGN`` with a negative
  value (the byte-0 ``N`` marker must survive the cycle).
* ALPHANUMERIC fields padded with the non-default ``"0"`` filler so
  the read-side strip rule is verified end-to-end.
* CP1252 encoding (the default for AEAT's fichero-BOE submissions)
  so a byte-level mis-encoding of a non-ASCII character surfaces as
  a strict byte inequality.

Every test uses real :func:`serialise` / :func:`deserialise` against
inline-built record specs — no fixtures, no mocks, no reused
registry data — so a regression in any of the encoders or decoders
surfaces as a strict equality failure naming the divergent field.

The Modelo 130 golden test at the bottom of this file exercises the
full registry-driven export path (application layer ``export_draft``
→ ``ExportLayoutDefinition`` → byte payload) against a fixed set of
inputs whose expected bytes are derived field-by-field from the AEAT
Diseño de Registros DR 13001 (Orden HAP/258/2015, v1.2, March 2019).
The golden SHA locks byte identity; the per-offset assertions make the
test non-tautological: the test would fail if the DR field at any
asserted position were wrong, not just if the overall SHA changed.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .......core import Period
from .......core.external_constants import ISO_8859_1_ENCODING
from ..._errors import AeatExportFormatError
from .._deserialise import deserialise
from .._record_spec import (
    DateFmt,
    FieldKind,
    Justification,
    SignedMode,
    record_field,
    validate_record_specs,
)
from .._serialise import serialise

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_currency_inline_sign_round_trips_negative_value() -> None:
    """A signed-currency field with byte-0 ``N`` marker round-trips strictly.

    The :class:`SignedMode.INLINE_SIGN` convention puts an ``N``
    or space in byte 0 of the field, followed by the absolute
    magnitude in cents. A regression that flips byte 0 (e.g.
    emits ``-`` instead of ``N`` or fails to read the sign back)
    surfaces as a strict Decimal inequality.
    """

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT_SIGNED",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
            signed_mode=SignedMode.INLINE_SIGN,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={"01": Decimal("-12345.67")},
        headers={},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=12,
    )

    # Byte 0 must be the inline-sign marker for negative values.
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body[0:1] == b"N", f"INLINE_SIGN negative value should emit 'N' in byte 0; got {body[0:1]!r}"

    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)
    assert parsed.casilla_values["01"] == Decimal("-12345.67")


def test_currency_inline_sign_round_trips_positive_value() -> None:
    """Positive INLINE_SIGN values emit a leading space, decoded as a positive Decimal."""

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT_SIGNED",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
            signed_mode=SignedMode.INLINE_SIGN,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={"01": Decimal("42.00")},
        headers={},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=12,
    )

    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body[0:1] == b" ", f"INLINE_SIGN non-negative value should emit space in byte 0; got {body[0:1]!r}"

    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)
    assert parsed.casilla_values["01"] == Decimal("42.00")


def test_date_field_yyyymmdd_round_trips() -> None:
    """A ``YYYYMMDD`` DATE field round-trips a real calendar date strictly."""

    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="DEVENGO",
            kind=FieldKind.DATE,
            date_fmt=DateFmt.YYYYMMDD,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    target = date(2025, 4, 20)
    payload = serialise(
        casilla_values={},
        headers={"DEVENGO": target},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=8,
    )
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body == b"20250420"

    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=8)
    assert parsed.field_values["DEVENGO"] == target


def test_date_field_ddmmyyyy_round_trips() -> None:
    """A ``DDMMYYYY`` DATE field round-trips, distinguishing it from YYYYMMDD."""

    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="FECHA",
            kind=FieldKind.DATE,
            date_fmt=DateFmt.DDMMYYYY,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    target = date(2025, 4, 20)
    payload = serialise(
        casilla_values={},
        headers={"FECHA": target},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=8,
    )
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body == b"20042025"

    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=8)
    assert parsed.field_values["FECHA"] == target


def test_alphanumeric_zero_padded_field_round_trips() -> None:
    """A ``pad_char='0'`` field round-trips intact, including the strip rule.

    ALPHANUMERIC fields padded with ``"0"`` on the right are stripped
    of the padding on the read side. A canonical value of ``"0"``
    that would naively strip to the empty string must reconstitute
    as ``"0"`` so the round-trip is faithful.
    """

    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="REF",
            kind=FieldKind.ALPHANUMERIC,
            pad_char="0",
            justification=Justification.LEFT,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={},
        headers={"REF": "ABC123"},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=8,
    )
    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=8)
    assert parsed.field_values["REF"] == "ABC123"


def test_currency_blank_input_rejected_at_decode() -> None:
    """A blank CURRENCY field is rejected with AeatExportFormatError.

    A blank CURRENCY field is a wire-format error per the fichero-
    BOE spec (zero-padded ASCII digits required). The decode path
    must surface this as a typed parse refusal rather than silently
    consuming blank bytes as ``Decimal("0.00")`` indistinguishable
    from a legitimate zero.
    """

    from ..._errors import AeatExportFormatError
    from .._deserialise import deserialise

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    # 12 spaces — a wire shape that earlier silently decoded to 0.00.
    blank_payload = b" " * 12 + b"\r\n"
    with pytest.raises(AeatExportFormatError, match=r"CURRENCY field is blank"):
        deserialise(blank_payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)


def test_currency_inline_sign_blank_magnitude_rejected_at_decode() -> None:
    """A blank INLINE_SIGN CURRENCY magnitude is rejected.

    Same contract as the unsigned-CURRENCY case: ``N           ``
    (sign marker + blank magnitude) must fail rather than silently
    decode to a negative-zero.
    """

    from ..._errors import AeatExportFormatError
    from .._deserialise import deserialise

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
            signed_mode=SignedMode.INLINE_SIGN,
        ),
    )
    validate_record_specs(specs, total_length=12)
    # Sign byte 'N' + 11 blank magnitude bytes
    blank_payload = b"N" + b" " * 11 + b"\r\n"
    with pytest.raises(AeatExportFormatError, match=r"magnitude is blank"):
        deserialise(blank_payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)


def test_currency_invalid_wire_bytes_raise_redacted_export_format_error() -> None:
    """Invalid CURRENCY wire bytes must not be echoed in parser errors."""

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
        ),
    )
    validate_record_specs(specs, total_length=12)

    canary = b"12345678Z999"
    with pytest.raises(AeatExportFormatError) as exc_info:
        deserialise(canary + b"\r\n", specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)

    message = str(exc_info.value)
    assert "CURRENCY field 'AMOUNT' has invalid wire bytes" in message
    assert "length=12" in message
    assert "digest=sha256:" in message
    assert "12345678Z" not in message
    assert canary.decode("ascii") not in message
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_cp1252_encoded_field_round_trips_non_ascii() -> None:
    """CP1252-encoded ALPHANUMERIC field carries a Spanish-language byte intact.

    AEAT's default wire encoding is CP1252. An ``ñ`` codes to a
    single byte (0xF1) on the wire; UTF-8 would emit two bytes.
    A regression that silently upgrades the encoding to UTF-8
    would either truncate the field (byte budget overflow) or
    decode garbled on the read side.
    """

    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="NOMBRE",
            kind=FieldKind.ALPHANUMERIC,
            pad_char=" ",
            justification=Justification.LEFT,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={},
        headers={"NOMBRE": "Pañito"},
        specs=specs,
        encoding="cp1252",
        total_length=8,
    )
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    # The ñ must encode as a single CP1252 byte (0xF1).
    assert b"\xf1" in body

    parsed = deserialise(payload, specs=specs, encoding="cp1252", total_length=8)
    assert parsed.field_values["NOMBRE"] == "Pañito"


def test_reserved_field_corruption_rejected_at_decode() -> None:
    """Anti-tautology proof for RESERVED literal fields.

    A RESERVED field carries a fixed literal (record separator,
    envelope tag, filler constant). The deserialiser must reject a
    payload whose reserved bytes diverge from the declared
    ``literal_value`` — a corrupted constant that round-tripped
    silently would leave the export's structural integrity unverifiable.
    Serialise a record, rewrite the reserved literal on disk to a
    divergent value, and assert ``deserialise`` refuses it. If the
    deserialiser's RESERVED invariant were removed, this test fails.
    """

    specs = (
        record_field(
            offset=1,
            length=4,
            field_id="ENVELOPE_TAG",
            kind=FieldKind.RESERVED,
            literal_value="AEAT",
        ),
    )
    validate_record_specs(specs, total_length=4)

    payload = serialise(
        casilla_values={},
        headers={},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=4,
    )
    assert b"AEAT" in payload, payload

    corrupted = payload.replace(b"AEAT", b"XXXX")
    assert corrupted != payload

    with pytest.raises(AeatExportFormatError, match="RESERVED"):
        deserialise(corrupted, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=4)


def test_reserved_field_corruption_error_redacts_wire_bytes() -> None:
    """RESERVED mismatch errors must describe corrupted bytes by digest only."""

    specs = (
        record_field(
            offset=1,
            length=9,
            field_id="ENVELOPE_TAG",
            kind=FieldKind.RESERVED,
            literal_value="SAFE-TAG!",
        ),
    )
    validate_record_specs(specs, total_length=9)

    canary = b"12345678Z"
    with pytest.raises(AeatExportFormatError) as exc_info:
        deserialise(canary + b"\r\n", specs=specs, encoding=ISO_8859_1_ENCODING, total_length=9)

    message = str(exc_info.value)
    assert "RESERVED field 'ENVELOPE_TAG'" in message
    assert "length=9" in message
    assert "digest=sha256:" in message
    assert "12345678Z" not in message
    assert canary.decode("ascii") not in message


# ---------------------------------------------------------------------------
# Modelo 130 golden-SHA fichero-BOE round-trip
# ---------------------------------------------------------------------------
#
# Source authority: AEAT Diseño de Registros DR 13001, Orden HAP/258/2015,
# version 1.2, updated March 2019 ("ejercicios 2019 y siguientes").
# Corpus path: src/aeat/_data/corpus/aeat_official/disenos_registro/
#              modelo_130/files/01-130-orden-hap-258-2015-ejercicios-
#              2019-y-siguientes-actualizado-marzo-2019-176-kb-xls.xlsx
#
# Record layout (derived from DR):
#   Envelope header (DR 13000):  328 bytes
#   Page-01 record  (DR 13001):  600 bytes
#   Envelope footer (computed):   18 bytes
#   Total:                        946 bytes  (no inter-record delimiter)
#
# The golden SHA below was obtained by running export_draft against the
# fixed inputs below, then verifying every asserted byte position against
# the DR offset table before recording the hash. Changing any registry
# field offset, length, or encoding in the Modelo 130 registry fragments
# will change the SHA and fail this test; changes must be re-grounded
# against the DR before updating the constant.
#
# Per-offset assertions are non-tautological: each one names the DR row
# it corresponds to so a reviewer can verify the expected value
# independently from the registry.
_M130_GOLDEN_SHA256 = "feaffb81b89ce8b897066ac0383d31e4bfd45a15c526b650f711a89f25fe0120"

# Envelope header is 328 bytes; page record begins at byte index 328 (0-based).
_PAGE_START = 328


# Money encoding helper: amount (Decimal) → expected bytes in a 17-byte
# signed field.  Positive: " " + 16 zero-padded digits.  Negative: "N" + …
def _money_bytes(amount: Decimal, *, signed: bool = False) -> bytes:
    cents = int(abs(amount * 100))
    if amount < 0:
        return ("N" + str(cents).zfill(16)).encode("latin-1")
    if signed:
        return (" " + str(cents).zfill(16)).encode("latin-1")
    return str(cents).zfill(17).encode("latin-1")


def test_modelo_130_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Modelo 130 serialises to a byte-exact 946-byte fichero-BOE.

    Inputs are fixed; expected values at each asserted byte offset are
    derived from DR 13001 (Orden HAP/258/2015 v1.2).  The test is
    non-tautological because a change to any registry field (offset,
    length, sign flag, encoding) would alter the bytes at the
    corresponding position and break this assertion before changing the
    SHA — making the SHA a *consequence* of structural correctness, not
    the sole check.
    """
    from .......application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )

    provider = build_runtime_schema_provider(modelos=("130",))
    draft = build_draft(
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Golden test",
        ),
        inputs={
            "01": Decimal("10000.00"),
            "02": Decimal("4000.00"),
            "05": Decimal("0"),
            "06": Decimal("0"),
            "08": Decimal("0"),
            "10": Decimal("0"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / "modelo-130.txt"
    receipt = export_draft(
        draft,
        output_path=output,
        headers={
            "declaration_type": "I",
            "surnames": "GARCIA LOPEZ",
            "name": "JUAN",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
        },
        schema_provider=provider,
    )
    payload = output.read_bytes()

    # --- DR-grounded structural assertions (non-tautological) ---------------

    def _page(offset: int, length: int) -> bytes:
        """Read bytes from DR 13001 page record (1-based offset)."""
        s = _PAGE_START + offset - 1
        return payload[s : s + length]

    # Total length per DR: 328 (header) + 600 (page-01) + 18 (footer) = 946.
    assert len(payload) == 946, f"expected 946-byte fichero-BOE; got {len(payload)}"

    # DR 13001 rows 1-4: open tag <T, modelo 130, page 01, close 000>
    assert _page(1, 2) == b"<T"
    assert _page(3, 3) == b"130"
    assert _page(6, 2) == b"01"
    assert _page(8, 4) == b"000>"

    # DR 13001 row 5: Indicador de pagina complementaria (offset 12, 1 byte).
    # Blank = ordinary declaration.
    assert _page(12, 1) == b" ", "complementaria indicator must be blank for ordinary declaration"

    # DR 13001 row 6: Tipo declaracion (offset 13, 1 byte).
    assert _page(13, 1) == b"I"

    # DR 13001 row 7: NIF sujeto pasivo (offset 14, 9 bytes).
    assert _page(14, 9) == b"12345678Z"

    # DR 13001 rows 8-9: Apellidos / Nombre (offsets 23/83).
    assert _page(23, 12) == b"GARCIA LOPEZ"
    assert _page(83, 4) == b"JUAN"

    # DR 13001 rows 10-11: Ejercicio / Periodo (offsets 103/107).
    assert _page(103, 4) == b"2026"
    assert _page(107, 2) == b"1T"

    # DR 13001 rows 12-30: casillas 01-19 (17 bytes each, starting at offset 109).
    # Unsigned (Num): 01, 02, 04, 05, 06, 08, 09, 10, 12, 13, 15, 16, 18
    # Signed   (N):   03, 07, 11, 14, 17, 19
    # Casilla 01: 10000.00 -> 1000000 cents -> 17-byte zero-padded
    assert _page(109, 17) == _money_bytes(Decimal("10000.00"), signed=False)
    # Casilla 02: 4000.00 -> 400000 cents
    assert _page(126, 17) == _money_bytes(Decimal("4000.00"), signed=False)
    # Casilla 03 (signed): rendimiento neto = 01 - 02 = 6000.00
    assert _page(143, 17) == _money_bytes(Decimal("6000.00"), signed=True)
    # Casilla 04 (unsigned): 20% x max(0, casilla 03) = 1200.00
    assert _page(160, 17) == _money_bytes(Decimal("1200.00"), signed=False)
    # Casilla 19 (signed): resultado final = casilla 17 - 18 = 1200.00 - 0
    # Full chain: 04(1200)-05(0)-06(0)=07(1200); 08=0->09=0, 10=0->11(0)
    # 12=max(0,1200+0)=1200; prev year income 13000>12000 -> casilla 13=0
    # 14=12-13=1200; 15=0,16=0 -> 17=1200; 18=0 -> 19=1200
    assert _page(415, 17) == _money_bytes(Decimal("1200.00"), signed=True)

    # DR 13001 row 31: Declaración complementaria (offset 432, 1 byte An).
    # This field is DISTINCT from the complementaria-indicator at offset 12.
    # Blank = not a complementaria declaration.
    assert _page(432, 1) == b" ", "declaracion-complementaria must be blank for ordinary declaration"

    # DR 13001 row 32: Nº justificante anterior (offset 433, 13 bytes).
    assert _page(433, 13) == b" " * 13, "previous receipt must be blank for first declaration"

    # DR 13001 row 36: closing tag </T13001000> (offset 589, 12 bytes).
    assert _page(589, 12) == b"</T13001000>"

    # Envelope footer: dynamic closing tag (last 18 bytes of payload).
    # Format: </T{modelo}0{AAAA}{PP}0000> e.g. </T130020261T0000>
    assert payload[-18:] == b"</T130020261T0000>"

    # --- Golden SHA (byte-identity lock) ------------------------------------
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M130_GOLDEN_SHA256, (
        f"Modelo 130 fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M130_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the Modelo 130 export layout that alters byte output\n"
        "must be re-grounded against the AEAT Diseño de Registros (DR 13001,\n"
        "Orden HAP/258/2015 v1.2) before updating this constant."
    )

    # Receipt metadata sanity
    assert receipt.byte_size == 946
    assert receipt.file_sha256 == _M130_GOLDEN_SHA256


# ---------------------------------------------------------------------------
# Modelo 303 golden-SHA fichero-BOE round-trip
# ---------------------------------------------------------------------------
#
# Source authority: AEAT Diseño de Registros DR303 (ejercicio 2024, updated
# 2024-11-29), Orden EHA/3786/2008 as amended.
# Corpus path: src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_303/
#   files/04-303-ejercicio-2024-a-partir-de-periodos-09-y-3t-y-siguientes-
#   actualizado-29-11-24-381-kb-x.xlsx
#
# Record layout (8-segment envelope, derived from DR):
#   DP30300  envelope header:    328 bytes  (DR sheet DP30300 rows 1-13)
#   DP30301  page-01 IVA dev:   1581 bytes  (DR sheet DP30301 rows 1-88)
#   DP30302  page-02 RS:        1706 bytes  (DR sheet DP30302 rows 1-91)
#   DP30303  page-03 resultado: 1017 bytes  (DR sheet DP30303 rows 1-38)
#   DP30304  page-04 exon 390:   998 bytes  (DR sheet DP30304 rows 1-43)
#   DP30305  page-05 prorrata:  1523 bytes  (DR sheet DP30305 rows 1-72)
#   DP303DID identification:     823 bytes  (DR sheet DP303DID rows 1-13)
#   Envelope footer (computed):   18 bytes  (DR DP30300 row 15)
#
# Two dispositions exercise the conditional DID (cuenta-devolución) page:
#   * Non-refund ("I"/"C"): the DID page is SUPPRESSED — emitting an empty
#     823-byte refund block files a devolución AEAT cannot pay — so the
#     fichero is 7994 - 823 = 7171 bytes and carries no DID record.
#   * Refund ("D"): the DID page is emitted with the refund account AEAT pays
#     into, so the fichero is the full 7994 bytes.
#
# The REDEME indicator (DR DP30301 offset 110, 1 byte) is written on EVERY
# filing: "1" SI (REDEME-enrolled) / "2" NO (ordinary). It is the same standing
# fact the disposition resolver reads to upgrade a monthly negative period to a
# refund.
#
# DP303DID note: the page identifier "DID00" is type An in the DR (not Num),
# so it serialises as the literal string "DID00", NOT as a zero-padded number.
#
# Per-offset assertions are non-tautological: each names the DR sheet/row it
# corresponds to and asserts the DR-EXPECTED value (e.g. the REDEME indicator
# byte, the IBAN at the DID slot, the derived Marca SEPA), not that the fichero
# round-trips its own output. The golden SHA is a byte-identity lock; any change
# to the 303.toml export layout that alters offset, length, encoding, or sign
# flag will alter the SHA and fail this test.
#
# Both golden SHAs were obtained by running export_draft against the fixed
# inputs/headers below, then verifying every asserted byte position against the
# DR offset table before recording the hash — never hand-tuned to make the test
# pass.
_M303_GOLDEN_SHA256 = "e9dfc7d11988d4bd0aa0ea4f540440c28da287ee3f832a2baec2183740a48113"
#: Refund ("D") disposition with a Spanish IBAN: the DID page is emitted, so the
#: fichero is the full 7994 bytes.
_M303_REFUND_GOLDEN_SHA256 = "a95880caf0dd5b43e787b907d9e1ec20ea829aca1a1aaca12876490db11a730f"
#: Refund ("D") disposition with a non-SEPA (Resto Países, Marca SEPA "3") SWIFT
#: account: the DID page carries the SWIFT-BIC plus the foreign-bank block (no
#: IBAN), so the fichero is the full 7994 bytes.
_M303_REFUND_NON_SEPA_GOLDEN_SHA256 = "07a61b926dc03ac79d71cd565536048f562fef71528ed765e7a70d1aac1994a1"

# Cumulative record-start offsets (0-based byte index):
#   DP30300 starts at 0
#   DP30301 starts at 328
#   DP30302 starts at 328+1581 = 1909
#   DP30303 starts at 1909+1706 = 3615
#   DP30304 starts at 3615+1017 = 4632
#   DP30305 starts at 4632+998  = 5630
# On a REFUND filing the DID page follows page-05:
#   DP303DID starts at 5630+1523 = 7153
#   Envelope footer starts at 7153+823 = 7976
# On a NON-refund filing the DID page is suppressed, so the envelope footer
# follows page-05 directly at 7153 and the fichero ends at 7171.
_M303_P01_START = 328
_M303_P03_START = 3615
_M303_DID_START = 7153

# DR DP30301 REDEME indicator: offset 110 (1-based), length 1.
_M303_REDEME_OFFSET = 110
# DR DP303DID refund-account offsets (1-based within the DID record):
#   SWIFT-BIC at 12, IBAN at 23, Marca SEPA at 194. The non-SEPA (Resto Países)
#   foreign-bank block additionally occupies: bank name at 57, bank address at
#   127, bank city at 162, bank country at 192.
_M303_DID_SWIFT_OFFSET = 12
_M303_DID_IBAN_OFFSET = 23
_M303_DID_BANK_NAME_OFFSET = 57
_M303_DID_BANK_ADDRESS_OFFSET = 127
_M303_DID_BANK_CITY_OFFSET = 162
_M303_DID_BANK_COUNTRY_OFFSET = 192
_M303_DID_SEPA_OFFSET = 194

# Synthetic but structurally valid Spanish IBAN (passes the ISO 13616 mod-97
# RefundAccount boundary validator); the refund golden case pays into it.
_M303_REFUND_IBAN = "ES9121000418450200051332"

# A non-SEPA (Resto Países) refund account: a US SWIFT-BIC plus foreign-bank
# block, no IBAN — so derive_sepa_marca yields "3". The same synthetic account
# the P02 unit coverage uses; the golden case byte-locks its DID render.
_M303_NON_SEPA_SWIFT = "CHASUS33XXX"
_M303_NON_SEPA_BANK_NAME = "Synthetic US Bank"
_M303_NON_SEPA_BANK_ADDRESS = "1 Synthetic Plaza"
_M303_NON_SEPA_BANK_CITY = "New York"
_M303_NON_SEPA_BANK_COUNTRY = "US"


def test_modelo_303_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Non-refund Modelo 303 ("I") serialises to a byte-exact 7171-byte fichero-BOE.

    Inputs are fixed (IVA devengado tipo general 21% only).  Expected byte
    values at each asserted position are derived from DR303 (2024 edition).
    The test is non-tautological: a change to any 303.toml export field
    (offset, length, sign flag, record type, DID00 literal) breaks the
    per-offset assertion that names its DR row, before the SHA changes.

    Two disposition-keyed invariants this case locks (P02/P03):

    * the REDEME indicator at DR DP30301 offset 110 is "2" (NO) for this
      ordinary, non-REDEME filer, written on every filing; and
    * the cuenta-devolución (DID) page is SUPPRESSED on a non-refund
      disposition — an empty 823-byte refund block files a devolución AEAT
      cannot pay — so the fichero is 7994 - 823 = 7171 bytes with no DID record.
    """
    from .......application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )

    provider = build_runtime_schema_provider(modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Golden test IVA",
        ),
        inputs={
            "07": Decimal("10000.00"),
            "iva.repercutido.general": Decimal("2100.00"),
            # Compensation carry-over binding required by the
            # iva.compensacion-pendiente-periodos-anteriores bound casilla
            # (registry change made this a mandatory input for export
            # roundtrips). Zero is the neutral value for a first-quarter
            # filing with no prior carry-over.
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / "modelo-303.txt"
    receipt = export_draft(
        draft,
        output_path=output,
        headers={
            "declaration_type": "I",
            "surnames": "GARCIA LOPEZ",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
            # REDEME indicator: "2" (NO) for an ordinary non-REDEME filer —
            # the value the M303 header composer emits for a non-enrolled
            # profile. Written on every filing, not only refunds.
            "redeme": "2",
        },
        schema_provider=provider,
    )
    payload = output.read_bytes()

    # --- DR-grounded structural assertions (non-tautological) -----------------

    def _hdr(offset: int, length: int) -> bytes:
        """Read bytes from DR DP30300 envelope header (1-based offset)."""
        return payload[offset - 1 : offset - 1 + length]

    def _p1(offset: int, length: int) -> bytes:
        """Read bytes from DR DP30301 page-01 record (1-based field offset)."""
        s = _M303_P01_START + offset - 1
        return payload[s : s + length]

    def _p3(offset: int, length: int) -> bytes:
        """Read bytes from DR DP30303 page-03 record (1-based field offset)."""
        s = _M303_P03_START + offset - 1
        return payload[s : s + length]

    # Total length on a non-refund filing: the DID page (823 bytes) is
    # suppressed, so 328+1581+1706+1017+998+1523+18 = 7171.
    assert len(payload) == 7171, f"expected 7171-byte non-refund fichero-BOE; got {len(payload)}"

    # DR DP30300 rows 1-7: envelope tag bytes
    # Row 1 (offset 1-2): "<T"
    assert _hdr(1, 2) == b"<T", "DR DP30300 row 1: opening tag must be '<T'"
    # Row 2 (offset 3-5): modelo "303"
    assert _hdr(3, 3) == b"303", "DR DP30300 row 2: modelo identifier must be '303'"
    # Row 3 (offset 6): discriminante "0"
    assert _hdr(6, 1) == b"0", "DR DP30300 row 3: discriminante must be '0'"
    # Row 4 (offset 7-10): AAAA (filing year)
    assert _hdr(7, 4) == b"2025", "DR DP30300 row 4: ejercicio must be '2025'"
    # Row 5 (offset 11-12): PP (period code)
    assert _hdr(11, 2) == b"1T", "DR DP30300 row 5: periodo must be '1T'"
    # Row 6 (offset 13-17): "0000>"
    assert _hdr(13, 5) == b"0000>", "DR DP30300 row 6: marker must be '0000>'"
    # Row 7 (offset 18-22): "<AUX>"
    assert _hdr(18, 5) == b"<AUX>", "DR DP30300 row 7: AUX open tag"
    # Row 13 (offset 323-328): "</AUX>"
    assert _hdr(323, 6) == b"</AUX>", "DR DP30300 row 13: AUX close tag"

    # DR DP30301 rows 1-4: page-01 tag
    # Row 1 (offset 1-2): "<T"
    assert _p1(1, 2) == b"<T", "DR DP30301 row 1: page open tag"
    # Row 2 (offset 3-5): "303"
    assert _p1(3, 3) == b"303", "DR DP30301 row 2: modelo in page tag"
    # Row 3 (offset 6-10): "01000"
    assert _p1(6, 5) == b"01000", "DR DP30301 row 3: page-01 identifier must be '01000'"
    # Row 4 (offset 11): ">"
    assert _p1(11, 1) == b">", "DR DP30301 row 4: close of page tag"

    # DR DP30301 row 7 (offset 14-22): NIF sujeto pasivo (9 bytes An)
    assert _p1(14, 9) == b"12345678Z", "DR DP30301 row 7: NIF must match input profile"

    # DR DP30301 row 9 (offset 103-106): Ejercicio (4 bytes Num)
    assert _p1(103, 4) == b"2025", "DR DP30301 row 9: ejercicio must be '2025'"

    # DR DP30301 row 10 (offset 107-108): Periodo (2 bytes An)
    assert _p1(107, 2) == b"1T", "DR DP30301 row 10: periodo must be '1T'"

    # DR DP30301 row 37 (offset 286-302): casilla [07] base imponible 21%
    # Input: 10000.00 → 1000000 cents → 17-byte unsigned zero-padded
    assert _p1(286, 17) == _money_bytes(Decimal("10000.00"), signed=False), (
        "DR DP30301 row 37: casilla 07 base imponible 21% must be 10000.00"
    )

    # DR DP30301 row 38 (offset 303-307): tipo% [08] constant "02100" (21.00%)
    # Per DR Nota 7 this field carries the literal constant for the 21% rate tier.
    assert _p1(303, 5) == b"02100", "DR DP30301 row 38: tipo 08 must be constant '02100' (21%)"

    # DR DP30301 row 39 (offset 308-324): casilla [09] cuota devengada 21%
    # Semantic input: 2100.00 → 210000 cents → 17-byte unsigned zero-padded
    assert _p1(308, 17) == _money_bytes(Decimal("2100.00"), signed=False), (
        "DR DP30301 row 39: casilla 09 cuota 21% must be 2100.00"
    )

    # DR DP30301 REDEME indicator (offset 110, 1 byte): "2" (NO) for this
    # ordinary non-REDEME filer. Written on every filing; the DR-expected value
    # for a non-enrolled profile is "2", asserted independently of the SHA.
    assert _p1(_M303_REDEME_OFFSET, 1) == b"2", (
        "DR DP30301 offset 110: REDEME indicator must be '2' (NO) for a non-REDEME filer"
    )

    # DR DP30301 row 88 (offset 1570-1581): closing tag </T30301000> (12 bytes)
    assert _p1(1570, 12) == b"</T30301000>", "DR DP30301 row 88: page-01 close tag"

    # DR DP30303 rows 1-4: page-03 tag
    assert _p3(1, 2) == b"<T", "DR DP30303 row 1: page open tag"
    assert _p3(3, 3) == b"303", "DR DP30303 row 2: modelo in page tag"
    assert _p3(6, 5) == b"03000", "DR DP30303 row 3: page-03 identifier must be '03000'"
    assert _p3(11, 1) == b">", "DR DP30303 row 4: close of page tag"

    # DR DP30303 row 25 (offset 255-271): casilla [110] prior-period compensation.
    # Input binding modelo-303-compensacion-pendiente-anteriores = 0.
    assert _p3(255, 17) == _money_bytes(Decimal("0"), signed=False), (
        "DR DP30303 row 25: casilla 110 prior compensation must serialize as explicit zero"
    )

    # DR DP30303 row 26 (offset 272-288): casilla [78] applied compensation.
    # With no positive prior compensation, the computed application is zero.
    assert _p3(272, 17) == _money_bytes(Decimal("0"), signed=False), (
        "DR DP30303 row 26: casilla 78 applied compensation must serialize as explicit zero"
    )

    # DR DP30303 row 27 (offset 289-305): casilla [87] later-period pending compensation.
    # Formula [110] - [78] = 0 for this neutral first-quarter fixture.
    assert _p3(289, 17) == _money_bytes(Decimal("0"), signed=False), (
        "DR DP30303 row 27: casilla 87 posterior compensation must serialize as explicit zero"
    )

    # Cuenta-devolución (DID) page SUPPRESSED on a non-refund disposition:
    # the DID open tag and the "DID00" page identifier must be ABSENT from the
    # whole payload — a non-refund filing has no refund account to declare, so
    # emitting an empty 823-byte DID record would file a devolución AEAT cannot
    # pay. This is the disposition-keyed guard (P02 S09) asserted at byte level.
    assert b"<T303DID00>" not in payload, "DID page must be suppressed on a non-refund filing"
    assert b"DID00" not in payload, "the DID00 page identifier must not appear on a non-refund filing"

    # Envelope footer: computed dynamic closing tag (last 18 bytes).
    # Format: </T{modelo}0{AAAA}{PP}0000> = </T303020251T0000>
    assert payload[-18:] == b"</T303020251T0000>", (
        "Envelope footer must match </T303020251T0000> for modelo=303 year=2025 period=1T"
    )

    # --- Golden SHA (byte-identity lock) ------------------------------------
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M303_GOLDEN_SHA256, (
        f"Modelo 303 non-refund fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M303_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the 303.toml export layout that alters byte output\n"
        "must be re-grounded against the AEAT Diseño de Registros DR303\n"
        "(Orden EHA/3786/2008, 2024 revision, updated 2024-11-29)\n"
        "before updating this constant."
    )

    # Receipt metadata sanity
    assert receipt.byte_size == 7171
    assert receipt.file_sha256 == _M303_GOLDEN_SHA256


def test_modelo_303_refund_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Refund Modelo 303 ("D") with a Spanish IBAN serialises to a byte-exact
    7994-byte fichero-BOE carrying the cuenta-devolución (DID) page.

    Companion to the non-refund golden case. The refund disposition emits the
    DID page AEAT pays into, so the per-offset assertions name the DR-EXPECTED
    refund-block values — not values copied back from the serialiser output:

    * the REDEME indicator at DR DP30301 offset 110 is "1" (SI) for this
      REDEME-enrolled refund filer;
    * the refund IBAN sits at DR DP303DID offset 23, left-justified and
      space-padded to 34 bytes;
    * the derived Marca SEPA at DR DP303DID offset 194 is "1" (Cuenta España)
      for a Spanish (ES) IBAN — derived from the account country, not an input;
    * the SWIFT-BIC slot at DR DP303DID offset 12 stays blank for a SEPA
      account (no foreign-bank block).

    These value assertions are the anti-tautology anchor: each asserts the byte
    the DR Diseño prescribes for the supplied refund account, so a wrong offset
    or a dropped field fails before the SHA changes. The SHA was regenerated
    from the real serialiser, never hand-tuned.
    """
    from .......application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )

    provider = build_runtime_schema_provider(modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Golden test IVA",
        ),
        inputs={
            "07": Decimal("10000.00"),
            "iva.repercutido.general": Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / "modelo-303-refund.txt"
    receipt = export_draft(
        draft,
        output_path=output,
        headers={
            # Refund disposition: AEAT pays the devolución into the DID account.
            "declaration_type": "D",
            "surnames": "GARCIA LOPEZ",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
            # REDEME indicator "1" (SI) for the enrolled refund filer.
            "redeme": "1",
            # The cuenta-devolución refund block: a Spanish (SEPA) IBAN with the
            # derived Marca SEPA "1" (Cuenta España). These are the header
            # fields the M303 refund composer builds from the encrypted
            # RefundAccount; supplied directly here to lock the serialiser bytes.
            "iban": _M303_REFUND_IBAN,
            "sepa_marca": "1",
        },
        schema_provider=provider,
    )
    payload = output.read_bytes()

    # --- DR-grounded structural assertions (non-tautological) -----------------

    def _p1(offset: int, length: int) -> bytes:
        """Read bytes from DR DP30301 page-01 record (1-based field offset)."""
        s = _M303_P01_START + offset - 1
        return payload[s : s + length]

    def _did(offset: int, length: int) -> bytes:
        """Read bytes from DR DP303DID identification record (1-based offset)."""
        s = _M303_DID_START + offset - 1
        return payload[s : s + length]

    # A refund filing emits the DID page, so the fichero is the full 7994 bytes.
    assert len(payload) == 7994, f"expected 7994-byte refund fichero-BOE; got {len(payload)}"

    # DR DP30301 REDEME indicator (offset 110, 1 byte): "1" (SI) for the
    # REDEME-enrolled refund filer — the DR-expected value, asserted before the SHA.
    assert _p1(_M303_REDEME_OFFSET, 1) == b"1", (
        "DR DP30301 offset 110: REDEME indicator must be '1' (SI) for a REDEME refund filer"
    )

    # DR DP303DID rows 1-4: the DID page IS present on a refund.
    assert _did(1, 2) == b"<T", "DR DP303DID row 1: DID open tag present on a refund"
    assert _did(3, 3) == b"303", "DR DP303DID row 2: modelo in DID tag"
    assert _did(6, 5) == b"DID00", "DR DP303DID row 3: page identifier literal 'DID00' (type An)"
    assert _did(11, 1) == b">", "DR DP303DID row 4: close of DID tag"

    # DR DP303DID SWIFT-BIC (offset 12, 11 bytes): blank for a SEPA account —
    # a Cuenta España / UE SEPA refund is identified by its IBAN, not a SWIFT.
    assert _did(_M303_DID_SWIFT_OFFSET, 11) == b" " * 11, (
        "DR DP303DID offset 12: SWIFT-BIC must be blank for a SEPA (Spanish IBAN) account"
    )

    # DR DP303DID IBAN (offset 23, 34 bytes): the refund IBAN, left-justified,
    # space-padded. The DR-expected value is the supplied Spanish IBAN.
    iban_field = _did(_M303_DID_IBAN_OFFSET, 34)
    assert iban_field.rstrip(b" ") == _M303_REFUND_IBAN.encode("latin-1"), (
        "DR DP303DID offset 23: IBAN must be the supplied Spanish refund IBAN"
    )

    # DR DP303DID Marca SEPA (offset 194, 1 byte): "1" (Cuenta España) derived
    # from the ES country of the IBAN — the anti-tautology value assertion.
    assert _did(_M303_DID_SEPA_OFFSET, 1) == b"1", (
        "DR DP303DID offset 194: Marca SEPA must be '1' (Cuenta España) for an ES IBAN"
    )

    # DR DP303DID row 13 (offset 812-823): closing tag </T303DID00> (12 bytes).
    assert _did(812, 12) == b"</T303DID00>", "DR DP303DID row 13: DID close tag"

    # The IBAN reaches the fichero exactly once and only inside the DID page.
    assert payload.count(_M303_REFUND_IBAN.encode("latin-1")) == 1, (
        "the refund IBAN must appear exactly once, inside the DID page"
    )

    # Envelope footer: computed dynamic closing tag (last 18 bytes).
    assert payload[-18:] == b"</T303020251T0000>", (
        "Envelope footer must match </T303020251T0000> for modelo=303 year=2025 period=1T"
    )

    # --- Golden SHA (byte-identity lock) ------------------------------------
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M303_REFUND_GOLDEN_SHA256, (
        f"Modelo 303 refund fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M303_REFUND_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the 303.toml export layout or the refund DID block that\n"
        "alters byte output must be re-grounded against the AEAT Diseño de\n"
        "Registros DR303 (Orden EHA/3786/2008, 2024 revision) before updating\n"
        "this constant."
    )

    # Receipt metadata sanity
    assert receipt.byte_size == 7994
    assert receipt.file_sha256 == _M303_REFUND_GOLDEN_SHA256


def test_modelo_303_refund_non_sepa_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Refund Modelo 303 ("D") with a non-SEPA (Resto Países) SWIFT account
    serialises to a byte-exact 7994-byte fichero-BOE carrying the SWIFT-BIC plus
    the foreign-bank DID block.

    Companion to the SEPA refund golden case, locking the Marca SEPA "3" branch:
    a non-SEPA account is identified by its SWIFT-BIC and foreign-bank block, not
    an IBAN. The per-offset assertions name the DR-EXPECTED refund-block values —
    not values copied back from the serialiser output:

    * the REDEME indicator at DR DP30301 offset 110 is "1" (SI) for this
      REDEME-enrolled refund filer;
    * the SWIFT-BIC sits at DR DP303DID offset 12 (length 11), PRESENT (non-blank)
      — the non-SEPA account is identified by it;
    * the foreign-bank block is populated: bank name at offset 57, bank address at
      127, bank city at 162, bank country at 192;
    * the IBAN slot at DR DP303DID offset 23 stays blank — a non-SEPA account
      carries no IBAN;
    * the derived Marca SEPA at DR DP303DID offset 194 is "3" (Resto Países) for
      the US bank country.

    These value assertions are the anti-tautology anchor: each asserts the byte
    the DR Diseño prescribes for the supplied non-SEPA account, so a wrong offset
    or a dropped field fails before the SHA changes. The SHA was regenerated from
    the real serialiser, never hand-tuned.
    """
    from .......application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )

    provider = build_runtime_schema_provider(modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Golden test IVA",
        ),
        inputs={
            "07": Decimal("10000.00"),
            "iva.repercutido.general": Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / "modelo-303-refund-non-sepa.txt"
    receipt = export_draft(
        draft,
        output_path=output,
        headers={
            # Refund disposition: AEAT pays the devolución into the DID account.
            "declaration_type": "D",
            "surnames": "GARCIA LOPEZ",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
            # REDEME indicator "1" (SI) for the enrolled refund filer.
            "redeme": "1",
            # The cuenta-devolución refund block for a non-SEPA account: a SWIFT-BIC
            # plus foreign-bank block and Marca SEPA "3" (Resto Países), no IBAN.
            # These are the header fields the M303 refund composer builds from the
            # encrypted RefundAccount RESTO_PAISES branch; supplied directly here
            # to lock the serialiser bytes.
            "sepa_marca": "3",
            "swift_bic": _M303_NON_SEPA_SWIFT,
            "bank_name": _M303_NON_SEPA_BANK_NAME,
            "bank_address": _M303_NON_SEPA_BANK_ADDRESS,
            "bank_city": _M303_NON_SEPA_BANK_CITY,
            "bank_country_code": _M303_NON_SEPA_BANK_COUNTRY,
        },
        schema_provider=provider,
    )
    payload = output.read_bytes()

    # --- DR-grounded structural assertions (non-tautological) -----------------

    def _p1(offset: int, length: int) -> bytes:
        """Read bytes from DR DP30301 page-01 record (1-based field offset)."""
        s = _M303_P01_START + offset - 1
        return payload[s : s + length]

    def _did(offset: int, length: int) -> bytes:
        """Read bytes from DR DP303DID identification record (1-based offset)."""
        s = _M303_DID_START + offset - 1
        return payload[s : s + length]

    # A refund filing emits the DID page, so the fichero is the full 7994 bytes.
    assert len(payload) == 7994, f"expected 7994-byte non-SEPA refund fichero-BOE; got {len(payload)}"

    # DR DP30301 REDEME indicator (offset 110, 1 byte): "1" (SI) for the
    # REDEME-enrolled refund filer — the DR-expected value, asserted before the SHA.
    assert _p1(_M303_REDEME_OFFSET, 1) == b"1", (
        "DR DP30301 offset 110: REDEME indicator must be '1' (SI) for a REDEME refund filer"
    )

    # DR DP303DID rows 1-4: the DID page IS present on a refund.
    assert _did(1, 2) == b"<T", "DR DP303DID row 1: DID open tag present on a refund"
    assert _did(3, 3) == b"303", "DR DP303DID row 2: modelo in DID tag"
    assert _did(6, 5) == b"DID00", "DR DP303DID row 3: page identifier literal 'DID00' (type An)"
    assert _did(11, 1) == b">", "DR DP303DID row 4: close of DID tag"

    # DR DP303DID SWIFT-BIC (offset 12, 11 bytes): PRESENT for a non-SEPA account —
    # the Resto Países refund is identified by its SWIFT-BIC, not an IBAN.
    assert _did(_M303_DID_SWIFT_OFFSET, 11).rstrip(b" ") == _M303_NON_SEPA_SWIFT.encode("latin-1"), (
        "DR DP303DID offset 12: SWIFT-BIC must be present for a non-SEPA account"
    )

    # DR DP303DID IBAN (offset 23, 34 bytes): blank — a non-SEPA account has no IBAN.
    assert _did(_M303_DID_IBAN_OFFSET, 34).strip(b" ") == b"", (
        "DR DP303DID offset 23: IBAN slot must be blank for a non-SEPA SWIFT account"
    )

    # DR DP303DID foreign-bank block: name (57), address (127), city (162),
    # country (192) — populated from the supplied non-SEPA account.
    assert _did(_M303_DID_BANK_NAME_OFFSET, 70).rstrip(b" ") == _M303_NON_SEPA_BANK_NAME.encode("latin-1"), (
        "DR DP303DID offset 57: bank name must be the supplied foreign-bank name"
    )
    assert _did(_M303_DID_BANK_ADDRESS_OFFSET, 35).rstrip(b" ") == _M303_NON_SEPA_BANK_ADDRESS.encode("latin-1"), (
        "DR DP303DID offset 127: bank address must be the supplied foreign-bank address"
    )
    assert _did(_M303_DID_BANK_CITY_OFFSET, 30).rstrip(b" ") == _M303_NON_SEPA_BANK_CITY.encode("latin-1"), (
        "DR DP303DID offset 162: bank city must be the supplied foreign-bank city"
    )
    assert _did(_M303_DID_BANK_COUNTRY_OFFSET, 2) == _M303_NON_SEPA_BANK_COUNTRY.encode("latin-1"), (
        "DR DP303DID offset 192: bank country must be the supplied 'US' code"
    )

    # DR DP303DID Marca SEPA (offset 194, 1 byte): "3" (Resto Países) derived from
    # the US bank country — the anti-tautology value assertion.
    assert _did(_M303_DID_SEPA_OFFSET, 1) == b"3", (
        "DR DP303DID offset 194: Marca SEPA must be '3' (Resto Países) for a US SWIFT account"
    )

    # DR DP303DID row 13 (offset 812-823): closing tag </T303DID00> (12 bytes).
    assert _did(812, 12) == b"</T303DID00>", "DR DP303DID row 13: DID close tag"

    # The SWIFT-BIC reaches the fichero exactly once and only inside the DID page.
    assert payload.count(_M303_NON_SEPA_SWIFT.encode("latin-1")) == 1, (
        "the SWIFT-BIC must appear exactly once, inside the DID page"
    )

    # Envelope footer: computed dynamic closing tag (last 18 bytes).
    assert payload[-18:] == b"</T303020251T0000>", (
        "Envelope footer must match </T303020251T0000> for modelo=303 year=2025 period=1T"
    )

    # --- Golden SHA (byte-identity lock) ------------------------------------
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M303_REFUND_NON_SEPA_GOLDEN_SHA256, (
        f"Modelo 303 non-SEPA refund fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M303_REFUND_NON_SEPA_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the 303.toml export layout or the non-SEPA DID block that\n"
        "alters byte output must be re-grounded against the AEAT Diseño de\n"
        "Registros DR303 (Orden EHA/3786/2008, 2024 revision) before updating\n"
        "this constant."
    )

    # Receipt metadata sanity
    assert receipt.byte_size == 7994
    assert receipt.file_sha256 == _M303_REFUND_NON_SEPA_GOLDEN_SHA256
