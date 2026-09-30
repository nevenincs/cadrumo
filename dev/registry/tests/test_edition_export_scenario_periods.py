"""Enrollment scenarios must select the promised edition inside product support."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.application.filing.producer_snapshot import (
    Modelo222ProfileFacts,
    Modelo296ProfileFacts,
)
from cadrumo.application.filing.producer_snapshot_m200 import Modelo200ProfileFacts
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..compiler.loader import load_modelo_directory, load_shared_catalogues, modelo_fact_scope
from ..conformance.loader_directory_mode_support import write_standard_manifest
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
    supported_scenario_periods,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_enrollment_scenarios_select_their_supported_edition() -> None:
    cases = (
        ("123", "2019-2023", M123_SCENARIO_PERIODS["2019-2023"]),
        ("200", "2025-y-siguientes", M200_SCENARIO_PERIODS["2025-y-siguientes"]),
        ("222", "2025-y-siguientes", M222_SCENARIO_PERIODS["2025-y-siguientes"]),
        ("296", "2024-2025", M296_SCENARIO_PERIODS["2024-2025"]),
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
        scenario = edition_export_scenarios("296")["2024-2025"]
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


def _write_edition(modelo_dir: Path, revision_id: str, *, year_from: int, year_to: int | None) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    valid_to = "" if year_to is None else f"valid_to = {year_to}-12-31\n"
    selector_to = "" if year_to is None else f", year_to = {year_to}"
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year_from}-01-01\n"
        f"{valid_to}"
        f'period_selector = {{ year_from = {year_from}{selector_to}, periods = ["0A"] }}\n'
        'legal_refs = ["ley-58-2003:art-29"]\n'
        'source_refs = ["aeat-manual"]\n',
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        f'[[revisions."{revision_id}".casillas]]\n'
        'id = "0001"\n'
        'number = "1"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        'continuidad_id = "base"\n'
        'legal_refs = ["ley-58-2003:art-29"]\n'
        'source_refs = ["aeat-manual"]\n',
        encoding="utf-8",
        newline="\n",
    )


def _synthetic_registry(root: Path, *, floor: int) -> Path:
    """A registry holding the bundled legal tree, a stated floor and one modelo whose editions meet it differently."""
    registry = root / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "legal"), registry / "legal")
    (registry / "legal" / "supported-filing-years.toml").write_text(
        f"[supported_filing_years]\nfloor = {floor}\nhorizon = {floor + 4}\n",
        encoding="utf-8",
        newline="\n",
    )
    modelo_dir = registry / "modelos" / "999"
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    _write_edition(modelo_dir, "2012-2015", year_from=2012, year_to=2015)
    _write_edition(modelo_dir, "2016-2021", year_from=2016, year_to=2021)
    _write_edition(modelo_dir, "2022-y-siguientes", year_from=2022, year_to=None)
    return registry


def test_a_period_declared_below_the_floor_renders_at_the_earliest_supported_one(tmp_path: Path) -> None:
    """An edition straddling the floor renders at its first supported year; one wholly below it has no scenario.

    The declared periods are what the tables used to render: the canonical
    selection refuses both of them outright, so a scenario left there proves
    nothing about the edition's bytes.
    """
    registry = _synthetic_registry(tmp_path, floor=2019)
    declared = {
        "2012-2015": Period.from_year_and_code(2012, "0A"),
        "2016-2021": Period.from_year_and_code(2016, "0A"),
        "2022-y-siguientes": Period.from_year_and_code(2022, "0A"),
    }
    modelo = load_modelo_directory(registry / "modelos" / "999")
    support = load_shared_catalogues(registry).require_supported_filing_years()
    for below in ("2012-2015", "2016-2021"):
        with pytest.raises(FilingYearOutsideSupportEnvelopeError):
            select_revision(modelo, filing_year=declared[below].filing_year, period="0A", support=support)

    rendered = supported_scenario_periods("999", declared, registry_root=registry)

    assert rendered == {
        "2016-2021": Period.from_year_and_code(2019, "0A"),
        "2022-y-siguientes": declared["2022-y-siguientes"],
    }
    for revision_id, period in rendered.items():
        selected = select_revision(modelo, filing_year=period.filing_year, period="0A", support=support)
        assert selected.id == revision_id


def test_every_declared_scenario_renders_inside_the_support_envelope() -> None:
    """Registry-wide: each scenario period is admitted and selects the edition it is keyed by."""
    modelo_ids = sorted(path.name for path in bundled_path("registry", "aeat", "modelos").iterdir() if path.is_dir())
    for modelo_id in modelo_ids:
        scenarios = edition_export_scenarios(modelo_id)
        if not scenarios:
            continue
        modelo, catalogues = committed_modelo(modelo_id)
        support = catalogues.require_supported_filing_years()
        for revision_id, scenario in scenarios.items():
            period = scenario.period
            assert support.admits_filing_year(period.filing_year), (modelo_id, revision_id, period)
            selected = select_revision(
                modelo, filing_year=period.filing_year, period=period.registry_token, support=support
            )
            assert selected.id == revision_id, (modelo_id, revision_id, period)
