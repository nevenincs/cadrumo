"""Truthful Modelo 341 record-design eras and historical byte geometry."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.hashing import hash_file
from .....core.resources import bundled_path
from .._validate_export_layout_coverage import validate_export_layout_record_coverage
from ..errors import AmbiguousRevisionSelectionError, NoRevisionForPeriodError
from ..record_design import extract_record_design
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_REF = "aeat-dr-341-2005-2015"
_HISTORICAL_LAYOUT = "modelo-341-fichero-2005-2015"


def test_modelo_341_historical_design_is_hash_pinned_and_completely_extracted() -> None:
    """Pin the exact official bytes and all twenty source coordinates."""
    _modelo, catalogues = _committed_modelo("341")
    source = catalogues.sources[_SOURCE_REF]
    path = bundled_path() / source.corpus_path

    assert source.evidence_tier == "layout_authority"
    assert source.authority == "aeat"
    assert source.kind == "record_design"
    assert source.record_design_epoch == "2005"
    assert (source.applies_from, source.applies_to) == (date(2005, 2, 1), date(2015, 12, 31))
    assert source.source_url.endswith("/ant_300_399/archivos/dr341_2005.pdf")
    assert hash_file(path) == (source.sha256, source.bytes)

    (sheet,) = extract_record_design(path).require_complete()
    assert sheet.total_positions == 619
    assert [(field.offset, field.length) for field in sheet.fields] == [
        (1, 3),
        (4, 1),
        (5, 9),
        (14, 4),
        (18, 4),
        (22, 2),
        (24, 13),
        (37, 13),
        (50, 13),
        (63, 5),
        (68, 5),
        (73, 5),
        (78, 13),
        (91, 13),
        (104, 13),
        (117, 13),
        (130, 20),
        (150, 100),
        (250, 20),
        (270, 350),
    ]


def test_modelo_341_refuses_pre_design_years_and_selects_two_layout_eras() -> None:
    """Refuse pre-design years and select each proven layout only in its era."""
    modelo, _catalogues = _committed_modelo("341")

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2004, period="4T", on=date(2004, 12, 31))
    historical = select_revision(modelo, filing_year=2005, period="1T", on=date(2005, 4, 1))
    historical_end = select_revision(modelo, filing_year=2015, period="4T", on=date(2015, 12, 31))
    current = select_revision(modelo, filing_year=2016, period="1T", on=date(2016, 1, 1))

    assert historical.id == historical_end.id == "2005-2015"
    assert historical.authority_grade.value == "applicability"
    assert historical.review_status.value == "agent_reviewed"
    assert [(layout.id, tuple(layout.source_refs)) for layout in historical.export_layouts] == [
        (_HISTORICAL_LAYOUT, (_SOURCE_REF,))
    ]

    assert current.id == "2016-y-siguientes"
    assert current.period_selector.year_from == 2016
    assert {ref for layout in current.export_layouts for ref in layout.source_refs} == {"aeat-dr-341-2016"}


def test_modelo_341_2005_effective_date_is_an_explicit_as_of_boundary() -> None:
    """Start on the first quarterly presentation period after 1 February."""
    modelo, _catalogues = _committed_modelo("341")

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2005, period="1T", on=date(2005, 3, 31))

    selected = select_revision(modelo, filing_year=2005, period="1T", on=date(2005, 4, 1))
    assert selected.id == "2005-2015"


def test_modelo_341_all_live_casillas_have_labels_in_every_shipped_locale() -> None:
    """Refuse a stale or missing locale occurrence in either live revision."""
    modelo, _catalogues = _committed_modelo("341")
    expected_ids = {
        "2005-2015": {
            "decl.ejercicio",
            "decl.periodo",
            "wire.letras-etiqueta",
            "wire.codigo-cuenta-cliente",
            "wire.observaciones",
            *(f"{number:02d}" for number in range(1, 11)),
        },
        "2016-y-siguientes": {
            "decl.ejercicio",
            "decl.periodo",
            *(f"{number:02d}" for number in range(1, 11)),
        },
    }

    for revision_id, casilla_ids in expected_ids.items():
        revision = modelo.revisions[revision_id]
        assert {casilla.id for casilla in revision.casillas} == casilla_ids
        for locale in ("es", "en", "ca", "hu"):
            assert all(casilla.get_label(locale).strip() for casilla in revision.casillas)

    historical = modelo.revisions["2005-2015"]
    wire_labels = {
        casilla.id: casilla.get_label("es") for casilla in historical.casillas if casilla.id.startswith("wire.")
    }
    assert wire_labels == {
        "wire.letras-etiqueta": "Letras de la etiqueta identificativa",
        "wire.codigo-cuenta-cliente": "Código de cuenta cliente (C.C.C.)",
        "wire.observaciones": "Observaciones",
    }


def test_modelo_341_historical_presentation_roles_are_shared_with_modelo_309() -> None:
    """Shared historical presentation concepts cannot retain singleton markers."""
    modelo_341, _catalogues = _committed_modelo("341")
    modelo_309, _catalogues = _committed_modelo("309")
    expected_roles = {
        "wire.letras-etiqueta": "letras_etiqueta_persona_fisica",
        "wire.observaciones": "observaciones_presentacion",
    }

    for modelo, revision_id in ((modelo_341, "2005-2015"), (modelo_309, "2004-2015")):
        casillas = {casilla.id: casilla for casilla in modelo.revisions[revision_id].casillas}
        for casilla_id, role in expected_roles.items():
            casilla = casillas[casilla_id]
            assert casilla.semantic_role == role
            assert casilla.semantic_role_cardinality == "shared"
            assert casilla.semantic_role_cardinality_reason is None


def test_modelo_341_historical_layout_covers_every_source_position() -> None:
    """Exercise the generic coverage validator against the real historical PDF."""
    modelo, catalogues = _committed_modelo("341")
    revision = modelo.revisions["2005-2015"]

    assert (
        validate_export_layout_record_coverage(
            prefix="modelo 341 revision 2005-2015",
            revision=revision,
            source_refs=catalogues.sources,
        )
        == []
    )

    (layout,) = revision.export_layouts
    (record,) = layout.records
    assert record.fields[0].offset == 1
    assert record.fields[-1].offset + record.fields[-1].length - 1 == 619


def test_modelo_341_selector_boundary_mutation_is_refused() -> None:
    """Extending the historical selector into 2016 must create ambiguity."""
    modelo, _catalogues = _committed_modelo("341")
    historical = modelo.revisions["2005-2015"]
    widened_selector = historical.period_selector.model_copy(update={"year_to": 2016})
    widened_historical = historical.model_copy(update={"period_selector": widened_selector})
    mutated = modelo.model_copy(
        update={"revisions": {**modelo.revisions, historical.id: widened_historical}},
    )

    with pytest.raises(AmbiguousRevisionSelectionError):
        select_revision(mutated, filing_year=2016, period="1T")


def test_modelo_341_historical_offset_mutation_is_refused() -> None:
    """Moving one authored slot must reopen the exact official coordinate."""
    modelo, catalogues = _committed_modelo("341")
    revision = modelo.revisions["2005-2015"]
    (layout,) = revision.export_layouts
    (record,) = layout.records
    index = next(index for index, field in enumerate(record.fields) if field.id.endswith("importe-operaciones-01"))
    fields = list(record.fields)
    fields[index] = fields[index].model_copy(update={"offset": 25})
    wounded_record = record.model_copy(update={"fields": tuple(fields)})
    wounded_layout = layout.model_copy(update={"records": (wounded_record,)})
    wounded_revision = revision.model_copy(update={"export_layouts": (wounded_layout,)})

    failures = validate_export_layout_record_coverage(
        prefix="modelo 341 revision 2005-2015",
        revision=wounded_revision,
        source_refs=catalogues.sources,
    )

    assert len(failures) == 1
    assert "@24+13" in failures[0]
