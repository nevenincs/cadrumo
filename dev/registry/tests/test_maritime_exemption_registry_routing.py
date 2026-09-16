"""Maritime exemption observations target the casilla the modelo 100 registry routes them to.

The routing is read through :class:`RegistryQueryService`, which consumes the
eager validated authority the development compiler builds from authored source.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.queries import RegistryQueryService
from cadrumo.domain.renta.maritime_exemption import (
    MaritimeWorkerFacts,
    calculate_art_7p_exemption,
    calculate_rebeca_exemption,
)

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _registry_target_for(observation: CasillaObservation) -> str:
    rows = (
        RegistryQueryService(compiled_bundled_authority()).formulas_for_scope("100", filing_year=2025, period="0A").rows
    )
    targets = {
        row.target_casilla_id
        for row in rows
        if set(observation.legal_refs).issubset(row.legal_refs)
        and set(observation.source_refs).issubset(row.source_refs)
    }
    assert len(targets) == 1
    return next(iter(targets))


class TestCalculateArt7pExemption:
    """Art. 7.p) calculation routes to the registry's renta exenta casilla."""

    _BASE_FACTS = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_flag="foreign",
        waters_type="international",
    )

    def test_observation_targets_renta_exenta_casilla(self) -> None:
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=100,
            facts=self._BASE_FACTS,
        )
        assert obs.casilla_id == _registry_target_for(obs)


class TestCalculateRebecaExemption:
    """REBECA 50% calculation routes to the registry's renta exenta casilla."""

    _REBECA_FACTS = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_registry="REBECA",
    )

    def test_observation_targets_renta_exenta_casilla(self) -> None:
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("30000"),
            facts=self._REBECA_FACTS,
        )
        assert obs.casilla_id == _registry_target_for(obs)
