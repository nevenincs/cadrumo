"""Roundtrip + anti-tautology tests for the three-axis taxpayer wizard fields.

The wizard collects the entity-type, IRPF income-category set, IRPF
estimation regime, and the SII / REDEME special enrolments. These
tests push a fully-populated :class:`SetupAnswers` through the real
canonical-token persistence cycle (``serialise_answers`` ->
``project_answers``) and through ``taxpayer_profile_from_mapping``,
asserting strict equality, and prove the roundtrip is non-tautological
by dropping a field from the canonical dict.
"""

from __future__ import annotations

import pytest

from ....core.setup_answers import SetupAnswers
from ....domain.deadlines.models import EntityType, IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, LegalEntityForm
from ....domain.deadlines.profiles import taxpayer_profile_from_mapping
from ..catalogue import SETUP_FLOW
from ..persistence import project_answers, serialise_answers

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _fully_populated_answers() -> SetupAnswers:
    """A SetupAnswers with every taxpayer-axis field non-default."""

    return SetupAnswers(
        tax_id="12345678Z",
        activity="Software development",
        entity_type=EntityType.NATURAL_PERSON,
        legal_entity_form="",
        irpf_income_categories="trabajo,capital_inmobiliario,pension",
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
        iva_regime=IVARegime.REAGP,
        iva_group_member_enrolled=True,
        iva_group_dominant_entity_enrolled=True,
        iva_sii_enrolled=True,
        iva_redeme_enrolled=True,
        art109_activity_income_withholding_ge_70pct=True,
    )


class TestSetupAnswersTaxpayerAxes:
    """The new SetupAnswers fields accept and normalise their typed input."""

    def test_legal_entity_form_accepts_a_recognised_form(self) -> None:
        answers = SetupAnswers(
            tax_id="B12345674",
            activity="Cooperative trading",
            entity_type=EntityType.LEGAL_ENTITY,
            legal_entity_form=LegalEntityForm.COOPERATIVA,
        )
        assert answers.legal_entity_form is LegalEntityForm.COOPERATIVA

    def test_irpf_income_categories_rejects_unknown_token(self) -> None:
        with pytest.raises(ValueError, match=r"not_a_category"):
            SetupAnswers(
                tax_id="12345678Z",
                activity="x",
                irpf_income_categories="trabajo,not_a_category",
            )

    def test_irpf_estimation_regime_rejects_unknown_token(self) -> None:
        with pytest.raises(ValueError):
            SetupAnswers(
                tax_id="12345678Z",
                activity="x",
                irpf_estimation_regime="estimacion_magica",
            )


class TestWizardPersistenceRoundTrip:
    """SetupAnswers survives the canonical-token persistence cycle."""

    def test_taxpayer_axes_round_trip_through_canonical_dict(self) -> None:
        original = _fully_populated_answers()
        canonical = serialise_answers(SETUP_FLOW, original)
        rebuilt = project_answers(SETUP_FLOW, canonical)
        assert isinstance(rebuilt, SetupAnswers)
        assert rebuilt.entity_type == original.entity_type
        assert rebuilt.irpf_income_categories == original.irpf_income_categories
        assert rebuilt.irpf_estimation_regime == original.irpf_estimation_regime
        assert rebuilt.iva_regime == original.iva_regime
        assert rebuilt.iva_group_member_enrolled == original.iva_group_member_enrolled
        assert rebuilt.iva_group_dominant_entity_enrolled == original.iva_group_dominant_entity_enrolled
        assert rebuilt.iva_sii_enrolled == original.iva_sii_enrolled
        assert rebuilt.iva_redeme_enrolled == original.iva_redeme_enrolled
        assert rebuilt.art109_activity_income_withholding_ge_70pct is True

    def test_canonical_dict_carries_taxpayer_axis_profile_keys(self) -> None:
        canonical = serialise_answers(SETUP_FLOW, _fully_populated_answers())
        assert canonical["taxpayer_type.entity_type"] == "natural_person"
        assert canonical["taxpayer_type.irpf_income_categories"] == ("trabajo,capital_inmobiliario,pension")
        assert canonical["irpf.estimation_regime"] == "directa_simplificada"
        assert canonical["irpf.art109_activity_income_withholding_ge_70pct"] == "true"
        assert canonical["iva.group_member_enrolled"] == "true"
        assert canonical["iva.group_dominant_entity_enrolled"] == "true"
        assert canonical["iva.sii_enrolled"] == "true"
        assert canonical["iva.redeme_enrolled"] == "true"

    def test_dropped_enrolment_key_stays_undeclared_on_reprojection(self) -> None:
        """Anti-tautology: removing iva.sii_enrolled preserves its undeclared state.

        If the roundtrip were tautological, the dropped key would not
        change the reprojected answers and a save-drops-field
        regression would be invisible.
        """

        original = _fully_populated_answers()
        canonical = serialise_answers(SETUP_FLOW, original)
        del canonical["iva.sii_enrolled"]
        rebuilt = project_answers(SETUP_FLOW, canonical)
        assert isinstance(rebuilt, SetupAnswers)
        assert rebuilt.iva_sii_enrolled == ""
        assert rebuilt != original


class TestTaxpayerProfileProjection:
    """taxpayer_profile_from_mapping carries the new axes onto TaxpayerProfile."""

    def test_mapping_projection_carries_every_taxpayer_axis(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "12345678Z",
                "activities.description": "Landlord",
                "taxpayer_type.entity_type": "natural_person",
                "taxpayer_type.irpf_income_categories": "capital_inmobiliario,pension",
                "irpf.estimation_regime": "objetiva",
                "irpf.art109_activity_income_withholding_ge_70pct": "true",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "REAGP",
                "iva.m303_regime_composition": "general",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
                "iva.group_member_enrolled": "true",
                "iva.group_dominant_entity_enrolled": "true",
                "iva.sii_enrolled": "true",
                "iva.redeme_enrolled": "true",
            },
            tax_id_default="00000000T",
        )
        assert profile.entity_type is EntityType.NATURAL_PERSON
        assert profile.irpf_income_categories == frozenset(
            {IrpfIncomeCategory.CAPITAL_INMOBILIARIO, IrpfIncomeCategory.PENSION},
        )
        assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA
        assert profile.art109_activity_income_withholding_ge_70pct is True
        assert profile.iva_regime is IVARegime.REAGP
        iva = profile.iva
        assert iva is not None
        assert iva.regime_composition.value == "general"
        assert iva.cash_accounting_regime_enrolled is False
        assert iva.voluntary_sii_enrolled is False
        assert iva.hydrocarbon_deposit_advance_payment_deduction_entitled is False
        assert iva.group_member_enrolled is True
        assert iva.group_dominant_entity_enrolled is True
        assert iva.sii_enrolled is True
        assert iva.redeme_enrolled is True

    def test_mapping_projection_carries_cross_period_group_roster(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "12345678Z",
                "activities.description": "Grupo IVA",
                "cross_period.group_member_roster.322.2026.12": "B00000000, A00000000",
                "iva_grupo.member_roster.2026.11": "C00000000;D00000000",
            },
            tax_id_default="00000000T",
        )

        assert [item.source_modelo for item in profile.cross_period_group_member_rosters] == ["322", "322"]
        assert [item.filing_year for item in profile.cross_period_group_member_rosters] == [2026, 2026]
        assert [item.period.registry_token for item in profile.cross_period_group_member_rosters] == ["11", "12"]
        assert profile.cross_period_group_member_rosters[0].member_nifs == ("C00000000", "D00000000")
        assert profile.cross_period_group_member_rosters[1].member_nifs == ("A00000000", "B00000000")

    def test_objetiva_regime_projects_structured_axis(self) -> None:
        """The wizard projects objective estimation through the enum axis."""

        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "12345678Z",
                "activities.description": "Modulos activity",
                "irpf.estimation_regime": "objetiva",
            },
            tax_id_default="00000000T",
        )
        assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA

    def test_objetiva_regime_projects_modulos_annual_profile_facts(self) -> None:
        """Annual módulos facts project from the real profile mapping."""

        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "12345678Z",
                "activities.description": "Modulos activity",
                "irpf.estimation_regime": "objetiva",
                "irpf.objective_estimation_modulos_iae_epigraph": "972.1",
                "irpf.objective_estimation_modulos_module_1_units": "2.50",
                "irpf.objective_estimation_modulos_module_2_units": "85",
                "irpf.objective_estimation_modulos_module_3_units": "12000.75",
            },
            tax_id_default="00000000T",
        )
        assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA
        assert profile.objective_estimation_modulos_iae_epigraph == "972.1"
        assert str(profile.objective_estimation_modulos_module_1_units) == "2.50"
        assert str(profile.objective_estimation_modulos_module_2_units) == "85"
        assert str(profile.objective_estimation_modulos_module_3_units) == "12000.75"

    def test_undeclared_axes_project_to_safe_empty_defaults(self) -> None:
        """A profile with no taxpayer-axis facts projects to undeclared.

        The taxpayer-axis schema is data-only — the engine still behaves as
        today — but an undeclared taxpayer model must not invent a
        default entity type or regime.
        """

        profile = taxpayer_profile_from_mapping(
            {"identity.tax_id": "12345678Z", "activities.description": "x"},
            tax_id_default="00000000T",
        )
        assert profile.entity_type is None
        assert profile.legal_entity_form is None
        assert profile.irpf_income_categories == frozenset()
        assert profile.irpf_estimation_regime is None
        # No IVA block-owned fact is declared, so the optional IVA block is absent.
        assert profile.iva is None


class TestNewEntityFirstTwoProfitPeriodsRoundTrip:
    """The LIS Art. 29 new-entity-first-two-profit-periods state survives
    the full wizard → persistence → reload → projection cycle as a
    three-state value.

    These tests exist because BLOCKER 1 demonstrated that a descriptor
    default of ``"false"`` collapsed the three-state down to a binary
    declared-False, silently corrupting every quiet-create legal entity
    profile. The contract under test: a profile that has not declared
    the fact projects to ``None`` (undeclared); a positively-declared
    True projects to ``True``; a positively-declared False projects to
    ``False``.
    """

    def _legal_entity_answers(
        self,
        *,
        new_entity: bool | str = "",
    ) -> SetupAnswers:
        return SetupAnswers(
            tax_id="B66012345",
            activity="Software development",
            entity_type=EntityType.LEGAL_ENTITY,
            legal_entity_form=LegalEntityForm.SL,
            new_entity_first_two_profit_periods=new_entity,
        )

    def test_undeclared_new_entity_state_drops_from_canonical_dict(self) -> None:
        """Blank ``new_entity_first_two_profit_periods`` produces an empty
        canonical token; the persistence-layer ``if value`` filter then
        drops the fact, so a profile that never positively declared the
        override does not carry the fact in storage."""

        answers = self._legal_entity_answers(new_entity="")
        canonical = serialise_answers(SETUP_FLOW, answers)
        assert canonical.get("taxpayer_type.new_entity_first_two_profit_periods") == ""

    def test_declared_true_round_trips_through_canonical_dict(self) -> None:
        answers = self._legal_entity_answers(new_entity=True)
        canonical = serialise_answers(SETUP_FLOW, answers)
        assert canonical["taxpayer_type.new_entity_first_two_profit_periods"] == "true"

        rebuilt = project_answers(SETUP_FLOW, canonical)
        assert isinstance(rebuilt, SetupAnswers)
        assert rebuilt.new_entity_first_two_profit_periods is True

    def test_declared_false_round_trips_through_canonical_dict(self) -> None:
        answers = self._legal_entity_answers(new_entity=False)
        canonical = serialise_answers(SETUP_FLOW, answers)
        assert canonical["taxpayer_type.new_entity_first_two_profit_periods"] == "false"

        rebuilt = project_answers(SETUP_FLOW, canonical)
        assert isinstance(rebuilt, SetupAnswers)
        assert rebuilt.new_entity_first_two_profit_periods is False

    def test_taxpayer_profile_projects_absent_fact_to_none(self) -> None:
        """The downstream TaxpayerProfile projection treats an absent
        fact as the undeclared three-state, not as declared-False.

        This is the assertion that would have surfaced BLOCKER 1: the
        scripted ``--quiet`` legal-entity create with no flag must
        not materialise a ``"false"`` token in the canonical dict, and
        the projection must read absent → ``None``.
        """

        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "B66012345",
                "activities.description": "Software development",
                "taxpayer_type.entity_type": "legal_entity",
                "taxpayer_type.legal_entity_form": "sl",
            },
            tax_id_default="00000000T",
        )
        assert profile.new_entity_first_two_profit_periods is None

    def test_taxpayer_profile_projects_declared_true_to_true(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "B66012345",
                "activities.description": "Software development",
                "taxpayer_type.entity_type": "legal_entity",
                "taxpayer_type.legal_entity_form": "sl",
                "taxpayer_type.new_entity_first_two_profit_periods": "true",
            },
            tax_id_default="00000000T",
        )
        assert profile.new_entity_first_two_profit_periods is True

    def test_taxpayer_profile_projects_declared_false_to_false(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "B66012345",
                "activities.description": "Software development",
                "taxpayer_type.entity_type": "legal_entity",
                "taxpayer_type.legal_entity_form": "sl",
                "taxpayer_type.new_entity_first_two_profit_periods": "false",
            },
            tax_id_default="00000000T",
        )
        assert profile.new_entity_first_two_profit_periods is False

    def test_full_wizard_runtime_quiet_path_preserves_undeclared(self) -> None:
        """End-to-end through the scripted flow-substrate walk with no
        positively-declared CONFIRM answer for the new-entity flag.

        Exercises the exact code path that BLOCKER 1 broke: the
        ``--quiet`` scripted walk feeds ``question.default or ""``
        for any question the operator did not name. With the
        descriptor's stale ``default="false"`` removed and
        ``validate_confirm`` accepting blank for optional questions,
        the canonical dict must not carry the new-entity key at all,
        and the projection must reload at ``None``.
        """

        from ..commands import _run_scripted_walk

        # The scripted walk is driven by a sparse canonical dict; every
        # visible question falls back to its descriptor default (or
        # blank). The required-flag tax-id and activity must be seeded
        # explicitly — they are unconditionally required.
        canonical: dict[str, str] = {
            "tax-id": "B66012345",
            "activity": "Software development",
            "entity-type": "legal_entity",
            "legal-entity-form": "sl",
            "tax-residence-jurisdiction-scope": "common_regime",
            "iva-regime": "GENERAL",
            "iva-m303-regime-composition": "general",
            "iva-redeme-enrolled": "false",
            "iva-cash-accounting-regime-enrolled": "false",
            "iva-voluntary-sii-enrolled": "false",
            "iva-hydrocarbon-deposit-advance-payment-deduction-entitled": "false",
        }
        answers = _run_scripted_walk(
            SETUP_FLOW,
            canonical,
            mode="create",
            explicit_question_ids=frozenset(),
        )
        assert isinstance(answers, SetupAnswers)

        # The new-entity field stays at the undeclared sentinel; never
        # collapses onto False because the operator never declared it.
        assert answers.new_entity_first_two_profit_periods == ""

        # Serialise; the canonical dict drops the undeclared field at
        # the ``if value`` persistence filter ⇒ blank canonical token.
        serialised = serialise_answers(SETUP_FLOW, answers)
        assert serialised.get("taxpayer_type.new_entity_first_two_profit_periods") == ""

        # Filter blanks and the wizard's undeclared IVA defaults before
        # projecting the deadline-layer TaxpayerProfile. Those ``false``
        # tokens are not declared IVA block facts in this scenario.
        persisted = {key: value for key, value in serialised.items() if value and not key.startswith("iva.")}
        assert "taxpayer_type.new_entity_first_two_profit_periods" not in persisted
        profile = taxpayer_profile_from_mapping(
            persisted,
            tax_id_default="00000000T",
        )
        assert profile.new_entity_first_two_profit_periods is None
        assert profile.iva is None


class TestLey49SpecialRegimeRoundTrip:
    """The Ley 49/2002 Title II option axis survives wizard persistence."""

    def _answers(
        self,
        *,
        option_declared: bool | str = "",
        option_date: str = "",
        renunciation_declared: bool | str = "",
        renunciation_date: str = "",
    ) -> SetupAnswers:
        return SetupAnswers(
            tax_id="G66012345",
            activity="Foundation activity",
            entity_type=EntityType.LEGAL_ENTITY,
            legal_entity_form=LegalEntityForm.SIN_FINES_LUCRATIVOS,
            ley_49_2002_option_declared=option_declared,
            ley_49_2002_option_date=option_date,
            ley_49_2002_renunciation_declared=renunciation_declared,
            ley_49_2002_renunciation_date=renunciation_date,
        )

    def test_declared_option_and_renunciation_round_trip_through_canonical_dict(self) -> None:
        answers = self._answers(
            option_declared=True,
            option_date="2024-02-03",
            renunciation_declared=False,
            renunciation_date="2026-05-11",
        )
        canonical = serialise_answers(SETUP_FLOW, answers)

        assert canonical["taxpayer_type.ley_49_2002_special_regime_option_declared"] == "true"
        assert canonical["taxpayer_type.ley_49_2002_special_regime_option_date"] == "2024-02-03"
        assert canonical["taxpayer_type.ley_49_2002_special_regime_renunciation_declared"] == "false"
        assert canonical["taxpayer_type.ley_49_2002_special_regime_renunciation_date"] == "2026-05-11"

        rebuilt = project_answers(SETUP_FLOW, canonical)
        assert isinstance(rebuilt, SetupAnswers)
        assert rebuilt.ley_49_2002_option_declared is True
        assert rebuilt.ley_49_2002_option_date == "2024-02-03"
        assert rebuilt.ley_49_2002_renunciation_declared is False
        assert rebuilt.ley_49_2002_renunciation_date == "2026-05-11"

    def test_undeclared_ley_49_option_state_drops_from_canonical_dict(self) -> None:
        answers = self._answers()
        canonical = serialise_answers(SETUP_FLOW, answers)

        assert canonical.get("taxpayer_type.ley_49_2002_special_regime_option_declared") == ""
        assert canonical.get("taxpayer_type.ley_49_2002_special_regime_option_date") == ""
        assert canonical.get("taxpayer_type.ley_49_2002_special_regime_renunciation_declared") == ""
        assert canonical.get("taxpayer_type.ley_49_2002_special_regime_renunciation_date") == ""

        persisted = {key: value for key, value in canonical.items() if value and not key.startswith("iva.")}
        profile = taxpayer_profile_from_mapping(persisted, tax_id_default="00000000T")
        assert profile.ley_49_2002_special_regime_option_declared is None
        assert profile.ley_49_2002_special_regime_option_date is None
        assert profile.ley_49_2002_special_regime_renunciation_declared is None
        assert profile.ley_49_2002_special_regime_renunciation_date is None
        assert profile.iva is None

    def test_taxpayer_profile_projects_declared_ley_49_option_facts(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "G66012345",
                "activities.description": "Foundation activity",
                "taxpayer_type.entity_type": "legal_entity",
                "taxpayer_type.legal_entity_form": "sin_fines_lucrativos",
                "taxpayer_type.ley_49_2002_special_regime_option_declared": "true",
                "taxpayer_type.ley_49_2002_special_regime_option_date": "2024-02-03",
                "taxpayer_type.ley_49_2002_special_regime_renunciation_declared": "false",
                "taxpayer_type.ley_49_2002_special_regime_renunciation_date": "2026-05-11",
            },
            tax_id_default="00000000T",
        )

        assert profile.ley_49_2002_special_regime_option_declared is True
        assert str(profile.ley_49_2002_special_regime_option_date) == "2024-02-03"
        assert profile.ley_49_2002_special_regime_renunciation_declared is False
        assert str(profile.ley_49_2002_special_regime_renunciation_date) == "2026-05-11"
