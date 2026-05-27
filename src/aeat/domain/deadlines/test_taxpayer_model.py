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
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
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


class TestImpatriado:
    """SCHEMA-001: IMPATRIADO requires special_regime_start_date."""

    def test_impatriado_without_start_date_is_rejected(self) -> None:
        """Constructing IMPATRIADO without a start date raises ValidationError.

        This enforces the Art. 93 / RIRPF Art. 116 requirement that the
        election date is known so beckham_window_active can compute the
        6-year expiry. A missing date must surface immediately at construction,
        not silently default.
        """

        with pytest.raises(ValidationError, match=r"special_regime_start_date is required"):
            TaxpayerProfile(
                tax_id="X1234567L",
                entity_type=EntityType.NATURAL_PERSON,
                iva_regime=IVARegime.GENERAL,
                irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
                # special_regime_start_date intentionally omitted
            )

    def test_impatriado_with_start_date_is_accepted(self) -> None:
        """IMPATRIADO with a start date is a valid profile."""

        from datetime import date

        profile = TaxpayerProfile(
            tax_id="X1234567L",
            entity_type=EntityType.NATURAL_PERSON,
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
            special_regime_start_date=date(2023, 1, 15),
        )
        assert profile.irpf_special_regime is IrpfSpecialRegime.IMPATRIADO
        assert profile.special_regime_start_date == date(2023, 1, 15)

    def test_general_regime_without_start_date_is_accepted(self) -> None:
        """General-regime profile with no start date is fine — the validator
        only fires for IMPATRIADO."""

        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=IrpfSpecialRegime.GENERAL,
        )
        assert profile.special_regime_start_date is None

    def test_none_regime_without_start_date_is_accepted(self) -> None:
        """A profile with no special-regime declaration accepts no start date."""

        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
        )
        assert profile.irpf_special_regime is None
        assert profile.special_regime_start_date is None

    def test_impatriado_roundtrip_preserves_start_date(self) -> None:
        """IMPATRIADO + start_date survive the pydantic dict cycle unchanged.

        The non-default election date (2023-01-15) ensures a
        save-drops-field / load-re-defaults-field regression surfaces as
        strict inequality rather than passing silently.

        Dict roundtrip (model_dump / model_validate) preserves Python date
        objects; JSON roundtrip is unsuitable because strict=True rejects
        ISO strings for date fields.
        """

        from datetime import date

        original = TaxpayerProfile(
            tax_id="X1234567L",
            entity_type=EntityType.NATURAL_PERSON,
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
            special_regime_start_date=date(2023, 1, 15),
        )
        restored = TaxpayerProfile.model_validate(original.model_dump())
        assert restored == original

    def test_anti_tautology_dropping_start_date_breaks_equality(self) -> None:
        """Dropping special_regime_start_date from the dict payload raises
        a validation error — confirming the roundtrip gate is functional.

        SCHEMA-001 validator fires and rejects the reload with IMPATRIADO
        but no start_date, which is the exact regression the guard prevents.
        """

        from datetime import date

        original = TaxpayerProfile(
            tax_id="X1234567L",
            entity_type=EntityType.NATURAL_PERSON,
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
            special_regime_start_date=date(2023, 1, 15),
        )
        payload = original.model_dump()
        del payload["special_regime_start_date"]
        # SCHEMA-001 validator rejects IMPATRIADO without start_date.
        with pytest.raises(ValidationError, match=r"special_regime_start_date is required"):
            TaxpayerProfile.model_validate(payload)


class TestBeckhamWindow:
    """WINDOW-001: beckham_window_active oracle tests (RIRPF Art. 116.1).

    Window = start_date.year <= today.year <= start_date.year + 5.
    Election year 2023 → window 2023-2028 inclusive; 2029 is year 7 = expired.
    """

    def _impatriado(self) -> TaxpayerProfile:
        from datetime import date

        return TaxpayerProfile(
            tax_id="X1234567L",
            entity_type=EntityType.NATURAL_PERSON,
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
            special_regime_start_date=date(2023, 1, 15),
        )

    def test_election_year_is_within_window(self) -> None:
        from datetime import date

        assert self._impatriado().beckham_window_active(date(2023, 6, 1)) is True

    def test_year_five_is_within_window(self) -> None:
        from datetime import date

        assert self._impatriado().beckham_window_active(date(2027, 12, 31)) is True

    def test_year_six_is_within_window(self) -> None:
        from datetime import date

        assert self._impatriado().beckham_window_active(date(2028, 12, 31)) is True

    def test_year_seven_is_outside_window(self) -> None:
        from datetime import date

        assert self._impatriado().beckham_window_active(date(2029, 1, 1)) is False

    def test_year_before_election_is_outside_window(self) -> None:
        from datetime import date

        assert self._impatriado().beckham_window_active(date(2022, 12, 31)) is False

    def test_general_regime_profile_is_always_outside_window(self) -> None:
        from datetime import date

        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=IrpfSpecialRegime.GENERAL,
        )
        assert profile.beckham_window_active(date(2026, 5, 27)) is False

    def test_profile_without_special_regime_is_always_outside_window(self) -> None:
        from datetime import date

        profile = TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)
        assert profile.beckham_window_active(date(2026, 5, 27)) is False


class TestNonResidentAxis:
    """IRNR-001: fiscal_residency / country_of_fiscal_residence axis.

    TRLIRNR RDLeg 5/2004 Art. 2 defines non-residency; this class asserts
    the validator, the ue_eee_status property, and the roundtrip contract.
    """

    def test_non_resident_without_country_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"country_of_fiscal_residence is required"):
            TaxpayerProfile(
                tax_id="X1234567L",
                iva_regime=IVARegime.GENERAL,
                fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
                country_of_fiscal_residence=None,
            )

    def test_non_resident_with_country_is_accepted(self) -> None:
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="GB",
        )
        assert profile.fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR
        assert profile.country_of_fiscal_residence == "GB"

    def test_ue_eee_status_true_for_eu_member(self) -> None:
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="FR",
        )
        assert profile.ue_eee_status is True

    def test_ue_eee_status_false_for_gb_post_brexit(self) -> None:
        # GB left the EU/EEA on 2020-12-31; the authoritative set excludes it.
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="GB",
        )
        assert profile.ue_eee_status is False

    def test_ue_eee_status_false_when_country_none(self) -> None:
        profile = TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)
        assert profile.ue_eee_status is False

    def test_non_resident_roundtrip_preserves_fiscal_residency_and_country(self) -> None:
        original = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="DE",
        )
        restored = TaxpayerProfile.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_anti_tautology_dropping_country_breaks_when_non_resident(self) -> None:
        # Verify the anti-tautology contract: removing country_of_fiscal_residence
        # from a NON_RESIDENT_IRNR payload must surface as a ValidationError.
        original = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="IT",
        )
        payload = json.loads(original.model_dump_json())
        del payload["country_of_fiscal_residence"]
        with pytest.raises(ValidationError, match=r"country_of_fiscal_residence is required"):
            TaxpayerProfile.model_validate_json(json.dumps(payload))
