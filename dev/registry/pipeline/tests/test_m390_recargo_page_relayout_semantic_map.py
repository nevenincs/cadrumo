"""Exact-source Modelo 390 semantic map for the design that relays out the page 2 recargo rows."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_registry_tree
from ...tests.authored_edition_support import source_exercise, source_with_sha256
from .._export_tree import render_complete_export_tree
from ..record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..render_check import GeneratedExportBootstrapTransport, revision_render_inputs
from ..semantic_map import (
    SemanticMapEntry,
    load_semantic_map,
)
from ..source_defects import source_defects_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# The official record design this map is reviewed against, found by its pinned bytes;
# its catalogued applicability names the exercise. The predecessor design it is
# diffed against is the preceding exercise's.
_SOURCE_SHA256 = "179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7"
_SOURCE = source_with_sha256(_SOURCE_SHA256)
_SOURCE_REF = _SOURCE.id
_DESIGN_EXERCISE = source_exercise(_SOURCE)
_PREDECESSOR_EXERCISE = _DESIGN_EXERCISE - 1
_PREDECESSOR_SOURCE_REF = f"aeat-dr-390-{_PREDECESSOR_EXERCISE}"
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
    binding = (
        None
        if entry.binding is None
        else str(entry.binding).replace(f"modelo-390-{_PREDECESSOR_EXERCISE}.", f"modelo-390-{_DESIGN_EXERCISE}.")
    )
    source_refs = tuple(
        _SOURCE_REF if str(source_ref) == _PREDECESSOR_SOURCE_REF else str(source_ref)
        for source_ref in entry.source_refs
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


def test_m390_recargo_relayout_reuses_522_predecessor_anchors_and_pins_the_exact_page_2_delta() -> None:
    predecessor_design = _design(
        _PREDECESSOR_SOURCE_REF, filing_year=_PREDECESSOR_EXERCISE, epoch=str(_PREDECESSOR_EXERCISE)
    )
    design = _design(_SOURCE_REF, filing_year=_DESIGN_EXERCISE, epoch=str(_DESIGN_EXERCISE))
    predecessor_fields = _field_index(predecessor_design)
    fields = _field_index(design)
    measured_delta = {
        key for key in predecessor_fields.keys() | fields.keys() if predecessor_fields.get(key) != fields.get(key)
    }

    assert measured_delta == _PAGE_2_DELTA
    assert len(predecessor_fields) == 537
    assert len(fields) == 541
    assert len(set(predecessor_fields) & set(fields) - measured_delta) == 522
    assert sum(len(header.fields) for header in design.auxiliary_envelope_headers) == 13

    predecessor_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_390/{_PREDECESSOR_EXERCISE}"))
    semantic_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_390/{_DESIGN_EXERCISE}"))
    predecessor_entries = {
        (entry.anchor.record_identity, entry.anchor.source_cell): entry for entry in predecessor_map.entries
    }
    entries = {(entry.anchor.record_identity, entry.anchor.source_cell): entry for entry in semantic_map.entries}
    unchanged_keys = set(predecessor_fields) & set(fields) - measured_delta
    assert {key: _normalized_reused_owner(predecessor_entries[key]) for key in unchanged_keys} == {
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


def test_m390_recargo_relayout_profile_and_map_render_all_numbered_anchors_from_the_exact_source(
    tmp_path: Path,
) -> None:
    inputs = revision_render_inputs(
        compiled_bundled_authority(),
        modelo="390",
        revision=str(_DESIGN_EXERCISE),
        source_ref=_SOURCE_REF,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id=f"generated-modelo-390-{_DESIGN_EXERCISE}-fichero",
            line_ending="crlf",
            source_ref=_SOURCE_REF,
            source_sha256=_SOURCE_SHA256,
        ),
    )

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=str(_DESIGN_EXERCISE),
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
