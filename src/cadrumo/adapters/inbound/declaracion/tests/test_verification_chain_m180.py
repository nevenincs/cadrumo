from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._verification_chain_support import BindingId, CasillaId, Decimal, _assert_annual_relation_closure_chain

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M115_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M115_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M180_PERCEPTORES_BINDING: BindingId = "modelo-180-115-perceptores-anual"
_M180_RETIRED_PERCEPTORES_RELATION = "modelo-180-rel-115-perceptores-anual"
_M115_QUARTERLY_VALUES: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
        _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
        _M115_RETENCIONES_CASILLA: Decimal("570.00"),
    },
    "2T": {
        _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
        _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
        _M115_RETENCIONES_CASILLA: Decimal("570.00"),
    },
    "3T": {
        _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
        _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
        _M115_RETENCIONES_CASILLA: Decimal("570.00"),
    },
    "4T": {
        _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("0"),
        _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
        _M115_RETENCIONES_CASILLA: Decimal("570.00"),
    },
}


def test_verification_chain_m180_engine_recomputes_closure_casillas_from_m115_relations_and_binding() -> None:
    """Engine recomputes M180 annual closure casillas from M115 relations and binding values.

    FIXTURE, NOT ORACLE: the M180 specimen at
    src/cadrumo/tests/fixtures/justificantes/180/2024-0A.pdf is
    ``provenance = "synthetic_generated"``. Its LABELS and layout are grounded
    in the AEAT Orden HAP/1732/2014 printed form (that grounding is real and is
    what makes the parse assertions meaningful); its AMOUNTS are hand-authored
    literals in ``tests/fixtures/justificantes/_generate_misc_a.py`` and carry
    no AEAT authority. This test therefore proves the M115->M180 chain resolves
    and closes, not that the totals are what AEAT would compute.

    The fixture prints:
      decl.total-perceptores = 3       (dedicated annual perceptor binding)
      decl.base-total        = 12000.00 (sum of M115 casilla 02 across 4 quarters)
      decl.retenciones-total =  2280.00 (sum of M115 casilla 03 across 4 quarters)

    Legal grounding: Ley 35/2006 art.99; RD 439/2007 arts.100,108,109;
    Orden HAP/1732/2014 art.2; Orden HFP/1284/2023 art.7.

    Chain:
      1. Parse the 2024-0A M180 fixture -> extracted closure values.
      2. Build M115 quarterly observations whose monetary sums match the M180 totals.
      3. Resolve relation_values via resolve_relation_values_from_observations.
      4. Supply decl.total-perceptores through modelo-180-115-perceptores-anual.
      5. calculate_registry_snapshot(M180 snapshot, bound inputs, binding_values, relation_values).
      6. Assert perceptor count is bound, and monetary totals are relation-derived.

    Verdict: VERIFIED - the M115->M180 monetary relation chain resolves without
    resurrecting the retired quarterly perceptor-count relation.
    """
    _assert_annual_relation_closure_chain(
        annual_modelo="180",
        source_modelo="115",
        fixture_stem="2024-0A",
        year=2024,
        period="0A",
        source_period_values=_M115_QUARTERLY_VALUES,
        perceptor_binding_id=_M180_PERCEPTORES_BINDING,
        perceptor_binding_value=Decimal("3"),
        retired_perceptor_relation_id=_M180_RETIRED_PERCEPTORES_RELATION,
    )
