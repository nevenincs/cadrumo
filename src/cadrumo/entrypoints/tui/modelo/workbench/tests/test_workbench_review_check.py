"""The review checks staged changes first, and nothing a filer typed is lost without their say.

Driven through the standalone host with the synthetic form and fake ports:

* what the application's check finds is listed on the review, and a finding
  that would make it refuse the changes keeps Apply unavailable;
* a declaration that does not record which values the filer typed names the
  boxes applying would return to their source, and asks for acknowledgement
  before applying or recalculating;
* a declaration that moved under the staged changes is read again, the
  changes are re-based on it, and the boxes that now read differently are
  marked on a review that asks for acknowledgement;
* verification findings, including those that name no box, are listed and
  lead to their box.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import override

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, Static

from ......application.modelo.work_form_models import (
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
    edit_address,
)
from ......application.modelo.work_form_service import ModeloWorkFormLoadV1, modelo_work_form_changes
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..issue_projection import issue_lines
from ..issues import WorkbenchIssuesScreen
from ..ports import WorkbenchChange, WorkbenchFinding, WorkbenchPreflight
from ..result import ResultGroup, result_lines
from ..review import EditReviewScreen, UnattributedBoxes, at_risk_text
from ..screen import ModeloWorkbenchScreen
from ..session import WorkbenchEditSession
from ..vocabulary import editability_text
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, fed_by, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (140, 40)
_TYPED = "300,50"


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _unattributed_form() -> ModeloWorkForm:
    """The fixture form as a calculation from outside the workbench leaves it: box 07's value is nobody's."""
    form = synthetic_form()
    pages = tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(
                        update={
                            "blocks": tuple(
                                block.model_copy(
                                    update={
                                        "rows": tuple(
                                            row.model_copy(
                                                update={
                                                    "cells": tuple(
                                                        cell.model_copy(
                                                            update={
                                                                "field": cell.field.model_copy(
                                                                    update={
                                                                        "origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM,
                                                                        "unattributed": True,
                                                                    }
                                                                )
                                                            }
                                                        )
                                                        if cell.field is not None and cell.field.box == "07"
                                                        else cell
                                                        for cell in row.cells
                                                    )
                                                }
                                            )
                                            for row in block.rows
                                        )
                                    }
                                )
                                if isinstance(block, ModeloFormGridBlock)
                                else block
                                for block in section.blocks
                            )
                        }
                    )
                    for section in page.sections
                )
            }
        )
        for page in form.pages
    )
    return form.model_copy(update={"pages": pages, "operator_entries_known": False})


async def _stage_on_withholding(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> None:
    """Type a value into box 06, on the second page, whatever box the workbench opened on."""
    target = address_key(ModeloFormCasillaAddressV1(casilla_id="06"))
    if not screen.query_one(CasillaList).focus_address(target):
        await pilot.press("right_square_bracket")
        await _settle(pilot)
        assert screen.query_one(CasillaList).focus_address(target)
    await _settle(pilot)
    await pilot.press("enter")
    await _settle(pilot)
    await pilot.press(*_TYPED, "enter")
    await _settle(pilot)


@pytest.mark.asyncio
async def test_a_blocking_finding_is_listed_and_keeps_apply_unavailable() -> None:
    actions = FakeActions(
        preflight_answer=WorkbenchPreflight(
            findings=(
                WorkbenchFinding(
                    address=ModeloFormCasillaAddressV1(casilla_id="06"), message="No se puede vaciar.", blocking=True
                ),
            )
        )
    )
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await _stage_on_withholding(pilot, screen)
            await pilot.press("R")
            await _settle(pilot)
            review = app.screen
            assert isinstance(review, EditReviewScreen)
            findings = str(review.query_one("#review-findings", Static).render())
            apply_disabled = review.query_one("#review-apply", Button).disabled
            await pilot.press("a")
            await _settle(pilot)
            still_reviewing = app.screen is review

    assert len(actions.checked) == 1
    assert "▲ [06] No se puede vaciar." in findings
    assert apply_disabled
    assert still_reviewing
    assert actions.applied == []


@pytest.mark.asyncio
async def test_an_unattributed_declaration_names_what_applying_returns_to_source_and_asks_first() -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_unattributed_form()), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await _stage_on_withholding(pilot, screen)
            await pilot.press("R")
            await _settle(pilot)
            review = app.screen
            assert isinstance(review, EditReviewScreen)
            warning = str(review.query_one("#review-at-risk", Static).render())
            before_acknowledging = review.query_one("#review-apply", Button).disabled
            review.query_one("#review-acknowledge", Checkbox).value = True
            await _settle(pilot)
            after_acknowledging = review.query_one("#review-apply", Button).disabled
            one_box = UnattributedBoxes(boxes=("[07]",), sections=("",))
            expected_warning = at_risk_text(one_box, console=app.console, width=_SIZE[0])

    assert "[07]" in warning
    assert warning == expected_warning
    assert before_acknowledging
    assert not after_acknowledging


@pytest.mark.asyncio
async def test_recalculating_an_unattributed_declaration_asks_first_and_can_be_declined() -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_unattributed_form()), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("c")
            await _settle(pilot)
            asked = app.screen
            assert isinstance(asked, ConfirmScreen)
            message = str(asked.query_one("#confirm-message", Static).render())
            await pilot.click("#btn-confirm-cancel")
            await _settle(pilot)
            after_declining = list(actions.requested)
            notice = str(screen.query_one("#wb-notice", Static).render())
            await pilot.press("c")
            await _settle(pilot)
            await pilot.click("#btn-confirm-accept")
            await _settle(pilot)

    assert "[07]" in message
    assert after_declining == []
    assert "Nothing was recalculated" in notice
    assert actions.requested == ["calculate"]


@pytest.mark.asyncio
async def test_recalculating_names_an_optional_zero_nobody_entered_though_it_is_not_to_do() -> None:
    zero = replace_fields(
        synthetic_form(),
        {"07": {"origin": ModeloFormOrigin.OPTIONAL_EMPTY, "value": Decimal("0.00"), "unattributed": True}},
    )
    form = zero.model_copy(update={"operator_entries_known": False})
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("c")
            await _settle(pilot)
            asked = app.screen
            assert isinstance(asked, ConfirmScreen)
            message = str(asked.query_one("#confirm-message", Static).render())

    assert "[07]" in message


@pytest.mark.asyncio
async def test_a_declaration_with_recorded_entries_recalculates_without_asking() -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("c")
            await _settle(pilot)
            asked = isinstance(app.screen, ConfirmScreen)

    assert not asked
    assert actions.requested == ["calculate"]


@dataclass
class _MovingReader(FakeReader):
    """Returns the fixture form, then the same form with box 06 filled by a new source value."""

    later: ModeloWorkForm = field(default_factory=synthetic_form)

    @override
    def load(self, language: OutputLanguage) -> ModeloWorkFormLoadV1:
        self.loads += 1
        form = self.form if self.loads == 1 else self.later
        return ModeloWorkFormLoadV1(form=form, verified=False, filed=False)


@dataclass
class _StaleOnceActions(FakeActions):
    """Says the declaration moved on the first check, and nothing afterwards."""

    def __post_init__(self) -> None:
        self._answers = [WorkbenchPreflight(stale=True)]

    @override
    async def preflight(self, changes: tuple[WorkbenchChange, ...]) -> WorkbenchPreflight:
        self.checked.append(changes)
        return self._answers.pop(0) if self._answers else WorkbenchPreflight()


def _with_withholding(form: ModeloWorkForm, value: Decimal, origin: ModeloFormOrigin) -> ModeloWorkForm:
    pages = tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(
                        update={
                            "blocks": tuple(
                                block.model_copy(
                                    update={"field": block.field.model_copy(update={"value": value, "origin": origin})}
                                )
                                if isinstance(block, ModeloFormFieldBlock) and block.field.box == "06"
                                else block
                                for block in section.blocks
                            )
                        }
                    )
                    for section in page.sections
                )
            }
        )
        for page in form.pages
    )
    return form.model_copy(update={"pages": pages})


@pytest.mark.asyncio
async def test_a_moved_declaration_is_read_again_and_its_changed_boxes_are_marked_for_acknowledgement() -> None:
    reader = _MovingReader(later=_with_withholding(synthetic_form(), Decimal("120.00"), ModeloFormOrigin.ENTERED))
    actions = _StaleOnceActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await _stage_on_withholding(pilot, screen)
            await pilot.press("R")
            await _settle(pilot, times=8)
            review = app.screen
            assert isinstance(review, EditReviewScreen)
            marked = str(review.query_one("#review-rebased", Static).render())
            needs_acknowledgement = review.query_one("#review-apply", Button).disabled
            staged = screen.staged_changes

    assert reader.loads == 2
    assert len(actions.checked) == 2
    assert "changed: 1" in marked
    assert needs_acknowledgement
    assert [change.before_changed for change in staged] == [True]
    assert staged[0].field.value == Decimal("120.00")


def test_a_change_that_no_longer_applies_is_dropped_on_rebase() -> None:
    session = WorkbenchEditSession(OutputLanguage.EN)
    form = synthetic_form()
    withholding = next(item for item in form.fields() if item.box == "06")
    assert session.stage_value(withholding, Decimal("300.50"), "300.50") is None
    locked = _with_withholding(form, Decimal("0"), ModeloFormOrigin.IMPORTED)
    locked_pages = tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(
                        update={
                            "blocks": tuple(
                                block.model_copy(
                                    update={
                                        "field": block.field.model_copy(
                                            update={"editability": ModeloFormEditability.LOCKED_SOURCE}
                                        )
                                    }
                                )
                                if isinstance(block, ModeloFormFieldBlock) and block.field.box == "06"
                                else block
                                for block in section.blocks
                            )
                        }
                    )
                    for section in page.sections
                )
            }
        )
        for page in locked.pages
    )

    outcome = session.rebase(locked.model_copy(update={"pages": locked_pages}))

    assert [change.field.box for change in outcome.dropped] == ["06"]
    assert not session.dirty


def test_an_override_of_a_bound_box_is_submitted_to_the_binding_it_replaces() -> None:
    carried = form_field(
        "05",
        "Pagos fraccionados anteriores",
        ModeloFormOrigin.IMPORTED,
        Decimal("250.00"),
        editability=ModeloFormEditability.OVERRIDABLE_SOURCE,
        bindings=(fed_by("m130.pagos_anteriores", BindingSourceKind.PREVIOUS_FILING),),
    )
    typed = form_field("06", "Retenciones", ModeloFormOrigin.NEEDS_INPUT)
    session = WorkbenchEditSession(OutputLanguage.EN)
    session.stage_value(carried, Decimal("300.00"), "300.00")
    session.stage_value(typed, Decimal("10.00"), "10.00")

    addresses = [change.address for change in session.payload()]

    assert edit_address(carried) == ModeloFormBindingAddressV1(binding_id="m130.pagos_anteriores")
    assert addresses == [
        ModeloFormBindingAddressV1(binding_id="m130.pagos_anteriores"),
        ModeloFormCasillaAddressV1(casilla_id="06"),
    ]


def test_a_box_that_cannot_be_edited_says_why() -> None:
    dated = form_field("02", "Fecha", ModeloFormOrigin.OPTIONAL_EMPTY).model_copy(
        update={"editability": ModeloFormEditability.NOT_WRITABLE, "not_writable_reason": "value_channel_unavailable"}
    )
    with override_settings(cadrumo_output_language="en"):
        text = editability_text(dated)

    assert text == "Values of this kind cannot be entered here yet."


def _finding(casilla_id: str | None, severity: ModeloVerificationFindingSeverity) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=severity,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.oss_evidence_missing",
        legal_refs=("ley-37-1992:art-99",),
    )


def _verified_with_findings() -> ModeloWorkForm:
    return synthetic_form(needs_input=False).model_copy(
        update={
            "verification": VerificationCompletenessStatus.BLOCKED,
            "issues": (
                ModeloFormIssue(finding=_finding("06", ModeloVerificationFindingSeverity.BLOCKING), box="06"),
                ModeloFormIssue(finding=_finding(None, ModeloVerificationFindingSeverity.WARNING)),
            ),
        }
    )


def test_every_finding_is_listed_blocking_first_whether_or_not_it_names_a_box() -> None:
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(_verified_with_findings())

    assert [(line.blocking, line.box) for line in lines] == [(True, "06"), (False, "·")]
    assert all("one-stop-shop" in line.message for line in lines)
    assert lines[0].key == address_key(ModeloFormCasillaAddressV1(casilla_id="06"))
    assert lines[1].key is None


@pytest.mark.asyncio
async def test_an_unresolved_verification_sends_the_filer_to_its_findings_and_from_there_to_the_box() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_verified_with_findings()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            next_line = str(screen.query_one("#wb-next", Static).render())
            await pilot.press("f8")
            await _settle(pilot)
            listed = isinstance(app.screen, WorkbenchIssuesScreen)
            await pilot.press("enter")
            await _settle(pilot)
            highlighted = screen.query_one(CasillaList).highlighted

    assert "Resolve what blocks filing (to do: 1) [i]" in next_line
    assert listed
    assert highlighted is not None
    assert highlighted.field.box == "06"


def test_what_a_recalculation_changed_is_grouped_by_why_it_changed() -> None:
    before = synthetic_form()
    after = _with_withholding(before, Decimal("300.50"), ModeloFormOrigin.ENTERED)
    net = next(item for item in after.fields() if item.box == "03")
    recalculated = after.model_copy(
        update={
            "pages": tuple(
                page.model_copy(
                    update={
                        "sections": tuple(
                            section.model_copy(
                                update={
                                    "blocks": tuple(
                                        block.model_copy(
                                            update={"field": net.model_copy(update={"value": Decimal("14000.00")})}
                                        )
                                        if isinstance(block, ModeloFormFieldBlock) and block.field.box == "03"
                                        else block
                                        for block in section.blocks
                                    )
                                }
                            )
                            for section in page.sections
                        )
                    }
                )
                for page in after.pages
            )
        }
    )
    changes = modelo_work_form_changes(before, recalculated)
    with override_settings(cadrumo_output_language="es"):
        lines = result_lines(
            changes,
            before=before,
            after=recalculated,
            yours=frozenset({address_key(ModeloFormCasillaAddressV1(casilla_id="06"))}),
            language=OutputLanguage.ES,
        )

    assert [(line.group, line.box) for line in lines] == [
        (ResultGroup.YOURS, "06"),
        (ResultGroup.CALCULATED, "03"),
    ]
    assert "14.500,00" in lines[1].before
    assert "14.000,00" in lines[1].after


@pytest.mark.asyncio
async def test_on_a_small_terminal_the_review_keeps_its_acknowledgement_and_buttons_in_view() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_unattributed_form()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            await _stage_on_withholding(pilot, screen)
            await pilot.press("R")
            await _settle(pilot)
            review = app.screen
            assert isinstance(review, EditReviewScreen)
            visible = {
                widget_id: review.query_one(widget_id).region.intersection(review.region).area > 0
                for widget_id in ("#review-acknowledge", "#review-apply", "#review-back", "#review-discard")
            }
            change = str(review.query_one("#review-change-0", Static).render())

    assert visible == dict.fromkeys(visible, True)
    assert "300,50" in change
    assert "[06]" in change
