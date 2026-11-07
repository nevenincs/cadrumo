"""Enrollment scenarios must select the promised edition inside product support."""

from __future__ import annotations

import html
import re
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.calculations.m303_regimen_simplificado import (
    M303RegimenSimplificadoCalculationError,
    calculate_m303_regimen_simplificado_result,
)
from cadrumo.application.filing.producer_snapshot import (
    Modelo222ProfileFacts,
)
from cadrumo.application.filing.producer_snapshot_m200 import Modelo200ProfileFacts
from cadrumo.application.filing.producer_snapshot_m296 import (
    Modelo296ProfileFacts,
)
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    open_ended_revision,
    revision_covering,
    split_exercise_revisions,
)
from cadrumo.domain.iva.regimen_simplificado_rows import ActividadNoAgricolaSimplificado

from ..compiler.loader import load_modelo_directory, load_shared_catalogues, modelo_fact_scope
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..conformance.registry_schema_support import committed_modelo
from ..edition_export_periods import (
    M123_SCENARIO_PERIODS,
    M200_SCENARIO_PERIODS,
    M222_SCENARIO_PERIODS,
    M296_SCENARIO_PERIODS,
    M308_SCENARIO_PERIODS,
    M309_SCENARIO_PERIODS,
    M604_SCENARIO_PERIODS,
)
from ..edition_export_scenarios import (
    edition_export_scenarios,
    supported_scenario_periods,
)
from .modelo_100_registry_support import loaded_registry, source_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _scenario_editions() -> tuple[tuple[str, str, Period], ...]:
    """The enrolled scenario editions inside product support, each with the period its table declares.

    The floor edition of Modelos 123, 309 and 604 straddles the support floor,
    Modelo 296 declares one closed edition spanning two exercises inside
    support, and Modelos 200, 222 and 308 are rendered from their open-ended
    edition.
    """
    envelope = filing_year_envelope()
    floor_edition = {modelo_id: revision_covering(modelo_id, envelope.floor).id for modelo_id in ("123", "309", "604")}
    closed_edition = revision_covering("296", envelope.horizon - 1).id
    open_edition = {modelo_id: open_ended_revision(modelo_id).id for modelo_id in ("200", "222", "308")}
    return (
        ("123", floor_edition["123"], M123_SCENARIO_PERIODS[floor_edition["123"]]),
        ("200", open_edition["200"], M200_SCENARIO_PERIODS[open_edition["200"]]),
        ("222", open_edition["222"], M222_SCENARIO_PERIODS[open_edition["222"]]),
        ("296", closed_edition, M296_SCENARIO_PERIODS[closed_edition]),
        ("308", open_edition["308"], M308_SCENARIO_PERIODS[open_edition["308"]]),
        ("309", floor_edition["309"], M309_SCENARIO_PERIODS[floor_edition["309"]]),
        ("604", floor_edition["604"], M604_SCENARIO_PERIODS[floor_edition["604"]]),
    )


def test_enrollment_scenarios_select_their_supported_edition() -> None:
    for modelo_id, revision_id, period in _scenario_editions():
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
        select_revision(
            modelo, filing_year=filing_year_envelope().floor - 1, period="1T", support=catalogues.supported_filing_years
        )


def test_modelo296_scenario_supplies_every_required_detail_family() -> None:
    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", "296")):
        scenario = edition_export_scenarios("296")[revision_covering("296", filing_year_envelope().horizon - 1).id]
        profile = scenario.producer_snapshot().model_profile
    assert isinstance(profile, Modelo296ProfileFacts)
    assert profile.ejercicio == str(scenario.period.filing_year)
    assert len(profile.perceptor_rows) == 1
    assert len(profile.perceptor_intereses_rows) == 1
    assert len(profile.anexo_pago_rows) == 1
    assert len(profile.anexo_certificado_rows) == 1


@pytest.mark.parametrize("modelo_id", ("200", "222"))
def test_corporate_scenario_defers_software_identity_until_candidate_fact_scope(modelo_id: str) -> None:
    scenario = edition_export_scenarios(modelo_id)[open_ended_revision(modelo_id).id]
    assert scenario.product_software_identity_factory is not None
    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", modelo_id)):
        software = scenario.product_software_identity_factory()
        profile = scenario.producer_snapshot().model_profile
    assert software.program_identifier == f"C{modelo_id}"
    if modelo_id == "222":
        assert isinstance(profile, Modelo222ProfileFacts)
        assert profile.numero_grupo == "0001/25"
        assert profile.entidad_dominante_identificacion == "B00010082"
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


def _synthetic_registry(root: Path) -> tuple[Path, dict[str, Period], int]:
    """A registry holding the bundled legal tree and one modelo whose editions meet its floor differently.

    The floor is the bundled one rather than a stated one: the shared catalogues
    are validated together, so overriding the support span alone leaves the
    catalogues that enumerate its years inconsistent with it. Returns the
    registry, each edition's declared period keyed by revision id (wholly below,
    straddling, then serving the floor), and the floor.
    """
    registry = root / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "legal"), registry / "legal")
    floor = load_shared_catalogues(registry).require_supported_filing_years().floor
    modelo_dir = registry / "modelos" / "999"
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    spans = ((floor - 10, floor - 7), (floor - 6, floor + 1), (floor + 2, None))
    declared: dict[str, Period] = {}
    for year_from, year_to in spans:
        revision_id = f"{year_from}-y-siguientes" if year_to is None else f"{year_from}-{year_to}"
        _write_edition(modelo_dir, revision_id, year_from=year_from, year_to=year_to)
        declared[revision_id] = Period.from_year_and_code(year_from, "0A")
    return registry, declared, floor


def test_a_period_declared_below_the_floor_renders_at_the_earliest_supported_one(tmp_path: Path) -> None:
    """An edition straddling the floor renders at its first supported year; one wholly below it has no scenario.

    The declared periods are what the tables used to render: the canonical
    selection refuses both of them outright, so a scenario left there proves
    nothing about the edition's bytes.
    """
    registry, declared, floor = _synthetic_registry(tmp_path)
    wholly_below, straddling, serving = declared
    modelo = load_modelo_directory(registry / "modelos" / "999")
    support = load_shared_catalogues(registry).require_supported_filing_years()
    for below in (wholly_below, straddling):
        with pytest.raises(FilingYearOutsideSupportEnvelopeError):
            select_revision(modelo, filing_year=declared[below].filing_year, period="0A", support=support)

    rendered = supported_scenario_periods("999", declared, registry_root=registry)

    assert rendered == {
        straddling: Period.from_year_and_code(floor, "0A"),
        serving: declared[serving],
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


@pytest.mark.parametrize(("position", "period_code"), ((0, "1T"), (1, "2T")))
def test_m303_scenarios_select_both_form_editions_of_the_split_exercise(position: int, period_code: str) -> None:
    """Each paper edition of the exercise split at the first quarter has a scenario in its applicable quarter."""
    revision = split_exercise_revisions("303", early_period="1T", late_period="2T")[position]
    revision_id = str(revision.id)
    scenario = edition_export_scenarios("303")[revision_id]
    assert scenario.period == Period.from_year_and_code(revision.valid_from.year, period_code)
    modelo, catalogues = committed_modelo("303")
    selected = select_revision(
        modelo,
        filing_year=scenario.period.filing_year,
        period=scenario.period.registry_token,
        support=catalogues.supported_filing_years,
    )
    assert selected.id == revision_id


_ORDEN_LORCA_GRANT = re.compile(
    r"en el término municipal de Lorca y estén acogidos al régimen especial simplificado, "
    r"podrán reducir en un (\d+) por ciento"
)


def _annual_orden_grants_lorca(exercise: int) -> bool | None:
    """Whether the bundled official annual Orden of one exercise grants the Lorca reduction.

    Read from the Orden's own published text, not from the registry's pinned
    fact. ``None`` when the corpus holds no single annual Orden for the exercise.
    """
    _, catalogues = loaded_registry()
    first_day, last_day = date(exercise, 1, 1), date(exercise, 12, 31)
    ordenes = [
        source
        for source_id, source in catalogues.sources.items()
        if source_id.startswith("boe-orden-")
        and source_id.endswith("-iva-authority")
        and source.applies_from == first_day
        and source.applies_to == last_day
    ]
    if len(ordenes) != 1:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", (source_root() / ordenes[0].corpus_path).read_text(encoding="utf-8")))
    return _ORDEN_LORCA_GRANT.search(re.sub(r"\s+", " ", text)) is not None


def _scenario_editions_decided_by_their_orden(*, grants: bool) -> tuple[str, ...]:
    """The Modelo 303 scenario editions whose annual Orden text decides the Lorca reduction as ``grants``."""
    return tuple(
        revision_id
        for revision_id, scenario in edition_export_scenarios("303").items()
        if _annual_orden_grants_lorca(scenario.period.filing_year) is grants
    )


@pytest.mark.parametrize("revision_id", tuple(edition_export_scenarios("303")))
def test_m303_scenario_carries_the_lorca_reduction_exactly_when_the_official_orden_grants_it(
    revision_id: str,
) -> None:
    """Both directions: a granting Orden is pinned by the registry, and a silent one is not."""
    scenario = edition_export_scenarios("303")[revision_id]
    granted = _annual_orden_grants_lorca(scenario.period.filing_year)
    if granted is None:
        pytest.fail(f"the corpus holds no single annual Orden for edition {revision_id}; list it as undecidable")
    with bundled_indexed_authority().operation():
        facts = scenario.producer_snapshot().m303_filing_facts
        assert facts is not None
        carried = facts.regimen_simplificado.regimen_snapshot.orden.lorca_reduction is not None
    assert carried is granted


@pytest.mark.parametrize("revision_id", _scenario_editions_decided_by_their_orden(grants=True))
def test_m303_scenario_evidences_no_lorca_relief_and_missing_evidence_still_refuses(revision_id: str) -> None:
    """Synthetic non-Lorca activities render, while missing required evidence still fails."""
    scenario = edition_export_scenarios("303")[revision_id]
    with bundled_indexed_authority().operation() as operation:
        facts = scenario.producer_snapshot().m303_filing_facts
        assert facts is not None
        evidence = facts.regimen_simplificado
        assert evidence.regimen_snapshot.orden.lorca_reduction is not None
        row = evidence.rows.activities[0]
        assert isinstance(row, ActividadNoAgricolaSimplificado)
        eligibility = row.lorca_eligibility
        assert eligibility is not None
        assert not eligibility.eligible
        assert eligibility.evidence_reference == row.evidence_reference
        assert evidence.calculation_result.activities[0].lorca_reduction_amount == Decimal("0")
        assert eligibility.evidence_reference in evidence.calculation_result.activities[0].evidence_references
        missing_row = row.model_copy(update={"lorca_eligibility": None})
        missing_rows = evidence.rows.model_copy(update={"activities": (missing_row,)})

        with pytest.raises(M303RegimenSimplificadoCalculationError, match="requires Lorca eligibility evidence"):
            calculate_m303_regimen_simplificado_result(
                period=scenario.period,
                scope_decision=evidence.scope_decision,
                rows=missing_rows,
                regimen_snapshot=evidence.regimen_snapshot,
                dana_eligibility=evidence.dana_eligibility,
                operation=operation,
            )
