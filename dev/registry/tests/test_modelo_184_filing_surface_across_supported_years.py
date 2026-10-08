"""Modelo 184 record-design surface across every supported filing year.

The casillas and informative construct the ejercicio 2022 design already lays
out are authored once, at the support floor, and inherited forward; only the
campos a later orden adds are stated on the edition it reaches. The member-row
bindings are the exception: the floor is applicability grade and carries no
export layout, so nothing on it reads them, and they are declared by the first
edition whose layout writes the socio record. These tests read every year of the
registry's own support envelope, so a member re-keyed onto the wrong edition, or
a later edition losing its own grounding, fails here rather than in one pinned
year.

The extent of the member record is checked against an oracle independent of
the registry: the amending ordenes themselves print where the member record's
content ends (the position its trailing BLANCOS start at) and the ejercicio
each first applies to.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as CompiledAuthority
from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot

from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "184"
_MEMBER_SEGMENT = "184-2-socio"
_ENTITY_SEGMENT = "184-2-entidad"

#: The ordenes that re-cut the member record's trailing BLANCOS, by corpus file.
_MEMBER_RECORD_AMENDMENTS = ("orden-hfp-1192-2022", "orden-hfp-1284-2023")

_MEMBER_ROW_BINDINGS = frozenset(
    {
        "modelo-184-member-row-nif",
        "modelo-184-member-row-name",
        "modelo-184-member-row-share",
        "modelo-184-member-row-base-assigned",
        "modelo-184-member-row-clave",
        "modelo-184-member-row-subclave",
        "modelo-184-member-row-codigo-provincia",
        "modelo-184-member-row-miembro-a-31-diciembre",
        "modelo-184-member-row-dias-miembro",
        "modelo-184-member-row-domicilio-fiscal",
        "modelo-184-member-row-naturaleza-inmueble",
        "modelo-184-member-row-situacion-inmueble",
        "modelo-184-member-row-referencia-catastral",
        "modelo-184-member-row-clave-declarado",
        "modelo-184-member-row-porcentaje-titularidad-inmueble",
        "modelo-184-member-row-dias-arrendamiento",
        "modelo-184-member-row-reduccion",
    }
)
_ESTIMACION_OBJETIVA_BINDINGS = frozenset(
    {
        "modelo-184-member-row-rendimiento-neto-previo-eo",
        "modelo-184-member-row-rendimiento-neto-minorado-agricola-eo",
    }
)
_CONSTRUCT = "modelo-184-informative"
_REDUCCION = "modelo-184-member-row-reduccion"
#: The LIRPF articles whose reductions the member record's REDUCCION campo reports.
_REDUCCION_ARTICLES = frozenset({"23", "32"})


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


SUPPORTED_YEARS = _supported_years()
FLOOR = min(SUPPORTED_YEARS)


def _article_amending_modelo_184(text: str) -> str:
    """Return the one article of an amending orden that modifies Orden HAP/2250/2015."""
    lines = text.split("\n")
    start = next(index for index, line in enumerate(lines) if line.startswith("# ") and "Orden HAP/2250/2015" in line)
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("# ")), len(lines))
    return "\n".join(lines[start:end])


@cache
def _member_record_content_end_by_first_ejercicio() -> dict[int, int]:
    """Map each amending orden's first ejercicio to the last position of member-record content."""
    extents: dict[int, int] = {}
    for orden in _MEMBER_RECORD_AMENDMENTS:
        text = bundled_path("corpus", "normatives", "html", f"{orden}.html.extracted.md").read_text(encoding="utf-8")
        first = re.search(r"por primera vez, (?:para|a) las declaraciones[^.]*?ejercicio\s(\d{4})", text)
        assert first is not None, orden
        blancos = re.findall(r"^(\d+)-500\n[^\n]*\nBLANCOS", _article_amending_modelo_184(text), re.MULTILINE)
        assert len(blancos) == 1, (orden, blancos)
        extents[int(first.group(1))] = int(blancos[0]) - 1
    return extents


def _official_member_record_end(filing_year: int) -> int:
    governing = [year for year in _member_record_content_end_by_first_ejercicio() if year <= filing_year]
    assert governing, f"no amending orden governs the member record for {filing_year}"
    return _member_record_content_end_by_first_ejercicio()[max(governing)]


def _span_end(number: str) -> int:
    return int(number.rsplit("-", 1)[-1])


@pytest.fixture(scope="module")
def edition(registry_authority: CompiledAuthority) -> Callable[[int], RegistrySnapshot]:
    """The Modelo 184 annual edition the canonical resolver selects for one filing year.

    Read from the development compiler's authority over the authored source, so
    the assertions judge the declarations on disk rather than a published
    generation that may predate them.
    """

    def select(filing_year: int) -> RegistrySnapshot:
        return registry_authority.snapshot(
            _MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        )

    return select


def _later_cut_year() -> int:
    """The first ejercicio of the latest member-record cut, read from the orden."""
    return max(_member_record_content_end_by_first_ejercicio())


def test_the_oracle_reads_a_cut_on_each_side_of_the_floor() -> None:
    extents = _member_record_content_end_by_first_ejercicio()
    assert len(extents) == len(_MEMBER_RECORD_AMENDMENTS), extents
    assert min(extents) <= FLOOR < _later_cut_year() <= max(SUPPORTED_YEARS), extents
    assert extents[min(extents)] < extents[_later_cut_year()]


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_member_record_casillas_end_where_the_official_record_ends(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    casillas = [c for c in edition(filing_year).revision.casillas if c.segmento == _MEMBER_SEGMENT]
    official_end = _official_member_record_end(filing_year)

    assert casillas, filing_year
    ends = [_span_end(str(casilla.number)) for casilla in casillas]
    assert max(ends) == official_end, (filing_year, official_end, sorted(ends))


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_declarant_and_entity_records_hydrate_identically_in_every_year(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    # The declarant-record total Orden HAC/1430/2025 adds is that edition's own
    # campo; every other declarant and entity-record casilla keeps its place.
    def shape(year: int) -> list[tuple[str, str, str | None]]:
        return [
            (str(casilla.id), str(casilla.number), casilla.segmento)
            for casilla in edition(year).revision.casillas
            if casilla.segmento != _MEMBER_SEGMENT and casilla.id != "decl.total-registros-entidad"
        ]

    floor_shape = shape(FLOOR)
    assert any(segment == _ENTITY_SEGMENT for _, _, segment in floor_shape)
    assert any(casilla_id.startswith("decl.") and casilla_id != "decl.ejercicio" for casilla_id, _, _ in floor_shape)
    assert shape(filing_year) == floor_shape


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_member_row_bindings_and_construct_hydrate_in_every_year(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    revision = edition(filing_year).revision
    bindings = {str(binding.id) for binding in revision.bindings}
    constructs = {str(construct.id): construct for construct in revision.constructs}

    construct = constructs[_CONSTRUCT]
    if filing_year == FLOOR:
        assert not bindings & _MEMBER_ROW_BINDINGS, sorted(bindings & _MEMBER_ROW_BINDINGS)
        assert not construct.bindings
        assert "bindings" in revision.family_dispositions
    else:
        assert bindings >= _MEMBER_ROW_BINDINGS, sorted(_MEMBER_ROW_BINDINGS - bindings)
        assert {str(item) for item in construct.bindings} <= _MEMBER_ROW_BINDINGS
    assert bool(_ESTIMACION_OBJETIVA_BINDINGS & bindings) is (filing_year >= _later_cut_year()), filing_year
    assert f"modelo-184-{filing_year}-0a" in {str(item) for item in construct.deadline_windows}


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_filing_scope_members_hydrate_in_every_year(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    revision = edition(filing_year).revision

    assert {str(rule.id) for rule in revision.applicability} == {"m184-seed"}
    assert {str(schedule.id) for schedule in revision.filing_schedules} == {"modelo-184-anual"}
    assert {str(item.id) for item in revision.live_cross_references} == {
        "modelo-184-static-documentation",
        "modelo-184-filed-declarations-read",
    }
    assert {str(profile.id) for profile in revision.extraction_profiles} == {"modelo-184-declaracion-pdf"}
    links = {str(link.id) for link in revision.application_links}
    assert {"modelo-184-portal", "modelo-184-extractor", "modelo-184-filing", "modelo-184-deadline"} <= links


def test_per_edition_claims_stay_off_the_floor(edition: Callable[[int], RegistrySnapshot]) -> None:
    """The floor has no generated layout, so nothing that claims one is carried onto it."""
    revision = edition(FLOOR).revision

    assert not revision.export_layouts
    assert not revision.verification_expectations
    assert revision.completeness_manifest is None
    assert "modelo-184-export" not in {str(link.id) for link in revision.application_links}
    construct = next(item for item in revision.constructs if item.id == _CONSTRUCT)
    assert not construct.verification_expectations
    assert not construct.workbook_parity_refs
    assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY


@pytest.mark.parametrize("filing_year", [year for year in SUPPORTED_YEARS if year > FLOOR])
def test_later_editions_keep_their_own_design_grounding(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    revision = edition(filing_year).revision
    bindings = {str(binding.id): binding for binding in revision.bindings}
    links = {str(link.id): link for link in revision.application_links}
    profile = next(iter(revision.extraction_profiles))
    construct = next(item for item in revision.constructs if item.id == _CONSTRUCT)
    design = str(next(iter(links["modelo-184-export"].source_refs)))

    assert design.startswith("aeat-dr-184-"), design
    for binding_id in _MEMBER_ROW_BINDINGS:
        assert tuple(map(str, bindings[binding_id].source_refs)) == (
            "aeat-dr-184-2023-2024",
            "aeat-modelo-184-procedure",
        ), (filing_year, binding_id)
    assert tuple(map(str, links["modelo-184-extractor"].source_refs)) == (design,)
    assert tuple(map(str, profile.source_refs)) == (design,)
    assert design in {str(ref) for ref in construct.source_refs}
    assert tuple(map(str, construct.verification_expectations)) == ("modelo-184-informative-summary-verification",)
    assert tuple(map(str, construct.workbook_parity_refs)) == ("modelo-184-dr",)


def test_floor_members_cite_sources_that_reach_the_floor(edition: Callable[[int], RegistrySnapshot]) -> None:
    revision = edition(FLOOR).revision
    sources = load_shared_catalogues(bundled_path("registry", "aeat")).sources

    cited = {
        *(ref for binding in revision.bindings for ref in binding.source_refs),
        *(ref for link in revision.application_links for ref in link.source_refs),
        *(ref for profile in revision.extraction_profiles for ref in profile.source_refs),
        *(ref for construct in revision.constructs for ref in construct.source_refs),
        *(ref for casilla in revision.casillas for ref in casilla.source_refs),
    }
    for ref in sorted(map(str, cited)):
        source = sources[ref]
        assert source.applies_from is None or source.applies_from.year <= FLOOR, ref
        assert source.applies_to is None or source.applies_to.year >= FLOOR, ref


def _reduccion_lirpf_refs(revision: ModeloRevision) -> dict[str, str]:
    """Map each LIRPF article the reduccion binding cites to the cited legal id."""
    catalogue = load_shared_catalogues(bundled_path("registry", "aeat")).legal
    binding = next(item for item in revision.bindings if str(item.id) == _REDUCCION)
    cited: dict[str, str] = {}
    for legal_id in map(str, binding.legal_refs):
        reference = catalogue[legal_id]
        if reference.document_id == "BOE-A-2006-20764" and reference.article in _REDUCCION_ARTICLES:
            assert reference.article not in cited, (legal_id, cited)
            cited[reference.article] = legal_id
    return cited


@pytest.mark.parametrize("filing_year", [year for year in SUPPORTED_YEARS if year > FLOOR])
def test_reduccion_binding_cites_each_lirpf_article_once(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    assert set(_reduccion_lirpf_refs(edition(filing_year).revision)) == _REDUCCION_ARTICLES, filing_year


@pytest.mark.parametrize("filing_year", [year for year in SUPPORTED_YEARS if year > FLOOR])
def test_later_reduccion_keys_its_own_redactions(edition: Callable[[int], RegistrySnapshot], filing_year: int) -> None:
    """Each edition that writes the socio record grounds REDUCCION in the LIRPF redactions it keys."""
    cited = _reduccion_lirpf_refs(edition(filing_year).revision)

    assert cited == {"23": "ley-35-2006:art-23", "32": "ley-35-2006:art-32"}, filing_year
