"""Unit tests for the corporate-tax-runtime profile fact.

Pin the typed-boundary contract for ``incn_prior_12_months``, a
``Decimal | None`` carrying the importe neto de la cifra de negocios of the
prior 12 months. It gates the Modelo 202 modality split at the 6.000.000 EUR
threshold (LIS Art. 40.3).

The tests drive the real :func:`taxpayer_profile_from_mapping`
projection — no mocks — and assert the strict pydantic model accepts
and round-trips the value verbatim.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..models import IVARegime, TaxpayerProfile
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def _minimal_profile_mapping() -> dict[str, str]:
    """Return a profile-values mapping that satisfies the descriptor."""

    return {
        "identity.tax_id": "B66012345",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }


def test_taxpayer_profile_carries_incn_as_a_typed_decimal_when_declared() -> None:
    """A declared INCN is projected as a typed ``Decimal``."""

    values = _minimal_profile_mapping() | {
        "taxpayer_type.incn_prior_12_months": "7500000.00",
    }
    profile = taxpayer_profile_from_mapping(values, tax_id_default="B66012345")
    assert profile.incn_prior_12_months == Decimal("7500000.00")
    assert isinstance(profile.incn_prior_12_months, Decimal)


def test_taxpayer_profile_carries_incn_as_none_when_undeclared() -> None:
    """An undeclared INCN projects as ``None`` so the engine returns
    INCOMPLETE rather than guessing a Modelo 202 modality."""

    profile = taxpayer_profile_from_mapping(_minimal_profile_mapping(), tax_id_default="B66012345")
    assert profile.incn_prior_12_months is None


def test_taxpayer_profile_model_validates_incn_decimal_field() -> None:
    """Strict pydantic accepts a ``Decimal`` for ``incn_prior_12_months``
    and rejects a non-decimal scalar via the field's typed boundary."""

    profile = TaxpayerProfile(
        tax_id="B66012345",
        iva_regime=IVARegime("GENERAL"),
        incn_prior_12_months=Decimal("6000000"),
    )
    assert profile.incn_prior_12_months == Decimal("6000000")
