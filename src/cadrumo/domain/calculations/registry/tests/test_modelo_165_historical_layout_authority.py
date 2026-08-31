"""Evidence-bounded historical record-layout authority for Modelo 165.

The three bundled official designs establish four distinct operational eras:
the incomplete 2013 design remains applicability-only; the complete 2016
design supports filing through 2022; 2023--2025 remain applicability-only; and
the design whose own heading is ``Ejercicio 2026`` starts only in 2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.resources.bundled_data import bundled_path
from .._validate import RegistryValidator
from .._validate_export_exemption import validate_export_exemption_declarations
from .._validate_export_layout_coverage import validate_export_layout_record_coverage
from ..errors import RegistryValidationError
from ..loader import load_catalogue_file, load_modelo_directory, load_registry_tree
from ..record_design import extract_record_design
from ..temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_and_catalogue():  # type: ignore[no-untyped-def]  # reason: this direct isolated authority proof keeps concrete loader types private
    """Load only Modelo 165 and its canonical legal/source catalogue."""
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "165"))
    catalogue = load_catalogue_file(bundled_path("registry", "aeat", "legal", "modelo-165.toml"))
    return modelo, catalogue


def _catalogues():  # type: ignore[no-untyped-def]  # reason: registry catalogue model is private test plumbing
    """Load the canonical merged catalogue without validating foreign modelos."""
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return catalogues


def _design(catalogue, source_id: str):  # type: ignore[no-untyped-def]  # reason: concrete source/parser models remain test-local
    source = catalogue.sources[source_id]
    return source, extract_record_design(bundled_path() / source.corpus_path)


def _field_spans(design, *, record_type: str):  # type: ignore[no-untyped-def]  # reason: the parser schema is intentionally not a public test fixture
    sheet = next(sheet for sheet in design.require_complete() if record_type in sheet.name)
    return [(field.offset, field.length, field.description) for field in sheet.fields]


def test_modelo_165_selection_keeps_each_source_claim_inside_its_evidenced_era() -> None:
    """A current-file name cannot backdate its 2026 exercise heading."""
    modelo, _catalogue = _modelo_and_catalogue()

    assert [
        (
            revision.id,
            revision.authority_grade.value,
            revision.valid_from,
            revision.valid_to,
            len(revision.export_layouts),
        )
        for revision in modelo.revisions.values()
    ] == [
        ("2013-2015", "applicability", date(2013, 1, 1), date(2015, 12, 31), 0),
        ("2016-2022", "filing", date(2016, 1, 1), date(2022, 12, 31), 1),
        ("2023-2025", "applicability", date(2023, 1, 1), date(2025, 12, 31), 0),
        ("2026-y-siguientes", "filing", date(2026, 1, 1), None, 1),
    ]
    assert [
        select_revision(modelo, filing_year=year, period="0A").id for year in (2013, 2015, 2016, 2022, 2023, 2025, 2026)
    ] == [
        "2013-2015",
        "2013-2015",
        "2016-2022",
        "2016-2022",
        "2023-2025",
        "2023-2025",
        "2026-y-siguientes",
    ]

    assert modelo.revisions["2016-2022"].source_refs[-1] == "aeat-dr-165-2016-2022"
    assert modelo.revisions["2026-y-siguientes"].source_refs[-1] == "aeat-dr-165-2026"
    assert "aeat-dr-165-2026" not in modelo.revisions["2023-2025"].source_refs


def test_modelo_165_no_layout_intervals_are_accepted_only_at_applicability_grade() -> None:
    """The missing historical geometries do not masquerade as a filing capability."""
    modelo, _catalogue = _modelo_and_catalogue()

    for revision_id in ("2013-2015", "2023-2025"):
        revision = modelo.revisions[revision_id]
        assert revision.authority_grade.value == "applicability"
        assert revision.export_layouts == ()
        assert (
            validate_export_exemption_declarations(
                prefix=f"modelo 165 revision {revision_id}",
                modelo_id="165",
                revision=revision,
                publishes_record_design=True,
            )
            == []
        )


def test_modelo_165_applicability_only_eras_need_no_false_parity_anchor() -> None:
    """No-layout historical eras remain valid without backdating another design."""
    modelo, _catalogue = _modelo_and_catalogue()

    RegistryValidator(_catalogues(), source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_165_filing_claim_without_layout_or_parity_still_refuses() -> None:
    """The parity prerequisite remains fail-closed once an era claims filing."""
    modelo, _catalogue = _modelo_and_catalogue()
    application_only = modelo.revisions["2023-2025"]
    falsely_promoted = application_only.model_copy(update={"authority_grade": RegistryAuthorityGrade.FILING})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, falsely_promoted.id: falsely_promoted}})

    with pytest.raises(RegistryValidationError, match="must declare official workbook parity coverage"):
        RegistryValidator(_catalogues(), source_root=bundled_path()).validate_modelo(mutated)


def test_modelo_165_complete_designs_have_distinct_2016_and_2026_type_one_geometry() -> None:
    """The 2026 EMPRESA EMERGENTE byte cannot be projected onto the 2016 design."""
    modelo, catalogue = _modelo_and_catalogue()
    historic_source, historic_design = _design(catalogue, "aeat-dr-165-2016-2022")
    current_source, current_design = _design(catalogue, "aeat-dr-165-2026")

    assert (historic_source.record_design_epoch, historic_source.applies_from, historic_source.applies_to) == (
        "2016",
        date(2016, 1, 1),
        date(2022, 12, 31),
    )
    assert (current_source.record_design_epoch, current_source.applies_from, current_source.applies_to) == (
        "2026",
        date(2026, 1, 1),
        None,
    )
    assert [span[:2] for span in _field_spans(historic_design, record_type="Tipo 1") if span[0] >= 168] == [
        (168, 16),
        (169, 13),
        (182, 2),
        (184, 317),
    ]
    assert [span[:2] for span in _field_spans(current_design, record_type="Tipo 1") if span[0] >= 168] == [
        (168, 16),
        (169, 13),
        (182, 2),
        (184, 1),
        (185, 316),
    ]
    for revision_id in ("2016-2022", "2026-y-siguientes"):
        assert (
            validate_export_layout_record_coverage(
                prefix=f"modelo 165 revision {revision_id}",
                revision=modelo.revisions[revision_id],
                source_refs=catalogue.sources,
            )
            == []
        )


def test_modelo_165_corrected_2013_design_stays_applicability_only_without_layout() -> None:
    """The sourced filler correction closes the hole without creating a filing claim."""
    modelo, catalogue = _modelo_and_catalogue()
    source, design = _design(catalogue, "aeat-dr-165-2013-2015")

    assert (source.record_design_epoch, source.applies_from, source.applies_to) == (
        "2013",
        date(2013, 1, 1),
        date(2015, 12, 31),
    )
    assert modelo.revisions["2013-2015"].export_layouts == ()
    type_two = next(sheet for sheet in design.require_complete() if sheet.name == "Tipo 2 - Registro De Socios O Partícipes")
    assert [(field.offset, field.length) for field in type_two.fields if field.offset >= 97] == [
        (97, 5),
        (102, 399),
    ]
    assert [(correction.kind, correction.declared_start, correction.corrected_start) for correction in type_two.corrections] == [
        ("range_start", 104, 102),
    ]


def test_modelo_165_2016_coverage_refuses_removing_the_historical_pre_trailer_amount() -> None:
    """A mutation cannot turn the bytes before the historic blank trailer into fill."""
    modelo, catalogue = _modelo_and_catalogue()
    revision = modelo.revisions["2016-2022"]
    (layout,) = revision.export_layouts
    declarante = next(record for record in layout.records if record.id.endswith("declarante"))
    wounded_record = declarante.model_copy(
        update={
            "fields": tuple(field for field in declarante.fields if field.id != "modelo-165-t1-importe-fondos-propios"),
        },
    )
    wounded_layout = layout.model_copy(
        update={"records": tuple(wounded_record if record is declarante else record for record in layout.records)},
    )
    wounded_revision = revision.model_copy(update={"export_layouts": (wounded_layout,)})

    failures = validate_export_layout_record_coverage(
        prefix="modelo 165 revision 2016-2022",
        revision=wounded_revision,
        source_refs=catalogue.sources,
    )

    assert len(failures) == 1
    assert "@168+16" in failures[0]
