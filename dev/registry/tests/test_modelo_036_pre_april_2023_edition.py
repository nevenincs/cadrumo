"""Modelo 036 before 25 April 2023 is filed on the design of Orden HAC/609/2021.

Orden HFP/381/2023 replaced the modelo 036 form from 2023-04-25. AEAT's design for
that form (aeat-dr-036-2023) prints the same records as the v3.8 design in force
since 2021-07-01 (aeat-dr-036-v35) plus boxes [744], [716.a/b] and [717.a/b] in
what was reserved space. The 2022-hasta-2023-04-24 edition is the storage baseline
without those five boxes; the edition from 2023-04-25 adds them and grounds every
continuing row's lineage in the two design lines.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.errors import AmbiguousRevisionSelectionError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OLD_DESIGN = "aeat-dr-036-v35"
_NEW_DESIGN = "aeat-dr-036-2023"
_ADDED_BOXES = frozenset({"744", "716.a", "717.a", "716.b", "717.b"})


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("036")


def _selected(on_year: int, on: date | None, period: str = "alta") -> ModeloRevision:
    modelo, catalogues = _modelo()
    return select_revision(modelo, filing_year=on_year, period=period, on=on, support=catalogues.supported_filing_years)


def _boundary() -> tuple[date, date]:
    _, catalogues = _modelo()
    first_new = catalogues.sources[_NEW_DESIGN].applies_from
    last_old = catalogues.sources[_OLD_DESIGN].applies_to
    assert first_new is not None and last_old is not None
    assert last_old + timedelta(days=1) == first_new
    return last_old, first_new


def test_the_design_windows_meet_on_the_orden_hfp_381_2023_entry_into_force() -> None:
    _, catalogues = _modelo()
    last_old, first_new = _boundary()
    assert catalogues.legal["orden-hfp-381-2023:df-unica"].effective_from == first_new
    modelo, _ = _modelo()
    old = modelo.revisions["2022-hasta-2023-04-24"]
    new = modelo.revisions["2023-hasta-2025-02-02"]
    assert (old.valid_to, new.valid_from) == (last_old, first_new)
    assert _OLD_DESIGN in old.source_refs and _NEW_DESIGN not in old.source_refs
    assert _NEW_DESIGN in new.source_refs and _OLD_DESIGN not in new.source_refs


def test_selection_by_date_splits_the_year_at_the_boundary() -> None:
    _, catalogues = _modelo()
    last_old, first_new = _boundary()
    floor = min(catalogues.supported_filing_years.years)
    for period in ("alta", "modificacion", "baja"):
        assert _selected(floor, None, period).id == "2022-hasta-2023-04-24"
        assert _selected(last_old.year, last_old, period).id == "2022-hasta-2023-04-24"
        assert _selected(first_new.year, first_new, period).id == "2023-hasta-2025-02-02"
    with pytest.raises(AmbiguousRevisionSelectionError):
        _selected(first_new.year, None)


def test_the_five_boxes_first_appear_on_the_april_2023_design() -> None:
    _, first_new = _boundary()
    old = _selected(first_new.year, first_new - timedelta(days=1))
    new = _selected(first_new.year, first_new)
    old_numbers = {casilla.number for casilla in old.casillas}
    new_numbers = {casilla.number for casilla in new.casillas}
    assert new_numbers - old_numbers == _ADDED_BOXES
    assert old_numbers <= new_numbers
    old_by_id = {casilla.id: casilla for casilla in old.casillas}
    for casilla in new.casillas:
        if casilla.number in _ADDED_BOXES:
            continue
        before = old_by_id[casilla.id]
        assert (before.number, before.section, before.data_type, before.continuidad_id) == (
            casilla.number,
            casilla.section,
            casilla.data_type,
            casilla.continuidad_id,
        )


def test_every_continuing_row_is_grounded_in_both_design_lines() -> None:
    _, first_new = _boundary()
    new = _selected(first_new.year, first_new)
    _, catalogues = _modelo()
    design_paths = set()
    for source in (_OLD_DESIGN, _NEW_DESIGN):
        corpus_path = catalogues.sources[source].corpus_path
        assert corpus_path is not None
        design_paths.add(corpus_path.removeprefix("corpus/") + ".extracted.md")
    for casilla in new.casillas:
        if casilla.continuidad_id is None or casilla.number in _ADDED_BOXES:
            continue
        assert casilla.continuidad_origin is CasillaLineageOrigin.GROUNDED, casilla.id
        evidence = casilla.continuidad_evidence or ""
        for design_path in design_paths:
            assert design_path in evidence, casilla.id
    corpus = bundled_path("corpus")
    for design_path in design_paths:
        assert (corpus / design_path).is_file()
