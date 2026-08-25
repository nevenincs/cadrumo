"""Tests for the committed Modelo 184 (atribucion de rentas) registry."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.validate import RegistryValidator
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
    # The earlier half of the split carries the 2015 start. Orden HAC/1430/2025
    # partitioned this modelo at ejercicio 2025, so the revision reaching back to
    # 2015 is `2015-2024`; `2025-y-siguientes` starts at the boundary.
    revision = modelo.revisions["2015-2024"]

    # `valid_from` is the revision's DEVENGO window start, canonicalised to the
    # ejercicio start -- 87 of the tree's 95 revisions sit on January 1, and the
    # eight that do not are genuine mid-year regime starts (the 369 OSS esquemas,
    # 490's second quarter), never an orden's publication date. Asserting
    # 2015-10-30 here conflated the two axes: that is when Orden HAP/2250/2015
    # entered force, which is a fact about the ORDEN, and the window checks read
    # `valid_from` as a devengo date.
    assert revision.valid_from == date(2015, 1, 1)
    # The orden's own effective date, asserted where it actually lives, so the
    # fact this test used to cover is not dropped by moving it.
    assert catalogues.legal["orden-hap-2250-2015:art-1"].effective_from == date(2015, 10, 30)
    assert revision.period_selector.year_from == 2015
    assert revision.period_selector.periods == ("0A",)
    assert revision.orden_aplicabilidad == ("orden-hap-2250-2015:art-1",)


def test_modelo_184_snapshot_builds_for_each_published_filing_year() -> None:
    """Every published year resolves, and resolves to the half the orden governs.

    Before the split one revision answered for every year, so this could only
    assert that a snapshot built at all. Now it also pins WHICH side of the
    boundary each year lands on, which is the fact that matters: the two halves
    carry different byte layouts, so a year resolving to the wrong one would
    write a filing at the wrong offsets while still building cleanly.
    """
    expected_by_year = {
        2018: "2015-2024",
        2019: "2015-2024",
        2020: "2015-2024",
        2021: "2015-2024",
        2022: "2015-2024",
        2023: "2015-2024",
        2024: "2015-2024",
        # Orden HAC/1430/2025 art. cuarto is applicable for the first time to
        # ejercicio 2025 for modelo 184.
        2025: "2025-y-siguientes",
        2026: "2025-y-siguientes",
    }
    for filing_year, expected in expected_by_year.items():
        snapshot = _committed_snapshot("184", filing_year, "0A")
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
    """Every February window is correct AND sits on the half its ejercicio resolves to.

    This pinned all nine windows on ``2025-y-siguientes`` while one revision
    answered for every year. Orden HAC/1430/2025 partitioned the modelo at
    ejercicio 2025, and a window belongs to the revision whose span contains its
    ejercicio, so seven moved to ``2015-2024``. Asserting a literal set against
    one revision would have to be rewritten at the next split; asserting that the
    window is found on the LAW-SELECTED revision survives it.
    """
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
        revision = _committed_snapshot("184", ejercicio, "0A").revision
        windows = {w.id: w for w in revision.deadline_windows}

        assert window_id in windows, (
            f"{window_id} is absent from {revision.id!r}, the revision ejercicio {ejercicio} resolves to"
        )
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes
        seen_by_revision[revision.id] = seen_by_revision.get(revision.id, 0) + 1

    # The partition itself, so a regression that copied every window back into
    # both halves would still be caught: each window must live on exactly one.
    assert seen_by_revision == {"2015-2024": 7, "2025-y-siguientes": 2}
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


def _tipo2_sheets(design_ref: str) -> tuple[object, object]:
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


@pytest.mark.parametrize("revision_id", ["2015-2024", "2025-y-siguientes"])
def test_modelo_184_manifest_declares_the_entidad_positions_it_was_verified_against(revision_id: str) -> None:
    """The manifest must still declare exactly the positions the design proof pins.

    A rename or renumber in the manifest would otherwise leave the proof above
    asserting the design against numbers nothing declares.
    """
    modelo, _ = _load_modelo_184()
    manifest = modelo.revisions[revision_id].completeness_manifest
    declared = {entry.casilla_id: entry for entry in manifest.casillas}

    for casilla_id, offset, length, _description in _ENTIDAD_POSITIONS:
        entry = declared.get(casilla_id)
        assert entry is not None, f"{casilla_id} is no longer declared in the {revision_id} manifest"
        assert entry.segmento == "184-2-entidad", f"{casilla_id} moved to segmento {entry.segmento!r}"
        expected = str(offset) if length == 1 else f"{offset}-{offset + length - 1}"
        assert entry.number == expected, f"{casilla_id} declares {entry.number!r}, design says {expected!r}"
