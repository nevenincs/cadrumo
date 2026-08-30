"""Operator-manual M303 observations stay outside canonical carry evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import (
    CalculationObservationRepository,
    M303CarryIngressError,
    resolve_relations_from_local_store,
    validate_normalized_m303_carry_observation_envelope,
)
from .._local_observation_actions import record_operator_local_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
_FILING_YEAR = 2025
_UNRELATED_ANNUAL_RELATION = "modelo-390-rel-303-cuota-devengada-total"


def test_operator_manual_m303_is_not_carry_evidence_but_remains_available_to_unrelated_prefill(
    tmp_path: Path,
) -> None:
    """The deliberate non-normalizing policy blocks carry without suppressing ordinary prefill."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        for quarter, value in zip(
            ("1T", "2T", "3T", "4T"),
            (Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")),
            strict=True,
        ):
            period = Period.from_year_and_code(_FILING_YEAR, quarter)
            record_operator_local_observation(
                modelo=Modelo.M303.value,
                filing_year=_FILING_YEAR,
                period=period,
                casilla_values={"iva.cuota-devengada-total": value},
                repository=repository,
                clock=_CAPTURED_AT,
            )

        first_quarter = repository.load_observation(
            Modelo.M303.value,
            Period.from_year_and_code(_FILING_YEAR, "1T"),
        )
        assert first_quarter is not None
        assert first_quarter.result_disposition is None
        assert first_quarter.m303_compensation_basis is None
        with pytest.raises(
            M303CarryIngressError,
            match="accepts only official AEAT or app_filing provenance",
        ):
            validate_normalized_m303_carry_observation_envelope(first_quarter)

        annual_snapshot = bundled_authority().snapshot(
            Modelo.M390.value,
            filing_year=_FILING_YEAR,
            period="0A",
        )
        relation_prefill = resolve_relations_from_local_store(
            annual_snapshot,
            repository=repository,
            captured_at=_CAPTURED_AT,
        )
        unrelated = next(item for item in relation_prefill.values if item.relation == _UNRELATED_ANNUAL_RELATION)
        assert unrelated.value is not None
        assert unrelated.provenance == "local_filing"
