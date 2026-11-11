"""The warning about values nobody is recorded as typing names them in a few lines, never as a wall of numbers.

Every such box is still counted, a held zero as much as an assumed value,
because recalculating can change either. Up to twenty boxes are named by
number, in at most two lines at the width shown, the rest counted as "and N
more". Past twenty, the sections that hold them are named with how many each
holds. On a real Modelo 100 form, where every box holds such a value, the
recalculation warning names sections with counts that add up to every box.
"""

from __future__ import annotations

import re

import pytest
from rich.console import Console
from rich.text import Text
from textual.widgets import Static

from ......application.modelo.work_form_models import ModeloWorkForm
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....tests.settling import settle
from ..review import UnattributedBoxes, unattributed_words
from ..screen import ModeloWorkbenchScreen
from ..sources import BOX_LIST_LINES
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, registry_form_of

_CONSOLE = Console(width=200)
_SECTION_COUNT = re.compile(r"\((\d+)\)")


def _boxes(count: int, sections: tuple[str, ...] = ("Section",)) -> UnattributedBoxes:
    return UnattributedBoxes(
        boxes=tuple(f"[{number:02d}]" for number in range(1, count + 1)),
        sections=tuple(sections[number % len(sections)] for number in range(count)),
    )


@pytest.mark.unit
@pytest.mark.hex_entrypoint
@pytest.mark.parametrize("width", [30, 60, 120])
def test_up_to_twenty_boxes_are_named_in_two_lines_and_the_rest_counted(width: int) -> None:
    unattributed = _boxes(20)
    with override_settings(cadrumo_output_language="en"):
        words = unattributed_words(unattributed, console=_CONSOLE, width=width)

    named = re.findall(r"\[\d+\]", words)
    more = re.search(r"and (\d+) more", words)
    assert len(Text(words).wrap(_CONSOLE, width)) <= BOX_LIST_LINES
    assert named == list(unattributed.boxes[: len(named)])
    assert len(named) + (int(more.group(1)) if more else 0) == 20
    assert (more is None) == (len(named) == 20)


@pytest.mark.unit
@pytest.mark.hex_entrypoint
def test_past_twenty_boxes_the_sections_are_named_with_their_counts() -> None:
    unattributed = _boxes(25, ("Income", "Expenses", "Result"))
    with override_settings(cadrumo_output_language="en"):
        words = unattributed_words(unattributed, console=_CONSOLE, width=120)

    assert words == "Income (9), Expenses (8), Result (8)"


def _modelo_100(operation: PinnedAuthorityOperation) -> ModeloWorkForm:
    return registry_form_of(
        operation,
        modelo="100",
        year=newest_authored_edition("100"),
        code="0A",
        bucket_id="13000000-0000-4000-8000-000000000100",
        work_unit_id="d" * 64,
    )


@pytest.mark.integration
@pytest.mark.hex_entrypoint
@pytest.mark.asyncio
async def test_a_modelo_100_whose_values_nobody_typed_names_sections_with_counts_before_recalculating(
    operation: PinnedAuthorityOperation,
) -> None:
    built = _modelo_100(operation)
    boxes = {field.box for field in built.fields() if (field.box is not None and field.box)}
    form = replace_fields(built, {box: {"unattributed": True} for box in boxes}).model_copy(
        update={"calculation_revision_id": "b" * 64, "operator_entries_known": False}
    )
    total = sum(1 for field in form.fields() if field.unattributed)
    assert total > 20
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await pilot.press("c")
            await settle(pilot)
            dialog = app.screen
            message = (
                str(dialog.query_one("#confirm-message", Static).render()) if isinstance(dialog, ConfirmScreen) else ""
            )
            app.exit(None)
        lead = tr("workspace.modelo.calculate.operator_entries_at_risk", count=total, boxes="\u0000").split("\u0000")

    assert isinstance(dialog, ConfirmScreen)
    listed = message.removeprefix(lead[0]).removesuffix(lead[1])
    assert listed != message, "the warning names the boxes in its sentence"
    assert not re.search(r"\[\w+\]", listed), "past twenty boxes, sections are named, not box numbers"
    counted = sum(int(number) for number in _SECTION_COUNT.findall(listed))
    more = re.search(r"and (\d+) more$", listed)
    assert counted > 0
    assert counted == total or more is not None
    assert len(Text(listed).wrap(_CONSOLE, 120 - 4)) <= BOX_LIST_LINES
