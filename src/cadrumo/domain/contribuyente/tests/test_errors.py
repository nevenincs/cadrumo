"""Unit tests for the tax-residence profile error hierarchy.

Verifies that :class:`cadrumo.domain.contribuyente.TaxResidenceProfileError` and
its subclasses register stable error codes through the
:mod:`cadrumo.core.errors` registry, and that the foral-regime detector
trips :class:`cadrumo.domain.contribuyente.ForalRegimeError` for every accented
and underscored alias.
"""

from __future__ import annotations

import pytest

from ....core.errors import ErrorCategory, get_registered_error_code
from ..errors import ForalRegimeError, ProfileNotConfiguredError, TaxResidenceProfileError
from ..tax_residence import parse_tax_region

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_profile_errors_have_registered_codes() -> None:
    assert get_registered_error_code(TaxResidenceProfileError("x")).code == "ERROR_PROFILE_TAX_RESIDENCE"
    assert get_registered_error_code(ProfileNotConfiguredError()).category is ErrorCategory.REFUSED
    assert get_registered_error_code(ForalRegimeError("navarra")).code == "REFUSED_PROFILE_FORAL_REGIME"


@pytest.mark.parametrize("raw", ("pais-vasco", "país_vasco", "navarra"))
def test_foral_regime_detection(raw: str) -> None:
    with pytest.raises(ForalRegimeError, match="foral regime outside the scope"):
        parse_tax_region(raw)


def test_unknown_tax_region_preserves_the_profile_error_contract() -> None:
    """An unsupported common-regime token remains a typed profile refusal."""
    with pytest.raises(TaxResidenceProfileError, match="unknown tax-region 'not-a-region'") as raised:
        parse_tax_region("not-a-region")

    assert raised.value.context == {"tax_region": "not-a-region"}
