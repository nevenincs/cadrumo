"""Registry contract for operator-supplied local observation errors."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ..action_errors import ModeloLocalObservationError
from ..local_observation_actions import _canonical_casilla_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M200_AMBIGUOUS_PRINTED_NUMBER: CasillaId = validated_casilla_id(
    "00562",
    surface="_M200_AMBIGUOUS_PRINTED_NUMBER",
)
_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)
_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)


def test_local_observation_refuses_ambiguous_printed_number_with_canonical_candidates() -> None:
    snapshot = bundled_authority().snapshot("200", filing_year=2025, period="0A")

    with pytest.raises(ModeloLocalObservationError) as exc_info:
        _canonical_casilla_values(
            revision=snapshot.revision,
            casilla_values={_M200_AMBIGUOUS_PRINTED_NUMBER: Decimal("1")},
        )

    assert exc_info.value.context == {
        "casillas": _M200_AMBIGUOUS_PRINTED_NUMBER,
        "revision_id": snapshot.revision.id,
    }
    assert (
        f"{_M200_AMBIGUOUS_PRINTED_NUMBER!r} is ambiguous; candidate casilla.id values: "
        f"{_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA}, {_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA}"
    ) in str(exc_info.value)
