"""Regression guard: actividad-economica positive rendimiento
must yield a NON-negative base imponible general.

A positive actividad-economica income input previously produced a
NEGATIVE base imponible (a sign/routing defect). Note that in the 2024 M100
revision casilla 0006 is *trabajo en especie*, not actividad economica
(casilla ids renumber across filing years). The current
actividad-economica estimacion-directa chain is:

    0171 (ingresos de explotacion, ledger income)
      -> 0180 (ingresos computables, sum)
      -> 0224 (rendimiento neto = ingresos 0180 - gastos 0220)
      -> 0226 (rendimiento neto reducido)
      -> 0231 -> 0235 (rendimiento neto reducido total)
      -> 0432 (saldo neto rendimientos, sum incl. 0235)
      -> 0435 (base imponible general = 0432 - 0433).

For a positive income with smaller deductible expenses every node in that chain
is strictly positive, so the base imponible general (0435) must be positive.
This test drives real persisted ledger income + expenses through the live
bucket-aggregation calculate action and asserts the *sign* of the base
imponible — a structural invariant, not a re-computation of any registry
formula (the harness never hand-derives a registry expression). It fails loudly
if a future edit re-introduces the sign/routing inversion this test guards.

Real-behaviour, real-adapter: real encrypted-SQLite secure store, the real
registry authority, the real calculation engine, and the real ledger income /
expense aggregation resolvers. No mocks, stubs, skips, or xfail.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....tests.secure_sql import isolated_runtime_profile
from .test_e2e_ledger_m130_quarters_to_m100_annual import (
    _BUCKET_ID,
    _EXPECTED_M100_ACTIVITY_NET,
    _calculate_m100_annual,
    _persist_autonoma_style_ledger,
    _seed_prior_year_m100,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Chain nodes from actividad-economica income through to the base imponible
# general. Each must be non-negative for a positive-income / smaller-expense
# persona; the base imponible (0435) is the node that was previously inverted.
_ACTIVIDAD_ECONOMICA_INGRESOS = "0171"
_RENDIMIENTO_NETO = "0224"
_RENDIMIENTO_NETO_REDUCIDO_TOTAL = "0235"
_SALDO_NETO_RENDIMIENTOS = "0432"
_BASE_IMPONIBLE_GENERAL = "0435"


def test_positive_actividad_economica_income_yields_non_negative_base_imponible(
    tmp_path: Path,
) -> None:
    """A positive actividad-economica rendimiento must not invert into a
    negative base imponible general."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        secure_objects: SecureObjectRepository = profile.repository
        _persist_autonoma_style_ledger(secure_objects)
        _seed_prior_year_m100(secure_objects)

        annual = _calculate_m100_annual(secure_objects)
        casilla_values = annual.casilla_values

        # The rendimiento neto is the positive activity result the ledger drives.
        rendimiento_neto = Decimal(casilla_values[_RENDIMIENTO_NETO])
        assert rendimiento_neto == _EXPECTED_M100_ACTIVITY_NET, (
            f"actividad-economica rendimiento neto (0224) must be the positive net "
            f"{_EXPECTED_M100_ACTIVITY_NET}; got {rendimiento_neto}"
        )

        # Sign invariant: every node from income to base imponible general
        # stays non-negative when income exceeds deductible expenses.
        for casilla in (
            _ACTIVIDAD_ECONOMICA_INGRESOS,
            _RENDIMIENTO_NETO,
            _RENDIMIENTO_NETO_REDUCIDO_TOTAL,
            _SALDO_NETO_RENDIMIENTOS,
            _BASE_IMPONIBLE_GENERAL,
        ):
            value = Decimal(casilla_values[casilla])
            assert value >= Decimal("0"), (
                f"casilla {casilla} inverted to a negative value ({value}) on positive "
                f"actividad-economica income — the sign/routing defect has regressed"
            )

        # The base imponible general carries the positive activity net through
        # (no other income/reduction in this pure actividad-economica persona).
        base_imponible = Decimal(casilla_values[_BASE_IMPONIBLE_GENERAL])
        assert base_imponible == _EXPECTED_M100_ACTIVITY_NET, (
            f"base imponible general (0435) must carry the positive activity net "
            f"{_EXPECTED_M100_ACTIVITY_NET}; got {base_imponible}"
        )
