"""Shape + contiguity tests for the Modelo 130 2024 fichero-BOE spec.

Wave 77c (EPIC #201 / EPIC #305). This test suite proves the
concrete `_RECORD_SPECS` tuple is well-formed. The actual
serialise / parse round-trip lands in wave 78 with the C3b
serialiser + a golden-fixture byte-exact test.
"""

from __future__ import annotations

import pytest

from ._record_spec import FieldKind, validate_record_specs
from .modelo_130_2024 import _RECORD_SPECS, ENCODING, RECORD_LENGTH

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo1302024Shape:
    def test_total_record_length(self) -> None:
        # Field content is 878 bytes (positions 1-878). The on-wire
        # stream adds a 2-byte CRLF terminator (positions 879-880)
        # handled by the serialiser. Total on-wire = 880.
        assert RECORD_LENGTH == 878

    def test_encoding(self) -> None:
        assert ENCODING == "cp1252"

    def test_specs_are_contiguous_and_fill_record(self) -> None:
        """Wave 77a validator runs at import time; re-asserting here
        catches any future regression that smuggles an import-order
        trick past the module-level call."""
        validate_record_specs(_RECORD_SPECS, total_length=RECORD_LENGTH)

    def test_header_block_canonical_offsets(self) -> None:
        """Wave 79a: offsets pinned to dr130.09.pdf consolidated spec."""
        first = _RECORD_SPECS[0]
        assert first.field_id == "MODELO"
        assert first.literal_value == "130"
        assert first.offset == 1
        assert first.length == 3
        by_id = {s.field_id: s for s in _RECORD_SPECS}
        assert by_id["PAGINA"].offset == 4
        assert by_id["PAGINA"].length == 2
        assert by_id["PAGINA"].literal_value == "01"
        assert by_id["IND_COMPLEMENTARIA"].offset == 6
        assert by_id["TIPO_DECLARACION"].offset == 7
        assert by_id["COD_ADMINISTRACION"].offset == 8
        assert by_id["COD_ADMINISTRACION"].length == 5
        assert by_id["NIF_DECLARANTE"].offset == 13
        assert by_id["NIF_DECLARANTE"].length == 9
        assert by_id["APELLIDOS"].offset == 26
        assert by_id["APELLIDOS"].length == 30
        assert by_id["NOMBRE"].offset == 56
        assert by_id["NOMBRE"].length == 15
        assert by_id["EJERCICIO"].offset == 71
        assert by_id["PERIODO"].offset == 75

    def test_all_19_casillas_mapped(self) -> None:
        """The Modelo 130 ruleset has 19 casillas (01..19); every one
        must have exactly one corresponding record field."""
        casilla_ids = {s.casilla_id for s in _RECORD_SPECS if s.casilla_id is not None}
        expected = {f"{i:02d}" for i in range(1, 20)}
        assert casilla_ids == expected, (
            f"missing or extra casillas: missing={expected - casilla_ids}, extra={casilla_ids - expected}"
        )

    def test_every_casilla_is_currency_13_bytes(self) -> None:
        """Wave 77c: every casilla field is 13-byte currency (11 int + 2 dec)."""
        for spec in _RECORD_SPECS:
            if spec.casilla_id is None:
                continue
            assert spec.kind is FieldKind.CURRENCY, (
                f"casilla {spec.casilla_id!r} field_id={spec.field_id!r} is {spec.kind!r}, expected CURRENCY"
            )
            assert spec.length == 13, f"casilla {spec.casilla_id!r} length={spec.length}, expected 13"

    def test_final_field_reaches_record_end(self) -> None:
        final = _RECORD_SPECS[-1]
        assert final.offset + final.length - 1 == RECORD_LENGTH
