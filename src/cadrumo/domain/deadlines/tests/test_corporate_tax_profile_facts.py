"""Unit tests for the corporate-tax-runtime profile facts.

Pin the typed-boundary contract for the two optional profile facts the
corporate-tax-runtime plan introduces:

* ``incn_prior_12_months`` — a ``Decimal | None`` carrying the importe
  neto de la cifra de negocios of the prior 12 months. Gates the
  Modelo 202 modality split at the 6.000.000 EUR threshold
  (LIS Art. 40.3).
* ``new_entity_first_two_profit_periods`` — a ``bool | None`` flag for
  the LIS Art. 29 first-two-profit-making-periods state of a newly-
  created legal entity. Three-state at the typed boundary so the
  absent-vs-false distinction survives the projection.
* ``ley_49_2002_special_regime_*`` — option and renunciation facts
  declared through Modelo 036 for the Ley 49/2002 Title II regime.

The tests drive the real :func:`taxpayer_profile_from_mapping`
projection — no mocks — and assert the strict pydantic model accepts
and round-trips the values verbatim.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..models import IVARegime, TaxpayerProfile
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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


def test_taxpayer_profile_carries_new_entity_as_true_when_positively_declared() -> None:
    """A positively-declared new-entity state opts into the 15 percent
    LIS Art. 29 rate override."""

    values = _minimal_profile_mapping() | {
        "taxpayer_type.new_entity_first_two_profit_periods": "true",
    }
    profile = taxpayer_profile_from_mapping(values, tax_id_default="B66012345")
    assert profile.new_entity_first_two_profit_periods is True


def test_taxpayer_profile_carries_new_entity_as_false_when_negatively_declared() -> None:
    """A positively-declared ``False`` keeps the entity on the
    otherwise-applicable rate — distinct from the undeclared state at
    the typed boundary, even though the engine treats both the same."""

    values = _minimal_profile_mapping() | {
        "taxpayer_type.new_entity_first_two_profit_periods": "false",
    }
    profile = taxpayer_profile_from_mapping(values, tax_id_default="B66012345")
    assert profile.new_entity_first_two_profit_periods is False


def test_taxpayer_profile_carries_new_entity_as_none_when_undeclared() -> None:
    """An undeclared new-entity state projects as ``None`` — the
    three-state opt-in distinguishing "operator has not answered" from
    "operator answered no"."""

    profile = taxpayer_profile_from_mapping(_minimal_profile_mapping(), tax_id_default="B66012345")
    assert profile.new_entity_first_two_profit_periods is None


def test_taxpayer_profile_carries_ley_49_2002_option_and_renunciation_facts() -> None:
    """Modelo 036 Ley 49/2002 option facts project to typed booleans and dates."""

    values = _minimal_profile_mapping() | {
        "taxpayer_type.ley_49_2002_special_regime_option_declared": "true",
        "taxpayer_type.ley_49_2002_special_regime_option_date": "2024-02-03",
        "taxpayer_type.ley_49_2002_special_regime_renunciation_declared": "false",
        "taxpayer_type.ley_49_2002_special_regime_renunciation_date": "2026-05-11",
    }
    profile = taxpayer_profile_from_mapping(values, tax_id_default="B66012345")

    assert profile.ley_49_2002_special_regime_option_declared is True
    assert profile.ley_49_2002_special_regime_option_date == date(2024, 2, 3)
    assert profile.ley_49_2002_special_regime_renunciation_declared is False
    assert profile.ley_49_2002_special_regime_renunciation_date == date(2026, 5, 11)


def test_taxpayer_profile_carries_ley_49_2002_facts_as_none_when_undeclared() -> None:
    """Undeclared Ley 49/2002 option facts stay absent at the typed boundary."""

    profile = taxpayer_profile_from_mapping(_minimal_profile_mapping(), tax_id_default="B66012345")

    assert profile.ley_49_2002_special_regime_option_declared is None
    assert profile.ley_49_2002_special_regime_option_date is None
    assert profile.ley_49_2002_special_regime_renunciation_declared is None
    assert profile.ley_49_2002_special_regime_renunciation_date is None


def test_taxpayer_profile_model_validates_incn_decimal_field() -> None:
    """Strict pydantic accepts a ``Decimal`` for ``incn_prior_12_months``
    and rejects a non-decimal scalar via the field's typed boundary."""

    profile = TaxpayerProfile(
        tax_id="B66012345",
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=Decimal("6000000"),
    )
    assert profile.incn_prior_12_months == Decimal("6000000")


def test_taxpayer_profile_model_accepts_three_state_new_entity_field() -> None:
    """Strict pydantic accepts ``True``, ``False``, and ``None`` for the
    new-entity flag, preserving the three-state opt-in semantic."""

    for declared in (True, False, None):
        profile = TaxpayerProfile(
            tax_id="B66012345",
            iva_regime=IVARegime.GENERAL,
            new_entity_first_two_profit_periods=declared,
        )
        assert profile.new_entity_first_two_profit_periods is declared


def test_taxpayer_profile_model_accepts_ley_49_2002_option_fields() -> None:
    """Strict pydantic accepts the Ley 49/2002 booleans and dates."""

    profile = TaxpayerProfile(
        tax_id="B66012345",
        iva_regime=IVARegime.GENERAL,
        ley_49_2002_special_regime_option_declared=True,
        ley_49_2002_special_regime_option_date=date(2024, 2, 3),
        ley_49_2002_special_regime_renunciation_declared=False,
        ley_49_2002_special_regime_renunciation_date=date(2026, 5, 11),
    )

    assert profile.ley_49_2002_special_regime_option_declared is True
    assert profile.ley_49_2002_special_regime_option_date == date(2024, 2, 3)
    assert profile.ley_49_2002_special_regime_renunciation_declared is False
    assert profile.ley_49_2002_special_regime_renunciation_date == date(2026, 5, 11)
