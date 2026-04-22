"""Golden-fixture byte-exactness tests for Modelo 130 (wave 84).

These tests pin the full 880-byte serialiser output for a known-good
Kent filing scenario. Any future change to the schema, encoder, or
serialiser that alters a single byte will fail this test immediately.

The SHA256 digest is the audit-trail anchor: a future wave that
genuinely needs to change the byte layout (e.g., wave 85+ offset
correction after a manual AEAT portal-upload test) must update
this file AND document the reason in the commit message. A stray
byte shift should NEVER pass silently.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from ._serialise import serialise
from .modelo_130_2024 import (
    _RECORD_SPECS,
    ENCODING,
    RECORD_LENGTH,
    REQUIRED_HEADER_FIELDS,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo1302024GoldenKentQ1:
    """Kent's Q1 2024 Modelo 130: 20 000 ingresos, 5 000 gastos, 3 000 resultado."""

    @staticmethod
    def _serialise_kent_q1() -> bytes:
        return serialise(
            casilla_values={
                "01": Decimal("20000.00"),
                "02": Decimal("5000.00"),
                "03": Decimal("15000.00"),
                "04": Decimal("3000.00"),
                "07": Decimal("3000.00"),
                "12": Decimal("3000.00"),
                "14": Decimal("3000.00"),
                "17": Decimal("3000.00"),
                "19": Decimal("3000.00"),
            },
            headers={
                "EJERCICIO": "2024",
                "PERIODO": "1T",
                "NIF_DECLARANTE": "X1234567L",
                "APELLIDOS": "DOE RODRIGUEZ",
                "NOMBRE": "KENT",
                "TIPO_DECLARACION": "I",
            },
            specs=_RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )

    def test_total_length_is_880(self) -> None:
        """RECORD_LENGTH (878) + CRLF (2) = 880 on the wire."""
        payload = self._serialise_kent_q1()
        assert len(payload) == 880

    def test_sha256_digest_is_stable(self) -> None:
        """Golden digest — DO NOT change without documented intent.

        A byte-layout change that alters this digest is a decision,
        not an accident. The commit message must name which offset /
        encoder / field changed and why.
        """
        payload = self._serialise_kent_q1()
        expected = "fb5fd7955a2265d0cf6b1bcb31b8ceee52aeea75297d8de98d8b649cbd479494"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, (
            f"byte-layout drift detected!\n"
            f"  expected SHA256: {expected}\n"
            f"  actual   SHA256: {actual}\n"
            f"If the change is intentional (wave-Nx offset correction),\n"
            f"update the `expected` literal above AND document the\n"
            f"reason in the commit message."
        )

    def test_payload_ends_with_crlf(self) -> None:
        payload = self._serialise_kent_q1()
        assert payload.endswith(b"\r\n")

    def test_canonical_header_bytes(self) -> None:
        payload = self._serialise_kent_q1()
        assert payload[0:3] == b"130"  # MODELO literal
        assert payload[3:5] == b"01"  # PAGINA literal
        assert payload[6:7] == b"I"  # TIPO_DECLARACION
        assert payload[12:21] == b"X1234567L"  # NIF
        assert payload[70:74] == b"2024"  # EJERCICIO
        assert payload[74:76] == b"1T"  # PERIODO

    def test_canonical_casilla_bytes(self) -> None:
        """Casilla 01 at bytes 76-88 (positions 77-89); casilla 19 at 310-322."""
        payload = self._serialise_kent_q1()
        # Casilla 01 = 20 000.00 → 2 000 000 cents → 0000002000000
        assert payload[76:89] == b"0000002000000"
        # Casilla 04 = 3 000.00 at positions 116-128 → bytes 115-127
        assert payload[115:128] == b"0000000300000"
        # Casilla 19 = 3 000.00 at positions 311-323 → bytes 310-322
        assert payload[310:323] == b"0000000300000"
