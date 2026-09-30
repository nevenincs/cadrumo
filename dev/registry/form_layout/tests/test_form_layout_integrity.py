"""The registry validator refuses a layout that misdescribes its revision.

Every defect is introduced into an in-memory copy of a real compiled revision
or into a temporary copy of a modelo directory, never into the registry tree,
and each refusal is proven beside the unmodified layout passing.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.form_layout_integrity import form_layout_failures
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormFieldBlock,
    FormLayoutDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
    FormSectionDefinition,
)

from ...compiler.loader import load_modelo_directory, load_registry_tree
from ...compiler.validate_form_layouts import validate_form_layout_section
from ..cli import REGISTRY_ROOT
from ..serialization import form_layout_fragment_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _modelos() -> Mapping[str, ModeloDefinition]:
    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    return {str(modelo.id): modelo for modelo in modelos}


def _revision(modelo: str, revision: str) -> ModeloRevision:
    return _modelos()[modelo].revisions[revision]


def _with_layout(revision: ModeloRevision, layout: FormLayoutDefinition) -> ModeloRevision:
    return revision.model_copy(update={"form_layouts": (layout,)})


def _add_block(layout: FormLayoutDefinition, block: object) -> FormLayoutDefinition:
    page = layout.pages[0]
    section = page.sections[0]
    grown = section.model_copy(update={"blocks": (*section.blocks, block)})
    page = page.model_copy(update={"sections": (grown, *page.sections[1:])})
    return layout.model_copy(update={"pages": (page, *layout.pages[1:])})


def test_the_committed_layout_describes_its_revision() -> None:
    revision = _revision("303", "2025")
    assert len(revision.form_layouts) == 1
    assert form_layout_failures(revision) == ()
    assert validate_form_layout_section(prefix="303 2025", revision=revision) == []


def test_an_omitted_casilla_is_refused() -> None:
    revision = _revision("303", "2025")
    layout = revision.form_layouts[0]
    dropped = layout.placements[0].casilla_id
    failures = form_layout_failures(
        _with_layout(revision, layout.model_copy(update={"placements": layout.placements[1:]}))
    )
    assert f"omits casilla {dropped!r}: every casilla carries exactly one placement" in " ".join(failures)


def test_an_invented_casilla_is_refused() -> None:
    revision = _revision("303", "2025")
    layout = revision.form_layouts[0]
    invented = FormPlacementDefinition(casilla_id="not-a-casilla", kind=FormPlacementKind.WORKING_FIGURE)
    failures = form_layout_failures(
        _with_layout(revision, layout.model_copy(update={"placements": (*layout.placements, invented)}))
    )
    assert any("places casilla 'not-a-casilla', which the revision does not declare" in item for item in failures)
    shown = _add_block(layout, FormFieldBlock(id="invented", casilla_id="also-not-a-casilla"))
    assert any(
        "shows casilla 'also-not-a-casilla'" in item for item in form_layout_failures(_with_layout(revision, shown))
    )


def test_a_casilla_shown_twice_is_refused() -> None:
    revision = _revision("303", "2025")
    layout = revision.form_layouts[0]
    on_form = next(item.casilla_id for item in layout.placements if item.kind is FormPlacementKind.ON_FORM)
    duplicated = _add_block(layout, FormFieldBlock(id="duplicate", casilla_id=on_form))
    failures = form_layout_failures(_with_layout(revision, duplicated))
    assert f"shows on-form casilla {on_form!r} in 2 positions; it belongs in exactly one" in " ".join(failures)


def test_a_working_figure_shown_on_the_form_is_refused() -> None:
    revision = _revision("303", "2025")
    layout = revision.form_layouts[0]
    working = next(item.casilla_id for item in layout.placements if item.kind is FormPlacementKind.WORKING_FIGURE)
    failures = form_layout_failures(
        _with_layout(revision, _add_block(layout, FormFieldBlock(id="w", casilla_id=working)))
    )
    assert any(
        f"shows casilla {working!r} on the form although it is placed 'working_figure'" in item for item in failures
    )


def test_a_stale_source_digest_is_refused() -> None:
    revision = _revision("303", "2025")
    stale = revision.form_layouts[0].model_copy(update={"source_state_digest": "0" * 64})
    assert any("form layout is stale" in item for item in form_layout_failures(_with_layout(revision, stale)))
    renumbered = revision.model_copy(
        update={"casillas": (revision.casillas[0].model_copy(update={"number": "999"}), *revision.casillas[1:])}
    )
    assert any("form layout is stale" in item for item in form_layout_failures(renumbered))


def test_a_repeating_group_over_a_scalar_binding_is_refused() -> None:
    revision = _revision("360", "2010-y-siguientes")
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    scalar = next(binding.id for binding in revision.bindings if binding.value.channel.value != "row_set")
    group = FormRepeatingGroupBlock(id="rows", row_source=FormRepeatingRowSource.ROW_SET_BINDING, binding_id=scalar)
    failures = form_layout_failures(_with_layout(revision, _add_block(layout, group)))
    assert any(f"ranges over non-row-set binding {scalar!r}" in item for item in failures)
    record = FormRepeatingGroupBlock(
        id="rows", row_source=FormRepeatingRowSource.EXPORT_RECORD, export_record_id="nope"
    )
    assert any(
        "is not a repeating export record" in item
        for item in form_layout_failures(_with_layout(revision, _add_block(layout, record)))
    )


def test_a_binding_offered_as_an_input_must_be_manual() -> None:
    revision = _revision("303", "2025")
    layout = revision.form_layouts[0]
    derived = next(binding.id for binding in revision.bindings if str(binding.provider.kind) != "manual_input")
    failures = form_layout_failures(
        _with_layout(revision, _add_block(layout, FormFieldBlock(id="b", binding_id=derived)))
    )
    assert any(f"offers binding {derived!r} as an input" in item for item in failures)


def test_two_layouts_for_one_revision_are_refused() -> None:
    revision = _revision("130", "2019-y-siguientes")
    layout = revision.form_layouts[0]
    doubled = revision.model_copy(update={"form_layouts": (layout, layout)})
    assert form_layout_failures(doubled) == ("declares 2 form layouts; a revision has at most one",)


def test_a_malformed_grid_in_a_temporary_registry_copy_fails_to_load(tmp_path: Path) -> None:
    source = REGISTRY_ROOT / "modelos" / "111"
    copy = tmp_path / "111"
    shutil.copytree(source, copy)
    fragment = form_layout_fragment_path(copy / "revisions" / "2019-y-siguientes")
    text = fragment.read_text(encoding="utf-8")
    narrowed = text.replace('cells = [{ kind = "casilla", casilla_id = "01" }, ', "cells = [", 1)
    assert narrowed != text
    assert isinstance(load_modelo_directory(copy).revisions["2019-y-siguientes"].form_layouts[0], FormLayoutDefinition)
    fragment.write_text(narrowed, encoding="utf-8", newline="\n")
    with pytest.raises(RegistryError, match="has 2 cells for 3 columns"):
        load_modelo_directory(copy)


def test_a_section_without_blocks_is_refused() -> None:
    with pytest.raises(ValueError, match="at least 1 item"):
        FormSectionDefinition.model_validate(
            {"id": "s", "heading_key": "modelo.form.s.heading", "blocks": []}, strict=False
        )
