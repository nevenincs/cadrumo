"""Which unanswered profile facts leave a period without a Modelo 303 filing schedule.

RIVA art. 71.3 makes the IVA period monthly for a gran empresa (volumen de
operaciones above 6.010.121,04 euros) or a REDEME enrolee, and quarterly
otherwise. The registry declares both schedules, so a profile that has not said
whether it is a gran empresa matches neither, and that fact, not the period, is
what must be asked.
"""

from __future__ import annotations

import pytest

from ....deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloEnrollment,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ..schedules import unresolved_schedule_deciding_fields
from .modelo_303_registry_support import load_modelo_303

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_LARGE_COMPANY = "enrollment.large_company"


def _profile(*, large_company: bool | None, redeme: bool = False) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime("GENERAL"),
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.from_registry("common_regime"),
            regime_composition=M303RegimeComposition.from_registry("general"),
            redeme_enrolled=redeme,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
        enrollment=ModeloEnrollment(large_company=large_company),
    )


def _revision():
    modelo, _catalogues = load_modelo_303()
    return modelo.revisions["2025"]


@pytest.mark.parametrize("period", ["1T", "01"])
def test_an_unanswered_gran_empresa_condition_decides_the_303_period(period: str) -> None:
    assert unresolved_schedule_deciding_fields(_revision(), _profile(large_company=None), period=period) == (
        _LARGE_COMPANY,
    )


@pytest.mark.parametrize(("large_company", "period"), [(False, "1T"), (True, "01")])
def test_an_answered_condition_whose_schedule_matches_leaves_nothing_to_ask(large_company: bool, period: str) -> None:
    assert unresolved_schedule_deciding_fields(_revision(), _profile(large_company=large_company), period=period) == ()


@pytest.mark.parametrize(("large_company", "period"), [(False, "01"), (True, "1T")])
def test_a_genuine_cadence_mismatch_is_not_an_unanswered_fact(large_company: bool, period: str) -> None:
    """A quarterly filer asking for a month, or a gran empresa for a quarter, answered everything."""
    assert unresolved_schedule_deciding_fields(_revision(), _profile(large_company=large_company), period=period) == ()


def test_a_redeme_enrolee_is_monthly_whatever_the_gran_empresa_answer() -> None:
    profile = _profile(large_company=None, redeme=True)

    assert unresolved_schedule_deciding_fields(_revision(), profile, period="01") == ()
