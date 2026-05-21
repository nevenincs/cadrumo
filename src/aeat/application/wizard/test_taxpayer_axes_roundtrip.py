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

from ...domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
    taxpayer_profile_from_mapping,
)
from ._catalogue import SETUP_FLOW
from ._persistence import project_answers, serialise_answers
from ._setup_answers import SetupAnswers

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _fully_populated_answers() -> SetupAnswers:
    """A SetupAnswers with every W01 taxpayer-axis field non-default."""

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
        assert canonical["taxpayer_type.irpf_income_categories"] == (
            "trabajo,capital_inmobiliario,pension"
        )
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
            {IrpfIncomeCategory.CAPITAL_INMOBILIARIO, IrpfIncomeCategory.PENSION}
        )
        assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA
        assert profile.iva_regime is IVARegime.REAGP
        assert profile.iva.sii_enrolled is True
        assert profile.iva.redeme_enrolled is True

    def test_objetiva_regime_derives_objective_estimation_boolean(self) -> None:
        """The projection keeps uses_objective_estimation_irpf consistent.

        An OBJETIVA estimation regime from the wizard must derive the
        legacy boolean the registry schedule predicates still test.
        """

        profile = taxpayer_profile_from_mapping(
            {
                "identity.tax_id": "12345678Z",
                "activities.description": "Modulos activity",
                "irpf.estimation_regime": "objetiva",
            },
            tax_id_default="00000000T",
        )
        assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA
        assert profile.uses_objective_estimation_irpf is True

    def test_undeclared_axes_project_to_safe_empty_defaults(self) -> None:
        """A profile with no taxpayer-axis facts projects to undeclared.

        The W01 schema is data-only — the engine still behaves as
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
