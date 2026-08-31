"""Override precedence and prior-observation cross-check tests.

See Also:
    :class:`~application.prorrata_register.ProrrataRegisterService`
        Application facade whose persisted-plus-transient resolver path proves
        authorised and inicio candidates outrank the carried prior definitive.
    :func:`~application.prorrata_register._seed.cross_check_prorrata_entry_against_prior_observation`
        Prior-observation guard under test for blocking carried contradictions
        and advisory regulated override differences.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Register row type used to build carried, authorised, and inicio
        candidate entries with provenance.
    :class:`~application.calculations.CalculationObservationRepository`
        Encrypted observation catalogue populated with the prior Modelo 303
        settlement percentage used by the cross-checks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.prorrata_register.register import ProrrataRegisterEntry
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations.cross_period_clean_state import CrossPeriodCleanStateBlocker
from ...calculations.observations_repository import CalculationObservationRepository
from .._seed import cross_check_prorrata_entry_against_prior_observation
from .._service import ProrrataRegisterService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_KIND = "aeat_sede_justificante"
_CLOCK = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CURRENT_YEAR = 2026
_PRIOR_YEAR = 2025
_SETTLEMENT_PERIOD = "4T"
_SOURCE_REF = "303:2025:4T"

_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")


def _prior_revision_id() -> str:
    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    return str(snapshot.revision.id)


def _save_prior_prorrata_observation(repo: CalculationObservationRepository, *, percentage: Decimal) -> None:
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
            stamped_revision_id=_prior_revision_id(),
        )
    )


def _carried_entry(*, percentage: Decimal) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=_CURRENT_YEAR,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=percentage,
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref=_SOURCE_REF,
    )


def _override_entry(
    *,
    provenance: ProrrataProvisionalProvenance,
    percentage: Decimal,
    reference: str,
) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=_CURRENT_YEAR,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=percentage,
        provisional_provenance=provenance,
        authorisation_reference=reference,
    )


@pytest.mark.parametrize(
    ("candidate", "expected_percentage", "expected_provenance"),
    (
        (
            _override_entry(
                provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
                percentage=Decimal("63"),
                reference="AEAT-AUTH-2026-0009",
            ),
            Decimal("63"),
            ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        ),
        (
            _override_entry(
                provenance=ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
                percentage=Decimal("55"),
                reference="INICIO-036-2026-0005",
            ),
            Decimal("55"),
            ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
        ),
    ),
)
def test_override_precedence_outranks_carried_prior_definitiva(
    tmp_path: Path,
    candidate: ProrrataRegisterEntry,
    expected_percentage: Decimal,
    expected_provenance: ProrrataProvisionalProvenance,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        service.declare(_carried_entry(percentage=Decimal("80")))

        resolution = service.resolve_provisional(_CURRENT_YEAR, candidate_entries=(candidate,))

    assert resolution.resolved
    assert resolution.percentage == expected_percentage
    assert resolution.provenance is expected_provenance


def test_carried_prior_definitiva_contradiction_blocks(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        observation_repo = CalculationObservationRepository(objects=profile.repository)
        _save_prior_prorrata_observation(observation_repo, percentage=Decimal("87"))

        findings = cross_check_prorrata_entry_against_prior_observation(
            _carried_entry(percentage=Decimal("80")),
            observation_repository=observation_repo,
        )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE.value
    assert finding.blocking
    assert not finding.advisory
    assert finding.source_modelo == Modelo.M303.value
    assert finding.source_filing_year == _PRIOR_YEAR
    assert finding.source_period == _SETTLEMENT_PERIOD
    assert "carried_prior_definitiva" in finding.message


@pytest.mark.parametrize(
    ("entry", "provenance_text"),
    (
        (
            _override_entry(
                provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
                percentage=Decimal("63"),
                reference="AEAT-AUTH-2026-0011",
            ),
            "aeat_autorizada",
        ),
        (
            _override_entry(
                provenance=ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
                percentage=Decimal("55"),
                reference="INICIO-036-2026-0006",
            ),
            "inicio_actividad",
        ),
    ),
)
def test_regulated_override_difference_surfaces_informational_notice(
    tmp_path: Path,
    entry: ProrrataRegisterEntry,
    provenance_text: str,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        observation_repo = CalculationObservationRepository(objects=profile.repository)
        _save_prior_prorrata_observation(observation_repo, percentage=Decimal("87"))

        findings = cross_check_prorrata_entry_against_prior_observation(
            entry,
            observation_repository=observation_repo,
        )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "regulated_prorrata_override_difference"
    assert finding.advisory
    assert not finding.blocking
    assert finding.source_modelo == Modelo.M303.value
    assert finding.source_filing_year == _PRIOR_YEAR
    assert finding.source_period == _SETTLEMENT_PERIOD
    assert provenance_text in finding.message
