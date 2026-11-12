"""The workbench offers the statements the form serves, stages several for one review, and marks a stated box.

Driven through the standalone host with the synthetic form, which here also
shows carries that hold no value and serves a statement for each family of
them, and the fake ports:

* ``a`` lists every statement the form serves, in its order and in its words;
* ticking two stages both, on every box each names, for one review that
  checks them together and says what each does in the form's words;
* a box the filer stated holds no amount draws a mark of its own beside the
  form's words for the statement, never the mark of a value typed, and its
  panel offers only to withdraw the statement;
* a form that serves no statement offers none, on the form or in a box's panel.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.widgets import Button, Checkbox, Static

from ......application.modelo.work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    address_key,
)
from ......application.modelo.work_form_models import (
    ModeloFormCarryAttestation,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormPage,
    ModeloFormSection,
    ModeloWorkForm,
)
from ......application.modelo.work_form_wording import origin_words
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ....components.host import ScreenHostApp
from ....tests.settling import settle
from ..casilla_list import CasillaList
from ..ports import WorkbenchChange, WorkbenchChangeKind
from ..review import EditReviewScreen
from ..screen import ModeloWorkbenchScreen
from ..session import WorkbenchEditSession
from ..statements import StatementsScreen
from ..vocabulary import ORIGIN_GLYPHS, STATED_MARK
from .editor_panel import open_panel
from .workbench_fixture import FakeActions, FakeReader, form_counts, form_text, synthetic_form, with_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (160, 48)
# The family set grows; two of its members are enough to show one statement per family.
_FIRST, _SECOND, *_ = tuple(AbsenceAttestationFamily)
#: The open carries each family's statement names, and one carry already stated under the first family.
_OPEN: dict[AbsenceAttestationFamily, tuple[str, ...]] = {
    _FIRST: ("carry.first.a", "carry.first.b"),
    _SECOND: ("carry.second.a",),
}
_STATED_BINDING = "carry.first.stated"


def _carry(
    binding_id: str,
    label: str,
    *,
    stated: AbsenceAttestationFamily | None = None,
    editability: ModeloFormEditability = ModeloFormEditability.EDITABLE_VALUE,
) -> ModeloFormField:
    """A carry no casilla owns: open and typed by the filer, or holding a zero they stated."""
    return ModeloFormField(
        address=ModeloFormBindingAddressV1(binding_id=binding_id),
        box=None,
        label=form_text(label),
        help=None,
        data_type="money",
        value=None if stated is None else Decimal("0"),
        origin=ModeloFormOrigin.OPTIONAL_EMPTY if stated is None else ModeloFormOrigin.ENTERED,
        editability=editability,
        required=False,
        stated_absent=stated,
    )


def _statement(family: AbsenceAttestationFamily) -> ModeloFormCarryAttestation:
    """A served statement with synthetic words, naming the family's open carries."""
    return ModeloFormCarryAttestation(
        family=family,
        binding_ids=tuple(sorted(_OPEN[family])),
        action_words=f"Synthetic action {family.value}",
        statement_words=f"Synthetic statement {family.value}",
        effect_words=f"Synthetic effect {family.value}",
    )


def _form(*, served: bool = True) -> ModeloWorkForm:
    """The synthetic form with a page of carries, serving a statement per family unless ``served`` is false."""
    base = synthetic_form()
    carries = [
        *(_carry(binding_id, f"Carry {binding_id}") for family in _OPEN for binding_id in _OPEN[family]),
        _carry(_STATED_BINDING, "Carry already stated", stated=_FIRST),
    ]
    section = ModeloFormSection(
        id="p3.s1",
        heading=form_text("Carries"),
        official_heading=None,
        blocks=tuple(ModeloFormFieldBlock(id=f"carry{index}", field=item) for index, item in enumerate(carries)),
        counts=form_counts(carries),
        applies=True,
    )
    page = base.pages[0].model_copy(
        update={"id": "p3", "heading": form_text("Carries"), "sections": (section,), "counts": form_counts(carries)}
    )
    statements = tuple(_statement(family) for family in (_FIRST, _SECOND)) if served else ()
    pages: tuple[ModeloFormPage, ...] = (*base.pages, page)
    return with_pages(base, pages, carry_attestations=statements)


def _list_text(screen: ModeloWorkbenchScreen) -> str:
    widget = screen.query_one(CasillaList)
    return "\n".join(widget.render_line(y).text for y in range(widget.size.height))


@pytest.mark.asyncio
async def test_the_offer_lists_every_served_statement_in_the_served_order_and_words() -> None:
    form = _form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            dialog = app.screen
            assert isinstance(dialog, StatementsScreen)
            listed = dialog.statements
            ticks = [str(box.label) for box in dialog.query(Checkbox)]
            words = [str(item.render()) for item in dialog.query(".statement-words").results(Static)]
            ticked = [box.value for box in dialog.query(Checkbox)]
            stage_disabled = dialog.query_one("#statements-stage", Button).disabled

    assert listed == form.carry_attestations
    assert ticks == [statement.action_words for statement in form.carry_attestations]
    assert words == [statement.statement_words for statement in form.carry_attestations]
    assert ticked == [False, False]
    assert stage_disabled


@pytest.mark.asyncio
async def test_choosing_two_statements_stages_both_on_every_box_they_name_for_one_review() -> None:
    form = _form()
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            dialog = app.screen
            assert isinstance(dialog, StatementsScreen)
            for box in dialog.query(Checkbox):
                box.value = True
            await settle(pilot)
            await pilot.click("#statements-stage")
            await settle(pilot)
            staged = screen.staged_changes
            await pilot.press("R")
            await settle(pilot)
            review = app.screen
            assert isinstance(review, EditReviewScreen)
            lines = [str(item.render()) for item in review.query(".review-change").results(Static)]
            await pilot.press("a")
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            reopened = app.screen
            assert isinstance(reopened, StatementsScreen)
            reopened_ticks = [box.value for box in reopened.query(Checkbox)]

    expected = tuple(
        WorkbenchChange(
            address=ModeloFormBindingAddressV1(binding_id=binding_id), kind=WorkbenchChangeKind.STATE_ABSENT
        )
        for statement in form.carry_attestations
        for binding_id in statement.binding_ids
    )
    assert tuple(change.change for change in staged) == expected
    assert actions.checked == [expected]
    assert actions.applied == [expected]
    for statement in form.carry_attestations:
        named = [line for line in lines if statement.effect_words in line]
        assert len(named) == len(statement.binding_ids), (statement.family, lines)
        assert all(statement.action_words in line for line in named)
    assert reopened_ticks == [True, True]


@pytest.mark.asyncio
async def test_leaving_a_staged_statement_unticked_withdraws_it_and_keeps_the_other() -> None:
    form = _form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            for box in app.screen.query(Checkbox):
                box.value = True
            await pilot.click("#statements-stage")
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            app.screen.query_one("#statement-0", Checkbox).value = False
            await settle(pilot)
            await pilot.click("#statements-stage")
            await settle(pilot)
            kept = {change.statement.family for change in screen.staged_changes if change.statement is not None}

    assert kept == {form.carry_attestations[1].family}


@pytest.mark.asyncio
async def test_a_stated_box_draws_its_own_mark_and_the_served_words_and_offers_only_withdrawal() -> None:
    form = _form()
    stated = next(item for item in form.fields() if item.stated_absent is not None)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            screen._go_to(address_key(stated.address))
            await settle(pilot)
            listing = _list_text(screen)
            help_band = str(screen.query_one("#wb-help", Static).render())
            await pilot.press("enter")
            await settle(pilot)
            panel = open_panel(app.screen)
            assert panel is not None
            buttons = {str(button.label) for button in panel.query(Button)}
        served_words = origin_words(stated)

    stated_line = next(line for line in listing.splitlines() if "Carry already stated" in line)
    open_line = next(line for line in listing.splitlines() if "Carry carry.first.a" in line)
    assert f"{STATED_MARK.glyph} {served_words}" in stated_line, stated_line
    assert ORIGIN_GLYPHS[ModeloFormOrigin.ENTERED] not in stated_line
    assert STATED_MARK.glyph not in open_line
    assert f"{STATED_MARK.glyph} {served_words}" in help_band
    assert "Withdraw the statement" in buttons
    assert "Clear" not in buttons


@pytest.mark.asyncio
async def test_a_form_serving_no_statement_offers_none_on_the_form_or_in_a_box() -> None:
    form = _form(served=False)
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            offered = isinstance(app.screen, StatementsScreen)
            notice = str(screen.query_one("#wb-notice", Static).render())
            open_carry = next(item for item in form.fields() if item.stated_absent is None and item.box is None)
            screen._go_to(address_key(open_carry.address))
            await settle(pilot)
            await pilot.press("enter")
            await settle(pilot)
            panel = open_panel(app.screen)
            assert panel is not None
            button_ids = {button.id for button in panel.query(Button)}

    assert not offered
    assert notice == "This declaration offers no statement to make now."
    assert button_ids <= {"editor-cancel", "editor-save", "editor-save-next", "editor-clear", "editor-restore"}
    assert not screen.staged_changes


def _stated_family_form(*, locked: bool = False) -> ModeloWorkForm:
    """A form holding two carries stated under the first family and one under the second.

    With ``locked``, the second carry of the first family takes no withdrawal of its own.
    """
    first_b = _carry(
        "carry.first.stated.b",
        "Carry stated b",
        stated=_FIRST,
        editability=ModeloFormEditability.LOCKED_SOURCE if locked else ModeloFormEditability.EDITABLE_VALUE,
    )
    carries = [
        _carry("carry.first.stated.a", "Carry stated a", stated=_FIRST),
        first_b,
        _carry("carry.second.stated", "Carry stated second", stated=_SECOND),
    ]
    base = _form(served=False)
    section = (
        base.pages[-1]
        .sections[0]
        .model_copy(
            update={
                "blocks": tuple(
                    ModeloFormFieldBlock(id=f"stated{index}", field=item) for index, item in enumerate(carries)
                ),
                "counts": form_counts(carries),
            }
        )
    )
    page = base.pages[-1].model_copy(update={"sections": (section,), "counts": form_counts(carries)})
    return with_pages(base, (*base.pages[:-1], page))


def test_withdrawing_one_stated_box_withdraws_its_whole_family_and_no_other() -> None:
    form = _stated_family_form()
    session = WorkbenchEditSession(OutputLanguage.EN)
    first = next(item for item in form.fields() if item.stated_absent is _FIRST)

    assert session.withdraw_stated(form, first) is None
    withdrawn = {address_key(change.field.address) for change in session.changes}
    assert withdrawn == {address_key(item.address) for item in form.fields() if item.stated_absent is _FIRST}
    assert all(change.kind in {WorkbenchChangeKind.CLEAR, WorkbenchChangeKind.RESTORE} for change in session.changes)


def test_a_family_member_that_takes_no_withdrawal_stages_nothing_for_the_family() -> None:
    form = _stated_family_form(locked=True)
    session = WorkbenchEditSession(OutputLanguage.EN)
    first = next(
        item
        for item in form.fields()
        if item.stated_absent is _FIRST and item.editability is ModeloFormEditability.EDITABLE_VALUE
    )

    assert session.withdraw_stated(form, first) is not None
    assert not session.changes
