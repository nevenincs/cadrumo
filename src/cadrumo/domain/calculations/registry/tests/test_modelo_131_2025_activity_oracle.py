"""Independent 2025 Modelo 131 activity-identity prerequisite.

The bundled AEAT Modelo 131 instructions require an IAE epigraph for each
independent activity and describe its rendimiento neto as an annual-base
amount used for the quarterly payment calculation.  The existing M131 oracle
tables independently transcribe the 2025 Orden HAC/1347/2024 coefficients.

This test is deliberately only a source-capability prerequisite.  It keeps
the activity-level values keyed by epigraph and does not synthesize an
aggregate or claim a transfer to M100 casilla 1481.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core import RegistryAuthorityGrade
from ..formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIODS = ("1T", "2T", "3T", "4T")
_ZERO_MODULE_INPUTS = {
    "modulos-1-unidades": Decimal("0"),
    "modulos-2-unidades": Decimal("0"),
    "modulos-3-unidades": Decimal("0"),
    "modulos-4-unidades": Decimal("0"),
    "modulos-5-unidades": Decimal("0"),
    "modulos-6-unidades": Decimal("0"),
    "modulos-7-unidades": Decimal("0"),
    "modulos-1-unidades-anterior": Decimal("0"),
    "modulos-minoracion-inversion": Decimal("0"),
    "modulos-indice-pequena-dimension": Decimal("0"),
    "modulos-indice-temporada": Decimal("0"),
    "modulos-indice-inicio-actividad": Decimal("0"),
}
_ZERO_PRIOR_NEGATIVE_BINDING = {"modelo-131-2025-resultados-negativos-anteriores": Decimal("0")}
_ACTIVITY_CASES = {
    "972.1": (
        {
            "modulos-1-unidades": Decimal("2"),
            "modulos-2-unidades": Decimal("1"),
            "modulos-3-unidades": Decimal("50"),
            "modulos-4-unidades": Decimal("30"),
        },
        Decimal("22473.79"),
    ),
    "721.2": (
        {"modulos-2-unidades": Decimal("1"), "modulos-3-unidades": Decimal("40")},
        Decimal("8987.09"),
    ),
}


def _calculate_activity_value(period: str, epigrafe: str, module_inputs: dict[str, Decimal]) -> Decimal:
    snapshot = _committed_snapshot("131", 2025, period, grade=RegistryAuthorityGrade.CALCULATION)
    assert snapshot.filing_period is not None
    result = calculate_registry_snapshot(
        snapshot,
        inputs={**_ZERO_MODULE_INPUTS, **module_inputs},
        binding_values=_ZERO_PRIOR_NEGATIVE_BINDING,
        text_inputs={"modulos-epigrafe": epigrafe},
        date_context={"filing_period": snapshot.filing_period.end_date},
    )
    return result.values["modulos-rendimiento-neto-actividad"]


def test_2025_activity_identity_preserves_annual_base_across_quarters() -> None:
    """Each independent activity keeps its own annual-base result in 1T-4T."""
    observed = {
        period: {
            epigrafe: _calculate_activity_value(period, epigrafe, module_inputs)
            for epigrafe, (module_inputs, _expected_value) in _ACTIVITY_CASES.items()
        }
        for period in _PERIODS
    }
    expected = {
        period: {epigrafe: expected_value for epigrafe, (_inputs, expected_value) in _ACTIVITY_CASES.items()}
        for period in _PERIODS
    }

    assert observed == expected
    assert set(observed["1T"]) == set(_ACTIVITY_CASES)
    assert observed["1T"]["972.1"] != observed["1T"]["721.2"]
