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

The tests drive the real :func:`taxpayer_profile_from_mapping`
projection — no mocks — and assert the strict pydantic model accepts
and round-trips the values verbatim.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .. import TaxpayerProfile
from .._models import IVARegime
from .._profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _minimal_profile_mapping() -> dict[str, str]:
    """Return a profile-values mapping that satisfies the descriptor."""

    return {
        "identity.tax_id": "B66012345",
        "iva.regime": "GENERAL",
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
