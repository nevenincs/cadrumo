"""Truthful Modelo 270 record-design eras and historical byte geometry."""

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

_HISTORICAL_SOURCE_REF = "boe-dr-270-2013-2022"
_CURRENT_SOURCE_REF = "aeat-dr-270-2023"
_AMENDMENT_LAYOUT_REF = "orden-hfp-1286-2023:art-2"
_AMENDMENT_APPLICABILITY_REF = "orden-hfp-1286-2023:df-unica"


def test_modelo_270_official_designs_are_hash_pinned_and_completely_extracted() -> None:
    """The two supported epochs each name exact, complete official bytes."""
    _modelo, catalogues = _committed_modelo("270")
    historical = catalogues.sources[_HISTORICAL_SOURCE_REF]
    current = catalogues.sources[_CURRENT_SOURCE_REF]

    assert "enrolled-modelo-270-layout" not in catalogues.sources
    assert historical.evidence_tier == "layout_authority"
    assert historical.authority == "boe"
    assert historical.kind == "record_design"
    assert historical.record_design_epoch == "2013"
    assert (historical.applies_from, historical.applies_to) == (date(2013, 1, 1), date(2022, 12, 31))
    assert historical.source_url.endswith("/BOE-A-2013-13228.pdf")
    historical_path = bundled_path() / historical.corpus_path
    assert hash_file(historical_path) == (historical.sha256, historical.bytes)

    sheets = extract_record_design(historical_path).require_complete()
    assert [(sheet.name, sheet.total_positions) for sheet in sheets] == [
        ("Tipo 1 - Registro De Declarante", 500),
        ("Tipo 2 - Registro De Perceptor", 500),
    ]
    assert [(field.offset, field.length) for field in sheets[0].fields] == [
        (1, 1),
        (2, 3),
        (5, 4),
        (9, 9),
        (18, 40),
        (58, 1),
        (59, 49),
        (108, 13),
        (121, 2),
        (123, 13),
        (136, 9),
        (145, 17),
        (162, 17),
        (179, 17),
        (196, 305),
    ]
    assert [(field.offset, field.length) for field in sheets[1].fields] == [
        (1, 1),
        (2, 3),
        (5, 4),
        (9, 9),
        (18, 9),
        (27, 9),
        (36, 40),
        (76, 40),
        (116, 1),
        (117, 1),
        (118, 2),
        (120, 8),
        (128, 8),
        (136, 15),
        (151, 15),
        (166, 15),
        (181, 1),
        (182, 251),
        (433, 20),
        (453, 8),
        (461, 37),
        (498, 2),
        (500, 1),
    ]

    assert current.evidence_tier == "layout_authority"
    assert current.authority == "aeat"
    assert current.kind == "record_design"
    assert current.record_design_epoch == "2023"
    assert (current.applies_from, current.applies_to) == (date(2023, 1, 1), date(2024, 12, 31))
    assert hash_file(bundled_path() / current.corpus_path) == (current.sha256, current.bytes)


def test_modelo_270_selects_each_proven_epoch_and_refuses_2025() -> None:
    """Never backdate the shifted 2023 layout or extrapolate an unproven one."""
    modelo, _catalogues = _committed_modelo("270")

    historical_start = select_revision(modelo, filing_year=2013, period="0A", on=date(2013, 1, 1))
    historical_end = select_revision(modelo, filing_year=2022, period="0A", on=date(2022, 12, 31))
    current_start = select_revision(modelo, filing_year=2023, period="0A", on=date(2023, 1, 1))
    current_end = select_revision(modelo, filing_year=2024, period="0A", on=date(2024, 12, 31))

    assert historical_start.id == historical_end.id == "2013-2022"
    assert current_start.id == current_end.id == "2023-2024"
    assert {ref for layout in historical_start.export_layouts for ref in layout.source_refs} == {_HISTORICAL_SOURCE_REF}
    assert {ref for layout in current_start.export_layouts for ref in layout.source_refs} == {_CURRENT_SOURCE_REF}

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2025, period="0A", on=date(2025, 1, 1))

    # HFP/1286/2023 reserves monthly period codes for convention-backed SELAE
    # and ONCE reporting. This ordinary annual Modelo 270 surface deliberately
    # does not invent a selector for that external route.
    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2023, period="01", on=date(2023, 1, 1))


def test_modelo_270_type_1_geometry_changes_only_at_the_proven_2023_boundary() -> None:
    """Pin the Type 1 PERIODO insertion and the corresponding shifted summary."""
    modelo, _catalogues = _committed_modelo("270")
    historical = modelo.revisions["2013-2022"]
    current = modelo.revisions["2023-2024"]

    def declarante_offsets(revision_id: str) -> dict[str, tuple[int, int]]:
        revision = modelo.revisions[revision_id]
        layout = next(layout for layout in revision.export_layouts if layout.id == "modelo-270-fichero-boe")
        record = next(record for record in layout.records if record.record_type == "declarante")
        offsets: dict[str, tuple[int, int]] = {}
        for field in record.fields:
            assert field.offset is not None
            assert field.length is not None
            offsets[field.id] = (field.offset, field.length)
        return offsets

    historical_fields = declarante_offsets(historical.id)
    current_fields = declarante_offsets(current.id)
    assert "modelo-270-decl-periodo" not in historical_fields
    assert historical_fields["modelo-270-decl-total-perceptores"] == (136, 9)
    assert historical_fields["modelo-270-decl-total-importe-premios"] == (145, 17)
    assert historical_fields["modelo-270-decl-total-base-retencion"] == (162, 17)
    assert historical_fields["modelo-270-decl-total-retenciones"] == (179, 17)
    assert historical_fields["modelo-270-decl-blancos"] == (196, 305)
    assert current_fields["modelo-270-decl-periodo"] == (136, 2)
    assert current_fields["modelo-270-decl-total-perceptores"] == (138, 9)
    assert current_fields["modelo-270-decl-total-importe-premios"] == (147, 17)
    assert current_fields["modelo-270-decl-total-base-retencion"] == (164, 17)
    assert current_fields["modelo-270-decl-total-retenciones"] == (181, 17)
    assert current_fields["modelo-270-decl-blancos"] == (198, 303)


def test_modelo_270_2023_type_1_change_is_legally_load_bearing() -> None:
    """Removing the amendment reference makes the shifted geometry ungrounded."""
    modelo, catalogues = _committed_modelo("270")
    current = modelo.revisions["2023-2024"]
    layout = next(layout for layout in current.export_layouts if layout.id == "modelo-270-fichero-boe")
    record = next(record for record in layout.records if record.record_type == "declarante")
    shifted_ids = {
        "modelo-270-decl-periodo",
        "modelo-270-decl-total-perceptores",
        "modelo-270-decl-total-importe-premios",
        "modelo-270-decl-total-base-retencion",
        "modelo-270-decl-total-retenciones",
        "modelo-270-decl-blancos",
    }

    assert {_AMENDMENT_LAYOUT_REF, _AMENDMENT_APPLICABILITY_REF} <= set(current.legal_refs)
    assert {_AMENDMENT_LAYOUT_REF, _AMENDMENT_APPLICABILITY_REF} <= set(current.orden_aplicabilidad)
    assert _AMENDMENT_LAYOUT_REF in layout.legal_refs
    assert all(_AMENDMENT_LAYOUT_REF in field.legal_refs for field in record.fields if field.id in shifted_ids)
    assert _AMENDMENT_LAYOUT_REF in catalogues.legal
    assert _AMENDMENT_APPLICABILITY_REF in catalogues.legal


def test_modelo_270_historical_layout_comment_matches_the_pinned_boe_source() -> None:
    """The historical human evidence trace must not borrow the 2023 digest."""
    _modelo, catalogues = _committed_modelo("270")
    historical = catalogues.sources[_HISTORICAL_SOURCE_REF]
    current = catalogues.sources[_CURRENT_SOURCE_REF]
    layout_path = (
        bundled_path() / "registry/aeat/modelos/270/revisions/2013-2022/export_layouts/0003-modelo-270-fichero-boe.toml"
    )
    layout_text = layout_path.read_text(encoding="utf-8")

    assert historical.sha256 in layout_text
    assert str(historical.bytes) in layout_text
    assert current.sha256 not in layout_text
    assert str(current.bytes) not in layout_text


def test_modelo_270_split_epochs_have_shipped_locale_labels() -> None:
    """The generated locale move must leave no live epoch on the retired key."""
    modelo, _catalogues = _committed_modelo("270")

    for revision_id in ("2013-2022", "2023-2024"):
        revision = modelo.revisions[revision_id]
        assert revision.casillas
        for locale in ("es", "en", "ca", "hu"):
            assert all(casilla.get_label(locale).strip() for casilla in revision.casillas)


def test_modelo_270_historical_layout_covers_every_source_position() -> None:
    """Exercise the generic coverage validator against the real historical PDF."""
    modelo, catalogues = _committed_modelo("270")
    historical = modelo.revisions["2013-2022"]

    assert (
        validate_export_layout_record_coverage(
            prefix="modelo 270 revision 2013-2022",
            revision=historical,
            source_refs=catalogues.sources,
        )
        == []
    )


def test_modelo_270_selector_boundary_mutation_is_refused() -> None:
    """Extending the historical selector into 2023 must create ambiguity."""
    modelo, _catalogues = _committed_modelo("270")
    historical = modelo.revisions["2013-2022"]
    widened_selector = historical.period_selector.model_copy(update={"year_to": 2023})
    widened_historical = historical.model_copy(update={"period_selector": widened_selector})
    mutated = modelo.model_copy(
        update={"revisions": {**modelo.revisions, historical.id: widened_historical}},
    )

    with pytest.raises(AmbiguousRevisionSelectionError):
        select_revision(mutated, filing_year=2023, period="0A")


def test_modelo_270_historical_offset_mutation_is_refused() -> None:
    """Moving one historical summary slot must reopen the official coordinate."""
    modelo, catalogues = _committed_modelo("270")
    historical = modelo.revisions["2013-2022"]
    layout = next(layout for layout in historical.export_layouts if layout.id == "modelo-270-fichero-boe")
    record = next(record for record in layout.records if record.record_type == "declarante")
    index = next(index for index, field in enumerate(record.fields) if field.id.endswith("total-importe-premios"))
    fields = list(record.fields)
    fields[index] = fields[index].model_copy(update={"offset": 146})
    wounded_record = record.model_copy(update={"fields": tuple(fields)})
    wounded_layout = layout.model_copy(
        update={
            "records": tuple(
                wounded_record if candidate.id == record.id else candidate for candidate in layout.records
            ),
        },
    )
    wounded_revision = historical.model_copy(
        update={
            "export_layouts": tuple(
                wounded_layout if candidate.id == layout.id else candidate for candidate in historical.export_layouts
            ),
        },
    )

    failures = validate_export_layout_record_coverage(
        prefix="modelo 270 revision 2013-2022",
        revision=wounded_revision,
        source_refs=catalogues.sources,
    )

    assert len(failures) == 1
    assert "@145+15" in failures[0]
