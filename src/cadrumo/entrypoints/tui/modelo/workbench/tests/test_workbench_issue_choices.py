"""The findings list closes with a choice the workbench acts on: a box, an owning area, or confirming.

Driven on the list itself over the synthetic form, with real catalogue
messages. A finding about box 01, whose value comes from the filer's records,
offers ``a`` and closes asking to open those records; a finding about a box
the filer typed offers no area. While assumed values wait, ``c`` closes asking to
confirm them; on a declaration recorded as filed, where nothing is asked, it
does nothing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot

from ......application.modelo.source_policy import SourceSurface
from ......application.modelo.work_form_models import ModeloFormIssue, ModeloFormOrigin, ModeloWorkForm
from ......core.config import override_settings
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....components.host import ScreenHostApp
from ..issues import ConfirmAssumedValues, WorkbenchIssuesScreen, issue_lines
from ..sources import OpenSourceSurface
from .declaration_states import recorded_as_filed
from .form_edits import replace_fields
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LEGAL_REF = "ley-37-1992:art-99"
_STILL_OPEN = "still open"


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _warning(casilla_id: str) -> ModeloFormIssue:
    return ModeloFormIssue(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.oss_evidence_missing",
            legal_refs=(_LEGAL_REF,),
        ),
        box=casilla_id,
    )


def _form(*issues: ModeloFormIssue, assumed: bool = False) -> ModeloWorkForm:
    form = synthetic_form(needs_input=False)
    if assumed:
        form = replace_fields(form, {"07": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("0")}})
    return form.model_copy(update={"issues": issues})


async def _choose(form: ModeloWorkForm, *keys: str) -> object:
    with override_settings(cadrumo_output_language="en"):
        screen = WorkbenchIssuesScreen(form)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await pilot.press(*keys)
            await _settle(pilot)
            still_open = isinstance(app.screen, WorkbenchIssuesScreen)
            if still_open:
                app.exit(None)
    return _STILL_OPEN if still_open else app.return_value


def test_a_finding_about_a_box_fed_by_the_records_names_the_area_that_owns_it() -> None:
    with override_settings(cadrumo_output_language="en"):
        fed, unfed = issue_lines(_form(_warning("01"), _warning("07")))

    assert fed.area is SourceSurface.LEDGER
    assert unfed.area is None


@pytest.mark.asyncio
async def test_a_opens_the_area_that_owns_the_selected_findings_value() -> None:
    assert await _choose(_form(_warning("01")), "end", "a") == OpenSourceSurface(SourceSurface.LEDGER)


@pytest.mark.asyncio
async def test_a_does_nothing_on_a_finding_no_area_owns() -> None:
    assert await _choose(_form(_warning("07")), "end", "a") == _STILL_OPEN


@pytest.mark.asyncio
async def test_c_asks_to_confirm_the_assumed_values_while_any_wait() -> None:
    assert await _choose(_form(assumed=True), "c") == ConfirmAssumedValues()
    assert await _choose(_form(), "c") == _STILL_OPEN


@pytest.mark.asyncio
async def test_c_asks_nothing_on_a_declaration_recorded_as_filed() -> None:
    assert await _choose(recorded_as_filed(_form(assumed=True)), "c") == _STILL_OPEN
