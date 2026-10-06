"""Read-only form context is visible without becoming a casilla editing target."""

import pytest

from cadrumo.application.modelo.work_form_models import ModeloFormContextFieldBlock, section_fields
from cadrumo.application.modelo.workbench_projection import PublicModeloFormContextFieldBlock
from cadrumo.application.operations.public_mirror import project_public_mirror, restore_public_mirror

from ..casilla_list_models import CasillaListEntry, CasillaListNote
from ..page_items import WorkbenchFilter, page_items, workbench_pages
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("value", [None, False, "00123456X"])
def test_context_is_a_note_not_an_editable_field_and_mirrors_losslessly(value):
    form = synthetic_form()
    page = form.pages[0]
    section = page.sections[0]
    block = ModeloFormContextFieldBlock(
        id="context", label=section.heading.model_copy(update={"text": "Identificación"}), value=value
    )
    changed = section.model_copy(update={"blocks": (block, *section.blocks)})
    assert section_fields(changed) == section_fields(section)
    page = page.model_copy(update={"sections": (changed, *page.sections[1:])})
    form = form.model_copy(update={"pages": (page, *form.pages[1:])})
    shown = page_items(workbench_pages(form)[0], staged={})
    notes = [item for item in shown if isinstance(item, CasillaListNote) and item.text.startswith("Identificación:")]
    assert len(notes) == 1
    assert "False" not in notes[0].text and "None" not in notes[0].text
    assert all(item.key[1] != "context" for item in shown if isinstance(item, CasillaListEntry))
    assert not any(
        isinstance(item, CasillaListNote) and item.text.startswith("Identificación:")
        for item in page_items(workbench_pages(form)[0], staged={}, mode=WorkbenchFilter.CALCULATED)
    )
    public = project_public_mirror(block, ModeloFormContextFieldBlock, PublicModeloFormContextFieldBlock)
    assert restore_public_mirror(public, ModeloFormContextFieldBlock, PublicModeloFormContextFieldBlock) == block
    assert "address" not in block.model_dump()
