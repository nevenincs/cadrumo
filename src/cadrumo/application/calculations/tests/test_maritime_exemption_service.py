"""Integration tests for the maritime worker exemption application service.

Verifies that the application-layer service correctly wires domain calculation
functions and produces CasillaObservation rows with legal_refs and source_refs
propagated from the registry binding entries.

These tests exercise real domain functions without mocks.

Covers contract (application layer wiring) and contract (integration test asserting
legal_refs and source_refs in the observation output).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.renta.errors import RentaValidationError
from ....domain.renta.maritime_exemption import (
    ART_7P_EXEMPTION_CAP_EUR,
    RENTA_EXENTA_CASILLA,
    MaritimeExemptionInactiveError,
    MaritimeWorkerFacts,
    ProfileCompletenessError,
)
from .._maritime_exemption_service import (
    MaritimeExemptionResult,
    resolve_maritime_exemption,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ART_7P_LEGAL_REFS = ("ley-35-2006:art-7",)
_REBECA_LEGAL_REFS = ("ley-19-1994:art-75",)
_ART_7P_SOURCE_REFS = ("boe-lirpf-art-7-authority",)
_REBECA_SOURCE_REFS = ("boe-ley-19-1994-art-75-authority",)


class TestResolveMaritimeExemptionArt7p:
    """Art. 7.p) pathway through the application service."""

    _FACTS = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_flag="foreign",
        waters_type="international",
    )

    def test_returns_typed_observation_for_eligible_profile(self) -> None:
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            annual_salary=Decimal("36500"),
            qualifying_days=100,
        )
        assert isinstance(result, MaritimeExemptionResult)
        assert len(result.observations) == 1

    def test_observation_carries_art7p_legal_refs(self) -> None:
        """Contract close gate: observations carry canonical legal ids."""
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            annual_salary=Decimal("36500"),
            qualifying_days=100,
        )
        obs = result.observations[0]
        assert obs.legal_refs == _ART_7P_LEGAL_REFS

    def test_observation_carries_source_refs(self) -> None:
        """Contract close gate: source_refs must be exact registry binding ids."""
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            annual_salary=Decimal("36500"),
            qualifying_days=100,
        )
        obs = result.observations[0]
        assert obs.source_refs == _ART_7P_SOURCE_REFS

    def test_observation_targets_renta_exenta_casilla(self) -> None:
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            annual_salary=Decimal("36500"),
            qualifying_days=100,
        )
        assert result.observations[0].casilla_id == RENTA_EXENTA_CASILLA

    def test_cap_applied_at_60100_eur(self) -> None:
        """Registry-authoritative cap: 60,100 EUR per Ley 35/2006 Art. 7.p)."""
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            annual_salary=Decimal("120000"),
            qualifying_days=365,
        )
        assert result.observations[0].value == ART_7P_EXEMPTION_CAP_EUR

    def test_casilla_values_derived_view_matches_observations(self) -> None:
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            annual_salary=Decimal("36500"),
            qualifying_days=100,
        )
        assert result.casilla_values[RENTA_EXENTA_CASILLA] == result.observations[0].value

    def test_raises_when_salary_missing_for_eligible_profile(self) -> None:
        with pytest.raises(RentaValidationError) as excinfo:
            resolve_maritime_exemption(
                facts=self._FACTS,
                qualifying_days=100,
            )

        assert str(excinfo.value) == "application.calculations.maritime_exemption.errors.art_7p_inputs_required"
        assert excinfo.value.context == {"annual_salary_supplied": False, "qualifying_days_supplied": True}

    def test_raises_when_qualifying_days_missing_for_eligible_profile(self) -> None:
        with pytest.raises(RentaValidationError) as excinfo:
            resolve_maritime_exemption(
                facts=self._FACTS,
                annual_salary=Decimal("36500"),
            )

        assert str(excinfo.value) == "application.calculations.maritime_exemption.errors.art_7p_inputs_required"
        assert excinfo.value.context == {"annual_salary_supplied": True, "qualifying_days_supplied": False}


class TestResolveMaritimeExemptionRebeca:
    """REBECA 50% pathway through the application service."""

    _FACTS = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_registry="REBECA",
    )

    def test_returns_typed_observation_for_eligible_profile(self) -> None:
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            gross_navigation_income=Decimal("30000"),
        )
        assert len(result.observations) == 1

    def test_observation_carries_rebeca_legal_refs(self) -> None:
        """Contract close gate: legal_refs must be canonical registry ids."""
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            gross_navigation_income=Decimal("30000"),
        )
        obs = result.observations[0]
        assert obs.legal_refs == _REBECA_LEGAL_REFS

    def test_observation_carries_source_refs(self) -> None:
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            gross_navigation_income=Decimal("30000"),
        )
        assert result.observations[0].source_refs == _REBECA_SOURCE_REFS

    def test_exempt_amount_is_50_percent(self) -> None:
        """Registry-authoritative fraction: 0.50 per Ley 19/1994 Arts. 73-75."""
        result = resolve_maritime_exemption(
            facts=self._FACTS,
            gross_navigation_income=Decimal("40000"),
        )
        assert result.observations[0].value == Decimal("20000")

    def test_raises_when_navigation_income_missing_for_rebeca_eligible(self) -> None:
        with pytest.raises(RentaValidationError) as excinfo:
            resolve_maritime_exemption(facts=self._FACTS)

        assert str(excinfo.value) == "application.calculations.maritime_exemption.errors.rebeca_input_required"
        assert excinfo.value.context == {"gross_navigation_income_supplied": False}


class TestResolveMaritimeExemptionDa41Guard:
    """DA 41 inactive guard fires before any observation is produced."""

    def test_raises_maritime_exemption_inactive_error(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=True,
        )
        with pytest.raises(MaritimeExemptionInactiveError):
            resolve_maritime_exemption(facts=facts)

    def test_no_observations_produced_when_da41_guard_fires(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=True,
        )
        with pytest.raises(MaritimeExemptionInactiveError):
            resolve_maritime_exemption(
                facts=facts,
                annual_salary=Decimal("36500"),
                qualifying_days=100,
            )


class TestResolveMaritimeExemptionRetmarGate:
    """RETMAR completeness gate raises ProfileCompletenessError."""

    def test_raises_profile_completeness_warning_for_retmar_registered(self) -> None:
        facts = MaritimeWorkerFacts(retmar_registered=True)
        with pytest.raises(ProfileCompletenessError) as exc_info:
            resolve_maritime_exemption(facts=facts)
        assert "RETMAR" in str(exc_info.value)
        assert "BOE-A-2006-20764" in str(exc_info.value)

    def test_retmar_flag_propagated_to_result(self) -> None:
        # When retmar_registered but not RETMAR-gate-triggering (should not happen
        # in production, but the result flag reflects the fact).
        # We test via the result directly: no warning is raised when retmar=False.
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="REBECA",
            retmar_registered=False,
        )
        result = resolve_maritime_exemption(
            facts=facts,
            gross_navigation_income=Decimal("30000"),
        )
        assert result.retmar_mandatory_filing is False

    def test_no_maritime_worker_class_returns_empty_result(self) -> None:
        result = resolve_maritime_exemption(facts=MaritimeWorkerFacts())
        assert result.observations == ()
        assert result.casilla_values == {}
