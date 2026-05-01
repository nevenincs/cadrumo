"""DP30301 recargo-de-equivalencia rate-rows layout lock.

Complements 's régimen-general rate-row lock with the
recargo-de-equivalencia rows — the second-order surcharge rates
(1.40 %, 5.20 %, 1.75 %) applied when Kent's counterparty is in
the recargo regime.

Canonical rate-row offsets per DR303e24 (the recargo-equivalencia
block starts at offset 427 after the casillas 10-15 rectification
block):

  recargo 5% (alimentos temporal):
    CAS156 base @ 427, CAS157 tipo="00175" @ 444, CAS158 cuota @ 449
  recargo 10%:
    CAS20 tipo="00140" @ 522, CAS21 base @ 527, CAS22 cuota @ 544
  recargo 21%:
    CAS23 tipo="00520" @ 561, CAS24 base @ 566, CAS25 cuota @ 583

Note: casilla 17 (offset 483, 5 bytes, RESERVED literal "00000")
appears in the rate-column position but carries a zero-percent
literal. The exact semantics require DR303 cross-reference;
the observed layout but doesn't claim to know
what "00000" means — future contributors should consult the
xlsx source before changing it.
"""

from __future__ import annotations

import pytest

from ._record_spec import FieldKind, RecordFieldSpec
from .modelo_303_2024 import ENVELOPE

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _dp30301_by_casilla() -> dict[str, RecordFieldSpec]:
    for seg in ENVELOPE:
        if seg.segment_id == "DP30301":
            return {s.casilla_id: s for s in seg.specs if s.casilla_id is not None}
    raise AssertionError("DP30301 missing from envelope")


class TestRecargoEquivalenciaRates:
    def test_recargo_5_pct_rate_literal(self) -> None:
        """Recargo 5%: tipo CAS157 = "00175" (1.75%) at offset 444."""
        casillas = _dp30301_by_casilla()
        tipo = casillas["157"]
        assert tipo.offset == 444
        assert tipo.length == 5
        assert tipo.kind is FieldKind.RESERVED
        assert tipo.literal_value == "00175"

    def test_recargo_10_pct_rate_literal(self) -> None:
        """Recargo 10%: tipo CAS20 = "00140" (1.40%) at offset 522."""
        casillas = _dp30301_by_casilla()
        tipo = casillas["20"]
        assert tipo.offset == 522
        assert tipo.length == 5
        assert tipo.kind is FieldKind.RESERVED
        assert tipo.literal_value == "00140"

    def test_recargo_21_pct_rate_literal(self) -> None:
        """Recargo 21%: tipo CAS23 = "00520" (5.20%) at offset 561."""
        casillas = _dp30301_by_casilla()
        tipo = casillas["23"]
        assert tipo.offset == 561
        assert tipo.length == 5
        assert tipo.kind is FieldKind.RESERVED
        assert tipo.literal_value == "00520"


class TestRecargo5PctRow:
    """Recargo 5% row is the full 39-byte block CAS156 / CAS157 / CAS158."""

    def test_base_at_offset_427(self) -> None:
        casillas = _dp30301_by_casilla()
        base = casillas["156"]
        assert base.offset == 427
        assert base.length == 17
        assert base.kind is FieldKind.CURRENCY

    def test_cuota_at_offset_449(self) -> None:
        casillas = _dp30301_by_casilla()
        cuota = casillas["158"]
        assert cuota.offset == 449  # = 427 + 17 + 5
        assert cuota.length == 17
        assert cuota.kind is FieldKind.CURRENCY


class TestRecargo10PctAnd21PctRows:
    """Recargo 10% and 21% rows use a {tipo / base / cuota} layout where the
    tipo literal precedes the base (different from the 5% row's layout)."""

    def test_recargo_10_base_at_offset_527(self) -> None:
        casillas = _dp30301_by_casilla()
        base = casillas["21"]
        assert base.offset == 527  # = 522 + 5
        assert base.length == 17
        assert base.kind is FieldKind.CURRENCY

    def test_recargo_10_cuota_at_offset_544(self) -> None:
        casillas = _dp30301_by_casilla()
        cuota = casillas["22"]
        assert cuota.offset == 544  # = 527 + 17
        assert cuota.length == 17

    def test_recargo_21_base_at_offset_566(self) -> None:
        casillas = _dp30301_by_casilla()
        base = casillas["24"]
        assert base.offset == 566  # = 561 + 5
        assert base.length == 17

    def test_recargo_21_cuota_at_offset_583(self) -> None:
        casillas = _dp30301_by_casilla()
        cuota = casillas["25"]
        assert cuota.offset == 583  # = 566 + 17
        assert cuota.length == 17


class TestSuspiciousZeroRateLiteral:
    """Casilla 17 carries a RESERVED literal "00000" at offset 483 — 5 bytes
    in the rate-column position but with a zero-percent value.
    documents this as observed behaviour; it's not clear from the fixture
    alone whether this is "tipo exento" or an xlsx-extraction artefact.
    Future contributors should resolve with the DR303 PDF before changing.
    """

    def test_casilla_17_is_reserved_zero_literal(self) -> None:
        casillas = _dp30301_by_casilla()
        cas17 = casillas["17"]
        assert cas17.offset == 483
        assert cas17.length == 5
        assert cas17.kind is FieldKind.RESERVED
        assert cas17.literal_value == "00000", (
            "Casilla 17 was expected to carry the '00000' literal per the "
            "observation. If this changed, cross-reference the DR303 "
            "PDF and update _EXPECTED_GAPS + this test together."
        )
