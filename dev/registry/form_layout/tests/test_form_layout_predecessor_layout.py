"""A revision without a record design follows its predecessor only where its own form proves it.

Modelo 390 for ejercicio 2026 has an official form (Orden HAC/27/2026, anexo
IV) and no AEAT diseño de registro. Its committed layout is checked against
that form read independently of the generator: each continued box must stand
on the form page printing its page label. Each refusal is proven on a scratch
copy of the form's extracted text, beside the unmodified copy reproducing the
committed layout, never on the corpus.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormLayoutDefinition,
    FormLayoutSeedSource,
    FormPlacementKind,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from dev.docs.preprocess.sidecar import load_sidecar, write_sidecar

from ...compiler.loader import load_registry_tree
from ...record_design_labels import DATA_ROOT
from ..cli import REGISTRY_ROOT
from ..generator import generate_revision_layout
from ..official_form_pages import read_official_form_pages
from ..predecessor_layout import PredecessorLayout
from ..stability import continuity_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FORM = "boe-modelo-390-2026-form"
_PREDECESSOR_DESIGN = "aeat-dr-390-2025"
_PAGE_HEADING = re.compile(r"^# Pag\. \d+$", re.MULTILINE)


@cache
def _registry() -> tuple[Mapping[str, ModeloDefinition], Mapping[str, SourceReference]]:
    modelos, catalogues = load_registry_tree(REGISTRY_ROOT)
    return {str(modelo.id): modelo for modelo in modelos}, catalogues.sources


def _layout(revision: str) -> FormLayoutDefinition:
    return _registry()[0]["390"].revisions[revision].form_layouts[0]


def _form_pages_read_plainly() -> list[str]:
    """Split the form's extracted text on its page headings, without the generator's reader."""
    source = _registry()[1][_FORM]
    binary = DATA_ROOT / source.corpus_path
    text = binary.with_name(binary.name + ".extracted.md").read_text(encoding="utf-8")
    return [str(page) for page in _PAGE_HEADING.split(text)[1:]]


def _page_printing(label: str) -> str:
    """The one form page whose line ends with the page label, as the form prints it top right."""
    pattern = re.compile(re.escape(label) + r"$", re.MULTILINE)
    pages = [page for page in _form_pages_read_plainly() if pattern.search(page)]
    assert len(pages) == 1, label
    return pages[0]


def _on_form(layout: FormLayoutDefinition) -> dict[str, tuple[str, str]]:
    return layout.casilla_sections()


def test_390_2026_keeps_each_continuing_box_where_its_own_form_prints_it() -> None:
    layout = _layout("2026")
    assert layout.seed_source is FormLayoutSeedSource.PREDECESSOR_LAYOUT
    assert {_FORM, _PREDECESSOR_DESIGN} <= {source.source_ref for source in layout.design_sources}
    pages = {page.id: page.official_ref for page in layout.pages}
    boxes = {placement.casilla_id: placement.box_number for placement in layout.placements}
    continued = {
        casilla_id: page for casilla_id, (page, _section) in _on_form(layout).items() if pages[page] is not None
    }
    assert continued
    unprinted = [
        (casilla_id, boxes[casilla_id], pages[page])
        for casilla_id, page in continued.items()
        if boxes[casilla_id] not in _page_printing(str(pages[page])).split()
    ]
    assert unprinted == []


def test_390_2026_is_paginated_like_2025_for_every_box_it_declares() -> None:
    before, after = _layout("2025"), _layout("2026")
    revision = _registry()[0]["390"].revisions["2026"]
    keys_before = continuity_keys(_registry()[0]["390"].revisions["2025"])
    keys_after = continuity_keys(revision)
    positions_before = {keys_before[casilla_id]: position for casilla_id, position in _on_form(before).items()}
    positions_after = {keys_after[casilla_id]: position for casilla_id, position in _on_form(after).items()}
    shared = positions_before.keys() & positions_after.keys()
    assert shared
    assert {key: positions_after[key] for key in shared} == {key: positions_before[key] for key in shared}
    by_key = {keys_after[casilla.id]: casilla for casilla in revision.casillas}
    not_carried = positions_before.keys() - positions_after.keys()
    assert all(not by_key[key].number.isdigit() and by_key[key].form_number is None for key in not_carried)
    numbered = {
        keys_after[casilla_id] for casilla_id, (page, _section) in _on_form(after).items() if page == "numbered-boxes"
    }
    assert numbered
    assert numbered.isdisjoint(positions_before)


def test_the_form_reader_sets_aside_running_heads_and_arithmetic_captions() -> None:
    modelos, sources = _registry()
    form = read_official_form_pages(modelos["390"].revisions["2026"].source_refs, sources, DATA_ROOT)
    labels = {page.official_ref for page in _layout("2025").pages if page.official_ref is not None}
    second = form.page_labelled("Pág. 2", labels=labels)
    second_bis = form.page_labelled("Pág. 2 bis", labels=labels)
    assert second is not None and second_bis is not None and second is not second_bis
    assert "Pág. 2" not in second_bis.labels(labels)
    raw_bis = _page_printing("Pág. 2 bis")
    assert "26" in raw_bis.split() and "(34" in raw_bis.split()
    assert second.prints_box("26") and second.prints_box("34")
    assert not second_bis.prints_box("26")
    assert not second_bis.prints_box("34")
    assert second_bis.prints_box("47") and second_bis.prints_apartado("5")


def _generate_from(data_root: Path) -> tuple[FormLayoutDefinition, tuple[str, ...]]:
    modelos, sources = _registry()
    modelo = modelos["390"]
    predecessor = PredecessorLayout(revision=modelo.revisions["2025"], layout=modelo.revisions["2025"].form_layouts[0])
    outcome = generate_revision_layout(
        "390", modelo.revisions["2026"], sources=sources, data_root=data_root, predecessor=predecessor
    )
    assert outcome.layout is not None
    return outcome.layout, outcome.notes


def _scratch_form(tmp_path: Path, edit: Callable[[str, str], str] | None) -> Path:
    """Copy the forms 390/2026 cites into a scratch data root, rewriting the PDF's extracted pages."""
    modelos, sources = _registry()
    for ref in modelos["390"].revisions["2026"].source_refs:
        relative = sources[str(ref)].corpus_path
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DATA_ROOT / relative, target)
    binary = tmp_path / sources[_FORM].corpus_path
    extracted = load_sidecar(DATA_ROOT / sources[_FORM].corpus_path)
    if edit is not None:
        units = tuple(unit.model_copy(update={"text": edit(unit.title or "", unit.text)}) for unit in extracted.units)
        extracted = extracted.model_copy(update={"units": units})
    write_sidecar(binary, extracted)
    return tmp_path


def _sections(layout: FormLayoutDefinition) -> dict[str, tuple[str, str]]:
    return layout.casilla_sections()


def test_a_scratch_copy_of_the_form_reproduces_the_committed_layout(tmp_path: Path) -> None:
    layout, _notes = _generate_from(_scratch_form(tmp_path, None))
    assert layout == _layout("2026")


def test_a_box_its_page_no_longer_prints_falls_to_the_numbered_page(tmp_path: Path) -> None:
    box = "47"
    casilla = next(item.casilla_id for item in _layout("2026").placements if item.box_number == box)
    assert _sections(_layout("2026"))[casilla][0] == "pag-2-bis"

    def drop_box(title: str, text: str) -> str:
        return re.sub(rf"(?<!\S){box}(?!\S)", " ", text) if "Pág. 2 bis" in text else text

    layout, notes = _generate_from(_scratch_form(tmp_path, drop_box))
    assert _sections(layout)[casilla][0] == "numbered-boxes"
    assert any(casilla in note for note in notes)
    moved = {key for key, position in _sections(layout).items() if _sections(_layout("2026")).get(key) != position}
    assert moved == {casilla}


def test_a_page_label_printed_on_two_pages_confirms_neither(tmp_path: Path) -> None:
    def repeat_label(title: str, text: str) -> str:
        return text + "\nPág. 3" if title == "Pag. 19" else text

    layout, _notes = _generate_from(_scratch_form(tmp_path, repeat_label))
    assert "pag-3" in {page.id for page in _layout("2026").pages}
    assert "pag-3" not in {page.id for page in layout.pages}
    shown_on_page_3 = {key for key, (page, _section) in _sections(_layout("2026")).items() if page == "pag-3"}
    assert shown_on_page_3
    assert {_sections(layout)[key][0] for key in shown_on_page_3} == {"numbered-boxes"}


def test_an_apartado_its_page_no_longer_prints_drops_its_sections(tmp_path: Path) -> None:
    def drop_apartado(title: str, text: str) -> str:
        return text.replace("6. ", "") if "Pág. 5" in text else text

    layout, _notes = _generate_from(_scratch_form(tmp_path, drop_apartado))
    assert "pag-5" not in {page.id for page in layout.pages}
    assert {page.id for page in layout.pages} == {page.id for page in _layout("2026").pages} - {"pag-5"}


def test_a_revision_with_its_own_record_design_never_follows_its_predecessor() -> None:
    modelos, sources = _registry()
    modelo = modelos["390"]
    predecessor = PredecessorLayout(revision=modelo.revisions["2024"], layout=modelo.revisions["2024"].form_layouts[0])
    followed = generate_revision_layout(
        "390", modelo.revisions["2025"], sources=sources, data_root=DATA_ROOT, predecessor=predecessor
    )
    assert followed.layout == _layout("2025")
    assert followed.layout is not None and followed.layout.seed_source is FormLayoutSeedSource.EXPORT_RECORD_DESIGN


def test_every_continued_placement_is_on_the_form() -> None:
    layout = _layout("2026")
    shown = _on_form(layout)
    for placement in layout.placements:
        assert (placement.casilla_id in shown) == (placement.kind is FormPlacementKind.ON_FORM)
