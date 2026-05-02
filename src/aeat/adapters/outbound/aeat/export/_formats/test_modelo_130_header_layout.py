"""Modelo 130 2024 record header-field layout lock.

Pins intra-segment offsets for the hand-authored Modelo 130 record.
The header block (positions 1-76 of 878) carries the filing
identification: ``MODELO``, ``PAGINA``, ``TIPO_DECLARACION``,
``NIF_DECLARANTE``, ``APELLIDOS``, ``NOMBRE``, ``EJERCICIO``,
``PERIODO``. Every byte-offset assertion in the golden SHA suite,
the export byte tests, and the 2024/2025 end-to-end integration
suites depends on these offsets staying stable.

Earlier authoring iterations placed ``TIPO_DECLARACION`` at offset
79, ``NIF_DECLARANTE`` at 10, ``EJERCICIO`` at 4, and ``PERIODO``
at 8 — all wrong per ``dr130.09.pdf``. This module's tests pin the
corrected layout against any future regression.
"""

from __future__ import annotations

import pytest

from .modelo_130_2024 import RECORD_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


#: Canonical 130-header layout per dr130.09.pdf + DR130e15v12.xls.
#: (field_id, 1-based offset, length, kind_name).
_EXPECTED_130_HEADER: list[tuple[str, int, int, str]] = [
    ("MODELO", 1, 3, "RESERVED"),
    ("PAGINA", 4, 2, "RESERVED"),
    ("IND_COMPLEMENTARIA", 6, 1, "ALPHANUMERIC"),
    ("TIPO_DECLARACION", 7, 1, "ALPHANUMERIC"),
    ("COD_ADMINISTRACION", 8, 5, "NUMERIC"),
    ("NIF_DECLARANTE", 13, 9, "ALPHANUMERIC"),
    ("COMIENZO_APELLIDO", 22, 4, "ALPHANUMERIC"),
    ("APELLIDOS", 26, 30, "ALPHANUMERIC"),
    ("NOMBRE", 56, 15, "ALPHANUMERIC"),
    ("EJERCICIO", 71, 4, "NUMERIC"),
    ("PERIODO", 75, 2, "ALPHANUMERIC"),
]


class TestModelo130HeaderLayout:
    """Per-field structural locks for the Modelo 130 header block."""

    def test_header_fields_match_canonical_layout(self) -> None:
        """Assert every expected header field exists at the canonical offset/length/kind."""
        by_field_id = {s.field_id: s for s in RECORD_SPECS}
        for expected_field, expected_offset, expected_length, expected_kind in _EXPECTED_130_HEADER:
            assert expected_field in by_field_id, (
                f"Modelo 130 missing field {expected_field!r}. Hand-authored schema drift — "
                f"miscite risk; consult dr130.09.pdf before re-pinning."
            )
            spec = by_field_id[expected_field]
            assert spec.offset == expected_offset, (
                f"Modelo 130 field {expected_field!r} at offset {spec.offset}; expected "
                f"{expected_offset} per dr130.09.pdf."
            )
            assert spec.length == expected_length, (
                f"Modelo 130 field {expected_field!r} length {spec.length}; expected {expected_length}."
            )
            assert spec.kind.name == expected_kind, (
                f"Modelo 130 field {expected_field!r} kind {spec.kind.name}; expected {expected_kind}."
            )

    def test_tipo_declaracion_at_offset_7(self) -> None:
        """Lock ``TIPO_DECLARACION`` at offset 7 per ``dr130.09.pdf``.

        An earlier miscite placed the field at offset 79; reinstating
        that bug would shift the tipo flag into the filler zone.
        """
        by_field_id = {s.field_id: s for s in RECORD_SPECS}
        tipo = by_field_id["TIPO_DECLARACION"]
        assert tipo.offset == 7, (
            f"TIPO_DECLARACION at offset {tipo.offset}; expected 7 per dr130.09.pdf. "
            "A miscite would shift the tipo flag into the filler zone."
        )
        assert tipo.length == 1

    def test_nif_at_offset_13(self) -> None:
        """Lock ``NIF_DECLARANTE`` at offset 13 (corrected from an earlier 10)."""
        by_field_id = {s.field_id: s for s in RECORD_SPECS}
        nif = by_field_id["NIF_DECLARANTE"]
        assert nif.offset == 13
        assert nif.length == 9

    def test_ejercicio_at_offset_71(self) -> None:
        """Lock ``EJERCICIO`` at offset 71 (corrected from an earlier 4)."""
        by_field_id = {s.field_id: s for s in RECORD_SPECS}
        ejercicio = by_field_id["EJERCICIO"]
        assert ejercicio.offset == 71
        assert ejercicio.length == 4

    def test_periodo_at_offset_75(self) -> None:
        """Lock ``PERIODO`` at offset 75 (corrected from an earlier 8)."""
        by_field_id = {s.field_id: s for s in RECORD_SPECS}
        periodo = by_field_id["PERIODO"]
        assert periodo.offset == 75
        assert periodo.length == 2

    def test_apellidos_and_nombre_slots(self) -> None:
        """Lock the name block: ``APELLIDOS`` 30 bytes @26, ``NOMBRE`` 15 bytes @56.

        The 30+15=45 byte name block ends at offset 70 (inclusive);
        ``EJERCICIO`` must therefore begin at offset 71.
        """
        by_field_id = {s.field_id: s for s in RECORD_SPECS}
        assert by_field_id["APELLIDOS"].offset == 26
        assert by_field_id["APELLIDOS"].length == 30
        assert by_field_id["NOMBRE"].offset == 56
        assert by_field_id["NOMBRE"].length == 15
        assert by_field_id["EJERCICIO"].offset == 71

    def test_header_block_fits_in_first_76_bytes(self) -> None:
        """Assert the header occupies positions 1-76, so ``INGRESOS_COMPUTABLES`` lands at 77.

        The first data casilla (``INGRESOS_COMPUTABLES`` / casilla 01)
        must immediately follow the header block.
        """
        by_field_id = {s.field_id: s for s in RECORD_SPECS}
        assert by_field_id["INGRESOS_COMPUTABLES"].offset == 77
