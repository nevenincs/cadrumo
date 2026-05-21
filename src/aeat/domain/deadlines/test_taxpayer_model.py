"""Roundtrip and anti-tautology tests for the three-axis taxpayer model.

Covers the entity-type, IRPF income-category, tax-regime, and
special-enrolment fields added to :class:`TaxpayerProfile`. Each new
typed field is populated with a non-default value, pushed through the
real pydantic JSON persistence cycle, and asserted equal with strict
model equality. The anti-tautology proofs delete or mutate a field in
the on-disk payload and assert the drift surfaces.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from . import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
    ModeloIVAProfile,
    TaxpayerProfile,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _fully_populated_taxpayer() -> TaxpayerProfile:
    """A TaxpayerProfile with every W01 axis set to a non-default value.

    entity_type, legal_entity_form, irpf_income_categories,
    irpf_estimation_regime, iva_regime (REAGP, the new member), and the
    sii_enrolled / redeme_enrolled enrolment flags are all non-default
    so a save-drops-field / load-re-defaults-field regression surfaces
    as model inequality.
    """

    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.COOPERATIVA,
        irpf_income_categories=frozenset(
            {
                IrpfIncomeCategory.CAPITAL_INMOBILIARIO,
                IrpfIncomeCategory.PENSION,
                IrpfIncomeCategory.TRABAJO,
            }
        ),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
        iva_regime=IVARegime.REAGP,
        iva=ModeloIVAProfile(
            roi_enrolled=True,
            oss_enrolled=True,
            sii_enrolled=True,
            redeme_enrolled=True,
            intracommunity_operations_exceed_50000_eur=True,
        ),
    )


class TestTaxpayerModelRoundTrip:
    """The new typed axes survive a strict pydantic JSON roundtrip."""

    def test_every_new_axis_round_trips_with_strict_equality(self) -> None:
        original = _fully_populated_taxpayer()
        restored = TaxpayerProfile.model_validate_json(original.model_dump_json())
        assert restored == original
        # Spot-check each axis explicitly so a regression names the axis.
        assert restored.entity_type is EntityType.LEGAL_ENTITY
        assert restored.legal_entity_form is LegalEntityForm.COOPERATIVA
        assert restored.irpf_income_categories == frozenset(
            {
                IrpfIncomeCategory.CAPITAL_INMOBILIARIO,
                IrpfIncomeCategory.PENSION,
                IrpfIncomeCategory.TRABAJO,
            }
        )
        assert restored.irpf_estimation_regime is IrpfEstimationRegime.DIRECTA_SIMPLIFICADA
        assert restored.iva_regime is IVARegime.REAGP
        assert restored.iva.sii_enrolled is True
        assert restored.iva.redeme_enrolled is True

    def test_objetiva_regime_round_trips_with_derived_objective_boolean(self) -> None:
        """An OBJETIVA regime derives uses_objective_estimation_irpf and survives."""

        original = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.SIMPLIFICADO,
            irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        )
        assert original.uses_objective_estimation_irpf is True
        restored = TaxpayerProfile.model_validate_json(original.model_dump_json())
        assert restored == original
        assert restored.uses_objective_estimation_irpf is True
        assert restored.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA


class TestObjectiveEstimationConsistency:
    """The legacy objective-estimation boolean stays in lockstep with the regime."""

    def test_objetiva_regime_forces_objective_boolean_true(self) -> None:
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        )
        assert profile.uses_objective_estimation_irpf is True

    def test_directa_regime_keeps_objective_boolean_false(self) -> None:
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        )
        assert profile.uses_objective_estimation_irpf is False

    def test_undeclared_regime_leaves_legacy_boolean_untouched(self) -> None:
        """An undeclared regime keeps an explicit legacy boolean working.

        Existing profiles that set only uses_objective_estimation_irpf
        must keep resolving until the engine reads the enum directly.
        """

        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            uses_objective_estimation_irpf=True,
        )
        assert profile.irpf_estimation_regime is None
        assert profile.uses_objective_estimation_irpf is True

    def test_contradictory_regime_and_boolean_are_rejected(self) -> None:
        """A non-objective regime with a True objective boolean is rejected."""

        with pytest.raises(ValidationError, match=r"contradicts uses_objective_estimation"):
            TaxpayerProfile(
                tax_id="X1234567L",
                iva_regime=IVARegime.GENERAL,
                irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
                uses_objective_estimation_irpf=True,
            )


class TestTaxpayerModelAntiTautology:
    """Mutating or dropping a new field in the payload surfaces on reload."""

    def test_dropped_enrolment_field_re_defaults_and_surfaces_inequality(self) -> None:
        """Deleting sii_enrolled from the payload makes the reload differ.

        If this test passed with the field deleted, the roundtrip would
        be tautological — a save-drops-field regression would be
        invisible.
        """

        original = _fully_populated_taxpayer()
        payload = json.loads(original.model_dump_json())
        del payload["iva"]["sii_enrolled"]
        reloaded = TaxpayerProfile.model_validate_json(json.dumps(payload))
        # The dropped field silently re-defaults to False.
        assert reloaded.iva.sii_enrolled is False
        # Strict equality therefore breaks — the proof the roundtrip bites.
        assert reloaded != original

    def test_mutated_income_category_surfaces_inequality(self) -> None:
        """Swapping an income-category token in the payload breaks equality."""

        original = _fully_populated_taxpayer()
        payload = json.loads(original.model_dump_json())
        payload["irpf_income_categories"] = [IrpfIncomeCategory.ACTIVIDAD_ECONOMICA.value]
        reloaded = TaxpayerProfile.model_validate_json(json.dumps(payload))
        assert reloaded.irpf_income_categories != original.irpf_income_categories
        assert reloaded != original

    def test_unknown_income_category_token_is_rejected(self) -> None:
        """An income-category token outside the closed set is rejected."""

        original = _fully_populated_taxpayer()
        payload = json.loads(original.model_dump_json())
        payload["irpf_income_categories"] = ["not_a_real_category"]
        with pytest.raises(ValidationError):
            TaxpayerProfile.model_validate_json(json.dumps(payload))

    def test_unknown_entity_type_token_is_rejected(self) -> None:
        """An entity-type token outside the closed set is rejected."""

        original = _fully_populated_taxpayer()
        payload = json.loads(original.model_dump_json())
        payload["entity_type"] = "alien_lifeform"
        with pytest.raises(ValidationError):
            TaxpayerProfile.model_validate_json(json.dumps(payload))
