from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._verification_chain_support import BindingId, CasillaId, Decimal, _assert_annual_relation_closure_chain

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M123_TOTAL_RENTAS_CASILLA: CasillaId = validated_casilla_id("03")
_M123_TOTAL_BASE_CASILLA: CasillaId = validated_casilla_id("06")
_M123_TOTAL_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("09")
_M193_PERCEPTORES_BINDING: BindingId = "modelo-193-123-perceptores-anual"
_M193_RETIRED_PERCEPTORES_RELATION = "modelo-193-rel-123-perceptores-anual"
_M123_QUARTERLY_VALUES: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M123_TOTAL_RENTAS_CASILLA: Decimal("2"),
        _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
        _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
    },
    "2T": {
        _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
        _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
        _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
    },
    "3T": {
        _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
        _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
        _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
    },
    "4T": {
        _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
        _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
        _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
    },
}


def test_verification_chain_m193_engine_recomputes_closure_casillas_from_m123_relations_and_binding() -> None:
    """Engine recomputes M193 annual closure casillas from M123 relations and binding values.

    FIXTURE, NOT ORACLE: the M193 specimen at
    src/cadrumo/tests/fixtures/justificantes/193/2024-0A.pdf is
    ``provenance = "synthetic_generated"``. Its labels are modelled on the AEAT
    printed form; its AMOUNTS are hand-authored generator literals with no AEAT
    authority. This test proves the M123->M193 chain resolves and closes, not
    that the totals match AEAT.

    The fixture prints:
      decl.total-perceptores = 2      (dedicated annual perceptor binding)
      decl.base-total        = 8000.00 (sum of M123 casilla 06 across 4 quarters)
      decl.retenciones-total = 1520.00 (sum of M123 casilla 09 across 4 quarters)

    Legal grounding: Ley 35/2006 art.25, art.99; RD 439/2007 art.109, art.108,
    art.90, art.101; Orden EHA/3377/2011 art.1; Ley 58/2003 art.93.

    Chain:
      1. Parse the 2024-0A M193 fixture -> extracted closure values.
      2. Build M123 quarterly observations whose monetary sums match the M193 totals.
      3. Resolve relation_values via resolve_relation_values_from_observations.
      4. Supply decl.total-perceptores through modelo-193-123-perceptores-anual.
      5. calculate_registry_snapshot(M193 snapshot, bound inputs, binding_values, relation_values).
      6. Assert perceptor count is bound, and monetary totals are relation-derived.

    NOTE: The relation uses M123 2024-y-siguientes casillas 03, 06, 09 which are
    all computed by the engine (not manual inputs). The observations must supply
    them directly as CasillaObservation (representing engine-computed outputs from
    prior quarterly filing runs), not as engine inputs for the current run.

    Verdict: VERIFIED - the M123->M193 monetary relation chain resolves without
    resurrecting the retired quarterly perceptor-count relation.
    """
    _assert_annual_relation_closure_chain(
        annual_modelo="193",
        source_modelo="123",
        fixture_stem="2024-0A",
        year=2024,
        period="0A",
        source_period_values=_M123_QUARTERLY_VALUES,
        perceptor_binding_id=_M193_PERCEPTORES_BINDING,
        perceptor_binding_value=Decimal("2"),
        retired_perceptor_relation_id=_M193_RETIRED_PERCEPTORES_RELATION,
    )
