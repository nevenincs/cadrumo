"""Shape and contiguity tests for the Modelo 130 2024 fichero-BOE spec.

Proves that the concrete ``RECORD_SPECS`` tuple is well-formed. The
serialise / parse round-trip lives separately in the serialiser
golden-fixture suite.
"""

from __future__ import annotations

import pytest

from ._record_spec import FieldKind, validate_record_specs
from .modelo_130_2024 import RECORD_LENGTH, RECORD_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


class TestModelo1302024Shape:
    """Structural invariants on :data:`RECORD_SPECS`."""

    def test_specs_are_contiguous_and_fill_record(self) -> None:
        """Re-assert :func:`validate_record_specs` at test time.

        The validator runs at import time too, but re-asserting here
        catches any future regression that smuggles an import-order
        trick past the module-level call.
        """
        validate_record_specs(RECORD_SPECS, total_length=RECORD_LENGTH)

    def test_header_block_canonical_offsets(self) -> None:
        """Pin header-block offsets to the ``dr130.09.pdf`` consolidated spec."""
        first = RECORD_SPECS[0]
        assert first.field_id == "MODELO"
        assert first.literal_value == "130"
        assert first.offset == 1
        assert first.length == 3
        by_id = {s.field_id: s for s in RECORD_SPECS}
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
        """Assert every Modelo 130 casilla (01..19) has exactly one record field.

        The Modelo 130 ruleset enumerates 19 casillas; each one must
        map to exactly one entry in :data:`RECORD_SPECS`.
        """
        casilla_ids = {s.casilla_id for s in RECORD_SPECS if s.casilla_id is not None}
        expected = {f"{i:02d}" for i in range(1, 20)}
        assert casilla_ids == expected, (
            f"missing or extra casillas: missing={expected - casilla_ids}, extra={casilla_ids - expected}"
        )

    def test_every_casilla_is_currency_13_bytes(self) -> None:
        """Assert every casilla field is 13-byte CURRENCY (11 int + 2 dec)."""
        for spec in RECORD_SPECS:
            if spec.casilla_id is None:
                continue
            assert spec.kind is FieldKind.CURRENCY, (
                f"casilla {spec.casilla_id!r} field_id={spec.field_id!r} is {spec.kind!r}, expected CURRENCY"
            )
            assert spec.length == 13, f"casilla {spec.casilla_id!r} length={spec.length}, expected 13"

    def test_final_field_reaches_record_end(self) -> None:
        """Assert the trailing field's offset + length saturates :data:`RECORD_LENGTH`."""
        final = RECORD_SPECS[-1]
        assert final.offset + final.length - 1 == RECORD_LENGTH
