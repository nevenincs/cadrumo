"""DP30301 régimen-general rate-rows layout lock.

The 4 % / 5 % / 10 % / 21 % IVA rate rows in DP30301 are 39-byte
blocks: a 17-byte base-imponible CURRENCY, a 5-byte rate literal
(RESERVED, the tipo impositivo), and a 17-byte cuota CURRENCY. A
fixture extension that inserts a new rate row (some future
hypothetical extra reduced rate, for example) must preserve the byte
positions of the existing rows — otherwise every downstream
byte-offset assertion shifts silently.

Canonical rate-row offsets per ``DR303e24``::

    4%  : CAS01 base  @ 169,  CAS02 tipo @ 186 (5B RESERVED), CAS03 cuota @ 191
    5%  : CAS153 base @ 208,  CAS154 tipo @ 225 (5B RESERVED), CAS155 cuota @ 230
    10% : CAS04 base  @ 247,  CAS05 tipo @ 264 (5B RESERVED), CAS06 cuota @ 269
    21% : CAS07 base  @ 286,  CAS08 tipo @ 303 (5B RESERVED), CAS09 cuota @ 308

The tests lock all four row layouts and their rate-literal values.
"""

from __future__ import annotations

import pytest

from ._record_spec import FieldKind, RecordFieldSpec
from .modelo_303_2024 import ENVELOPE

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _dp30301_specs() -> tuple[RecordFieldSpec, ...]:
    for seg in ENVELOPE:
        if seg.segment_id == "DP30301":
            return seg.specs
    raise AssertionError("DP30301 missing")


def _by_casilla() -> dict[str, RecordFieldSpec]:
    return {s.casilla_id: s for s in _dp30301_specs() if s.casilla_id is not None}


#: Each row = (rate_label, base_casilla, tipo_casilla, tipo_literal, cuota_casilla, row_start_offset).
_RATE_ROWS: list[tuple[str, str, str, str, str, int]] = [
    ("4%", "01", "02", "00400", "03", 169),
    ("5%", "153", "154", "00500", "155", 208),
    ("10%", "04", "05", "01000", "06", 247),
    ("21%", "07", "08", "02100", "09", 286),
]


class TestRegimenGeneralRateRows:
    """Per-row layout assertions for the 4 / 5 / 10 / 21 % rate rows."""

    @pytest.mark.parametrize(
        ("label", "base", "tipo", "tipo_literal", "cuota", "row_start"),
        _RATE_ROWS,
        ids=[r[0] for r in _RATE_ROWS],
    )
    def test_rate_row_layout(
        self,
        label: str,
        base: str,
        tipo: str,
        tipo_literal: str,
        cuota: str,
        row_start: int,
    ) -> None:
        """Each rate row occupies exactly 39 bytes: 17-byte base CURRENCY,
        5-byte tipo RESERVED literal, 17-byte cuota CURRENCY."""
        casillas = _by_casilla()

        base_spec = casillas[base]
        assert base_spec.offset == row_start, (
            f"{label} base casilla {base} at offset {base_spec.offset}; expected {row_start}."
        )
        assert base_spec.kind is FieldKind.CURRENCY
        assert base_spec.length == 17

        tipo_spec = casillas[tipo]
        assert tipo_spec.offset == row_start + 17
        assert tipo_spec.kind is FieldKind.RESERVED
        assert tipo_spec.length == 5
        assert tipo_spec.literal_value == tipo_literal, (
            f"{label} tipo casilla {tipo} literal {tipo_spec.literal_value!r}; expected {tipo_literal!r}."
        )

        cuota_spec = casillas[cuota]
        assert cuota_spec.offset == row_start + 22
        assert cuota_spec.kind is FieldKind.CURRENCY
        assert cuota_spec.length == 17


class TestRateRowsAreContiguous:
    """The four rate rows must be byte-contiguous, with no padding between them."""

    def test_5_percent_row_immediately_follows_4_percent(self) -> None:
        """The 5% row (alimentos temporal) starts at offset 208 —
        exactly the byte after the 4% row ends (169 + 39 = 208)."""
        casillas = _by_casilla()
        assert casillas["153"].offset == 169 + 39

    def test_10_percent_row_starts_after_5_percent(self) -> None:
        """10% row @ 247 = 208 + 39."""
        casillas = _by_casilla()
        assert casillas["04"].offset == 208 + 39

    def test_21_percent_row_starts_after_10_percent(self) -> None:
        """21% row @ 286 = 247 + 39."""
        casillas = _by_casilla()
        assert casillas["07"].offset == 247 + 39

    def test_21_percent_row_ends_before_casilla_10(self) -> None:
        """After the 21% row (286 + 39 = 325), casilla 10 begins.
        Locks that no new rate row gets inserted between 21% and
        casilla 10 without explicitly updating this test."""
        casillas = _by_casilla()
        assert casillas["10"].offset == 286 + 39
