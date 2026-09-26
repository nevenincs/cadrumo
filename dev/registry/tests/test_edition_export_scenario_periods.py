"""Enrollment scenarios must select the promised edition inside product support."""

from __future__ import annotations

import pytest

from cadrumo.application.filing.producer_snapshot import (
    Modelo222ProfileFacts,
    Modelo296ProfileFacts,
)
from cadrumo.application.filing.producer_snapshot_m200 import Modelo200ProfileFacts
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..compiler.loader import modelo_fact_scope
from ..conformance.registry_schema_support import committed_modelo
from ..edition_export_scenarios import (
    M123_SCENARIO_PERIODS,
    M200_SCENARIO_PERIODS,
    M222_SCENARIO_PERIODS,
    M296_SCENARIO_PERIODS,
    M308_SCENARIO_PERIODS,
    M309_SCENARIO_PERIODS,
    M604_SCENARIO_PERIODS,
    edition_export_scenarios,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_enrollment_scenarios_select_their_supported_edition() -> None:
    cases = (
        ("123", "2019-2023", M123_SCENARIO_PERIODS["2019-2023"]),
        ("200", "2025-y-siguientes", M200_SCENARIO_PERIODS["2025-y-siguientes"]),
        ("222", "2025-y-siguientes", M222_SCENARIO_PERIODS["2025-y-siguientes"]),
        ("296", "2024-y-siguientes", M296_SCENARIO_PERIODS["2024-y-siguientes"]),
        ("308", "2019-y-siguientes", M308_SCENARIO_PERIODS["2019-y-siguientes"]),
        ("309", "2018-2022", M309_SCENARIO_PERIODS["2018-2022"]),
        ("604", "2021-2023", M604_SCENARIO_PERIODS["2021-2023"]),
    )
    for modelo_id, revision_id, period in cases:
        modelo, catalogues = committed_modelo(modelo_id)
        revision = select_revision(
            modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
            support=catalogues.supported_filing_years,
        )
        assert revision.id == revision_id
        assert edition_export_scenarios(modelo_id)[revision_id].period == period


def test_the_retired_below_floor_period_still_refuses() -> None:
    modelo, catalogues = committed_modelo("123")
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision(modelo, filing_year=2019, period="1T", support=catalogues.supported_filing_years)


def test_modelo296_scenario_supplies_every_required_detail_family() -> None:
    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", "296")):
        scenario = edition_export_scenarios("296")["2024-y-siguientes"]
        profile = scenario.producer_snapshot().model_profile
    assert isinstance(profile, Modelo296ProfileFacts)
    assert profile.ejercicio == str(scenario.period.filing_year)
    assert len(profile.perceptor_rows) == 1
    assert len(profile.perceptor_intereses_rows) == 1
    assert len(profile.anexo_pago_rows) == 1
    assert len(profile.anexo_certificado_rows) == 1


@pytest.mark.parametrize("modelo_id", ("200", "222"))
def test_corporate_scenario_defers_software_identity_until_candidate_fact_scope(modelo_id: str) -> None:
    scenario = edition_export_scenarios(modelo_id)["2025-y-siguientes"]
    assert scenario.product_software_identity_factory is not None
    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", modelo_id)):
        software = scenario.product_software_identity_factory()
        profile = scenario.producer_snapshot().model_profile
    assert software.program_identifier == f"C{modelo_id}"
    if modelo_id == "222":
        assert isinstance(profile, Modelo222ProfileFacts)
        assert profile.numero_grupo == "0001/25"
        assert profile.entidad_dominante_identificacion == "B00000000"
    else:
        assert isinstance(profile, Modelo200ProfileFacts)
        rows = profile.projection_rows
        # Every record made of projection fields alone is declared required, so the
        # scenario must carry a row of every family the typed rows admit. Derived from
        # the model's own fields so a new family cannot be added and left unsupplied.
        assert {name: len(getattr(rows, name)) for name in type(rows).model_fields} == dict.fromkeys(
            type(rows).model_fields,
            1,
        )
