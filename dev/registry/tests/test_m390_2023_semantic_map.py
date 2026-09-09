"""Exact-source Modelo 390 2023 semantic-map and render-profile coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.loader import load_registry_tree

from ..pipeline._export_tree import render_complete_export_tree
from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..pipeline.render_check import GeneratedExportBootstrapTransport, revision_render_inputs
from ..pipeline.semantic_map import (
    SemanticMapEntry,
    load_semantic_map,
)
from ..pipeline.source_defects import source_defects_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_REF = "aeat-dr-390-2023"
_SOURCE_SHA256 = "179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7"
_PAGE_2_DELTA = {("Pág. 2", f"A{row}") for row in range(83, 102)}
_PAGE_2_DELTA_OWNERS = (
    (
        "A83",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-0-base",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-0.base",
    ),
    (
        "A84",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-0-cuota",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-0.cuota",
    ),
    (
        "A85",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-0-5-base",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-0-5.base",
    ),
    (
        "A86",
        "modelo-390-page-02-casilla-repercutido-recargo-super-reducido",
        "casilla",
        "iva.anual.repercutido.recargo.super-reducido",
    ),
    (
        "A87",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-0-62-base",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-0-62.base",
    ),
    (
        "A88",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-0-62-cuota",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-0-62.cuota",
    ),
    (
        "A89",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-1-4-base",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-1-4.base",
    ),
    (
        "A90",
        "modelo-390-page-02-casilla-repercutido-recargo-reducido",
        "casilla",
        "iva.anual.repercutido.recargo.reducido",
    ),
    (
        "A91",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-5-2-base",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-5-2.base",
    ),
    (
        "A92",
        "modelo-390-page-02-casilla-repercutido-recargo-general",
        "casilla",
        "iva.anual.repercutido.recargo.general",
    ),
    (
        "A93",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-1-75-base",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-1-75.base",
    ),
    (
        "A94",
        "modelo-390-page-02-casilla-repercutido-recargo-tipo-1-75-cuota",
        "casilla",
        "iva.anual.repercutido.recargo.tipo-1-75.cuota",
    ),
    ("A95", "modelo-390-page-02-casilla-modificacion-recargo-base", "casilla", "iva.anual.modificacion.recargo.base"),
    ("A96", "modelo-390-page-02-casilla-modificacion-recargo-cuota", "casilla", "iva.anual.modificacion.recargo.cuota"),
    (
        "A97",
        "modelo-390-page-02-casilla-modificacion-recargo-concurso-base",
        "casilla",
        "iva.anual.modificacion.recargo-concurso.base",
    ),
    (
        "A98",
        "modelo-390-page-02-casilla-modificacion-recargo-concurso-cuota",
        "casilla",
        "iva.anual.modificacion.recargo-concurso.cuota",
    ),
    ("A99", "modelo-390-page-02-casilla-cuota-devengada-total", "casilla", "iva.anual.cuota-devengada-total"),
    ("A100", "modelo-390-page-02-reserved-1526", "filler", None),
    ("A101", "modelo-390-page-02-close", "literal", "</T39002000>"),
)


def _design(source_ref: str, *, filing_year: int, epoch: str) -> RecordDesignIntermediate:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=epoch,
    )


def _field_index(design: RecordDesignIntermediate) -> dict[tuple[str, str], RecordDesignIntermediateField]:
    return {
        (sheet.record_identity, field.source_cell or ""): field for sheet in design.sheets for field in sheet.fields
    }


def _normalized_reused_owner(
    entry: SemanticMapEntry,
) -> tuple[
    str,
    str,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    tuple[str, ...],
    tuple[str, ...],
]:
    binding = None if entry.binding is None else str(entry.binding).replace("modelo-390-2022.", "modelo-390-2023.")
    source_refs = tuple(
        _SOURCE_REF if str(source_ref) == "aeat-dr-390-2022" else str(source_ref) for source_ref in entry.source_refs
    )
    return (
        entry.export_field_id,
        entry.kind.value,
        None if entry.casilla_id is None else str(entry.casilla_id),
        binding,
        entry.literal,
        entry.producer_key,
        None if entry.projection_ref is None else str(entry.projection_ref),
        entry.draft_attribute,
        entry.computed_key,
        tuple(str(legal_ref) for legal_ref in entry.legal_refs),
        source_refs,
    )


def test_m390_2023_reuses_522_anchors_and_pins_the_exact_page_2_relayout() -> None:
    design_2022 = _design("aeat-dr-390-2022", filing_year=2022, epoch="2022")
    design_2023 = _design(_SOURCE_REF, filing_year=2023, epoch="2023")
    fields_2022 = _field_index(design_2022)
    fields_2023 = _field_index(design_2023)
    measured_delta = {
        key for key in fields_2022.keys() | fields_2023.keys() if fields_2022.get(key) != fields_2023.get(key)
    }

    assert measured_delta == _PAGE_2_DELTA
    assert len(fields_2022) == 537
    assert len(fields_2023) == 541
    assert len(set(fields_2022) & set(fields_2023) - measured_delta) == 522
    assert sum(len(header.fields) for header in design_2023.auxiliary_envelope_headers) == 13

    semantic_map_2022 = load_semantic_map(Path("dev/registry/mappings/modelo_390/2022"))
    semantic_map = load_semantic_map(Path("dev/registry/mappings/modelo_390/2023"))
    entries_2022 = {
        (entry.anchor.record_identity, entry.anchor.source_cell): entry for entry in semantic_map_2022.entries
    }
    entries = {(entry.anchor.record_identity, entry.anchor.source_cell): entry for entry in semantic_map.entries}
    unchanged_keys = set(fields_2022) & set(fields_2023) - measured_delta
    assert {key: _normalized_reused_owner(entries_2022[key]) for key in unchanged_keys} == {
        key: _normalized_reused_owner(entries[key]) for key in unchanged_keys
    }
    actual = tuple(
        (
            cell,
            entries[("Pág. 2", cell)].export_field_id,
            entries[("Pág. 2", cell)].kind.value,
            str(entries[("Pág. 2", cell)].casilla_id)
            if entries[("Pág. 2", cell)].casilla_id is not None
            else entries[("Pág. 2", cell)].literal,
        )
        for cell, _field_id, _kind, _owner in _PAGE_2_DELTA_OWNERS
    )
    assert actual == _PAGE_2_DELTA_OWNERS


def test_m390_2023_profile_and_map_render_all_numbered_anchors_from_the_exact_source(tmp_path: Path) -> None:
    inputs = revision_render_inputs(
        bundled_authority(),
        modelo="390",
        revision="2023",
        source_ref=_SOURCE_REF,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-390-2023-fichero",
            line_ending="crlf",
            source_ref=_SOURCE_REF,
            source_sha256=_SOURCE_SHA256,
        ),
    )

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2023",
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
        source_defects=source_defects_for(_SOURCE_REF),
    )

    assert len(rendered.layout.records) == 8
    assert sum(len(record.fields) for record in rendered.layout.records) == 541
    close = next(
        field
        for record in rendered.layout.records
        for field in record.fields
        if str(field.id) == "modelo-390-page-07-close"
    )
    assert close.literal == "</T39007000>"
