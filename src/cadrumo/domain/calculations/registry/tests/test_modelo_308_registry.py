"""Source-grounded temporal epochs for Modelo 308."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.hashing import hash_file
from .....core.resources._boundary import bundled_path
from .._validate import RegistryValidator
from .._validate_export_layout_coverage import validate_export_layout_record_coverage
from ..errors import AmbiguousRevisionSelectionError, NoRevisionForPeriodError, RegistryValidationError
from ..record_design import extract_record_design
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_SOURCES = (
    (
        "2009-2011-junio",
        "aeat-dr-308-2009",
        "02-308-orden-eha-1033-2011-ejercicios-2009-a-2011-julio.xls",
        "e6a67ab3fccb72adba80c0297cc9ff565af0a83b34e86cafb9f5da68bf118367",
        147456,
        "2009",
        date(2009, 1, 1),
        date(2011, 6, 30),
    ),
    (
        "2011-julio-2015",
        "aeat-dr-308-2011-july",
        "03-308-orden-eha-1033-2011-ejercicios-2011-julio-a-2015.pdf",
        "0d02c1477f291502203422342faed99035e8d52de775fe9f2f259b00ce226467",
        32183,
        "2011-julio",
        date(2011, 7, 1),
        date(2015, 12, 31),
    ),
    (
        "2016-2018",
        "aeat-dr-308-2016",
        "04-308-orden-eha-1033-2011-ejercicios-2016-hasta-2018.xls",
        "658e37957ebc2f888167cafd0a24b089b8868654d601102b82cc6d4c8ae66654",
        176640,
        "2016",
        date(2016, 1, 1),
        date(2018, 12, 31),
    ),
    (
        "2019-y-siguientes",
        "aeat-dr-308-2019",
        "01-308-ejercicios-2019-y-siguientes-v13.xls",
        "85eb926a84d309684db271e42a85dc3375e8265b6026d918400e647c76f15981",
        182784,
        "2019",
        date(2019, 1, 1),
        None,
    ),
)


def _modelo_308():
    return _committed_modelo("308")


def _source_path(filename: str):
    return bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_308", "files", filename)


def test_modelo_308_validates_each_declared_temporal_epoch() -> None:
    modelo, catalogues = _modelo_308()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert tuple(modelo.revisions) == tuple(revision_id for revision_id, *_rest in _SOURCES)


def test_modelo_308_hash_pins_four_distinct_official_designs() -> None:
    modelo, catalogues = _modelo_308()

    for revision_id, source_id, filename, sha256, byte_count, epoch, starts, ends in _SOURCES:
        revision = modelo.revisions[revision_id]
        source = catalogues.sources[source_id]
        path = _source_path(filename)

        assert revision.source_refs.count(source_id) == 1
        assert {ref for ref in revision.source_refs if ref.startswith("aeat-dr-308-")} == {source_id}
        assert source.kind == "record_design"
        assert source.record_design_epoch == epoch
        assert (source.applies_from, source.applies_to) == (starts, ends)
        assert hash_file(path) == (sha256, byte_count) == (source.sha256, source.bytes)


def test_modelo_308_historical_geometry_is_complete_without_claiming_a_layout() -> None:
    """Pin observed source geometry; this is not a generated filing layout."""
    early = extract_record_design(_source_path(_SOURCES[0][2])).require_complete()
    july = extract_record_design(_source_path(_SOURCES[1][2])).require_complete()
    modern = extract_record_design(_source_path(_SOURCES[2][2])).require_complete()

    (early_record,) = early
    assert (early_record.name, early_record.total_positions, len(early_record.fields)) == ("dr308", 1233, 46)
    assert [(field.offset, field.length) for field in early_record.fields] == [
        (1, 3),
        (4, 1),
        (5, 1),
        (6, 9),
        (15, 4),
        (19, 4),
        (23, 2),
        (25, 9),
        (34, 40),
        (74, 14),
        (88, 40),
        (128, 40),
        (168, 40),
        (208, 40),
        (248, 40),
        (288, 40),
        (328, 40),
        (368, 40),
        (408, 6),
        (414, 40),
        (454, 40),
        (494, 40),
        (534, 4),
        (538, 12),
        (550, 13),
        (563, 5),
        (568, 13),
        (581, 13),
        (594, 5),
        (599, 13),
        (612, 13),
        (625, 13),
        (638, 5),
        (643, 13),
        (656, 13),
        (669, 5),
        (674, 13),
        (687, 13),
        (700, 5),
        (705, 13),
        (718, 13),
        (731, 13),
        (744, 20),
        (764, 100),
        (864, 20),
        (884, 350),
    ]

    (july_record,) = july
    # The PDF visibly prints 49 rows. Two are its repeated position-656 row;
    # retaining both is evidence, not a licence to derive a wire layout.
    assert (july_record.name, july_record.total_positions, len(july_record.fields)) == ("PDF record design", 1259, 49)
    assert [(field.offset, field.length) for field in july_record.fields] == [
        (1, 3),
        (4, 1),
        (5, 1),
        (6, 9),
        (15, 4),
        (19, 4),
        (23, 2),
        (25, 9),
        (34, 40),
        (74, 14),
        (88, 40),
        (128, 40),
        (168, 40),
        (208, 40),
        (248, 40),
        (288, 40),
        (328, 40),
        (368, 40),
        (408, 6),
        (414, 40),
        (454, 40),
        (494, 40),
        (534, 4),
        (538, 12),
        (550, 13),
        (563, 5),
        (568, 13),
        (581, 13),
        (594, 5),
        (599, 13),
        (612, 13),
        (625, 13),
        (638, 5),
        (643, 13),
        (656, 13),
        (656, 13),
        (669, 5),
        (674, 13),
        (687, 13),
        (700, 5),
        (705, 13),
        (718, 13),
        (731, 13),
        (744, 13),
        (757, 13),
        (770, 20),
        (790, 100),
        (890, 20),
        (910, 350),
    ]

    prefix, page = modern
    assert (prefix.name, prefix.total_positions, len(prefix.fields)) == ("M30800", None, 13)
    assert prefix.variable_envelope is not None and prefix.variable_envelope.prefix_extent == 328
    assert prefix.fields[-1].offset + prefix.fields[-1].length - 1 == 328
    assert (page.name, page.total_positions, len(page.fields)) == ("M30801", 1500, 55)
    assert page.fields[-1].offset + page.fields[-1].length - 1 == 1500


def test_modelo_308_selects_each_date_window_including_the_july_2011_boundary() -> None:
    modelo, _catalogues = _modelo_308()

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2008, period="AD-HOC", on=date(2008, 12, 31))

    # Filing year 2011 contains two sub-year epochs. Without the filing date,
    # generic temporal selection must refuse rather than choose one silently.
    with pytest.raises(AmbiguousRevisionSelectionError):
        select_revision(modelo, filing_year=2011, period="AD-HOC")

    selected = [
        select_revision(modelo, filing_year=year, period="AD-HOC", on=on).id
        for year, on in (
            (2009, date(2009, 1, 1)),
            (2011, date(2011, 6, 30)),
            (2011, date(2011, 7, 1)),
            (2015, date(2015, 12, 31)),
            (2016, date(2016, 1, 1)),
            (2018, date(2018, 12, 31)),
            (2019, date(2019, 1, 1)),
            (2026, date(2026, 8, 26)),
        )
    ]
    assert selected == [
        "2009-2011-junio",
        "2009-2011-junio",
        "2011-julio-2015",
        "2011-julio-2015",
        "2016-2018",
        "2016-2018",
        "2019-y-siguientes",
        "2019-y-siguientes",
    ]


def test_modelo_308_july_boundary_mutation_is_refused() -> None:
    """The generic selector must not silently pick an overlapping sub-year era."""
    modelo, _catalogues = _modelo_308()
    early = modelo.revisions["2009-2011-junio"]
    overlapping_early = early.model_copy(update={"valid_to": date(2011, 7, 1)})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, early.id: overlapping_early}})

    with pytest.raises(AmbiguousRevisionSelectionError):
        select_revision(mutated, filing_year=2011, period="AD-HOC", on=date(2011, 7, 1))


def test_modelo_308_historical_epochs_are_explicitly_below_filing() -> None:
    modelo, _catalogues = _modelo_308()

    for revision_id, source_id, *_rest in _SOURCES[:3]:
        revision = modelo.revisions[revision_id]
        (parity,) = revision.workbook_parity_refs
        (construct,) = revision.constructs

        assert revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
        assert not revision.export_layouts
        assert not revision.bindings
        assert not revision.deadline_windows
        assert {casilla.id for casilla in revision.casillas} == {"decl.ejercicio", "decl.periodo"}
        assert {link.surface for link in revision.application_links} == {"portal", "filing", "extractor", "deadline"}
        assert parity.formula_coverage == "static_layout"
        assert parity.workbook_source == source_id
        assert construct.workbook_parity_refs == (parity.id,)
        assert construct.deadline_windows == ()

    current = modelo.revisions["2019-y-siguientes"]
    assert current.authority_grade is RegistryAuthorityGrade.FILING
    assert {source for layout in current.export_layouts for source in layout.source_refs} == {"aeat-dr-308-2019"}
    assert "export" in {link.surface for link in current.application_links}


def test_modelo_308_current_layout_covers_v13_and_offset_mutation_reopens_source_slot() -> None:
    modelo, catalogues = _modelo_308()
    revision = modelo.revisions["2019-y-siguientes"]

    assert (
        validate_export_layout_record_coverage(
            prefix="modelo 308 revision 2019-y-siguientes",
            revision=revision,
            source_refs=catalogues.sources,
        )
        == []
    )

    (layout,) = revision.export_layouts
    page = next(record for record in layout.records if record.id == "modelo-308-page-01")
    index = next(index for index, field in enumerate(page.fields) if field.id == "modelo-308-p1-devengo-periodo")
    fields = list(page.fields)
    fields[index] = fields[index].model_copy(update={"offset": 108})
    wounded_page = page.model_copy(update={"fields": tuple(fields)})
    wounded_layout = layout.model_copy(
        update={"records": tuple(wounded_page if record.id == page.id else record for record in layout.records)},
    )
    wounded_revision = revision.model_copy(update={"export_layouts": (wounded_layout,)})

    failures = validate_export_layout_record_coverage(
        prefix="modelo 308 revision 2019-y-siguientes",
        revision=wounded_revision,
        source_refs=catalogues.sources,
    )
    assert len(failures) == 1
    assert "@107+2 'Devengo - Periodo'" in failures[0]


def test_modelo_308_legal_boundary_and_applicability_snapshot_are_available() -> None:
    modelo, catalogues = _modelo_308()
    july_ref = catalogues.legal["orden-eha-1033-2011:disposicion-final-unica"]
    amendment_ref = catalogues.legal["orden-eha-1033-2011:articulo-unico"]
    july_revision = modelo.revisions["2011-julio-2015"]

    assert july_ref.effective_from == date(2011, 7, 1)
    assert july_ref.corpus_ref.endswith("orden-eha-1033-2011.html#disposicion-final-unica")
    assert amendment_ref.effective_from == date(2011, 7, 1)
    assert amendment_ref.corpus_ref.endswith("orden-eha-1033-2011.html#articulo-unico")
    assert amendment_ref.id in july_revision.legal_refs
    assert july_revision.orden_aplicabilidad == (
        "orden-eha-3786-2008:art-2",
        "orden-eha-1033-2011:articulo-unico",
        "orden-eha-1033-2011:disposicion-final-unica",
    )
    assert {
        casilla.id: casilla.legal_refs
        for casilla in july_revision.casillas
        if casilla.id in {"decl.ejercicio", "decl.periodo"}
    } == {
        "decl.ejercicio": ("orden-eha-3786-2008:art-2",),
        "decl.periodo": ("orden-eha-3786-2008:art-2",),
    }
    assert all(
        amendment_ref.id not in casilla.legal_refs and july_ref.id not in casilla.legal_refs
        for casilla in july_revision.casillas
        if casilla.id in {"decl.ejercicio", "decl.periodo"}
    )

    snapshot = _committed_snapshot("308", 2009, "AD-HOC", RegistryAuthorityGrade.APPLICABILITY)
    assert snapshot.revision.id == "2009-2011-junio"
    with pytest.raises(RegistryValidationError, match=r"declares 'applicability' authority grade.*requested 'filing'"):
        _committed_snapshot("308", 2009, "AD-HOC")


def test_modelo_308_live_casillas_have_labels_in_all_locales_after_revision_migration() -> None:
    modelo, _catalogues = _modelo_308()

    for revision in modelo.revisions.values():
        for locale in ("es", "en", "ca", "hu"):
            assert all(casilla.get_label(locale).strip() for casilla in revision.casillas)
