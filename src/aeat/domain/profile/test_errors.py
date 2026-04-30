"""Unit tests for tax-residence profile errors."""

from __future__ import annotations

import pytest

from ...core.errors import ErrorCategory, get_registered_error_code
from . import ForalRegimeError, ProfileNotConfiguredError, TaxResidenceProfileError, parse_tax_region

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_profile_errors_have_registered_codes() -> None:
    assert get_registered_error_code(TaxResidenceProfileError("x")).code == "ERROR_PROFILE_TAX_RESIDENCE"
    assert get_registered_error_code(ProfileNotConfiguredError()).category is ErrorCategory.REFUSED
    assert get_registered_error_code(ForalRegimeError("navarra")).code == "REFUSED_PROFILE_FORAL_REGIME"


@pytest.mark.parametrize("raw", ["pais-vasco", "país_vasco", "navarra"])
def test_foral_regime_detection(raw: str) -> None:
    with pytest.raises(ForalRegimeError, match="#424"):
        parse_tax_region(raw)
