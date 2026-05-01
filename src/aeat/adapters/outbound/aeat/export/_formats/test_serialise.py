"""Tests for the fichero-BOE serialiser (EPIC #201 C3b,)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._serialise import serialise
from .modelo_130_2024 import (
    ENCODING,
    RECORD_LENGTH,
    RECORD_SPECS,
    REQUIRED_HEADER_FIELDS,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _base_headers() -> dict[str, str]:
    """Minimal valid headers for Modelo 130 serialisation."""
    return {
        "EJERCICIO": "2024",
        "PERIODO": "1T",
        "NIF_DECLARANTE": "X1234567L",
        "APELLIDOS": "DOE RODRIGUEZ",
        "NOMBRE": "KENT",
        "TIPO_DECLARACION": "I",
    }


def _base_casillas() -> dict[str, Decimal]:
    """Positive-result Q1 filing."""
    return {
        "01": Decimal("10000.00"),
        "02": Decimal("3000.00"),
        "03": Decimal("7000.00"),
        "04": Decimal("1400.00"),
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "07": Decimal("1400.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "10": Decimal("0.00"),
        "11": Decimal("0.00"),
        "12": Decimal("1400.00"),
        "13": Decimal("0.00"),
        "14": Decimal("1400.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "17": Decimal("1400.00"),
        "18": Decimal("0.00"),
        "19": Decimal("1400.00"),
    }


class TestSerialiseModelo1302024:
    def test_total_output_is_content_plus_crlf(self) -> None:
        """Output is RECORD_LENGTH + 2 bytes (CRLF terminator)."""
        result = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        assert len(result) == RECORD_LENGTH + 2
        assert result.endswith(b"\r\n")

    def test_header_bytes_are_canonical(self) -> None:
        result = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # MODELO literal "130" at positions 1-3 (bytes 0-2).
        assert result[0:3] == b"130"
        # PAGINA literal "01" at positions 4-5 (bytes 3-4).
        assert result[3:5] == b"01"
        # TIPO_DECLARACION at position 7 (byte 6).
        assert result[6:7] == b"I"
        # NIF at positions 13-21 (bytes 12-20).
        assert result[12:21] == b"X1234567L"
        # EJERCICIO at positions 71-74 (bytes 70-73).
        assert result[70:74] == b"2024"
        # PERIODO at positions 75-76 (bytes 74-75).
        assert result[74:76] == b"1T"

    def test_casilla_01_bytes(self) -> None:
        """INGRESOS_COMPUTABLES at positions 77-89; Decimal 10000.00 → 13 zero-padded cents."""
        result = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # 10000.00 * 100 = 1000000 cents, padded to 13 digits.
        assert result[76:89] == b"0000001000000"

    def test_apellidos_space_padded(self) -> None:
        """APELLIDOS is left-justified, space-padded to 30 bytes."""
        result = serialise(
            casilla_values=_base_casillas(),
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # APELLIDOS "DOE RODRIGUEZ" (13 chars) at positions 26-55 (bytes 25-54).
        assert result[25:55] == b"DOE RODRIGUEZ                 "

    def test_missing_nif_raises(self) -> None:
        headers = _base_headers()
        del headers["NIF_DECLARANTE"]
        with pytest.raises(ValueError, match="NIF_DECLARANTE"):
            serialise(
                casilla_values=_base_casillas(),
                headers=headers,
                specs=RECORD_SPECS,
                encoding=ENCODING,
                total_length=RECORD_LENGTH,
                required_field_ids=REQUIRED_HEADER_FIELDS,
            )

    def test_empty_required_raises(self) -> None:
        headers = _base_headers()
        headers["EJERCICIO"] = ""
        with pytest.raises(ValueError, match="EJERCICIO"):
            serialise(
                casilla_values=_base_casillas(),
                headers=headers,
                specs=RECORD_SPECS,
                encoding=ENCODING,
                total_length=RECORD_LENGTH,
                required_field_ids=REQUIRED_HEADER_FIELDS,
            )

    def test_missing_casilla_defaults_to_zero(self) -> None:
        """Absent casilla → 13-byte zero-padded. AEAT expects every
        CURRENCY slot filled."""
        sparse = {"01": Decimal("500.00")}  # only casilla 01 provided
        result = serialise(
            casilla_values=sparse,
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # Casilla 02 at positions 90-102 (bytes 89-101) → all zeros.
        assert result[89:102] == b"0000000000000"
        # Casilla 01 still populated at bytes 76-88.
        assert result[76:89] == b"0000000050000"

    def test_negative_tipo_n_filing(self) -> None:
        """Negative-result filing: TIPO_DECLARACION='N', casilla 19 could be
        negative via casilla 15/18 offsets — but in BOE the MAGNITUDE is
        unsigned and the TIPO flag encodes the sign."""
        headers = _base_headers()
        headers["TIPO_DECLARACION"] = "N"
        casillas = _base_casillas()
        casillas["15"] = Decimal("2000.00")  # carried-forward negative
        casillas["17"] = Decimal("-600.00")  # diferencia negativa
        casillas["19"] = Decimal("-600.00")
        with pytest.raises(ValueError, match="signed=True"):
            # Default signed=False refuses negative magnitude; caller
            # must wire the SIGNO/TIPO flag flip explicitly.
            serialise(
                casilla_values=casillas,
                headers=headers,
                specs=RECORD_SPECS,
                encoding=ENCODING,
                total_length=RECORD_LENGTH,
                required_field_ids=REQUIRED_HEADER_FIELDS,
            )

    def test_all_zero_filing_is_well_formed(self) -> None:
        """A zero-value filing still emits a well-formed 880-byte record."""
        zeros = {f"{i:02d}": Decimal("0.00") for i in range(1, 20)}
        result = serialise(
            casilla_values=zeros,
            headers=_base_headers(),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        assert len(result) == 880
        # Every 13-byte casilla slot is zero-padded.
        for i in range(19):
            casilla_start = 76 + i * 13
            assert result[casilla_start : casilla_start + 13] == b"0000000000000", (
                f"casilla slot #{i + 1} not zero-padded"
            )
