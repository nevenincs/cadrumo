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
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.aggregation import ThirdPartyDeclarationRole
from ...calculations.registry.applicability import derive_tax_route
from ...calculations.registry.applicability_routes import TaxRoute
from ..models import (
    CrossPeriodGroupMemberRoster,
    EntityType,
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
    evaluate_multiple_pagadores_obligation,
    resolve_multiple_pagadores_reduced_limit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _fully_populated_taxpayer() -> TaxpayerProfile:
    """A TaxpayerProfile with every taxpayer axis set to a non-default value.

    entity_type, legal_entity_form, irpf_income_categories,
    irpf_estimation_regime, iva_regime (REAGP, the new member), and the
    SII, REDEME, and IVA-group enrolment flags are all non-default so
    a save-drops-field / load-re-defaults-field regression surfaces as
    model inequality.
    """

    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        declaration_roles=frozenset({ThirdPartyDeclarationRole.THIRD_PARTY_FEE_COLLECTOR}),
        legal_entity_form=LegalEntityForm.COOPERATIVA,
        irpf_income_categories=frozenset(
            {
                IrpfIncomeCategory.CAPITAL_INMOBILIARIO,
                IrpfIncomeCategory.PENSION,
                IrpfIncomeCategory.TRABAJO,
            },
        ),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
        iva_regime=IVARegime.REAGP,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            roi_enrolled=True,
            oss_enrolled=True,
            group_member_enrolled=True,
            group_dominant_entity_enrolled=True,
            sii_enrolled=True,
            redeme_enrolled=True,
            intracommunity_operations_exceed_50000_eur=True,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
        cross_period_group_member_rosters=(
            CrossPeriodGroupMemberRoster(
                source_modelo="322",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "12"),
                member_nifs=("B00000000", "A00000000"),
            ),
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
        assert restored.declaration_roles == frozenset({ThirdPartyDeclarationRole.THIRD_PARTY_FEE_COLLECTOR})
        assert restored.legal_entity_form is LegalEntityForm.COOPERATIVA
        assert restored.irpf_income_categories == frozenset(
            {
                IrpfIncomeCategory.CAPITAL_INMOBILIARIO,
                IrpfIncomeCategory.PENSION,
                IrpfIncomeCategory.TRABAJO,
            },
        )
        assert restored.irpf_estimation_regime is IrpfEstimationRegime.DIRECTA_SIMPLIFICADA
        assert restored.iva_regime is IVARegime.REAGP
        iva = restored.iva
        assert iva is not None
        assert iva.group_member_enrolled is True
        assert iva.group_dominant_entity_enrolled is True
        assert iva.sii_enrolled is True
        assert iva.redeme_enrolled is True
        assert restored.cross_period_group_member_rosters == (
            CrossPeriodGroupMemberRoster(
                source_modelo="322",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "12"),
                member_nifs=("A00000000", "B00000000"),
            ),
        )

    def test_objetiva_regime_round_trips_as_structured_axis(self) -> None:
        """An OBJETIVA regime survives without a derived boolean side channel."""

        original = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.SIMPLIFICADO,
            irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        )
        restored = TaxpayerProfile.model_validate_json(original.model_dump_json())
        assert restored == original
        assert restored.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA


class TestObjectiveEstimationRegimeAxis:
    """Objective estimation is represented by the structured regime axis only."""

    def test_objetiva_regime_is_the_current_objective_estimation_signal(self) -> None:
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        )
        assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA

    def test_directa_regime_is_not_objective_estimation(self) -> None:
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        )
        assert profile.irpf_estimation_regime is IrpfEstimationRegime.DIRECTA_NORMAL

    def test_old_objective_estimation_boolean_is_rejected(self) -> None:
        """The retired objective-estimation boolean is no longer a profile input."""

        with pytest.raises(ValidationError, match=r"uses_objective_estimation_irpf"):
            TaxpayerProfile.model_validate(
                {
                    "tax_id": "X1234567L",
                    "iva_regime": IVARegime.GENERAL,
                    "uses_objective_estimation_irpf": True,
                },
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
        iva = reloaded.iva
        assert iva is not None
        assert iva.sii_enrolled is False
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
        return TaxpayerProfile(
            tax_id="X1234567L",
            entity_type=EntityType.NATURAL_PERSON,
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
            special_regime_start_date=date(2023, 1, 15),
        )

    def test_impatriado_window_boundaries(self) -> None:
        cases = (
            (date(2023, 6, 1), True),
            (date(2027, 12, 31), True),
            (date(2028, 12, 31), True),
            (date(2029, 1, 1), False),
            (date(2022, 12, 31), False),
        )
        profile = self._impatriado()
        for today, expected in cases:
            assert profile.beckham_window_active(today) is expected, today

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
        # GB is post-Brexit non-EU/EEA; representante fiscal required.
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="GB",
            representante_fiscal_nif="12345678Z",
            representante_fiscal_nombre="Test Representative",
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
        # GB left the EU/EEA on 2020-12-31; representante is required.
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="GB",
            representante_fiscal_nif="12345678Z",
            representante_fiscal_nombre="Test Representative",
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


class TestRepresentanteFiscalAxis:
    """IRNR-002: representante_fiscal_nif / representante_fiscal_nombre axis.

    Art. 47 LGT + Art. 10 TRLIRNR RDLeg 5/2004: non-EU/EEA non-residents
    must appoint a fiscal representative in Spain. This class asserts the
    validator, the roundtrip contract, and the anti-tautology proof.
    """

    def test_non_eu_non_resident_without_representante_is_rejected(self) -> None:
        # GB is outside EU/EEA post-Brexit; representative required.
        with pytest.raises(ValidationError, match=r"representante_fiscal_nif and representante_fiscal_nombre required"):
            TaxpayerProfile(
                tax_id="X1234567L",
                iva_regime=IVARegime.GENERAL,
                fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
                country_of_fiscal_residence="GB",
                representante_fiscal_nif=None,
                representante_fiscal_nombre=None,
            )

    def test_non_eu_non_resident_with_partial_representante_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"representante_fiscal_nombre required"):
            TaxpayerProfile(
                tax_id="X1234567L",
                iva_regime=IVARegime.GENERAL,
                fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
                country_of_fiscal_residence="GB",
                representante_fiscal_nif="12345678Z",
                representante_fiscal_nombre=None,
            )

    def test_non_eu_non_resident_with_full_representante_is_accepted(self) -> None:
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="GB",
            representante_fiscal_nif="12345678Z",
            representante_fiscal_nombre="John Smith",
        )
        assert profile.representante_fiscal_nif == "12345678Z"
        assert profile.representante_fiscal_nombre == "John Smith"

    def test_eu_non_resident_does_not_require_representante(self) -> None:
        # FR is EU — representative not required.
        profile = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="FR",
        )
        assert profile.representante_fiscal_nif is None
        assert profile.representante_fiscal_nombre is None

    def test_resident_irpf_does_not_require_representante(self) -> None:
        profile = TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)
        assert profile.representante_fiscal_nif is None
        assert profile.representante_fiscal_nombre is None

    def test_representante_roundtrip_preserves_fields(self) -> None:
        original = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="US",
            representante_fiscal_nif="87654321A",
            representante_fiscal_nombre="Jane Doe",
        )
        restored = TaxpayerProfile.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_anti_tautology_dropping_representante_nif_breaks_non_eu_non_resident(self) -> None:
        original = TaxpayerProfile(
            tax_id="X1234567L",
            iva_regime=IVARegime.GENERAL,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            country_of_fiscal_residence="US",
            representante_fiscal_nif="87654321A",
            representante_fiscal_nombre="Jane Doe",
        )
        payload = json.loads(original.model_dump_json())
        del payload["representante_fiscal_nif"]
        with pytest.raises(ValidationError, match=r"representante_fiscal_nif"):
            TaxpayerProfile.model_validate_json(json.dumps(payload))


class TestMultiplePagadoresObligation:
    """Art. 96.3 LIRPF filing obligation: >= 2 pagadores AND secondary income > 1500.

    Expected values derive from Art. 96.3 Ley 35/2006 (LIRPF) which establishes
    the 1,500 EUR threshold for secondary pagador income that triggers mandatory
    Modelo 100 filing.  No threshold values are hand-invented here.
    """

    def test_multiple_pagadores_threshold_cases(self) -> None:
        cases = (
            (1, Decimal("18000"), False),
            (2, Decimal("1600"), True),
            (3, Decimal("1600"), True),
            (2, Decimal("1500"), False),
            (2, Decimal("1500.01"), True),
            (2, Decimal("1499"), False),
            (None, Decimal("2000"), False),
            (2, None, False),
            (None, None, False),
        )
        for pagadores_count, secondary_income, expected in cases:
            assert evaluate_multiple_pagadores_obligation(pagadores_count, secondary_income) is expected, (
                pagadores_count,
                secondary_income,
            )

    def test_taxpayer_profile_roundtrip_pagadores_fields(self) -> None:
        # TaxpayerProfile must carry the pagadores axes through construction unchanged.
        profile = TaxpayerProfile(
            tax_id="12345678Z",
            iva_regime=IVARegime.GENERAL,
            irpf_pagadores_count=3,
            irpf_pagadores_secondary_income=Decimal("2000"),
            irpf_pagadores_total_work_income=Decimal("19000"),
        )
        assert profile.irpf_pagadores_count == 3
        assert profile.irpf_pagadores_secondary_income == Decimal("2000")
        assert profile.irpf_pagadores_total_work_income == Decimal("19000")

    def test_taxpayer_profile_pagadores_fields_default_none(self) -> None:
        # Existing profiles without pagadores fields must load cleanly.
        profile = TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)
        assert profile.irpf_pagadores_count is None
        assert profile.irpf_pagadores_secondary_income is None
        assert profile.irpf_pagadores_total_work_income is None


class TestMultiplePagadoresReducedLimitSchedule:
    """Art. 96.3 LIRPF per-year reduced work-income exemption limit.

    Expected values derive from the dated statutory schedule, not hand
    computation: 14.000 EUR base (Art. 96.3 LIRPF, post-Ley 26/2014),
    raised to 15.000 EUR for 2023 (Ley 31/2022 PGE-2023, BOE-A-2022-22128)
    and to 15.876 EUR for 2024 onward (RD-Ley 4/2024, BOE-A-2024-13066;
    confirmed by the bundled consolidated LIRPF art-96 corpus, "15.876
    euros").
    """

    def test_reduced_limit_schedule(self) -> None:
        cases = (
            (2022, Decimal("14000")),
            (2023, Decimal("15000")),
            (2024, Decimal("15876")),
            (2025, Decimal("15876")),
            (2015, Decimal("14000")),
            (2099, Decimal("15876")),
            (None, Decimal("15876")),
        )
        for year, expected in cases:
            assert resolve_multiple_pagadores_reduced_limit(year) == expected, year


class TestMultiplePagadoresObligationWithTotalIncome:
    """Art. 96.2.a)/96.3 LIRPF obligation: total income vs the applicable limit.

    The multiple-pagadores situation never obliges a filing by itself — it
    lowers the work-income exemption limit from the general 22.000 EUR to the
    per-year reduced limit. The obligation arises only when total work income
    exceeds the applicable reduced limit. Expected limits derive from the dated
    statutory schedule (see TestMultiplePagadoresReducedLimitSchedule); no
    threshold is hand-invented.
    """

    def test_total_income_obligation_cases(self) -> None:
        cases = (
            (2, Decimal("1600"), Decimal("18000"), 2024, True),
            (2, Decimal("1600"), Decimal("10000"), 2024, False),
            (2, Decimal("1600"), Decimal("16000"), 2024, True),
            (2, Decimal("1600"), Decimal("15500"), 2023, True),
            (2, Decimal("1600"), Decimal("15500"), 2024, False),
            (1, Decimal("0"), Decimal("18000"), 2024, False),
            (2, Decimal("1500"), Decimal("18000"), 2024, False),
            (2, Decimal("1600"), None, 2024, True),
        )
        for pagadores_count, secondary_income, total_income, year, expected in cases:
            assert (
                evaluate_multiple_pagadores_obligation(
                    pagadores_count,
                    secondary_income,
                    total_income,
                    year,
                )
                is expected
            ), (
                pagadores_count,
                secondary_income,
                total_income,
                year,
            )


class TestThirdPartyDeclarationRoleOrthogonality:
    """`ThirdPartyDeclarationRole` must never change the tax-selection consequence.

    `EntityType` selects the tax route (see :func:`derive_tax_route`); a
    Modelo 347 filer-role membership is a SEPARATE, coexisting fact. The
    proof is not merely that the two fields hold independent values -- it is
    that the actual tax-route DERIVATION a real consumer runs is unchanged
    by every possible role membership, singly and combined.
    """

    def test_every_role_combination_leaves_the_legal_entity_tax_route_unchanged(self) -> None:
        baseline = TaxpayerProfile(
            tax_id="B12345674",
            entity_type=EntityType.LEGAL_ENTITY,
            iva_regime=IVARegime.GENERAL,
        )
        assert derive_tax_route(baseline) is TaxRoute.IMPUESTO_SOCIEDADES

        all_roles = frozenset(ThirdPartyDeclarationRole)
        for role in (*ThirdPartyDeclarationRole, None):
            roles = all_roles if role is None else frozenset({role})
            colegio_profesional = TaxpayerProfile(
                tax_id="B12345674",
                entity_type=EntityType.LEGAL_ENTITY,
                iva_regime=IVARegime.GENERAL,
                declaration_roles=roles,
            )
            assert derive_tax_route(colegio_profesional) is TaxRoute.IMPUESTO_SOCIEDADES
            assert colegio_profesional.entity_type is EntityType.LEGAL_ENTITY

    def test_every_role_combination_leaves_the_natural_person_tax_route_unchanged(self) -> None:
        """The same proof for IRPF, so the axis is orthogonal on both routes it could distort."""
        all_roles = frozenset(ThirdPartyDeclarationRole)
        for role in (*ThirdPartyDeclarationRole, None):
            roles = all_roles if role is None else frozenset({role})
            profile = TaxpayerProfile(
                tax_id="12345678Z",
                entity_type=EntityType.NATURAL_PERSON,
                iva_regime=IVARegime.GENERAL,
                declaration_roles=roles,
            )
            assert derive_tax_route(profile) is TaxRoute.IRPF
