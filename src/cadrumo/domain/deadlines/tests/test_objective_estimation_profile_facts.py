from __future__ import annotations

from decimal import Decimal

import pytest

from ..models import IrpfEstimationRegime, IVARegime, TaxpayerProfile
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_taxpayer_profile_projects_objective_estimation_exclusion_volumes() -> None:
    profile = taxpayer_profile_from_mapping(
        {
            "identity.tax_id": "X1234567L",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            "irpf.estimation_regime": "objetiva",
            "irpf.objective_estimation_prior_year_gross_income_eur": "250000.01",
            "irpf.objective_estimation_prior_year_invoice_gross_income_eur": "125000.01",
            "irpf.objective_estimation_prior_year_agri_livestock_forest_gross_eur": "250000.01",
            "irpf.objective_estimation_prior_year_purchases_eur": "250000.01",
        },
        tax_id_default="X1234567L",
    )

    assert profile.irpf_estimation_regime == IrpfEstimationRegime.from_registry("objetiva")
    assert profile.objective_estimation_prior_year_gross_income_eur == Decimal("250000.01")
    assert profile.objective_estimation_prior_year_invoice_gross_income_eur == Decimal("125000.01")
    assert profile.objective_estimation_prior_year_agri_livestock_forest_gross_eur == Decimal(
        "250000.01",
    )
    assert profile.objective_estimation_prior_year_purchases_eur == Decimal("250000.01")


def test_taxpayer_profile_round_trips_objective_estimation_exclusion_volumes() -> None:
    original = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime("GENERAL"),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("objetiva"),
        objective_estimation_prior_year_gross_income_eur=Decimal("250000.01"),
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("125000.01"),
        objective_estimation_prior_year_agri_livestock_forest_gross_eur=Decimal("250000.01"),
        objective_estimation_prior_year_purchases_eur=Decimal("250000.01"),
    )

    restored = TaxpayerProfile.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.objective_estimation_prior_year_gross_income_eur == Decimal("250000.01")
    assert restored.objective_estimation_prior_year_invoice_gross_income_eur == Decimal("125000.01")
    assert restored.objective_estimation_prior_year_agri_livestock_forest_gross_eur == Decimal(
        "250000.01",
    )
    assert restored.objective_estimation_prior_year_purchases_eur == Decimal("250000.01")
