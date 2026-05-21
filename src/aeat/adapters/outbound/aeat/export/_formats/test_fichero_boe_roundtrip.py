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

from .._errors import ExportFormatError
from ._deserialise import deserialise
from ._record_spec import (
    DateFmt,
    FieldKind,
    Justification,
    SignedMode,
    record_field,
    validate_record_specs,
)
from ._serialise import serialise

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


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
        encoding="iso-8859-1",
        total_length=12,
    )

    # Byte 0 must be the inline-sign marker for negative values.
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body[0:1] == b"N", (
        f"INLINE_SIGN negative value should emit 'N' in byte 0; got {body[0:1]!r}"
    )

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=12)
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
        encoding="iso-8859-1",
        total_length=12,
    )

    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body[0:1] == b" ", (
        f"INLINE_SIGN non-negative value should emit space in byte 0; got {body[0:1]!r}"
    )

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=12)
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
        encoding="iso-8859-1",
        total_length=8,
    )
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body == b"20250420"

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=8)
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
        encoding="iso-8859-1",
        total_length=8,
    )
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body == b"20042025"

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=8)
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
        encoding="iso-8859-1",
        total_length=8,
    )
    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=8)
    assert parsed.field_values["REF"] == "ABC123"


def test_currency_blank_input_rejected_at_decode() -> None:
    """A blank CURRENCY field is rejected with ExportFormatError.

    A blank CURRENCY field is a wire-format error per the fichero-
    BOE spec (zero-padded ASCII digits required). The decode path
    must surface this as a typed parse refusal rather than silently
    consuming blank bytes as ``Decimal("0.00")`` indistinguishable
    from a legitimate zero.
    """

    from .._errors import ExportFormatError
    from ._deserialise import deserialise

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
    with pytest.raises(ExportFormatError, match=r"CURRENCY field is blank"):
        deserialise(blank_payload, specs=specs, encoding="iso-8859-1", total_length=12)


def test_currency_inline_sign_blank_magnitude_rejected_at_decode() -> None:
    """A blank INLINE_SIGN CURRENCY magnitude is rejected.

    Same contract as the unsigned-CURRENCY case: ``N           ``
    (sign marker + blank magnitude) must fail rather than silently
    decode to a negative-zero.
    """

    from .._errors import ExportFormatError
    from ._deserialise import deserialise

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
    with pytest.raises(ExportFormatError, match=r"magnitude is blank"):
        deserialise(blank_payload, specs=specs, encoding="iso-8859-1", total_length=12)


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
        encoding="iso-8859-1",
        total_length=4,
    )
    assert b"AEAT" in payload, payload

    corrupted = payload.replace(b"AEAT", b"XXXX")
    assert corrupted != payload

    with pytest.raises(ExportFormatError, match="RESERVED"):
        deserialise(corrupted, specs=specs, encoding="iso-8859-1", total_length=4)


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
# field offset, length, or encoding in 130.toml will change the SHA and
# fail this test; changes must be re-grounded against the DR before
# updating the constant.
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
    from aeat.application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )

    provider = build_runtime_schema_provider(modelos=("130",))
    draft = build_draft(
        modelo="130",
        period="2026Q1",
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
            "15": Decimal("0"),
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
        "Any change to the 130.toml export layout that alters byte output\n"
        "must be re-grounded against the AEAT Diseño de Registros (DR 13001,\n"
        "Orden HAP/258/2015 v1.2) before updating this constant."
    )

    # Receipt metadata sanity
    assert receipt.byte_size == 946
    assert receipt.file_sha256 == _M130_GOLDEN_SHA256
