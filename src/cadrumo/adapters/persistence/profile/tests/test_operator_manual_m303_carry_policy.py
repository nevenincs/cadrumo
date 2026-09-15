"""Operator-manual M303 observations stay outside canonical carry evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import ModeloLocalObservationError
from cadrumo.application.modelo.local_observation_actions import record_operator_local_observation
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
_FILING_YEAR = 2025


def test_operator_manual_m303_carry_policy_refuses_without_persisting(
    tmp_path: Path,
) -> None:
    """M303 has one canonical filing write door; operator-manual rows are refused."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test, isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        period = Period.from_year_and_code(_FILING_YEAR, "1T")
        with pytest.raises(ModeloLocalObservationError, match="require canonical filed or official evidence"):
            record_operator_local_observation(
                modelo=Modelo("303").value,
                filing_year=_FILING_YEAR,
                period=period,
                casilla_values={"iva.cuota-devengada-total": Decimal("10")},
                repository=repository,
                clock=_CAPTURED_AT,
                operation=_authority_operation_for_test,
            )

        assert repository.load_observation(Modelo("303").value, period) is None
