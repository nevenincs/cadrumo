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
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_models import ModeloWorkForm
from ......application.modelo.work_form_service import modelo_form_snapshot
from ......application.modelo.work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.modelos.codes import ModeloCode
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ..review import UnattributedBoxes, unattributed_words
from ..screen import ModeloWorkbenchScreen
from ..sources import BOX_LIST_LINES
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader

_CONSOLE = Console(width=200)
_SECTION_COUNT = re.compile(r"\((\d+)\)")


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


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
    modelo, year, code = "100", 2025, "0A"
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000100",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="d" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


@pytest.mark.integration
@pytest.mark.hex_entrypoint
@pytest.mark.asyncio
async def test_a_modelo_100_whose_values_nobody_typed_names_sections_with_counts_before_recalculating(
    operation: PinnedAuthorityOperation,
) -> None:
    built = _modelo_100(operation)
    boxes = {field.box for field in built.fields() if field.box}
    form = replace_fields(built, {box: {"unattributed": True} for box in boxes}).model_copy(
        update={"calculation_revision_id": "b" * 64, "operator_entries_known": False}
    )
    total = sum(1 for field in form.fields() if field.unattributed)
    assert total > 20
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot, 8)
            await pilot.press("c")
            await _settle(pilot)
            dialog = app.screen
            message = (
                str(dialog.query_one("#confirm-message", Static).render()) if isinstance(dialog, ConfirmScreen) else ""
            )
            app.exit(None)
        lead = tr("tui.modelo.workbench.calculate.operator_entries_at_risk", count=total, boxes="\u0000").split(
            "\u0000"
        )

    assert isinstance(dialog, ConfirmScreen)
    listed = message.removeprefix(lead[0]).removesuffix(lead[1])
    assert listed != message, "the warning names the boxes in its sentence"
    assert not re.search(r"\[\w+\]", listed), "past twenty boxes, sections are named, not box numbers"
    counted = sum(int(number) for number in _SECTION_COUNT.findall(listed))
    more = re.search(r"and (\d+) more$", listed)
    assert counted > 0
    assert counted == total or more is not None
    assert len(Text(listed).wrap(_CONSOLE, 120 - 4)) <= BOX_LIST_LINES
