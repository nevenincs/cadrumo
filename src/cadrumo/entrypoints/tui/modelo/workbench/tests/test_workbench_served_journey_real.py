"""The workbench draws the journey the application serves with a real declaration, and decides none of it.

A Modelo 131 is seeded in real encrypted storage and calculated with an amount
nobody typed in the workbench, so the declaration waits for the filer to confirm
it. The production reader serves the form with its journey: the step states,
the next step, the first box that needs the filer, the check's verdict and why
the file for the AEAT is withheld. The workbench opened on that reader shows
each of those served values: its stepper marks the served states, its
next-action line names the served step and its key, it lands on the served
first box, the issue list says the served verdict, and refusing the file says
the served hold with the key of the served action that lifts it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.work_form_field_vocabulary import address_key
from ......application.modelo.work_form_header import ModeloFormExportHoldReason, form_header
from ......application.modelo.work_form_journey import ModeloFormStepStatus
from ......application.modelo.work_form_next_step import ModeloFormNextAction
from ......application.modelo.work_form_service import ModeloWorkFormLoadV1
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.calculations.registry.ids import BindingId
from .....tests.modelo_operator_work_storage import SEEDED_AT, seeded_operator_work
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import application_workbench
from ....tests.settling import settle, settle_until
from ..casilla_list import CasillaList
from ..factory import InstalledModeloWorkbench
from ..issues import WorkbenchIssuesScreen
from ..screen import ModeloWorkbenchScreen
from ..screen_constants import NEXT_KEYS
from ..vocabulary import DONE_MARK, HERE_MARK

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NO_VOLUME_BASE: BindingId = "modelo-131.page1.sin-datos-base-volumen"
"""A Modelo 131 amount the filer types that no printed box shows; calculated with it, it waits to be confirmed."""


@dataclass(frozen=True, slots=True)
class _Shown:
    """What the workbench showed of the declaration's journey."""

    highlighted: tuple[str, str] | None
    stepper: str
    next_line: str
    verdict: str
    withheld: bool
    hold_notice: str


@contextmanager
def _assumed_declaration(tmp_path: Path) -> Generator[InstalledModeloWorkbench]:
    with seeded_operator_work(tmp_path, modelo="131", estimation_regime="objetiva") as work:
        installed = application_workbench(work.work_unit, operation=work.operation)
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            clock=SEEDED_AT,
            binding_values={_NO_VOLUME_BASE: Decimal("250")},
        )
        yield installed


def _text(screen: ModeloWorkbenchScreen | WorkbenchIssuesScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


async def _opened(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> None:
    await settle_until(pilot, lambda: screen.form is not None, "the workbench to finish reading its declaration")


async def _shown(installed: InstalledModeloWorkbench) -> _Shown:
    """Open the workbench on the real reader and read what it draws of the journey."""
    screen = ModeloWorkbenchScreen(installed, actions=installed)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(160, 48)) as pilot:
        await _opened(pilot, screen)
        highlighted = screen.query_one(CasillaList).highlighted
        stepper = _text(screen, "#wb-stepper")
        next_line = _text(screen, "#wb-next")
        await pilot.press("i")
        await settle(pilot)
        issues = app.screen
        assert isinstance(issues, WorkbenchIssuesScreen), f"i opened {type(issues).__name__}, not the issue list"
        verdict = _text(issues, "#issues-verdict")
        await pilot.press("escape")
        await settle(pilot)
        withheld = screen._filing_withheld()
        await settle(pilot)
        hold_notice = _text(screen, "#wb-notice")
        app.exit(None)
    return _Shown(
        highlighted=None if highlighted is None else highlighted.key,
        stepper=stepper,
        next_line=next_line,
        verdict=verdict,
        withheld=withheld,
        hold_notice=hold_notice,
    )


def _step_words(load: ModeloWorkFormLoadV1) -> list[str]:
    """Each done or current step as the stepper names it, from the served step states."""
    marks = {ModeloFormStepStatus.DONE: DONE_MARK, ModeloFormStepStatus.CURRENT: HERE_MARK}
    return [
        f"{marks[state.status].glyph} {tr(f'workspace.modelo.step.{state.step.value}')}"
        for state in load.journey.steps
        if state.status in marks
    ]


def test_the_workbench_shows_the_served_journey_of_a_declaration_waiting_for_a_confirmation(tmp_path: Path) -> None:
    with _assumed_declaration(tmp_path) as installed, override_settings(cadrumo_output_language="en"):
        served = installed.load(OutputLanguage.EN)
        hold = form_header(served.form, OutputLanguage.EN, verified=served.verified, filed=served.filed).export_hold
        expected_steps = _step_words(served)
        next_words = tr("workspace.modelo.next.confirm", count=served.journey.next_step.count)
        shown = asyncio.run(_shown(installed))

    journey = served.journey
    assert journey.next_step.action is ModeloFormNextAction.CONFIRM, "the assumed amount waits to be confirmed"
    assert journey.first_attention is not None, "a declaration waiting for the filer serves where to start"
    assert journey.verdict.status is None, "the declaration was never checked"
    assert hold is not None and hold.reason is ModeloFormExportHoldReason.CONFIRM
    assert hold.action is ModeloFormNextAction.CONFIRM

    assert shown.highlighted == address_key(journey.first_attention.address), "it lands on the served first box"
    assert expected_steps, "the served journey has a current step"
    for words in expected_steps:
        assert words in shown.stepper, f"the stepper draws the served step {words!r}"
    assert next_words in shown.next_line
    assert shown.next_line.endswith(f"[{NEXT_KEYS[journey.next_step.action]}]")
    assert shown.verdict == journey.verdict.words, "the issue list says the served verdict"
    assert shown.withheld
    assert shown.hold_notice == f"{hold.words} [{NEXT_KEYS[hold.action]}]", "the hold names the served action's key"
