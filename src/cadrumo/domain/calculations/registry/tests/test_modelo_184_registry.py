"""Tests for the committed Modelo 184 (atribucion de rentas) registry."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.hashing import hash_file
from .....core.resources.bundled_data import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .._validate import RegistryValidator
from ..errors import AmbiguousRevisionSelectionError, RegistryValidationError
from ..record_design import extract_record_design
from ..record_design_schema import RecordDesignSheet
from ..schema import ModeloDefinition, RegistryCatalogues
from ..support_matrix import revision_capability_probe
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


def _load_modelo_184() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("184")


def test_modelo_184_registry_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_184()
    # A stubbed validator would silently accept an empty modelo. Pin the
    # committed modelo's shape so the test verifies validation actually
    # ran against non-trivial content rather than passing trivially.
    assert modelo.id == "184"
    assert modelo.revisions, "184 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "184 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_184_modelo_metadata_matches_hap_2250_2015() -> None:
    modelo, _ = _load_modelo_184()

    assert modelo.title == "Entidades en régimen de atribución de rentas (informativa anual)"
    assert modelo.tax_domain == "informative"
    assert modelo.cadence == "annual"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-hap-2250-2015:art-1" in modelo.legal_refs
    assert "orden-hap-2250-2015:art-4" in modelo.legal_refs
    assert "aeat-dr-184-2025" in modelo.source_refs
    assert "aeat-modelo-184-procedure" in modelo.source_refs


def test_modelo_184_revision_period_selector_starts_at_2015() -> None:
    modelo, catalogues = _load_modelo_184()
    revision = modelo.revisions["2015"]

    assert revision.valid_from == date(2015, 1, 1)
    assert revision.valid_to == date(2015, 12, 31)
    assert catalogues.legal["orden-hap-2250-2015:art-1"].effective_from == date(2015, 10, 30)
    assert revision.period_selector.year_from == 2015
    assert revision.period_selector.year_to == 2015
    assert revision.period_selector.periods == ("0A",)
    assert revision.orden_aplicabilidad == ("orden-hap-2250-2015:art-1",)


_RAW_BOE_DESIGN_ERAS = (
    ("2015", 2015, 2015, "boe-dr-184-2015", 160),
    ("2016-2018", 2016, 2018, "boe-dr-184-2016-2018", 81),
    ("2019-2021", 2019, 2021, "boe-dr-184-2019-2021", 95),
    ("2022", 2022, 2022, "boe-dr-184-2022", 103),
    ("2023-2024", 2023, 2024, "boe-dr-184-2023-2024", 27),
)


@pytest.mark.parametrize(("revision_id", "year_from", "year_to", "source_ref", "first_position"), _RAW_BOE_DESIGN_ERAS)
def test_modelo_184_raw_boe_design_eras_are_hash_pinned_and_explicitly_not_mapped(
    revision_id: str,
    year_from: int,
    year_to: int,
    source_ref: str,
    first_position: int,
) -> None:
    """A raw BOE design is provenance, not a surrogate for a later AEAT map.

    The parser refusal is intentional and load-bearing: reconsider promotion
    only when strict parsing produces complete records starting at position 1.
    """
    modelo, catalogues = _load_modelo_184()
    revision = modelo.revisions[revision_id]
    source = catalogues.sources[source_ref]
    path = bundled_path() / source.corpus_path

    assert source_ref in revision.source_refs
    assert source.kind == "record_design"
    assert source.design_authority == "provenance_only"
    assert source.record_design_epoch is None
    assert source.applies_from == date(year_from, 1, 1)
    assert source.applies_to == date(year_to, 12, 31)
    assert hash_file(path) == (source.sha256, source.bytes)
    if revision_id != "2023-2024":
        assert revision.authority_grade is not None
        assert revision.authority_grade.value == "applicability"
        assert revision.export_layouts == ()

    with pytest.raises(RegistryValidationError, match=rf"first field starts at position {first_position}"):
        extract_record_design(path)


def test_modelo_184_refuses_an_epoch_selector_mutation_that_overlaps_2023() -> None:
    """A widened 2022 selector cannot silently absorb the 2023-2024 design."""
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2022"]
    widened = revision.model_copy(
        update={
            "valid_to": date(2023, 12, 31),
            "period_selector": revision.period_selector.model_copy(update={"year_to": 2023}),
        },
    )
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: widened}})

    with pytest.raises(AmbiguousRevisionSelectionError):
        select_revision(mutated, filing_year=2023, period="0A", on=date(2023, 12, 31))


@pytest.mark.parametrize(
    ("revision_id", "filing_year"),
    (("2015", 2015), ("2016-2018", 2016), ("2019-2021", 2019), ("2022", 2022)),
)
def test_modelo_184_historical_filing_links_are_consumers_not_filing_capability(
    revision_id: str,
    filing_year: int,
) -> None:
    """A required filing consumer does not promote an unparsed design to filing grade."""
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions[revision_id]
    capability = revision_capability_probe(revision, modelo_id=modelo.id)

    assert revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert any(
        link.surface == "filing" and link.consumer == "cadrumo.application.filing"
        for link in revision.application_links
    )
    assert revision.export_layouts == ()
    assert not capability.has_fixed_width_export
    assert not capability.has_xml_dictionary_export
    assert not capability.has_extractor

    with pytest.raises(RegistryValidationError, match="cannot satisfy the requested 'filing' snapshot authority"):
        _committed_snapshot("184", filing_year, "0A")


@pytest.mark.parametrize("revision_id", ("2023-2024", "2025-y-siguientes"))
def test_modelo_184_parsed_epochs_retain_filing_links_and_layout_capability(revision_id: str) -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions[revision_id]
    capability = revision_capability_probe(revision, modelo_id=modelo.id)

    assert revision.authority_grade is RegistryAuthorityGrade.FILING
    assert any(
        link.surface == "filing" and link.consumer == "cadrumo.application.filing"
        for link in revision.application_links
    )
    assert capability.has_fixed_width_export


def test_modelo_184_snapshot_builds_for_each_published_filing_year() -> None:
    """Every claimed year resolves through its own design/applicability era."""
    expected_by_year = {
        2015: "2015",
        2016: "2016-2018",
        2017: "2016-2018",
        2018: "2016-2018",
        2019: "2019-2021",
        2020: "2019-2021",
        2021: "2019-2021",
        2022: "2022",
        2023: "2023-2024",
        2024: "2023-2024",
        2025: "2025-y-siguientes",
        2026: "2025-y-siguientes",
    }
    for filing_year, expected in expected_by_year.items():
        snapshot = _committed_snapshot("184", filing_year, "0A", RegistryAuthorityGrade.APPLICABILITY)
        assert snapshot.revision.id == expected, filing_year


def test_modelo_184_snapshot_exposes_legal_and_source_grounding() -> None:
    snapshot = _committed_snapshot("184", 2025, "0A")

    assert "orden-hap-2250-2015:art-1" in snapshot.legal
    assert "orden-hap-2250-2015:art-4" in snapshot.legal
    assert snapshot.revision.orden_aplicabilidad == ("orden-hap-2250-2015:art-1",)
    assert snapshot.legal["orden-hap-2250-2015:art-4"].article == "4"
    assert "aeat-dr-184-2025" in snapshot.sources
    assert "aeat-modelo-184-procedure" in snapshot.sources
    assert "boe-modelo-184-2015-form" in snapshot.sources
    assert snapshot.sources["aeat-modelo-184-procedure"].evidence_tier == "official_source_guidance"
    assert snapshot.sources["boe-modelo-184-2015-form"].evidence_tier == "layout_authority"


def test_modelo_184_february_deadline_windows_match_hap_2250_2015_art_4() -> None:
    """Every February window is on the canonical law-selected revision."""
    expected = {
        "modelo-184-2018-0a": (date(2019, 2, 1), date(2019, 2, 28)),
        "modelo-184-2019-0a": (date(2020, 2, 1), date(2020, 2, 29)),
        "modelo-184-2020-0a": (date(2021, 2, 1), date(2021, 2, 28)),
        "modelo-184-2021-0a": (date(2022, 2, 1), date(2022, 2, 28)),
        "modelo-184-2022-0a": (date(2023, 2, 1), date(2023, 2, 28)),
        "modelo-184-2023-0a": (date(2024, 2, 1), date(2024, 2, 29)),
        "modelo-184-2024-0a": (date(2025, 2, 1), date(2025, 2, 28)),
        "modelo-184-2025-0a": (date(2026, 2, 1), date(2026, 2, 28)),
        "modelo-184-2026-0a": (date(2027, 2, 1), date(2027, 2, 28)),
    }

    seen_by_revision: dict[str, int] = {}
    for window_id, (opens, closes) in expected.items():
        ejercicio = int(window_id.split("-")[2])
        revision = _committed_snapshot("184", ejercicio, "0A", RegistryAuthorityGrade.APPLICABILITY).revision
        windows = {w.id: w for w in revision.deadline_windows}

        assert window_id in windows, (
            f"{window_id} is absent from {revision.id!r}, the revision ejercicio {ejercicio} resolves to"
        )
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes
        seen_by_revision[revision.id] = seen_by_revision.get(revision.id, 0) + 1

    assert seen_by_revision == {
        "2016-2018": 1,
        "2019-2021": 3,
        "2022": 1,
        "2023-2024": 2,
        "2025-y-siguientes": 2,
    }
    for revision_id, count in seen_by_revision.items():
        declared = {w.id for w in _load_modelo_184()[0].revisions[revision_id].deadline_windows}
        assert len(declared) == count, f"{revision_id} declares windows beyond the {count} expected: {declared}"


def test_modelo_184_live_cross_references_are_read_only() -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2025-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-184-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False
    assert "presentation" in static_ref.forbidden_actions
    assert "signing" in static_ref.forbidden_actions

    filed_ref = cross_refs["modelo-184-filed-declarations-read"]
    assert filed_ref.surface == "authenticated_read_surface"
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert set(filed_ref.allowed_hosts) == {
        _WWW1_HOST,
        _WWW6_HOST,
    }
    forbidden = set(filed_ref.forbidden_actions)
    assert {
        "presentation",
        "signing",
        "amendment",
        "payment",
        "cancellation",
        "declaration-submission",
        "document-submission",
        "server-side-save",
    }.issubset(forbidden)


def test_modelo_184_construct_links_living_filing_and_extractor_surfaces() -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2025-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-184-informative")

    assert "modelo-184-filing" in construct.application_links
    assert "modelo-184-extractor" in construct.application_links
    assert "modelo-184-deadline" in construct.application_links
    assert "modelo-184-portal" in construct.application_links
    assert construct.filing_schedules == ("modelo-184-anual",)
    assert "modelo-184-static-documentation" in construct.live_cross_references
    assert "modelo-184-filed-declarations-read" in construct.live_cross_references


def test_modelo_184_filing_schedule_is_annual_february() -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2025-y-siguientes"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-184-anual")

    assert schedule.period_kind == "annual"
    assert schedule.periods == ("0A",)
    assert "orden-hap-2250-2015:art-4" in schedule.legal_refs


#: Modelo 184's Tipo 2 carries TWO distinct records -- the entidad's rentas and
#: the socio/heredero -- whose fields diverge from position 77 onward. The
#: completeness manifest is segment-qualified for exactly that reason, and the
#: segment-aware coverage gate cannot check it: that gate matches a declared
#: segmento against bracketed casilla tags the design prints, and this design
#: prints none on any sheet, so it derives an EMPTY pair set and stands down.
#: These positions are therefore proven against the design's own offsets and
#: field descriptions instead, which the same binary carries regardless of tags.
_ENTIDAD_POSITIONS: tuple[tuple[str, int, int, str], ...] = (
    ("tipo2.clave", 77, 1, "CLAVE"),
    ("tipo2.subclave", 78, 2, "SUBCLAVE"),
    ("tipo2.renta-atribuible-importe", 177, 14, "RENTA ATRIBUIBLE"),
)

#: Present only on the socio sheet, so it tells the two Tipo 2 records apart
#: without pinning a truncated PDF heading.
_SOCIO_MARKER = "MIEMBRO A 31 DICIEMBRE"


def _tipo2_sheets(design_ref: str) -> tuple[RecordDesignSheet, RecordDesignSheet]:
    """Return the (entidad, socio) Tipo 2 sheets of a Modelo 184 design."""
    from pathlib import Path

    from ..record_design_coverage import _extract_record_design

    _, catalogues = _load_modelo_184()
    source = catalogues.sources[design_ref]
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path

    sheets = [sheet for sheet in _extract_record_design(path) if sheet.name.startswith("Tipo 2")]
    assert len(sheets) == 2, f"{design_ref} must carry both Tipo 2 records, got {[s.name for s in sheets]}"

    socio = [s for s in sheets if any(_SOCIO_MARKER in f.description for f in s.fields)]
    entidad = [s for s in sheets if s not in socio]
    assert len(socio) == 1 and len(entidad) == 1, "the socio marker must select exactly one sheet"
    return entidad[0], socio[0]


@pytest.mark.parametrize("design_ref", ["aeat-dr-184-2023-2024", "aeat-dr-184-2025"])
def test_modelo_184_entidad_positions_match_the_official_design(design_ref: str) -> None:
    entidad, _ = _tipo2_sheets(design_ref)
    by_offset = {field.offset: field for field in entidad.fields if field.offset is not None}

    for casilla_id, offset, length, description in _ENTIDAD_POSITIONS:
        field = by_offset.get(offset)
        assert field is not None, f"{casilla_id}: the entidad record declares no field at @{offset}"
        assert field.length == length, f"{casilla_id}: @{offset} is {field.length} bytes, manifest says {length}"
        assert description in field.description, (
            f"{casilla_id}: @{offset} reads {field.description!r}, expected to contain {description!r}"
        )


@pytest.mark.parametrize("design_ref", ["aeat-dr-184-2023-2024", "aeat-dr-184-2025"])
def test_modelo_184_socio_record_does_not_carry_the_entidad_positions(design_ref: str) -> None:
    """The segment qualifier is load-bearing: the socio record differs at every pinned offset.

    Without this the sibling test could pass against either record and the
    manifest's ``segmento`` would be decorative.
    """
    _, socio = _tipo2_sheets(design_ref)
    by_offset = {field.offset: field for field in socio.fields if field.offset is not None}

    divergences = 0
    for casilla_id, offset, length, description in _ENTIDAD_POSITIONS:
        field = by_offset.get(offset)
        if field is None or field.length != length or description not in field.description:
            divergences += 1
            continue
        pytest.fail(f"{casilla_id}: the socio record matches @{offset} too, so the segmento proves nothing")

    assert divergences == len(_ENTIDAD_POSITIONS)


def test_modelo_184_2023_entidad_offset_mutation_conflicts_with_the_source_geometry() -> None:
    """The 2023 layout's f009 offset is evidence, not a replaceable constant."""
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2023-2024"]
    field = next(
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.id == "m184-2023.entidad.f009"
    )
    assert field.offset is not None
    mutated = field.model_copy(update={"offset": field.offset - 1})
    entidad, _ = _tipo2_sheets("aeat-dr-184-2023-2024")
    by_offset = {candidate.offset: candidate for candidate in entidad.fields if candidate.offset is not None}

    assert field.offset == 77
    assert mutated.offset is not None
    assert "CLAVE" in by_offset[field.offset].description
    assert by_offset[mutated.offset].description != by_offset[field.offset].description


@pytest.mark.parametrize("revision_id", ["2023-2024", "2025-y-siguientes"])
def test_modelo_184_manifest_declares_the_entidad_positions_it_was_verified_against(revision_id: str) -> None:
    """The manifest must still declare exactly the positions the design proof pins.

    A rename or renumber in the manifest would otherwise leave the proof above
    asserting the design against numbers nothing declares.
    """
    modelo, _ = _load_modelo_184()
    manifest = modelo.revisions[revision_id].completeness_manifest
    assert manifest is not None
    declared = {entry.casilla_id: entry for entry in manifest.casillas}

    for casilla_id, offset, length, _description in _ENTIDAD_POSITIONS:
        entry = declared.get(casilla_id)
        assert entry is not None, f"{casilla_id} is no longer declared in the {revision_id} manifest"
        assert entry.segmento == "184-2-entidad", f"{casilla_id} moved to segmento {entry.segmento!r}"
        expected = str(offset) if length == 1 else f"{offset}-{offset + length - 1}"
        assert entry.number == expected, f"{casilla_id} declares {entry.number!r}, design says {expected!r}"
