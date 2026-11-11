"""The Modelo 303 preflight asks for the fact that decides the IVA period.

RIVA art. 71.3 makes the period monthly for a gran empresa or a REDEME enrolee
and quarterly otherwise. With the gran empresa question unanswered no filing
schedule covers any period, so the preflight must name that fact before
calculation instead of letting the filing evidence refuse later with a reason
that names nothing.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_serving_period
from ....domain.calculations.registry.tests.modelo_303_registry_support import load_modelo_303
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_profile_schema,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ..preflight import ProfilePreflightService

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "0b5c8f1e-6a2d-4f3b-9c7e-1d2a3b4c5e6f"
_LARGE_COMPANY = "censo.large_company"
_FACTS: dict[str, object] = {
    "identity.tax_id": "12345678Z",
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "activities.description": "Servicios profesionales",
    "censo.activity_start_date": date(filing_year_envelope().floor, 1, 10).isoformat(),
    "irpf.estimation_regime": "directa_simplificada",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": False,
    "iva.sii_enrolled": False,
    "iva.cash_accounting_regime_enrolled": False,
    "iva.voluntary_sii_enrolled": False,
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": False,
    "tax_residence.jurisdiction_scope": "common_regime",
    "tax_residence.autonomous_community": "madrid",
}


def _missing_paths(*, large_company: bool | None, period: Period) -> tuple[str, ...]:
    facts = dict(_FACTS)
    if large_company is not None:
        facts[_LARGE_COMPANY] = large_company
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts.items()),
        context=leased_profile_create_context(),
    )
    modelo, _catalogues = load_modelo_303()
    revision = modelo.revisions[revision_serving_period("303", _YEAR, "1T").id]
    report = ProfilePreflightService(schema=published_profile_schema()).report(
        record=record,
        modelo="303",
        revision_id=revision.id,
        period=period,
        revision=revision,
    )
    return tuple(f"{requirement.section_key}.{requirement.field_key}" for requirement in report.missing)


@pytest.mark.parametrize("code", ["1T", "01"])
def test_an_unanswered_gran_empresa_condition_is_required_for_the_period(code: str) -> None:
    assert _LARGE_COMPANY in _missing_paths(large_company=None, period=Period.from_year_and_code(_YEAR, code))


def test_an_answered_condition_is_not_asked_again() -> None:
    assert _LARGE_COMPANY not in _missing_paths(large_company=False, period=Period.from_year_and_code(_YEAR, "1T"))


def test_a_cadence_mismatch_is_not_reported_as_a_missing_fact() -> None:
    """A quarterly filer asking for a month answered everything; the period is what is wrong."""
    assert _LARGE_COMPANY not in _missing_paths(large_company=False, period=Period.from_year_and_code(_YEAR, "01"))
