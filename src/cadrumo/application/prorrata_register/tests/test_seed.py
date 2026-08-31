"""Carried-prior-definitive seed coverage over real filed observations.

See Also:
    :func:`~application.prorrata_register._seed.evaluate_carried_prior_definitiva_seed`
        Seed evaluator under test for happy-path and divergent-revision outcomes.
    :class:`~application.calculations.CalculationObservationRepository`
        Real encrypted observation repository that stores the prior Modelo 303
        settlement observation.
    :class:`~application.calculations.CrossPeriodCleanStateBlocker`
        Blocking vocabulary asserted for registry-revision divergence findings.
    :func:`~tests.registry_observations.registry_grounded_modelo_observation`
        Test helper that builds registry-grounded Modelo 303 observation
        payloads instead of mirroring calculation logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.prorrata_register import ProrrataProvisionalProvenance
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations.cross_period_clean_state import CrossPeriodCleanStateBlocker
from ...calculations.observations_repository import CalculationObservationRepository
from ..seed import evaluate_carried_prior_definitiva_seed

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_KIND = "aeat_sede_justificante"
_CLOCK = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CURRENT_YEAR = 2026
_PRIOR_YEAR = 2025
_SETTLEMENT_PERIOD = "4T"
_DIVERGENT_REVISION_ID = "not-the-law-determined-m303-2025-4t-revision"

_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")


def _prior_revision_id(*, filing_year: int = _PRIOR_YEAR, period: str = _SETTLEMENT_PERIOD) -> str:
    snapshot = bundled_authority().snapshot(Modelo.M303.value, filing_year=filing_year, period=period)
    return str(snapshot.revision.id)


def _save_prior_prorrata_observation(
    repo: CalculationObservationRepository,
    *,
    percentage: Decimal,
    stamped_revision_id: str,
) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=Modelo.M303.value,
        filing_year=_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
        casilla_values={_PORCENTAJE_ID: percentage},
    )
    repo.save(
        repo.prepare_observation_envelope(
            observation,
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=stamped_revision_id,
        )
    )


def test_seed_happy_path_uses_prior_settlement_observation(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_prior_prorrata_observation(repo, percentage=Decimal("87"), stamped_revision_id=_prior_revision_id())

        evaluation = evaluate_carried_prior_definitiva_seed(
            ejercicio=_CURRENT_YEAR,
            observation_repository=repo,
        )

    assert not evaluation.blocked
    assert evaluation.findings == ()
    seed = evaluation.seed
    assert seed is not None
    assert seed.source_modelo == Modelo.M303.value
    assert seed.source_filing_year == _PRIOR_YEAR
    assert seed.source_period == _SETTLEMENT_PERIOD
    assert seed.source_casilla_id == _PORCENTAJE_ID
    assert seed.stamped_revision_id == _prior_revision_id()
    assert seed.entry.ejercicio == _CURRENT_YEAR
    assert seed.entry.provisional_percentage == Decimal("87")
    assert seed.entry.provisional_provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    assert seed.entry.source_observation_ref == "303:2025:4T"


def test_seed_divergent_revision_stamp_blocks(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_prior_prorrata_observation(
            repo,
            percentage=Decimal("91"),
            stamped_revision_id=_DIVERGENT_REVISION_ID,
        )

        evaluation = evaluate_carried_prior_definitiva_seed(
            ejercicio=_CURRENT_YEAR,
            observation_repository=repo,
        )

    assert evaluation.seed is None
    assert evaluation.blocked
    assert len(evaluation.findings) == 1
    finding = evaluation.findings[0]
    assert finding.code == CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE.value
    assert finding.blocking
    assert not finding.advisory
    assert finding.source_modelo == Modelo.M303.value
    assert finding.source_filing_year == _PRIOR_YEAR
    assert finding.source_period == _SETTLEMENT_PERIOD
    assert finding.stamped_revision_id == _DIVERGENT_REVISION_ID
    assert finding.selected_revision_id == _prior_revision_id()
