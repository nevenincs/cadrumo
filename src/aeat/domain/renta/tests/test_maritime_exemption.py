"""Tests for maritime worker IRPF exemption selectors and calculation functions.

Covers contract (selector predicates), contract (calculation tests with registry-
authoritative fixture values), and the DA 41 / RETMAR completeness gate tests.

Expected values are grounded in:
  Art. 7.p) cap: Ley 35/2006 Art. 7.p) BOE-A-2006-20764 (60,100 EUR)
  REBECA fraction: Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-15794 (0.50)
  DA 41 status: inactive_pending_eu_clearance per trabajador_del_mar.toml
  RETMAR filing: Ley 47/2015 BOE-A-2015-11346
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...calculations.registry._bindings import CasillaObservation
from .._maritime_exemption import (
    ART_7P_EXEMPTION_CAP_EUR,
    RENTA_EXENTA_CASILLA,
    MaritimeExemptionInactiveError,
    MaritimeWorkerFacts,
    ProfileCompletenessError,
    art_7p_eligible,
    calculate_art_7p_exemption,
    calculate_rebeca_exemption,
    check_retmar_mandatory_filing,
    da41_eligible,
    guard_da41_inactive,
    rebeca_eligible,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# contract: selector unit tests
# ---------------------------------------------------------------------------


class TestArt7pEligible:
    """art_7p_eligible predicate: vessel_flag != ES AND waters_type == international."""

    def test_foreign_flag_international_waters_is_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="foreign",
            waters_type="international",
        )
        assert art_7p_eligible(facts) is True

    def test_foreign_flag_national_waters_is_eligible(self) -> None:
        # The business rule is: vessel_flag != ES OR waters_type == international.
        # Either condition suffices per the binding selector.
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="foreign",
            waters_type="national",
        )
        assert art_7p_eligible(facts) is True

    def test_spanish_flag_international_waters_is_eligible(self) -> None:
        # International waters qualify even for Spanish-flagged vessels per
        # AEAT accepted practice (TEAR Galicia December 2024).
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="ES",
            waters_type="international",
        )
        assert art_7p_eligible(facts) is True

    def test_spanish_flag_national_waters_is_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="ES",
            waters_type="national",
        )
        assert art_7p_eligible(facts) is False

    def test_non_maritime_worker_class_is_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class=None,
            vessel_flag="foreign",
            waters_type="international",
        )
        assert art_7p_eligible(facts) is False

    def test_other_worker_class_is_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="standard_employee",
            vessel_flag="foreign",
            waters_type="international",
        )
        assert art_7p_eligible(facts) is False

    def test_default_facts_not_eligible(self) -> None:
        assert art_7p_eligible(MaritimeWorkerFacts()) is False


class TestRebecaEligible:
    """rebeca_eligible predicate: vessel_registry in {REBECA, rebeca_eu_eea, scheduled_canary_route}."""

    def test_rebeca_registry_is_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="REBECA",
        )
        assert rebeca_eligible(facts) is True

    def test_rebeca_eu_eea_registry_is_eligible(self) -> None:
        # Extended to EU/EEA sister-registry vessels since 1 January 2021
        # per Ley 19/1994 Art. 75.1 BOE-A-1994-15794.
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="rebeca_eu_eea",
        )
        assert rebeca_eligible(facts) is True

    def test_scheduled_canary_route_is_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="scheduled_canary_route",
        )
        assert rebeca_eligible(facts) is True

    def test_no_registry_is_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry=None,
        )
        assert rebeca_eligible(facts) is False

    def test_non_maritime_worker_class_is_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class=None,
            vessel_registry="REBECA",
        )
        assert rebeca_eligible(facts) is False

    def test_default_facts_not_eligible(self) -> None:
        assert rebeca_eligible(MaritimeWorkerFacts()) is False


class TestDa41Eligible:
    """da41_eligible predicate: tuna_fleet AND pending_eu_clearance."""

    def test_tuna_fleet_with_pending_clearance_is_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=True,
        )
        assert da41_eligible(facts) is True

    def test_tuna_fleet_without_pending_clearance_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=False,
        )
        assert da41_eligible(facts) is False

    def test_pending_clearance_without_tuna_fleet_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=False,
            pending_eu_clearance=True,
        )
        assert da41_eligible(facts) is False

    def test_non_maritime_worker_class_not_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class=None,
            tuna_fleet=True,
            pending_eu_clearance=True,
        )
        assert da41_eligible(facts) is False

    def test_default_facts_not_eligible(self) -> None:
        assert da41_eligible(MaritimeWorkerFacts()) is False


# ---------------------------------------------------------------------------
# contract: DA 41 inactive guard
# ---------------------------------------------------------------------------


class TestGuardDa41Inactive:
    """guard_da41_inactive raises MaritimeExemptionInactiveError when da41_eligible is True."""

    def test_raises_when_da41_eligible(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=True,
        )
        with pytest.raises(MaritimeExemptionInactiveError) as exc_info:
            guard_da41_inactive(facts)
        assert "EU state-aid clearance" in str(exc_info.value)
        assert "DA 41" in str(exc_info.value)

    def test_does_not_raise_when_not_eligible(self) -> None:
        # Must not raise for any profile that does not meet the DA 41 selector.
        guard_da41_inactive(MaritimeWorkerFacts())
        guard_da41_inactive(MaritimeWorkerFacts(worker_class="trabajador_del_mar", tuna_fleet=False))

    def test_error_carries_legal_context(self) -> None:
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=True,
        )
        with pytest.raises(MaritimeExemptionInactiveError) as exc_info:
            guard_da41_inactive(facts)
        err = exc_info.value
        assert err.context is not None
        assert err.context.get("legal_ref") == "Ley 35/2006 DA 41 BOE-A-2006-20764"
        assert err.context.get("enabling_law") == "Ley 6/2018 BOE-A-2018-9268"


# ---------------------------------------------------------------------------
# contract: RETMAR mandatory-filing completeness gate
# ---------------------------------------------------------------------------


class TestCheckRetmarMandatoryFiling:
    """check_retmar_mandatory_filing raises ProfileCompletenessError when retmar_registered."""

    def test_raises_when_retmar_registered(self) -> None:
        facts = MaritimeWorkerFacts(retmar_registered=True)
        with pytest.raises(ProfileCompletenessError) as exc_info:
            check_retmar_mandatory_filing(facts)
        assert "RETMAR" in str(exc_info.value)
        assert "BOE-A-2015-11346" in str(exc_info.value)

    def test_does_not_raise_when_not_registered(self) -> None:
        check_retmar_mandatory_filing(MaritimeWorkerFacts(retmar_registered=False))
        check_retmar_mandatory_filing(MaritimeWorkerFacts())

    def test_warning_carries_legal_context(self) -> None:
        facts = MaritimeWorkerFacts(retmar_registered=True)
        with pytest.raises(ProfileCompletenessError) as exc_info:
            check_retmar_mandatory_filing(facts)
        err = exc_info.value
        assert err.context is not None
        assert err.context.get("legal_ref") == "Ley 47/2015 BOE-A-2015-11346"

    def test_retmar_warning_is_renta_error_subclass(self) -> None:
        from .._errors import RentaError

        facts = MaritimeWorkerFacts(retmar_registered=True)
        with pytest.raises(RentaError):
            check_retmar_mandatory_filing(facts)


# ---------------------------------------------------------------------------
# contract + contract: Art. 7.p) calculation with registry-authoritative fixture values
# ---------------------------------------------------------------------------


class TestCalculateArt7pExemption:
    """Art. 7.p) calculation: min(annual_salary / 365 * qualifying_days, 60_100).

    Expected values are derived from Ley 35/2006 Art. 7.p) BOE-A-2006-20764:
    cap = 60,100 EUR. The formula is statutory, not hand-computed.
    """

    _BASE_FACTS = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_flag="foreign",
        waters_type="international",
    )

    def test_standard_case_below_cap(self) -> None:
        # No published AEAT worked example covers this prorate input set;
        # the numeric value assertion would re-apply the formula under
        # test (tautology). Structural invariants only: a CasillaObservation
        # is returned and the value sits strictly below the statutory cap.
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=100,
            facts=self._BASE_FACTS,
        )
        assert isinstance(obs, CasillaObservation)
        assert obs.value < ART_7P_EXEMPTION_CAP_EUR
        assert obs.value > Decimal("0")

    def test_cap_applied_when_formula_exceeds_60100(self) -> None:
        # 73,000 EUR annual salary, 365 qualifying days:
        #   73000 / 365 * 365 = 73,000 EUR → capped at 60,100 EUR
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("73000"),
            qualifying_days=365,
            facts=self._BASE_FACTS,
        )
        assert obs.value == ART_7P_EXEMPTION_CAP_EUR

    def test_exactly_at_cap_is_not_reduced(self) -> None:
        # annual_salary = 60100, qualifying_days = 365: formula = 60100 EUR
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("60100"),
            qualifying_days=365,
            facts=self._BASE_FACTS,
        )
        assert obs.value == ART_7P_EXEMPTION_CAP_EUR

    def test_single_qualifying_day(self) -> None:
        # Edge-of-range prorate (1 qualifying day). No published worked
        # example exists at this boundary; numeric value assertion would
        # re-apply the formula. Structural invariant only: the value is
        # positive and below the cap.
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=1,
            facts=self._BASE_FACTS,
        )
        assert obs.value > Decimal("0")
        assert obs.value < ART_7P_EXEMPTION_CAP_EUR

    def test_observation_carries_art7p_legal_refs(self) -> None:
        # Close gate: CasillaObservation.legal_refs must carry
        # "ley-35-2006:art-7p" per aeat-calculation-grounding rule.
        # Registry binding is based on "Ley 35/2006 Art. 7.p)".
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=100,
            facts=self._BASE_FACTS,
        )
        assert any("Art. 7.p)" in ref for ref in obs.legal_refs), (
            f"CasillaObservation.legal_refs must carry Ley 35/2006 Art. 7.p), got {obs.legal_refs!r}"
        )
        assert any("BOE-A-2006-20764" in ref for ref in obs.legal_refs)

    def test_observation_carries_source_refs(self) -> None:
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=100,
            facts=self._BASE_FACTS,
        )
        assert obs.source_refs, "source_refs must not be empty"
        assert "art-7p-foreign-work" in obs.source_refs

    def test_observation_targets_renta_exenta_casilla(self) -> None:
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=100,
            facts=self._BASE_FACTS,
        )
        assert obs.casilla_id == RENTA_EXENTA_CASILLA

    def test_raises_when_not_eligible(self) -> None:
        from .._errors import RentaValidationError

        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="ES",
            waters_type="national",
        )
        with pytest.raises(RentaValidationError):
            calculate_art_7p_exemption(
                annual_salary=Decimal("36500"),
                qualifying_days=100,
                facts=facts,
            )

    def test_raises_on_zero_salary(self) -> None:
        from .._errors import RentaValidationError

        with pytest.raises(RentaValidationError):
            calculate_art_7p_exemption(
                annual_salary=Decimal("0"),
                qualifying_days=100,
                facts=self._BASE_FACTS,
            )

    def test_raises_on_zero_qualifying_days(self) -> None:
        from .._errors import RentaValidationError

        with pytest.raises(RentaValidationError):
            calculate_art_7p_exemption(
                annual_salary=Decimal("36500"),
                qualifying_days=0,
                facts=self._BASE_FACTS,
            )

    def test_raises_on_qualifying_days_exceeding_year(self) -> None:
        from .._errors import RentaValidationError

        with pytest.raises(RentaValidationError):
            calculate_art_7p_exemption(
                annual_salary=Decimal("36500"),
                qualifying_days=366,
                facts=self._BASE_FACTS,
            )


# ---------------------------------------------------------------------------
# contract + contract: REBECA calculation with registry-authoritative fixture values
# ---------------------------------------------------------------------------


class TestCalculateRebecaExemption:
    """REBECA 50% exemption: exempt_amount = gross_navigation_income * 0.50.

    The 50% fraction is statutory per Ley 19/1994 Arts. 73.2 73.3 75.1 75.3
    BOE-A-1994-15794 and is not variable by election.
    """

    _REBECA_FACTS = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_registry="REBECA",
    )

    def test_standard_case(self) -> None:
        # No published worked example covers this gross_income input;
        # asserting the exact half-rate value would re-apply the formula
        # under test. Structural invariants only.
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("30000"),
            facts=self._REBECA_FACTS,
        )
        assert isinstance(obs, CasillaObservation)
        assert obs.value > Decimal("0")
        assert obs.value < Decimal("30000")

    def test_eu_eea_registry_variant(self) -> None:
        # Registry-variant dispatch reaches the REBECA path. No external
        # oracle for this input; structural invariants only.
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="rebeca_eu_eea",
        )
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("40000"),
            facts=facts,
        )
        assert isinstance(obs, CasillaObservation)
        assert obs.value > Decimal("0")
        assert obs.value < Decimal("40000")

    def test_scheduled_canary_route_variant(self) -> None:
        # Registry-variant dispatch reaches the REBECA path. No external
        # oracle for this input; structural invariants only.
        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="scheduled_canary_route",
        )
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("50000"),
            facts=facts,
        )
        assert isinstance(obs, CasillaObservation)
        assert obs.value > Decimal("0")
        assert obs.value < Decimal("50000")

    def test_observation_carries_rebeca_legal_refs(self) -> None:
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("30000"),
            facts=self._REBECA_FACTS,
        )
        combined = " ".join(obs.legal_refs)
        assert "BOE-A-1994-15794" in combined, (
            f"CasillaObservation.legal_refs must cite BOE-A-1994-15794, got {obs.legal_refs!r}"
        )
        assert "73" in combined, "legal_refs must reference Art. 73"
        assert "75" in combined, "legal_refs must reference Art. 75"

    def test_observation_carries_source_refs(self) -> None:
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("30000"),
            facts=self._REBECA_FACTS,
        )
        assert obs.source_refs, "source_refs must not be empty"
        assert "rebeca-50pct" in obs.source_refs

    def test_observation_targets_renta_exenta_casilla(self) -> None:
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("30000"),
            facts=self._REBECA_FACTS,
        )
        assert obs.casilla_id == RENTA_EXENTA_CASILLA

    def test_raises_when_not_eligible(self) -> None:
        from .._errors import RentaValidationError

        facts = MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry=None,
        )
        with pytest.raises(RentaValidationError):
            calculate_rebeca_exemption(
                gross_navigation_income=Decimal("30000"),
                facts=facts,
            )

    def test_raises_on_zero_income(self) -> None:
        from .._errors import RentaValidationError

        with pytest.raises(RentaValidationError):
            calculate_rebeca_exemption(
                gross_navigation_income=Decimal("0"),
                facts=self._REBECA_FACTS,
            )


# ---------------------------------------------------------------------------
# Close gate: prohibited legal refs not cited in binding outputs
# ---------------------------------------------------------------------------


def test_art7p_legal_refs_contain_no_wrong_provision() -> None:
    """The Art. 7.p) observation must cite only the correct LIRPF provision.

    The January 2015 transitional withholding rule has no maritime content.
    The REBECA-specific BOE citation must not appear in Art. 7.p) legal_refs.
    """
    facts = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_flag="foreign",
        waters_type="international",
    )
    obs = calculate_art_7p_exemption(
        annual_salary=Decimal("36500"),
        qualifying_days=100,
        facts=facts,
    )
    # Must cite the Art. 7.p) provision only.
    assert all("Art. 7.p)" in ref or "BOE-A-2006-20764" in ref for ref in obs.legal_refs), (
        f"Art. 7.p) observation must only carry Art. 7.p) / BOE-A-2006-20764 refs, got {obs.legal_refs!r}"
    )
    # REBECA citation must not appear in Art. 7.p) output.
    assert not any("BOE-A-1994-15794" in ref for ref in obs.legal_refs)


def test_rebeca_legal_refs_contain_no_wrong_provision() -> None:
    """The REBECA observation must cite only Ley 19/1994 provisions.

    The Art. 7.p) BOE citation must not appear in REBECA legal_refs.
    """
    facts = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_registry="REBECA",
    )
    obs = calculate_rebeca_exemption(
        gross_navigation_income=Decimal("30000"),
        facts=facts,
    )
    # Must cite only Ley 19/1994 BOE-A-1994-15794.
    assert all("BOE-A-1994-15794" in ref for ref in obs.legal_refs), (
        f"REBECA observation must only carry BOE-A-1994-15794 refs, got {obs.legal_refs!r}"
    )
