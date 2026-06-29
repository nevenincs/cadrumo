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
from ....domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
    taxpayer_profile_from_mapping,
)
from .._catalogue import SETUP_FLOW
from .._persistence import project_answers, serialise_answers

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
        iva_sii_enrolled=True,
        iva_redeme_enrolled=True,
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
        assert rebuilt.iva_sii_enrolled == original.iva_sii_enrolled
        assert rebuilt.iva_redeme_enrolled == original.iva_redeme_enrolled

    def test_canonical_dict_carries_taxpayer_axis_profile_keys(self) -> None:
        canonical = serialise_answers(SETUP_FLOW, _fully_populated_answers())
        assert canonical["taxpayer_type.entity_type"] == "natural_person"
        assert canonical["taxpayer_type.irpf_income_categories"] == ("trabajo,capital_inmobiliario,pension")
        assert canonical["irpf.estimation_regime"] == "directa_simplificada"
        assert canonical["iva.sii_enrolled"] == "true"
        assert canonical["iva.redeme_enrolled"] == "true"

    def test_dropped_enrolment_key_re_defaults_on_reprojection(self) -> None:
        """Anti-tautology: removing iva.sii_enrolled re-defaults the field.

        If the roundtrip were tautological, the dropped key would not
        change the reprojected answers and a save-drops-field
        regression would be invisible.
        """

        original = _fully_populated_answers()
        canonical = serialise_answers(SETUP_FLOW, original)
        del canonical["iva.sii_enrolled"]
        rebuilt = project_answers(SETUP_FLOW, canonical)
        assert isinstance(rebuilt, SetupAnswers)
        assert rebuilt.iva_sii_enrolled is False
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
                "iva.regime": "REAGP",
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
        assert profile.iva_regime is IVARegime.REAGP
        assert profile.iva.sii_enrolled is True
        assert profile.iva.redeme_enrolled is True

    def test_mapping_projection_carries_cross_period_group_roster(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "12345678Z",
                "activities.description": "Grupo IVA",
                "cross_period.group_member_roster.322.2026.12": "B00000001, A00000000",
                "iva_grupo.member_roster.2026.11": "C00000002;D00000003",
            },
            tax_id_default="00000000T",
        )

        assert [item.source_modelo for item in profile.cross_period_group_member_rosters] == ["322", "322"]
        assert [item.filing_year for item in profile.cross_period_group_member_rosters] == [2026, 2026]
        assert [item.period.registry_token for item in profile.cross_period_group_member_rosters] == ["11", "12"]
        assert profile.cross_period_group_member_rosters[0].member_nifs == ("C00000002", "D00000003")
        assert profile.cross_period_group_member_rosters[1].member_nifs == ("A00000000", "B00000001")

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
        assert profile.iva.sii_enrolled is False
        assert profile.iva.redeme_enrolled is False


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
        """End-to-end through ``run_flow`` with the scripted prompter and
        no positively-declared CONFIRM answer for the new-entity flag.

        Exercises the exact code path that BLOCKER 1 broke: the
        ``--quiet`` scripted prompter feeds ``question.default or ""``
        for any question the operator did not name. With the
        descriptor's stale ``default="false"`` removed and
        ``validate_confirm`` accepting blank for optional questions,
        the canonical dict must not carry the new-entity key at all,
        and the projection must reload at ``None``.
        """

        from .._commands import _scripted_from_canonical
        from .._runner import run_flow

        # The scripted prompter is driven by an empty canonical dict;
        # every visible question falls back to its descriptor default
        # (or blank). The required-flag tax-id and activity must be
        # seeded explicitly — they are unconditionally required.
        canonical: dict[str, str] = {
            "tax-id": "B66012345",
            "activity": "Software development",
            "entity-type": "legal_entity",
            "legal-entity-form": "sl",
        }
        prompter = _scripted_from_canonical(SETUP_FLOW, canonical)
        answers = run_flow(SETUP_FLOW, prompter)
        assert isinstance(answers, SetupAnswers)

        # The new-entity field stays at the undeclared sentinel; never
        # collapses onto False because the operator never declared it.
        assert answers.new_entity_first_two_profit_periods == ""

        # Serialise; the canonical dict drops the undeclared field at
        # the ``if value`` persistence filter ⇒ blank canonical token.
        serialised = serialise_answers(SETUP_FLOW, answers)
        assert serialised.get("taxpayer_type.new_entity_first_two_profit_periods") == ""

        # Filter blanks the way ``persist_answers`` does for create,
        # then project the deadline-layer TaxpayerProfile.
        persisted = {key: value for key, value in serialised.items() if value}
        assert "taxpayer_type.new_entity_first_two_profit_periods" not in persisted
        profile = taxpayer_profile_from_mapping(
            persisted,
            tax_id_default="00000000T",
        )
        assert profile.new_entity_first_two_profit_periods is None
