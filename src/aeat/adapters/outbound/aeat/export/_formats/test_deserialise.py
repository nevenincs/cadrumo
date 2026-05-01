"""Tests for the fichero-BOE deserialiser + round-trip fidelity (EPIC #201 C3d,)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._deserialise import deserialise
from ._serialise import serialise
from .modelo_130_2024 import (
    ENCODING,
    RECORD_LENGTH,
    RECORD_SPECS,
    REQUIRED_HEADER_FIELDS,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _base_headers() -> dict[str, str]:
    return {
        "EJERCICIO": "2024",
        "PERIODO": "1T",
        "NIF_DECLARANTE": "X1234567L",
        "APELLIDOS": "DOE RODRIGUEZ",
        "NOMBRE": "KENT",
        "TIPO_DECLARACION": "I",
    }


def _base_casillas() -> dict[str, Decimal]:
    return {f"{i:02d}": Decimal(f"{(i + 1) * 100}.00") for i in range(1, 20)}


class TestDeserialiseModelo1302024:
    def test_parses_literal_values(self) -> None:
        """RESERVED fields surface their literal_value in field_values."""
        payload = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        result = deserialise(
            payload,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
        )
        assert result.field_values["MODELO"] == "130"
        assert result.field_values["PAGINA"] == "01"

    def test_parses_header_text(self) -> None:
        payload = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        result = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING, total_length=RECORD_LENGTH)
        assert result.field_values["NIF_DECLARANTE"] == "X1234567L"
        assert result.field_values["EJERCICIO"] == "2024"
        assert result.field_values["PERIODO"] == "1T"
        assert result.field_values["APELLIDOS"] == "DOE RODRIGUEZ"
        assert result.field_values["NOMBRE"] == "KENT"
        assert result.field_values["TIPO_DECLARACION"] == "I"

    def test_parses_casilla_values_as_decimal(self) -> None:
        payload = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        result = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING, total_length=RECORD_LENGTH)
        # Casilla 01 input was Decimal("200.00") per _base_casillas ((i+1)*100 for i=1).
        assert result.casilla_values["01"] == Decimal("200.00")
        assert result.casilla_values["19"] == Decimal("2000.00")
        assert isinstance(result.casilla_values["01"], Decimal)

    def test_raw_length_matches_content(self) -> None:
        payload = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        result = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING, total_length=RECORD_LENGTH)
        assert result.raw_length == RECORD_LENGTH

    def test_payload_without_crlf_also_parses(self) -> None:
        """Deserialiser accepts content-only (no terminator) for forward
        compatibility (e.g. from a verify-against-AEAT path that strips
        CRLF before hashing)."""
        payload = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        content_only = payload[:-2]  # strip CRLF
        result = deserialise(
            content_only,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
        )
        assert result.field_values["MODELO"] == "130"

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="content is"):
            deserialise(
                b"SHORT_PAYLOAD",
                specs=RECORD_SPECS,
                encoding=ENCODING,
                total_length=RECORD_LENGTH,
            )


class TestRoundTripFidelity:
    """The single most important C3d acceptance test: serialise -> deserialise
    preserves every casilla value and every header."""

    def test_round_trip_preserves_casilla_values(self) -> None:
        casillas = _base_casillas()
        headers = _base_headers()

        payload = serialise(
            casilla_values=casillas,
            headers=headers,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        parsed = deserialise(
            payload,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
        )

        # Every casilla value survives byte-exactly.
        for cid, expected in casillas.items():
            assert parsed.casilla_values[cid] == expected, (
                f"casilla {cid!r} drift: expected {expected}, got {parsed.casilla_values[cid]}"
            )

    def test_round_trip_preserves_headers(self) -> None:
        headers = _base_headers()
        payload = serialise(
            casilla_values=_base_casillas(),
            headers=headers,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        parsed = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING, total_length=RECORD_LENGTH)
        for field_id, expected in headers.items():
            assert parsed.field_values[field_id] == expected, (
                f"header {field_id!r} drift: expected {expected!r}, got {parsed.field_values[field_id]!r}"
            )

    def test_round_trip_with_accented_names(self) -> None:
        """ñ-preserving round trip — CP1252 encoding handles Spanish names correctly."""
        headers = _base_headers()
        headers["APELLIDOS"] = "MUÑOZ ÑAÑEZ"
        payload = serialise(
            casilla_values=_base_casillas(),
            headers=headers,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        parsed = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING, total_length=RECORD_LENGTH)
        assert parsed.field_values["APELLIDOS"] == "MUÑOZ ÑAÑEZ"

    def test_round_trip_zero_padded_casillas(self) -> None:
        """Zero-valued casillas decode back to Decimal("0.00") — not empty string."""
        zeros = {f"{i:02d}": Decimal("0.00") for i in range(1, 20)}
        payload = serialise(
            casilla_values=zeros,
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        parsed = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING, total_length=RECORD_LENGTH)
        for cid in zeros:
            assert parsed.casilla_values[cid] == Decimal("0.00")
            assert isinstance(parsed.casilla_values[cid], Decimal)
