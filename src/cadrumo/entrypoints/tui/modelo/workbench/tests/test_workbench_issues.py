"""The issues list puts everything to look at on one scale, wraps every word and acts on every Enter.

The findings are real verification findings with real catalogue messages over
the synthetic form: one that blocks filing on a box, one worth checking about
the whole declaration, one about a box the form does not show, and the boxes
whose value was assumed. Driven through the workbench, the list is grouped by
level with a count per level, reads where, what is wrong and what to do for
each finding without cutting a word, keeps codes behind ``t``, and Enter goes
to a box, opens a detail in place or says the box is not on the form.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
)
from ......core.config import override_settings
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..issues import IssueLevel, WorkbenchIssuesScreen, assumed_values, issue_lines, level_counts, title_text
from ..screen import ModeloWorkbenchScreen
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MESSAGE_KEY = "application.modelo.findings.oss_evidence_missing"
_LEGAL_REF = "ley-37-1992:art-99"


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _finding(
    casilla_id: str | None,
    severity: ModeloVerificationFindingSeverity,
    kind: ModeloVerificationFindingKind = ModeloVerificationFindingKind.BLOCKING_RULE,
) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=kind,
        severity=severity,
        casilla_id=casilla_id,
        message_locale_key=_MESSAGE_KEY,
        legal_refs=(_LEGAL_REF,),
    )


def _checked(*, assumed: bool = True) -> ModeloWorkForm:
    """The fixture checked and blocked, with box 07 assumed rather than entered."""
    form = synthetic_form(needs_input=False)
    if assumed:
        form = replace_fields(form, {"07": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("0")}})
    return form.model_copy(
        update={
            "verification": VerificationCompletenessStatus.BLOCKED,
            "issues": (
                ModeloFormIssue(
                    finding=_finding(
                        None, ModeloVerificationFindingSeverity.WARNING, ModeloVerificationFindingKind.ADVISORY
                    )
                ),
                ModeloFormIssue(finding=_finding("06", ModeloVerificationFindingSeverity.BLOCKING), box="06"),
                ModeloFormIssue(
                    finding=_finding(
                        "71",
                        ModeloVerificationFindingSeverity.WARNING,
                        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
                    )
                ),
            ),
        }
    )


def _list_text(screen: WorkbenchIssuesScreen) -> str:
    options = screen.query_one("#issues-list", OptionList)
    return "\n".join(options.render_line(y).text.rstrip() for y in range(options.size.height))


def _words(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_findings_sit_on_one_scale_with_where_what_and_what_to_do() -> None:
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(_checked())
        assumed = assumed_values(_checked())
        title = title_text(level_counts(lines, assumed))

    assert [(line.level, line.box, line.where) for line in lines] == [
        (IssueLevel.BLOCKS, "06", "[06] Retenciones e ingresos a cuenta"),
        (IssueLevel.CHECK, "·", "Whole declaration"),
        (IssueLevel.CHECK, "71", "[71]"),
    ]
    assert [line.action for line in lines] == [
        "What to do: Correct what it describes, then calculate and check again.",
        "What to do: Read it and decide whether it applies to you. It does not stop you from filing.",
        "What to do: Compare the figures, correct the one that is wrong, then calculate again.",
    ]
    assert all(line.message.startswith("This declaration includes one-stop-shop") for line in lines)
    assert lines[0].key == address_key(ModeloFormCasillaAddressV1(casilla_id="06"))
    assert lines[1].key is None
    assert lines[2].key is None
    assert lines[2].detail.startswith("Box [71] is not shown on this declaration's pages.")
    assert assumed is not None
    assert assumed.where == "[07]"
    assert title == "Issues to look at   ▲ 1   ◐ 1   ◆ 2"


@pytest.mark.asyncio
async def test_the_list_groups_by_level_wraps_every_word_and_keeps_codes_behind_t() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_checked()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 100)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            title = str(issues.query_one("#issues-title", Static).render())
            before = _list_text(issues)
            await pilot.press("t")
            await _settle(pilot)
            technical = _list_text(issues)
            app.exit(None)

    headings = [line.strip() for line in before.splitlines() if line.strip().startswith(("▲", "◐", "◆"))]
    assert headings == ["▲ Blocks filing (1)", "◐ Assumed, please confirm (1)", "◆ Worth checking (2)"][: len(headings)]
    assert len(headings) == 3
    assert title.startswith("Issues to look at")
    message = "This declaration includes one-stop-shop (OSS) activity, but no supporting documents for it are saved."
    assert _words(before).count(message) == 3
    assert "…" not in before
    assert _LEGAL_REF not in before
    assert _words(technical).count(_LEGAL_REF) == 1


@pytest.mark.asyncio
async def test_enter_goes_to_a_box_opens_a_detail_or_says_the_box_is_not_on_the_form() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_checked()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 100)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            await pilot.press("end", "up", "enter")
            await _settle(pilot)
            opened = _list_text(issues)
            still_open = app.screen is issues
            await pilot.press("down", "enter")
            await _settle(pilot)
            not_on_form = _list_text(issues)
            await pilot.press("home", "enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted
            app.exit(None)

    assert still_open
    assert "This is advice. You can file the declaration as it is." in _words(opened)
    assert "Box [71] is not shown on this declaration's pages." in _words(not_on_form)
    assert back
    assert landed_on is not None
    assert landed_on.field.box == "06"


@pytest.mark.asyncio
async def test_enter_on_the_assumed_values_goes_to_the_first_of_their_boxes() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_checked()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            await pilot.press("down", "enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted
            app.exit(None)

    assert back
    assert landed_on is not None
    assert landed_on.field.box == "07"


def test_without_findings_or_assumed_values_the_list_says_there_is_nothing_to_look_at() -> None:
    form = _checked(assumed=False).model_copy(
        update={"issues": (), "verification": VerificationCompletenessStatus.COMPLETE}
    )
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(form)
        title = title_text(level_counts(lines, assumed_values(form)))

    assert lines == ()
    assert assumed_values(form) is None
    assert title == "Issues to look at"
