"""EU/EEA residence decides the representante fiscal by the date of the fact, never by the run date."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from ....core.time.clock import frozen_clock, today_madrid
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.renta_codes_catalogue import (
    EnvelopeMembership,
    ue_eea_country_codes,
    ue_eea_membership_across_envelope,
)
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...calculations.registry.tests.eu_eea_membership_editions import eu_eea_membership_editions
from ...contribuyente.renta_codes import FiscalResidency
from ..models import (
    IVARegime,
    TaxpayerProfile,
    irnr_representante_fiscal_required,
    irnr_representante_fiscal_required_on_every_date,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_FLOOR = filing_year_envelope().floor
_HORIZON = filing_year_envelope().horizon
_LEAVES_ON = date(_HORIZON, 7, 1)
_BEFORE = _LEAVES_ON - timedelta(days=1)
_MEMBERS_BEFORE = ("ES", "FR", "GB")
_MEMBERS_AFTER = ("ES", "FR")


def _a_member_that_leaves_inside_the_envelope():
    return eu_eea_membership_editions(
        (date(_FLOOR, 1, 1), _BEFORE, _MEMBERS_BEFORE),
        (_LEAVES_ON, None, _MEMBERS_AFTER),
    )


def _irnr_profile(country: str) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X0001500M",
        iva_regime=IVARegime("GENERAL"),
        fiscal_residency=FiscalResidency.from_registry("non_resident_irnr"),
        country_of_fiscal_residence=country,
    )


def test_the_published_membership_gives_one_answer_for_every_date() -> None:
    assert ue_eea_membership_across_envelope("FR") is EnvelopeMembership.EVERY_EDITION
    assert ue_eea_membership_across_envelope("GB") is EnvelopeMembership.NO_EDITION
    assert ue_eea_membership_across_envelope(None) is None
    assert irnr_representante_fiscal_required_on_every_date("FR") is False
    assert irnr_representante_fiscal_required_on_every_date("GB") is True
    assert irnr_representante_fiscal_required_on_every_date(None) is False


def test_a_country_that_leaves_between_editions_depends_on_the_date_of_the_fact() -> None:
    with _a_member_that_leaves_inside_the_envelope():
        assert ue_eea_membership_across_envelope("GB") is EnvelopeMembership.DEPENDS_ON_DATE
        assert ue_eea_membership_across_envelope("FR") is EnvelopeMembership.EVERY_EDITION
        assert irnr_representante_fiscal_required_on_every_date("GB") is None
        assert irnr_representante_fiscal_required("GB", effective_date=_BEFORE) is False
        assert irnr_representante_fiscal_required("GB", effective_date=_LEAVES_ON) is True
        assert irnr_representante_fiscal_required("FR", effective_date=_LEAVES_ON) is False


@pytest.mark.parametrize(
    "run_date",
    [date(_FLOOR - 3, 2, 1), date(_FLOOR, 3, 1), date(_HORIZON, 3, 1), date(_HORIZON + 3, 9, 1)],
)
def test_no_answer_changes_with_the_date_the_program_runs(run_date: date) -> None:
    with (
        _a_member_that_leaves_inside_the_envelope(),
        frozen_clock(datetime(run_date.year, run_date.month, run_date.day, 12, tzinfo=UTC)),
    ):
        assert today_madrid() == run_date
        assert irnr_representante_fiscal_required_on_every_date("GB") is None
        assert ue_eea_country_codes() == frozenset(_MEMBERS_BEFORE)
        assert irnr_representante_fiscal_required("GB", effective_date=_BEFORE) is False
        assert irnr_representante_fiscal_required("GB", effective_date=_LEAVES_ON) is True


def test_a_profile_decides_a_country_whose_membership_never_changes_without_a_date() -> None:
    with _a_member_that_leaves_inside_the_envelope():
        assert _irnr_profile("FR").country_of_fiscal_residence == "FR"
        with pytest.raises(ValidationError, match="representante_fiscal_nif and representante_fiscal_nombre required"):
            _irnr_profile("AR")


def test_a_profile_leaves_a_country_whose_membership_changes_to_the_dated_reader() -> None:
    with _a_member_that_leaves_inside_the_envelope():
        profile = _irnr_profile("GB")

    assert profile.representante_fiscal_nif is None


def test_a_membership_with_no_edition_inside_the_envelope_is_refused_not_guessed() -> None:
    with (
        eu_eea_membership_editions((date(_FLOOR - 9, 1, 1), date(_FLOOR - 8, 12, 31), ("ES",))),
        pytest.raises(RegistryValidationError, match="authors no edition inside the supported filing years"),
    ):
        ue_eea_membership_across_envelope("ES")
