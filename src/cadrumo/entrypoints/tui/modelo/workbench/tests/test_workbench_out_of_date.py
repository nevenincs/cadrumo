"""A calculation the filer's records changed under reads as out of date, and the next step is to calculate again.

Driven through the real workbench over the synthetic declaration with a result
to pay. When the last check found that the records changed after the
calculation, the header marks the result out of date and says to calculate
again, Calculate is no longer done, the next-action line names calculating
again with its key, and F8 calculates. The same declaration without that
finding shows the calculation done.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.work_form_models import ModeloFormIssue, ModeloFormResultDirection, ModeloWorkForm
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ....components.host import ScreenHostApp
from ..screen import ModeloWorkbenchScreen
from ..vocabulary import DONE_MARK, STALE_MARK
from .declaration_states import with_result
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _records_changed(form: ModeloWorkForm) -> ModeloWorkForm:
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.ledger_snapshot_drift_removed",
        message_facts={
            "modelo": "130",
            "filing_year": 2026,
            "period": "1T",
            "anchored": True,
            "changed_count": 0,
            "removed_count": 1,
        },
        legal_refs=("ley-37-1992:art-99",),
    )
    return form.model_copy(
        update={"issues": (ModeloFormIssue(finding=finding),), "verification": VerificationCompletenessStatus.BLOCKED}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [True, False], ids=["records-changed", "records-unchanged"])
async def test_records_changed_after_the_calculation_mark_it_out_of_date_and_lead_to_calculating_again(
    changed: bool,
) -> None:
    form = with_result(synthetic_form(needs_input=False), ModeloFormResultDirection.TO_PAY, Decimal("315"))
    if changed:
        form = _records_changed(form)
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        stale_words = f"{STALE_MARK.glyph} {tr('tui.modelo.workbench.header.stale.recalculate', key='c')}"
        next_words = tr("tui.modelo.workbench.next_line", action=tr("tui.modelo.workbench.next.recalculate"), key="c")
        calculate = tr("tui.modelo.workbench.step.calculate")
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(160, 40)) as pilot:
            await _settle(pilot)
            stale = str(screen.query_one("#wb-stale", Static).render())
            dimmed = screen.query_one("#wb-result", Static).has_class("-stale")
            stepper = str(screen.query_one("#wb-stepper", Static).render())
            next_line = str(screen.query_one("#wb-next", Static).render())
            await pilot.press("f8")
            await _settle(pilot, 6)
            app.exit(None)

    done = f"{DONE_MARK.glyph} {calculate}"
    if changed:
        assert stale == stale_words
        assert dimmed, "the figure no longer current is dimmed"
        assert done not in stepper
        assert next_line == next_words
        assert actions.requested == ["calculate"]
    else:
        assert stale == ""
        assert not dimmed
        assert done in stepper
        assert next_line != next_words
