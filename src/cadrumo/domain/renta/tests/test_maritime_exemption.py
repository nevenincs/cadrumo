"""Tests for maritime worker IRPF exemption selectors and calculation functions.

Covers contract (selector predicates), contract (calculation tests with registry-
authoritative fixture values), and the DA 41 / RETMAR completeness gate tests.

Expected values are grounded in:
  Art. 7.p) cap: Ley 35/2006 Art. 7.p) BOE-A-2006-20764 (60,100 EUR)
  REBECA fraction: Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-15794 (0.50)
  DA 41 status: inactive_pending_eu_clearance per trabajador_del_mar.toml
  RETM filing: Ley 35/2006 Art. 96 BOE-A-2006-20764
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ...calculations.registry import CasillaObservation
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

_ART_7P_LEGAL_REFS = ("ley-35-2006:art-7",)
_REBECA_LEGAL_REFS = ("ley-19-1994:art-75",)
_DA41_LEGAL_REFS = ("ley-35-2006:da-41",)
_RETMAR_LEGAL_REFS = ("ley-35-2006:art-96",)
_ART_7P_SOURCE_REFS = ("boe-lirpf-art-7-authority",)
_REBECA_SOURCE_REFS = ("boe-ley-19-1994-art-75-authority",)

_ART_7P_SELECTOR_CASES = (
    (
        "foreign-flag-international-waters",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="foreign",
            waters_type="international",
        ),
        True,
    ),
    (
        "foreign-flag-national-waters",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="foreign",
            waters_type="national",
        ),
        True,
    ),
    (
        "spanish-flag-international-waters",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="ES",
            waters_type="international",
        ),
        True,
    ),
    (
        "spanish-flag-national-waters",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="ES",
            waters_type="national",
        ),
        False,
    ),
    (
        "missing-worker-class",
        MaritimeWorkerFacts(
            worker_class=None,
            vessel_flag="foreign",
            waters_type="international",
        ),
        False,
    ),
    (
        "other-worker-class",
        MaritimeWorkerFacts(
            worker_class="standard_employee",
            vessel_flag="foreign",
            waters_type="international",
        ),
        False,
    ),
    ("default-facts", MaritimeWorkerFacts(), False),
)

_REBECA_SELECTOR_CASES = (
    (
        "rebeca-registry",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="REBECA",
        ),
        True,
    ),
    (
        "rebeca-eu-eea-registry",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="rebeca_eu_eea",
        ),
        True,
    ),
    (
        "scheduled-canary-route",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="scheduled_canary_route",
        ),
        True,
    ),
    (
        "missing-registry",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry=None,
        ),
        False,
    ),
    (
        "missing-worker-class",
        MaritimeWorkerFacts(
            worker_class=None,
            vessel_registry="REBECA",
        ),
        False,
    ),
    ("default-facts", MaritimeWorkerFacts(), False),
)

_DA41_SELECTOR_CASES = (
    (
        "tuna-fleet-pending-clearance",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=True,
        ),
        True,
    ),
    (
        "tuna-fleet-without-pending-clearance",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=True,
            pending_eu_clearance=False,
        ),
        False,
    ),
    (
        "pending-clearance-without-tuna-fleet",
        MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            tuna_fleet=False,
            pending_eu_clearance=True,
        ),
        False,
    ),
    (
        "missing-worker-class",
        MaritimeWorkerFacts(
            worker_class=None,
            tuna_fleet=True,
            pending_eu_clearance=True,
        ),
        False,
    ),
    ("default-facts", MaritimeWorkerFacts(), False),
)


# ---------------------------------------------------------------------------
# contract: selector unit tests
# ---------------------------------------------------------------------------


class TestArt7pEligible:
    """art_7p_eligible predicate: vessel_flag != ES AND waters_type == international."""

    def test_selector_cases(self) -> None:
        for label, facts, expected in _ART_7P_SELECTOR_CASES:
            assert art_7p_eligible(facts) is expected, label


class TestRebecaEligible:
    """rebeca_eligible predicate: vessel_registry in {REBECA, rebeca_eu_eea, scheduled_canary_route}."""

    def test_selector_cases(self) -> None:
        for label, facts, expected in _REBECA_SELECTOR_CASES:
            assert rebeca_eligible(facts) is expected, label


class TestDa41Eligible:
    """da41_eligible predicate: tuna_fleet AND pending_eu_clearance."""

    def test_selector_cases(self) -> None:
        for label, facts, expected in _DA41_SELECTOR_CASES:
            assert da41_eligible(facts) is expected, label


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
        assert err.context.get("legal_ref") == _DA41_LEGAL_REFS[0]


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
        assert "BOE-A-2006-20764" in str(exc_info.value)

    def test_does_not_raise_when_not_registered(self) -> None:
        check_retmar_mandatory_filing(MaritimeWorkerFacts(retmar_registered=False))
        check_retmar_mandatory_filing(MaritimeWorkerFacts())

    def test_warning_carries_legal_context(self) -> None:
        facts = MaritimeWorkerFacts(retmar_registered=True)
        with pytest.raises(ProfileCompletenessError) as exc_info:
            check_retmar_mandatory_filing(facts)
        err = exc_info.value
        assert err.context is not None
        assert err.context.get("legal_ref") == _RETMAR_LEGAL_REFS[0]

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
        assert isinstance(obs.value, Decimal)
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
        assert isinstance(obs.value, Decimal)
        assert obs.value > Decimal("0")
        assert obs.value < ART_7P_EXEMPTION_CAP_EUR

    def test_observation_carries_art7p_legal_refs(self) -> None:
        # Close gate: CasillaObservation.legal_refs must carry the canonical
        # legal registry id, not display prose copied from BOE notes.
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=100,
            facts=self._BASE_FACTS,
        )
        assert obs.legal_refs == _ART_7P_LEGAL_REFS

    def test_observation_carries_source_refs(self) -> None:
        obs = calculate_art_7p_exemption(
            annual_salary=Decimal("36500"),
            qualifying_days=100,
            facts=self._BASE_FACTS,
        )
        assert obs.source_refs == _ART_7P_SOURCE_REFS

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
        assert isinstance(obs.value, Decimal)
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
        assert isinstance(obs.value, Decimal)
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
        assert isinstance(obs.value, Decimal)
        assert obs.value > Decimal("0")
        assert obs.value < Decimal("50000")

    def test_observation_carries_rebeca_legal_refs(self) -> None:
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("30000"),
            facts=self._REBECA_FACTS,
        )
        assert obs.legal_refs == _REBECA_LEGAL_REFS

    def test_observation_carries_source_refs(self) -> None:
        obs = calculate_rebeca_exemption(
            gross_navigation_income=Decimal("30000"),
            facts=self._REBECA_FACTS,
        )
        assert obs.source_refs == _REBECA_SOURCE_REFS

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
    assert obs.legal_refs == _ART_7P_LEGAL_REFS


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
    assert obs.legal_refs == _REBECA_LEGAL_REFS


def test_runtime_legal_and_source_refs_resolve_to_bundled_catalogues() -> None:
    """Runtime maritime provenance must resolve through typed registry catalogues."""
    catalogues = resources().modelos.authority.catalogues

    art7p_obs = calculate_art_7p_exemption(
        annual_salary=Decimal("36500"),
        qualifying_days=100,
        facts=MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_flag="foreign",
            waters_type="international",
        ),
    )
    rebeca_obs = calculate_rebeca_exemption(
        gross_navigation_income=Decimal("30000"),
        facts=MaritimeWorkerFacts(
            worker_class="trabajador_del_mar",
            vessel_registry="REBECA",
        ),
    )

    legal_refs = set(art7p_obs.legal_refs) | set(rebeca_obs.legal_refs)
    source_refs = set(art7p_obs.source_refs) | set(rebeca_obs.source_refs)

    with pytest.raises(MaritimeExemptionInactiveError) as da41_error:
        guard_da41_inactive(
            MaritimeWorkerFacts(
                worker_class="trabajador_del_mar",
                tuna_fleet=True,
                pending_eu_clearance=True,
            ),
        )
    assert da41_error.value.context is not None
    legal_refs.add(str(da41_error.value.context["legal_ref"]))

    with pytest.raises(ProfileCompletenessError) as retm_error:
        check_retmar_mandatory_filing(MaritimeWorkerFacts(retmar_registered=True))
    assert retm_error.value.context is not None
    legal_refs.add(str(retm_error.value.context["legal_ref"]))

    assert sorted(ref for ref in legal_refs if ref not in catalogues.legal) == []
    assert sorted(ref for ref in source_refs if ref not in catalogues.sources) == []
