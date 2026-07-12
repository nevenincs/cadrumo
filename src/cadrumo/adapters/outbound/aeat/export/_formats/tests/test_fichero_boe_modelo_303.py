"""Modelo 303 golden-SHA fichero-BOE round-trip tests."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from ._fichero_boe_roundtrip_support import _export_approved_303_fichero, _m303_headers, _money_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_M303_GOLDEN_SHA256 = "6b0822ce2cb8ce112066438c245afec78c3051abbfd69825d01cc65b2322720e"
_M303_REFUND_GOLDEN_SHA256 = "283699403be00cc249625da21e5ffcbaf6dc0b429202a7f69feaaacc3701e2a1"
_M303_REFUND_NON_SEPA_GOLDEN_SHA256 = "4dc53ab2e9ba9bda51f114112a01d93c8e90892f7fc0c0781de3c7106158f30b"

_M303_P01_START = 328
_M303_P02_START = 1909
_M303_P03_START = 3809
_M303_DID_START = 7347

_M303_REDEME_OFFSET = 110
_M303_DID_SWIFT_OFFSET = 12
_M303_DID_IBAN_OFFSET = 23
_M303_DID_BANK_NAME_OFFSET = 57
_M303_DID_BANK_ADDRESS_OFFSET = 127
_M303_DID_BANK_CITY_OFFSET = 162
_M303_DID_BANK_COUNTRY_OFFSET = 192
_M303_DID_SEPA_OFFSET = 194

_M303_REFUND_IBAN = "ES9121000418450200051332"
_M303_NON_SEPA_SWIFT = "CHASUS33XXX"
_M303_NON_SEPA_BANK_NAME = "Synthetic US Bank"
_M303_NON_SEPA_BANK_ADDRESS = "1 Synthetic Plaza"
_M303_NON_SEPA_BANK_CITY = "New York"
_M303_NON_SEPA_BANK_COUNTRY = "US"


def test_modelo_303_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Non-refund Modelo 303 ("I") serialises to a byte-exact 7365-byte fichero-BOE."""
    exported = _export_approved_303_fichero(
        tmp_path,
        filename="modelo-303.txt",
        headers=_m303_headers(
            declaration_type="I",
            redeme="2",
        ),
    )
    payload = exported.payload

    def _hdr(offset: int, length: int) -> bytes:
        return payload[offset - 1 : offset - 1 + length]

    def _p1(offset: int, length: int) -> bytes:
        s = _M303_P01_START + offset - 1
        return payload[s : s + length]

    def _p2(offset: int, length: int) -> bytes:
        s = _M303_P02_START + offset - 1
        return payload[s : s + length]

    def _p3(offset: int, length: int) -> bytes:
        s = _M303_P03_START + offset - 1
        return payload[s : s + length]

    assert len(payload) == 7365, f"expected 7365-byte non-refund fichero-BOE; got {len(payload)}"
    assert _hdr(1, 2) == b"<T", "DR DP30300 row 1: opening tag must be '<T'"
    assert _hdr(3, 3) == b"303", "DR DP30300 row 2: modelo identifier must be '303'"
    assert _hdr(6, 1) == b"0", "DR DP30300 row 3: discriminante must be '0'"
    assert _hdr(7, 4) == b"2025", "DR DP30300 row 4: ejercicio must be '2025'"
    assert _hdr(11, 2) == b"1T", "DR DP30300 row 5: periodo must be '1T'"
    assert _hdr(13, 5) == b"0000>", "DR DP30300 row 6: marker must be '0000>'"
    assert _hdr(18, 5) == b"<AUX>", "DR DP30300 row 7: AUX open tag"
    assert _hdr(323, 6) == b"</AUX>", "DR DP30300 row 13: AUX close tag"

    assert _p1(1, 2) == b"<T", "DR DP30301 row 1: page open tag"
    assert _p1(3, 3) == b"303", "DR DP30301 row 2: modelo in page tag"
    assert _p1(6, 5) == b"01000", "DR DP30301 row 3: page-01 identifier must be '01000'"
    assert _p1(11, 1) == b">", "DR DP30301 row 4: close of page tag"
    assert _p1(14, 9) == b"12345678Z", "DR DP30301 row 7: NIF must match input profile"
    assert _p1(23, 80).rstrip(b" ") == b"GARCIA LOPEZ JUAN", (
        "DR DP30301 row 8: legal name must combine surnames and name"
    )
    assert _p1(103, 4) == b"2025", "DR DP30301 row 9: ejercicio must be '2025'"
    assert _p1(107, 2) == b"1T", "DR DP30301 row 10: periodo must be '1T'"
    assert _p1(286, 17) == _money_bytes(Decimal("10000.00"), signed=False), (
        "DR DP30301 row 37: casilla 07 base imponible 21% must be 10000.00"
    )
    assert _p1(303, 5) == b"02100", "DR DP30301 row 38: tipo 08 must be constant '02100' (21%)"
    assert _p1(308, 17) == _money_bytes(Decimal("2100.00"), signed=False), (
        "DR DP30301 row 39: casilla 09 cuota 21% must be 2100.00"
    )
    assert _p1(_M303_REDEME_OFFSET, 1) == b"2", (
        "DR DP30301 offset 110: REDEME indicator must be '2' (NO) for a non-REDEME filer"
    )
    assert _p1(1570, 12) == b"</T30301000>", "DR DP30301 row 88: page-01 close tag"

    assert _p2(1615, 274) == b" " * 274, "DR DP30302 row 165: reserved tail must be 274 bytes"
    assert _p2(1889, 12) == b"</T30302000>", "DR DP30302 row 166: page-02 close tag"

    assert _p3(1, 2) == b"<T", "DR DP30303 row 1: page open tag"
    assert _p3(3, 3) == b"303", "DR DP30303 row 2: modelo in page tag"
    assert _p3(6, 5) == b"03000", "DR DP30303 row 3: page-03 identifier must be '03000'"
    assert _p3(11, 1) == b">", "DR DP30303 row 4: close of page tag"
    assert _p3(255, 17) == _money_bytes(Decimal("0"), signed=False), (
        "DR DP30303 row 25: casilla 110 prior compensation must serialize as explicit zero"
    )
    assert _p3(272, 17) == _money_bytes(Decimal("0"), signed=False), (
        "DR DP30303 row 26: casilla 78 applied compensation must serialize as explicit zero"
    )
    assert _p3(289, 17) == _money_bytes(Decimal("0"), signed=False), (
        "DR DP30303 row 27: casilla 87 posterior compensation must serialize as explicit zero"
    )

    assert b"<T303DID00>" not in payload, "DID page must be suppressed on a non-refund filing"
    assert b"DID00" not in payload, "the DID00 page identifier must not appear on a non-refund filing"
    assert payload[-18:] == b"</T303020251T0000>", (
        "Envelope footer must match </T303020251T0000> for modelo=303 year=2025 period=1T"
    )

    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M303_GOLDEN_SHA256, (
        f"Modelo 303 non-refund fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M303_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the 303.toml export layout that alters byte output must be re-grounded against DR303."
    )
    assert exported.receipt_byte_size == 7365
    assert exported.receipt_file_sha256 == _M303_GOLDEN_SHA256


def test_modelo_303_refund_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Refund Modelo 303 ("D") with a Spanish IBAN emits the DID page."""
    exported = _export_approved_303_fichero(
        tmp_path,
        filename="modelo-303-refund.txt",
        headers=_m303_headers(
            declaration_type="D",
            redeme="1",
            iban=_M303_REFUND_IBAN,
            sepa_marca="1",
        ),
    )
    payload = exported.payload

    def _p1(offset: int, length: int) -> bytes:
        s = _M303_P01_START + offset - 1
        return payload[s : s + length]

    def _did(offset: int, length: int) -> bytes:
        s = _M303_DID_START + offset - 1
        return payload[s : s + length]

    assert len(payload) == 8188, f"expected 8188-byte refund fichero-BOE; got {len(payload)}"
    assert _p1(_M303_REDEME_OFFSET, 1) == b"1", (
        "DR DP30301 offset 110: REDEME indicator must be '1' (SI) for a REDEME refund filer"
    )
    assert _did(1, 2) == b"<T", "DR DP303DID row 1: DID open tag present on a refund"
    assert _did(3, 3) == b"303", "DR DP303DID row 2: modelo in DID tag"
    assert _did(6, 5) == b"DID00", "DR DP303DID row 3: page identifier literal 'DID00' (type An)"
    assert _did(11, 1) == b">", "DR DP303DID row 4: close of DID tag"
    assert _did(_M303_DID_SWIFT_OFFSET, 11) == b" " * 11, (
        "DR DP303DID offset 12: SWIFT-BIC must be blank for a SEPA (Spanish IBAN) account"
    )

    iban_field = _did(_M303_DID_IBAN_OFFSET, 34)
    assert iban_field.rstrip(b" ") == _M303_REFUND_IBAN.encode("latin-1"), (
        "DR DP303DID offset 23: IBAN must be the supplied Spanish refund IBAN"
    )
    assert _did(_M303_DID_SEPA_OFFSET, 1) == b"1", (
        "DR DP303DID offset 194: Marca SEPA must be '1' (Cuenta España) for an ES IBAN"
    )
    assert _did(812, 12) == b"</T303DID00>", "DR DP303DID row 13: DID close tag"
    assert payload.count(_M303_REFUND_IBAN.encode("latin-1")) == 1, (
        "the refund IBAN must appear exactly once, inside the DID page"
    )
    assert payload[-18:] == b"</T303020251T0000>", (
        "Envelope footer must match </T303020251T0000> for modelo=303 year=2025 period=1T"
    )

    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M303_REFUND_GOLDEN_SHA256, (
        f"Modelo 303 refund fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M303_REFUND_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the 303.toml export layout or refund DID block must be re-grounded against DR303."
    )
    assert exported.receipt_byte_size == 8188
    assert exported.receipt_file_sha256 == _M303_REFUND_GOLDEN_SHA256


def test_modelo_303_refund_non_sepa_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Refund Modelo 303 ("D") with a non-SEPA SWIFT account emits the foreign-bank DID block."""
    exported = _export_approved_303_fichero(
        tmp_path,
        filename="modelo-303-refund-non-sepa.txt",
        headers=_m303_headers(
            declaration_type="D",
            redeme="1",
            sepa_marca="3",
            swift_bic=_M303_NON_SEPA_SWIFT,
            bank_name=_M303_NON_SEPA_BANK_NAME,
            bank_address=_M303_NON_SEPA_BANK_ADDRESS,
            bank_city=_M303_NON_SEPA_BANK_CITY,
            bank_country_code=_M303_NON_SEPA_BANK_COUNTRY,
        ),
    )
    payload = exported.payload

    def _p1(offset: int, length: int) -> bytes:
        s = _M303_P01_START + offset - 1
        return payload[s : s + length]

    def _did(offset: int, length: int) -> bytes:
        s = _M303_DID_START + offset - 1
        return payload[s : s + length]

    assert len(payload) == 8188, f"expected 8188-byte non-SEPA refund fichero-BOE; got {len(payload)}"
    assert _p1(_M303_REDEME_OFFSET, 1) == b"1", (
        "DR DP30301 offset 110: REDEME indicator must be '1' (SI) for a REDEME refund filer"
    )
    assert _did(1, 2) == b"<T", "DR DP303DID row 1: DID open tag present on a refund"
    assert _did(3, 3) == b"303", "DR DP303DID row 2: modelo in DID tag"
    assert _did(6, 5) == b"DID00", "DR DP303DID row 3: page identifier literal 'DID00' (type An)"
    assert _did(11, 1) == b">", "DR DP303DID row 4: close of DID tag"
    assert _did(_M303_DID_SWIFT_OFFSET, 11).rstrip(b" ") == _M303_NON_SEPA_SWIFT.encode("latin-1"), (
        "DR DP303DID offset 12: SWIFT-BIC must be present for a non-SEPA account"
    )
    assert _did(_M303_DID_IBAN_OFFSET, 34).strip(b" ") == b"", (
        "DR DP303DID offset 23: IBAN slot must be blank for a non-SEPA SWIFT account"
    )
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
    assert _did(_M303_DID_SEPA_OFFSET, 1) == b"3", (
        "DR DP303DID offset 194: Marca SEPA must be '3' (Resto Países) for a US SWIFT account"
    )
    assert _did(812, 12) == b"</T303DID00>", "DR DP303DID row 13: DID close tag"
    assert payload.count(_M303_NON_SEPA_SWIFT.encode("latin-1")) == 1, (
        "the SWIFT-BIC must appear exactly once, inside the DID page"
    )
    assert payload[-18:] == b"</T303020251T0000>", (
        "Envelope footer must match </T303020251T0000> for modelo=303 year=2025 period=1T"
    )

    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M303_REFUND_NON_SEPA_GOLDEN_SHA256, (
        f"Modelo 303 non-SEPA refund fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M303_REFUND_NON_SEPA_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the 303.toml export layout or non-SEPA DID block must be re-grounded against DR303."
    )
    assert exported.receipt_byte_size == 8188
    assert exported.receipt_file_sha256 == _M303_REFUND_NON_SEPA_GOLDEN_SHA256
