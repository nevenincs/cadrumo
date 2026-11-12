"""The EU/EEA residence advisory reads membership on the filing period's date and refuses without one."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import resolve_error_message
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.eu_eea_membership_editions import eu_eea_membership_editions
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ..action_errors import ModeloPredicateDateRequiredError
from ..verification_predicates import evaluate_advisory_predicate_fires

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_FLOOR = filing_year_envelope().floor
_HORIZON = filing_year_envelope().horizon
_LEAVES_ON = date(_HORIZON, 7, 1)
_BEFORE = _LEAVES_ON - timedelta(days=1)
_UE_RESIDENTE = 'casilla_equals_implies_profile_flag(["tipo_renta", "ue_residente", "ue_eee_status"])'
_FLAG_ENABLED = 'profile_flag_enabled("ue_eee_status")'
_TIPO_RENTA: CasillaId = validated_casilla_id("tipo_renta", surface="test_verification_predicate_dated_residence")
_TEXTS: dict[CasillaId, str] = {_TIPO_RENTA: "ue_residente"}
_LOCALES = ("en", "es", "ca", "hu")


def _leaving_member():
    return eu_eea_membership_editions(
        (date(_FLOOR, 1, 1), _BEFORE, ("ES", "FR", "GB")),
        (_LEAVES_ON, None, ("ES", "FR")),
    )


def _profile_in(country: str) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X0001500M",
        iva_regime=IVARegime("GENERAL"),
        fiscal_residency=FiscalResidency.from_registry("non_resident_irnr"),
        country_of_fiscal_residence=country,
    )


def test_the_dated_status_follows_the_edition_of_the_date() -> None:
    with _leaving_member():
        profile = _profile_in("GB")

        assert profile.ue_eee_status_on(_BEFORE) is True
        assert profile.ue_eee_status_on(_LEAVES_ON) is False


def test_the_residence_advisory_fires_only_on_a_date_the_country_is_outside_the_union() -> None:
    with _leaving_member():
        profile = _profile_in("GB")

        assert evaluate_advisory_predicate_fires(_UE_RESIDENTE, {}, _TEXTS, profile, fact_date=_BEFORE) is False
        assert evaluate_advisory_predicate_fires(_UE_RESIDENTE, {}, _TEXTS, profile, fact_date=_LEAVES_ON) is True
        assert evaluate_advisory_predicate_fires(_FLAG_ENABLED, {}, {}, profile, fact_date=_BEFORE) is True
        assert evaluate_advisory_predicate_fires(_FLAG_ENABLED, {}, {}, profile, fact_date=_LEAVES_ON) is False


@pytest.mark.parametrize("expression", [_UE_RESIDENTE, _FLAG_ENABLED])
def test_the_residence_flag_without_a_date_is_refused_in_all_locales(expression: str) -> None:
    profile = _profile_in("FR")

    with pytest.raises(ModeloPredicateDateRequiredError) as raised:
        evaluate_advisory_predicate_fires(expression, {}, _TEXTS, profile)

    assert raised.value.translated_message == "errors.refused.refused_modelo_predicate_date_required"
    for locale in _LOCALES:
        words = resolve_error_message(raised.value, locale=locale)
        assert words and not words.startswith("errors."), (locale, words)


def test_an_advisory_that_reads_no_dated_fact_needs_no_date() -> None:
    profile = _profile_in("FR")
    general: dict[CasillaId, str] = {_TIPO_RENTA: "general"}

    assert evaluate_advisory_predicate_fires(_UE_RESIDENTE, {}, general, profile) is False
