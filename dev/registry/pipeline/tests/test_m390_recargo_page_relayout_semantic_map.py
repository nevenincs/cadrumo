"""Exact-source Modelo 390 semantic map for the design that relays out the page 2 recargo rows."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.authored_edition_support import source_first_exercise, source_with_sha256
from ..semantic_map import SemanticMapEntry
from ..source_defects import source_defects_for
from .m390_semantic_map_support import (
    assert_page_07_close,
    load_edition_pair,
    render_edition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# The official record design this map is reviewed against, found by its pinned bytes;
# its catalogued applicability names the exercise. The predecessor design it is
# diffed against is the preceding exercise's.
_SOURCE_SHA256 = "179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7"
_SOURCE = source_with_sha256(_SOURCE_SHA256)
_SOURCE_REF = _SOURCE.id
_DESIGN_EXERCISE = source_first_exercise(_SOURCE)
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
        "iva.anual.repercutido.recargo.tipo-0-5.cuota",
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
        "iva.anual.repercutido.recargo.tipo-1-4.cuota",
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
        "iva.anual.repercutido.recargo.tipo-5-2.cuota",
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
    pair = load_edition_pair(
        source_ref=_SOURCE_REF,
        exercise=_DESIGN_EXERCISE,
        predecessor_source_ref=_PREDECESSOR_SOURCE_REF,
        predecessor_exercise=_PREDECESSOR_EXERCISE,
    )
    design, predecessor_fields, fields, measured_delta = pair.design, pair.predecessor_fields, pair.fields, pair.delta
    entries = pair.entries

    assert measured_delta == _PAGE_2_DELTA
    assert len(predecessor_fields) == 537
    assert len(fields) == 541
    assert len(set(predecessor_fields) & set(fields) - measured_delta) == 522
    assert sum(len(envelope.prefix_fields) for envelope in design.variable_envelopes) == 13

    unchanged_keys = pair.stable
    assert {key: _normalized_reused_owner(pair.predecessor_entries[key]) for key in unchanged_keys} == {
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
    rendered = render_edition(
        tmp_path,
        exercise=_DESIGN_EXERCISE,
        source_ref=_SOURCE_REF,
        source_sha256=_SOURCE_SHA256,
        source_defects=source_defects_for(_SOURCE_REF),
    )

    assert len(rendered.layout.records) == 8
    assert sum(len(record.fields) for record in rendered.layout.records) == 541
    assert_page_07_close(rendered)
