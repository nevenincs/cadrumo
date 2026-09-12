"""Operator-manual M303 observations stay outside canonical carry evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...calculations.observations_repository import CalculationObservationRepository
from ..action_errors import ModeloLocalObservationError
from ..local_observation_actions import record_operator_local_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
_FILING_YEAR = 2025


def test_operator_manual_m303_carry_policy_refuses_without_persisting(
    tmp_path: Path,
) -> None:
    """M303 has one canonical filing write door; operator-manual rows are refused."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        period = Period.from_year_and_code(_FILING_YEAR, "1T")
        with pytest.raises(ModeloLocalObservationError, match="require canonical filed or official evidence"):
            record_operator_local_observation(
                modelo=Modelo.M303.value,
                filing_year=_FILING_YEAR,
                period=period,
                casilla_values={"iva.cuota-devengada-total": Decimal("10")},
                repository=repository,
                clock=_CAPTURED_AT,
            )

        assert repository.load_observation(Modelo.M303.value, period) is None
