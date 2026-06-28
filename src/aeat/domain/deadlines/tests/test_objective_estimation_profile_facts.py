from __future__ import annotations

from decimal import Decimal

import pytest

from .. import IrpfEstimationRegime, IVARegime, TaxpayerProfile, taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_taxpayer_profile_projects_objective_estimation_exclusion_volumes() -> None:
    profile = taxpayer_profile_from_mapping(
        {
            "identity.tax_id": "X1234567L",
            "iva.regime": "GENERAL",
            "irpf.estimation_regime": "objetiva",
            "irpf.objective_estimation_prior_year_gross_income_eur": "250000.01",
            "irpf.objective_estimation_prior_year_invoice_gross_income_eur": "125000.01",
            "irpf.objective_estimation_prior_year_purchases_eur": "250000.01",
        },
        tax_id_default="X1234567L",
    )

    assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA
    assert profile.objective_estimation_prior_year_gross_income_eur == Decimal("250000.01")
    assert profile.objective_estimation_prior_year_invoice_gross_income_eur == Decimal("125000.01")
    assert profile.objective_estimation_prior_year_purchases_eur == Decimal("250000.01")


def test_taxpayer_profile_round_trips_objective_estimation_exclusion_volumes() -> None:
    original = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        objective_estimation_prior_year_gross_income_eur=Decimal("250000.01"),
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("125000.01"),
        objective_estimation_prior_year_purchases_eur=Decimal("250000.01"),
    )

    restored = TaxpayerProfile.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.objective_estimation_prior_year_gross_income_eur == Decimal("250000.01")
    assert restored.objective_estimation_prior_year_invoice_gross_income_eur == Decimal("125000.01")
    assert restored.objective_estimation_prior_year_purchases_eur == Decimal("250000.01")
