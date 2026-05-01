"""DP30301 intra-segment header-field layout lock (wave 143).

The DP30301 page carries Kent's filing-identification block:
TIPO_DECLARACION, NIF, APELLIDOS_Y_NOMBRE, DEVENGO_EJERCICIO,
DEVENGO_PERIODO. Their exact offsets within DP30301 are Kent-
observable — the wave-92 CLI verify test, the wave-93 golden
SHA, and the wave-135 payload-length pre-flight all depend on
these offsets being byte-stable.

Wave 142 locked inter-segment positions in the envelope; wave
143 complements that by locking intra-segment positions in the
Kent-critical DP30301 page. A fixture regeneration that shifts
any of these fields (say, inserting a new RESERVED padding slot
before TIPO_DECLARACION) would break every downstream Kent-
byte-offset assertion at once — now it breaks here first, with
a targeted message.
"""

from __future__ import annotations

import pytest

from ._record_spec import SegmentSpec
from .modelo_303_2024 import ENVELOPE

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _dp30301() -> SegmentSpec:
    for seg in ENVELOPE:
        if seg.segment_id == "DP30301":
            return seg
    raise AssertionError("DP30301 segment missing from envelope")


#: Canonical per-field layout at the DP30301 header block.
#: (field_id, 1-based offset within DP30301, length).
_EXPECTED_DP30301_HEADER: list[tuple[str, int, int]] = [
    ("DP30301_F001_INICIO_DEL_IDENTIFICADOR_DE", 1, 2),
    ("DP30301_F002_MODELO", 3, 3),
    ("DP30301_F003_P_GINA", 6, 5),
    ("DP30301_F004_FIN_DE_IDENTIFICADOR_DE_MODE", 11, 1),
    ("DP30301_F005_INDICADOR_DE_P_GINA_COMPLEME", 12, 1),
    ("DP30301_F006_TIPO_DECLARACI_N", 13, 1),
    ("DP30301_F007_IDENTIFICACI_N_NIF", 14, 9),
    ("DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N", 23, 80),
    ("DP30301_F009_DEVENGO_EJERCICIO", 103, 4),
    ("DP30301_F010_DEVENGO_PER_ODO", 107, 2),
]


class TestDp30301HeaderLayout:
    def test_header_fields_match_canonical_layout(self) -> None:
        segment = _dp30301()
        # type: ignore[attr-defined] — duck-typed for mypy; real type is SegmentSpec.
        specs_by_field_id = {s.field_id: s for s in segment.specs}
        for expected_field, expected_offset, expected_length in _EXPECTED_DP30301_HEADER:
            assert expected_field in specs_by_field_id, (
                f"DP30301 missing expected field {expected_field!r}. Fixture regeneration "
                "may have renamed the field; update the canonical layout and explain why."
            )
            spec = specs_by_field_id[expected_field]
            assert spec.offset == expected_offset, (
                f"DP30301 field {expected_field!r} at offset {spec.offset}; expected {expected_offset}. "
                "Upstream padding / field reorder / extension detected."
            )
            assert spec.length == expected_length, (
                f"DP30301 field {expected_field!r} has length {spec.length}; expected {expected_length}."
            )

    def test_apellidos_y_nombre_starts_at_offset_23(self) -> None:
        """Kent's APELLIDOS_Y_NOMBRE slot must begin at DP30301 offset 23 (1-based,
        immediately after the 9-byte NIF). The 80-byte slot ends at offset 102
        inclusive; the DEVENGO_EJERCICIO that follows must begin at offset 103."""
        segment = _dp30301()
        by_field_id = {s.field_id: s for s in segment.specs}
        a_y_n = by_field_id["DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N"]
        assert a_y_n.offset == 23
        assert a_y_n.length == 80
        # Immediate successor must start at 103 = 23 + 80.
        devengo = by_field_id["DP30301_F009_DEVENGO_EJERCICIO"]
        assert devengo.offset == 103

    def test_nif_slot_is_9_bytes_at_offset_14(self) -> None:
        """The NIF slot is exactly 9 bytes wide (matching the 9-char AEAT NIF/NIE/CIF
        canonical format) and starts immediately after the 1-byte TIPO_DECLARACION.
        This is the specific offset used by the wave-92 CLI export test's byte assertion."""
        segment = _dp30301()
        by_field_id = {s.field_id: s for s in segment.specs}
        nif = by_field_id["DP30301_F007_IDENTIFICACI_N_NIF"]
        assert nif.offset == 14
        assert nif.length == 9

    def test_periodo_is_2_bytes_at_offset_107(self) -> None:
        """DP30301 PERIODO is 2 bytes at offset 107 (1-based); wave-91 reclassified
        this from RESERVED literal '01' to ALPHANUMERIC user-supplied. The offset
        stays stable so the wave-92 CLI export byte assertion continues to work."""
        segment = _dp30301()
        by_field_id = {s.field_id: s for s in segment.specs}
        periodo = by_field_id["DP30301_F010_DEVENGO_PER_ODO"]
        assert periodo.offset == 107
        assert periodo.length == 2
