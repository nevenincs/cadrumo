"""The workbench lists a declaration's source disagreements and sends the operator's answers through its door.

Driven through the standalone host with the real workbench and dialog widgets.
The door stands at the runtime boundary: it records each call and whether an
event loop was running on the calling thread, and answers with the application's
own projections. Every sentence about a disagreement or its answer is served by
the door's projections; the cases check that the dialog shows those sentences
and sends exactly the coordinates the form and the served answer carry.

The dialog's own words are catalogue keys under ``tui.modelo.disagreements``;
a case that renders them fails only while those keys are missing from the
catalogue.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import UUID

import pytest
from rich.console import Group
from rich.padding import Padding
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import Button, Input, OptionList, Static

from ......application.modelo.credit_resolution_contracts import (
    CreditResolutionListProjection,
    CreditResolutionMutationProjection,
    CreditResolutionRefusalProjection,
    CreditResolutionRowProjection,
    CreditResolutionSourceProjection,
)
from ......application.modelo.work_form_declaration_facts import ModeloFormCalculationNote, ModeloFormResolutionAnswer
from ......application.modelo.work_form_findings import ModeloFormAttention
from ......application.modelo.work_form_issue_lines import form_issue_lines
from ......application.modelo.work_form_models import ModeloWorkForm
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.modelos.credit_resolution import CreditResolutionState
from ......domain.modelos.source_disagreement import SourceDisagreementRole
from ....components.host import ScreenHostApp
from ....refusal.panel import RefusalPanel
from ....tests.settling import settle
from ...disagreements import DisagreementEntryV1, disagreement_entries
from ...disagreements_screen import ModeloDisagreementsScreen
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE: Final = UUID("5aa00000-0000-4000-8000-0000000000aa")
_REVISION: Final = "b" * 64
_OPEN: Final = "a1" * 8
_ANSWERED: Final = "b2" * 8
_LOCKED: Final = "c3" * 8
_STORED_AT: Final = "stored-revision-7"
_AT: Final = datetime(2026, 11, 12, 9, 30, tzinfo=UTC)


def _note(finding_id: str, answer: ModeloFormResolutionAnswer) -> ModeloFormCalculationNote:
    return ModeloFormCalculationNote(
        reason="credit_source_disagreement",
        attention=ModeloFormAttention.BLOCKS,
        casilla_id=None,
        box=None,
        withholds_filing=True,
        finding_id=finding_id,
        resolution_answer=answer,
    )


def _form(*notes: ModeloFormCalculationNote) -> ModeloWorkForm:
    return synthetic_form().model_copy(update={"calculation_notes": notes})


def _row(
    finding_id: str,
    *,
    state: CreditResolutionState = CreditResolutionState.ACTIVE,
    revocable: bool = True,
    revision_id: str = _STORED_AT,
    tag: str = "",
) -> CreditResolutionRowProjection:
    language = OutputLanguage.EN
    return CreditResolutionRowProjection(
        finding_id=finding_id,
        key=f"served-key-{finding_id}",
        reached_casillas=("01",),
        sources=(
            CreditResolutionSourceProjection(
                role=SourceDisagreementRole.VALUE_SOURCE, source_family="served-family", value="10.00"
            ),
            CreditResolutionSourceProjection(
                role=SourceDisagreementRole.CROSS_CHECK, source_family="served-other", value="12.00"
            ),
        ),
        accepted_role=SourceDisagreementRole.VALUE_SOURCE,
        reason=f"operator reason {tag}",
        state=state,
        resolved_at=_AT,
        resolved_by_session="session-label",
        revoked_at=None if state is CreditResolutionState.ACTIVE else _AT,
        revoked_by_session=None if state is CreditResolutionState.ACTIVE else "session-label",
        revision_id=revision_id,
        applies=True,
        answer_words=f"served answer sentence {tag}",
        answer_words_language=language,
        state_words=f"served state sentence {tag}",
        state_words_language=language,
        current=True,
        current_words=f"served currency sentence {tag}",
        current_words_language=language,
        revocable=revocable,
        revoke_refusal_words=None if revocable else f"served revoke refusal {tag}",
        revoke_refusal_words_language=None if revocable else language,
    )


def _mutation(
    row: CreditResolutionRowProjection, outcome: Literal["accepted", "revoked"]
) -> CreditResolutionMutationProjection:
    return CreditResolutionMutationProjection(
        outcome=outcome,
        profile_id=_PROFILE,
        calculation_revision_id=_REVISION,
        resolution=row,
    )


def _refusal(words: str | None) -> CreditResolutionMutationProjection:
    return CreditResolutionMutationProjection(
        outcome="refused",
        profile_id=_PROFILE,
        calculation_revision_id=_REVISION,
        refusal=CreditResolutionRefusalProjection(
            code="REFUSED_CREDIT_RESOLUTION",
            reason="already_resolved",
            finding_id=_OPEN,
            refusal_words=words,
            refusal_words_language=None if words is None else OutputLanguage.EN,
        ),
    )


@dataclass
class FakeDoor:
    """Stands at the runtime boundary: records each call and whether it ran on an event loop."""

    rows: tuple[CreditResolutionRowProjection, ...] = ()
    list_error: Exception | None = None
    accept_answer: CreditResolutionMutationProjection | Exception | None = None
    revoke_answer: CreditResolutionMutationProjection | Exception | None = None
    listed: list[tuple[str, OutputLanguage]] = field(default_factory=list)
    accepted: list[tuple[str, str, str]] = field(default_factory=list)
    revoked: list[tuple[str, str, str]] = field(default_factory=list)
    on_loop: list[str] = field(default_factory=list)

    def _enter(self, name: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self.on_loop.append(name)

    def list_answers(self, calculation_revision_id: str, language: OutputLanguage) -> CreditResolutionListProjection:
        self._enter("list_answers")
        self.listed.append((calculation_revision_id, language))
        if self.list_error is not None:
            raise self.list_error
        return CreditResolutionListProjection(
            profile_id=_PROFILE, calculation_revision_id=calculation_revision_id, resolutions=self.rows
        )

    def accept(
        self, calculation_revision_id: str, finding_id: str, reason: str, language: OutputLanguage
    ) -> CreditResolutionMutationProjection:
        self._enter("accept")
        self.accepted.append((calculation_revision_id, finding_id, reason))
        if isinstance(self.accept_answer, Exception):
            raise self.accept_answer
        assert self.accept_answer is not None
        return self.accept_answer

    def revoke(
        self, calculation_revision_id: str, finding_id: str, expected_revision_id: str, language: OutputLanguage
    ) -> CreditResolutionMutationProjection:
        self._enter("revoke")
        self.revoked.append((calculation_revision_id, finding_id, expected_revision_id))
        if isinstance(self.revoke_answer, Exception):
            raise self.revoke_answer
        assert self.revoke_answer is not None
        return self.revoke_answer


def _plain(renderable: object) -> str:
    if isinstance(renderable, Text):
        return renderable.plain
    if isinstance(renderable, Padding):
        return _plain(renderable.renderable)
    if isinstance(renderable, Group):
        return "\n".join(_plain(part) for part in renderable.renderables)
    return str(renderable)


def _options(dialog: ModeloDisagreementsScreen) -> list[str]:
    listing = dialog.query_one(OptionList)
    return [_plain(listing.get_option_at_index(i).prompt) for i in range(listing.option_count)]


def _detail(dialog: ModeloDisagreementsScreen) -> str:
    return _plain(dialog.query_one("#disagreements-detail", Static).content)


def _status(dialog: ModeloDisagreementsScreen) -> str:
    return str(dialog.query_one("#disagreements-status", Static).render())


def _note_text(dialog: ModeloDisagreementsScreen) -> str:
    return str(dialog.query_one("#disagreements-note", Static).render())


def _notice(screen: ModeloWorkbenchScreen) -> str:
    return str(screen.query_one("#wb-notice", Static).render())


async def _open(pilot: Pilot[None], app: ScreenHostApp[None]) -> ModeloDisagreementsScreen:
    await settle(pilot)
    await pilot.press("D")
    await settle(pilot)
    assert isinstance(app.screen, ModeloDisagreementsScreen)
    return app.screen


def _workbench(
    door: FakeDoor | None, form: ModeloWorkForm
) -> tuple[ModeloWorkbenchScreen, ScreenHostApp[None], FakeReader]:
    reader = FakeReader(form=form)
    screen = ModeloWorkbenchScreen(reader, actions=FakeActions(), disagreements=door)
    return screen, ScreenHostApp(screen), reader


_BOTH: Final = (_note(_OPEN, ModeloFormResolutionAnswer.ACCEPT), _note(_ANSWERED, ModeloFormResolutionAnswer.REVOKE))


@pytest.mark.asyncio
async def test_the_dialog_lists_each_stated_disagreement_with_the_answer_held_for_it() -> None:
    door = FakeDoor(rows=(_row(_ANSWERED, tag="held"),))
    with override_settings(cadrumo_output_language="en"):
        _screen, app, _reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            options = _options(dialog)

    assert door.listed == [(_REVISION, OutputLanguage.EN)]
    assert door.on_loop == []
    assert len(options) == 2
    assert "served state sentence held" not in options[0]
    assert "served state sentence held" in options[1]


@pytest.mark.asyncio
async def test_the_highlighted_entry_shows_what_the_application_served_about_it_and_its_answer() -> None:
    door = FakeDoor(rows=(_row(_ANSWERED, revocable=False, tag="held"),))
    with override_settings(cadrumo_output_language="en"):
        _screen, app, _reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            first = _detail(dialog)
            await pilot.press("down")
            await settle(pilot)
            second = _detail(dialog)
            revoke_disabled = dialog.query_one("#disagreements-revoke", Button).disabled

    assert "served answer sentence" not in first
    for served in (
        "served answer sentence held",
        "served state sentence held",
        "served currency sentence held",
        "served revoke refusal held",
        tr("tui.modelo.disagreements.your_reason", locale="en", reason="operator reason held"),
    ):
        assert served in second
    assert revoke_disabled


@pytest.mark.asyncio
async def test_accepting_sends_the_finding_and_the_reason_then_reads_the_declaration_again() -> None:
    accepted = _row(_OPEN, tag="new")
    door = FakeDoor(accept_answer=_mutation(accepted, "accepted"))
    with override_settings(cadrumo_output_language="en"):
        screen, app, reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            assert dialog.query_one("#disagreements-accept", Button).disabled
            dialog.query_one("#disagreements-reason", Input).value = "  the ledger is right  "
            await settle(pilot)
            dialog.query_one("#disagreements-accept", Button).press()
            await settle(pilot)
            back_on_workbench = app.screen is screen
            notice = _notice(screen)

    assert door.accepted == [(_REVISION, _OPEN, "the ledger is right")]
    assert door.on_loop == []
    assert back_on_workbench
    assert reader.loads == 2
    assert notice == "served state sentence new"


@pytest.mark.asyncio
async def test_revoking_sends_the_revision_the_served_answer_is_stored_at() -> None:
    held = _row(_ANSWERED, tag="held")
    taken_back = _row(_ANSWERED, state=CreditResolutionState.REVOKED, tag="back")
    door = FakeDoor(rows=(held,), revoke_answer=_mutation(taken_back, "revoked"))
    with override_settings(cadrumo_output_language="en"):
        screen, app, reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            assert dialog.query_one("#disagreements-revoke", Button).disabled
            await pilot.press("down")
            await settle(pilot)
            await pilot.press("r")
            await settle(pilot)
            notice = _notice(screen)

    assert door.revoked == [(_REVISION, _ANSWERED, _STORED_AT)]
    assert door.on_loop == []
    assert reader.loads == 2
    assert notice == "served state sentence back"


@pytest.mark.asyncio
async def test_a_refused_answer_is_shown_in_the_served_words_and_nothing_is_read_again() -> None:
    door = FakeDoor(accept_answer=_refusal("Served refusal sentence."))
    with override_settings(cadrumo_output_language="en"):
        _screen, app, reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            dialog.query_one("#disagreements-reason", Input).value = "reason"
            await settle(pilot)
            dialog.query_one("#disagreements-accept", Button).press()
            await settle(pilot)
            still_open = app.screen is dialog
            words = str(dialog.query_one(RefusalPanel).query_one("#refusal-words", Static).render())
            lists = len(door.listed)

    assert still_open
    assert words == "Served refusal sentence."
    assert reader.loads == 1
    assert lists == 2


@pytest.mark.asyncio
async def test_a_refusal_with_no_served_words_says_it_was_refused_in_the_dialogs_own_words() -> None:
    door = FakeDoor(accept_answer=_refusal(None))
    with override_settings(cadrumo_output_language="en"):
        _screen, app, _reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            dialog.query_one("#disagreements-reason", Input).value = "reason"
            await settle(pilot)
            dialog.query_one("#disagreements-accept", Button).press()
            await settle(pilot)
            shown = _note_text(dialog)
            panels = len(dialog.query(RefusalPanel))

    assert panels == 0
    assert shown == tr("tui.modelo.disagreements.refused", locale="en")


@pytest.mark.asyncio
async def test_an_answer_with_an_unknown_outcome_is_never_sent_again_and_closing_reads_the_declaration() -> None:
    from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

    door = FakeDoor(accept_answer=RefusalError(RefusalCode.CONNECTION_CLOSED))
    with override_settings(cadrumo_output_language="en"):
        screen, app, reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            dialog.query_one("#disagreements-reason", Input).value = "reason"
            await settle(pilot)
            dialog.query_one("#disagreements-accept", Button).press()
            await settle(pilot)
            held_note = _note_text(dialog)
            accept_disabled = dialog.query_one("#disagreements-accept", Button).disabled
            await pilot.press("escape")
            await settle(pilot)
            closed_on_workbench = app.screen is screen
            notice = _notice(screen)

    assert len(door.accepted) == 1
    assert held_note == tr("tui.modelo.disagreements.outcome_unknown", locale="en")
    assert accept_disabled
    assert closed_on_workbench
    assert reader.loads == 2
    assert notice == tr("tui.modelo.disagreements.outcome_unknown", locale="en")


@pytest.mark.asyncio
async def test_a_declaration_stating_no_disagreement_and_holding_no_answer_says_so() -> None:
    door = FakeDoor()
    with override_settings(cadrumo_output_language="en"):
        _screen, app, _reader = _workbench(door, _form())
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            status = _status(dialog)
            options = _options(dialog)
            accept_disabled = dialog.query_one("#disagreements-accept", Button).disabled
            revoke_disabled = dialog.query_one("#disagreements-revoke", Button).disabled

    assert status == tr("tui.modelo.disagreements.none", locale="en")
    assert options == []
    assert accept_disabled
    assert revoke_disabled


@pytest.mark.asyncio
async def test_an_answer_the_form_no_longer_states_is_still_listed_in_the_served_words() -> None:
    door = FakeDoor(rows=(_row(_LOCKED, state=CreditResolutionState.REVOKED, tag="gone"),))
    with override_settings(cadrumo_output_language="en"):
        _screen, app, _reader = _workbench(door, _form())
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            options = _options(dialog)
            detail = _detail(dialog)
            offers = (
                dialog.query_one("#disagreements-accept", Button).disabled,
                dialog.query_one("#disagreements-revoke", Button).disabled,
            )

    assert len(options) == 1
    assert "served answer sentence gone" in options[0]
    assert "served currency sentence gone" in detail
    assert offers == (True, True)


@pytest.mark.asyncio
async def test_an_answers_list_that_cannot_be_read_still_shows_the_form_and_offers_no_revocation() -> None:
    from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

    door = FakeDoor(list_error=RefusalError(RefusalCode.CONNECTION_CLOSED))
    with override_settings(cadrumo_output_language="en"):
        _screen, app, _reader = _workbench(door, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            dialog = await _open(pilot, app)
            status = _status(dialog)
            options = _options(dialog)
            await pilot.press("down")
            await settle(pilot)
            revoke_disabled = dialog.query_one("#disagreements-revoke", Button).disabled

    assert status == tr("tui.modelo.disagreements.read_failed", locale="en")
    assert len(options) == 2
    assert revoke_disabled


@pytest.mark.asyncio
async def test_without_a_door_or_a_calculation_the_key_says_there_is_nothing_to_answer() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen, app, _reader = _workbench(None, _form(*_BOTH))
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(pilot)
            await pilot.press("D")
            await settle(pilot)
            notice = _notice(screen)
            stayed = app.screen is screen

    assert stayed
    assert notice == tr("tui.modelo.disagreements.unavailable", locale="en")


def test_entries_follow_the_forms_order_then_the_answers_it_does_not_state() -> None:
    form = _form(_note(_ANSWERED, ModeloFormResolutionAnswer.REVOKE), _note(_OPEN, ModeloFormResolutionAnswer.ACCEPT))
    lines = tuple(line for line in form_issue_lines(form, OutputLanguage.EN) if line.finding_id is not None)
    held = (_row(_LOCKED, tag="x"), _row(_ANSWERED, tag="y"))

    entries: tuple[DisagreementEntryV1, ...] = disagreement_entries(lines, held)

    assert [entry.finding_id for entry in entries] == [_ANSWERED, _OPEN, _LOCKED]
    assert [entry.answer is not None for entry in entries] == [True, False, True]
    assert [entry.line is not None for entry in entries] == [True, True, False]
    assert [entry.offers_accept for entry in entries] == [False, True, False]
    assert [entry.offers_revoke for entry in entries] == [True, False, False]
