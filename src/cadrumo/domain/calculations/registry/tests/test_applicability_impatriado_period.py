"""The impatriado window is decided for the return's tax period, never the clock.

The special regime of LIRPF art. 93 applies to the tax period in which
residence is acquired and the following five (RIRPF art. 116), so a return's
route to the impatriado modelo depends on the period the return is for.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.deadlines.models import IrpfSpecialRegime, IVARegime, TaxpayerProfile

from ..applicability import derive_modelo_applicability
from ..applicability_models import ApplicabilityVerdict
from ..irpf_regimes import irpf_special_regime_impatriado_window_years
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_ORDINARY_RETURN_MODELO = "100"
_IMPATRIADO_RETURN_MODELO = "151"


def _impatriado_profile(start_year: int) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X0001500M",
        entity_type=EntityType.from_registry("natural_person"),
        iva_regime=IVARegime("GENERAL"),
        irpf_special_regime=IrpfSpecialRegime.from_registry("impatriado"),
        special_regime_start_date=date(start_year, 1, 15),
    )


def _period_end(year: int) -> date:
    return date(year, 12, 31)


def test_a_return_inside_the_window_routes_to_the_impatriado_modelo() -> None:
    start_year = filing_year_envelope().floor
    last_year_inside = start_year + irpf_special_regime_impatriado_window_years() - 1
    profile = _impatriado_profile(start_year)

    for year in (start_year, last_year_inside):
        impatriado = derive_modelo_applicability(profile, _IMPATRIADO_RETURN_MODELO, reference_date=_period_end(year))
        ordinary = derive_modelo_applicability(profile, _ORDINARY_RETURN_MODELO, reference_date=_period_end(year))

        assert impatriado.verdict is ApplicabilityVerdict.APPLICABLE, year
        assert ordinary.verdict is ApplicabilityVerdict.NOT_APPLICABLE, year


def test_a_return_after_the_window_is_not_routed_to_the_impatriado_modelo() -> None:
    start_year = filing_year_envelope().floor
    first_year_after = start_year + irpf_special_regime_impatriado_window_years()
    profile = _impatriado_profile(start_year)

    impatriado = derive_modelo_applicability(
        profile,
        _IMPATRIADO_RETURN_MODELO,
        reference_date=_period_end(first_year_after),
    )
    ordinary = derive_modelo_applicability(
        profile,
        _ORDINARY_RETURN_MODELO,
        reference_date=_period_end(first_year_after),
    )
    inside_ordinary = derive_modelo_applicability(
        profile,
        _ORDINARY_RETURN_MODELO,
        reference_date=_period_end(start_year),
    )

    assert impatriado.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert ordinary.verdict is not ApplicabilityVerdict.NOT_APPLICABLE
    assert ordinary.reason != inside_ordinary.reason


def test_a_return_before_the_election_year_is_outside_the_window() -> None:
    start_year = filing_year_envelope().floor + 1
    profile = _impatriado_profile(start_year)

    result = derive_modelo_applicability(
        profile,
        _IMPATRIADO_RETURN_MODELO,
        reference_date=_period_end(start_year - 1),
    )

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_the_reference_date_is_a_required_keyword_with_no_clock_default() -> None:
    parameter = inspect.signature(derive_modelo_applicability).parameters["reference_date"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
