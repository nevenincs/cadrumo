"""Pilot-driven proofs for the profile setup walk on the manager page.

A profile whose setup is incomplete opens the manager as a guided walk: a
progress bar, one Continue button, and only the answers setup requires. These
tests drive the real registration, write and completion doors, so a walk that
only updated its own view, or that asked for more than the store requires,
fails here.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, DataTable, Input, OptionList, Static

from ....adapters.persistence.profile.tests.sealed_profile_world import copied_profile_world, sealed_profile_world
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from ....application.user_profile.overview import build_profile_overview
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.user_profile.registration import register_profile_with_credentials
from ....application.wizard.catalogue import build_setup_flow
from ....core.bucket_pointer import require_active_bucket_id
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.values import ProfileSetupState
from ..components.host import ScreenHostApp
from ..components.status import ProgressLine
from ..components.widgets import DisclosureGroup
from ..profile.edit_screens import FieldEditScreen, field_help_text
from ..profile.overview import ProfileManagerScreen
from ..profile.setup_journey import ProfileSetupStage
from .manager_pilot import wait_until_settled
from .settling import settle, settle_until
from .test_manager_screen import _CREDENTIAL_INPUT, _live_overview, _persist

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (160, 60)
_SYNTHETIC_NIF = "12345678Z"
"""A checksum-valid NIF that belongs to no one."""


def _register() -> str:
    with bundled_indexed_authority().operation():
        create_context, decode_context = _profile_contexts_for_test()
        return register_profile_with_credentials(
            label="Manager Subject",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        ).profile_id


@contextmanager
def _registered(tmp_path: Path) -> Generator[None]:
    """Open this test's own copy of the subject profile, registered once per worker and not yet set up."""
    world = sealed_profile_world((__name__, "Manager Subject", _CREDENTIAL_INPUT), _register)
    with copied_profile_world(world, tmp_path, profile_decode_context=_profile_contexts_for_test()[1]):
        yield


def _complete_setup():
    """The repository completion door the installed session binds."""
    with bundled_indexed_authority().operation() as operation:
        _create_context, decode_context = _profile_contexts_for_test()
        profile_id = require_active_bucket_id()
        profiles = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode_context)
        current = profiles.load(profile_id)
        promoted = profiles.complete_setup(
            profile_id,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
        )
        return build_profile_overview(
            promoted, label="Manager Subject", schema=decode_context.schema, flow=build_setup_flow(operation)
        )


def _visible_rows(app: ProfileManagerScreen) -> set[str]:
    return {
        str(row_key.value)
        for table in app.query(DataTable)
        if table.parent is not None and table.parent.parent is not None
        for row_key in table.rows
        if row_key.value is not None
    }


def _shown_folds(app: ProfileManagerScreen) -> set[str]:
    return {
        (fold.id or "").removeprefix("fold-")
        for fold in app.query(DisclosureGroup)
        if fold.display and (fold.id or "").startswith("fold-")
    }


async def _answer(app: ProfileManagerScreen, pilot) -> str:
    """Answer the open question the way an operator does, and return its path."""
    dialog = app.app.screen
    assert isinstance(dialog, FieldEditScreen)
    field = dialog._field
    if field.choices:
        dialog.query_one("#edit-options", OptionList).highlighted = 0
        await pilot.click("#btn-edit-save")
    else:
        dialog.query_one("#edit-input", Input).value = _SYNTHETIC_NIF
        await pilot.click("#btn-edit-save")
    await wait_until_settled(app, pilot)
    return field.path


async def _until_filtered(app: ProfileManagerScreen, pilot, *, required_only: bool) -> None:
    """Return once the page has taken the required-only switch and the rebuild it started has finished.

    Setting the switch only posts its change; the page's handler, which starts
    the rebuild worker, runs on a later turn. Joining the workers straight
    after the assignment therefore joins nothing, and one pause is not a wait
    for a rebuild that mounts every section's table in turn.
    """
    await settle_until(
        pilot,
        lambda: app._required_only is required_only,
        f"the page to finish filtering to required_only={required_only}",
    )


async def _until_searched(app: ProfileManagerScreen, pilot, query: str) -> None:
    """Return once the page has applied the typed search and redrawn its sections.

    Typing only posts the change; the page's handler holds the search back
    until typing pauses, on a timer, and the timer's callback rebuilds the
    sections under the render lock. A fixed wait longer than the timer is a
    guess about how fast that rebuild runs, so this waits until the page
    holds the query, no search is pending and the rebuild has let go of the
    lock.
    """
    await settle_until(
        pilot,
        lambda: app._query == query and app._search_timer is None and not app._render_lock.locked(),
        f"the page to apply the search {query!r}",
    )


async def _reach_required(app: ProfileManagerScreen, pilot) -> None:
    """Start setup and explicitly skip optional import through its visible action."""
    await pilot.click("#onboarding-continue")
    await settle(pilot)
    assert app._setup_stage is ProfileSetupStage.GET_DATA
    await pilot.click("#onboarding-continue")
    await settle(pilot)
    assert app._setup_stage is ProfileSetupStage.REQUIRED


@pytest.mark.asyncio
async def test_previous_keeps_saved_answers_and_incomplete_review_returns_to_required(tmp_path) -> None:
    """Navigation never clears a saved fact or bypasses the required-answer gate."""
    with _registered(tmp_path):
        app = ProfileManagerScreen(_live_overview(), persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=(80, 24)) as pilot:
            await _reach_required(app, pilot)
            await pilot.click("#onboarding-continue")
            await settle(pilot)
            path = await _answer(app, pilot)
            await pilot.press("escape")
            await settle(pilot)
            value = app._field_by_key[path].value
            assert value is not None and value
            await pilot.click("#onboarding-previous")
            await settle(pilot)
            assert app._setup_stage is ProfileSetupStage.GET_DATA
            assert not app.query(DataTable)
            await pilot.click("#setup-stage-review")
            await settle(pilot)
            assert app._setup_stage is ProfileSetupStage.REVIEW
            assert app.overview.setup_state is ProfileSetupState.INCOMPLETE
            assert app.query_one("#setup-stage-ready", Button).disabled
            await pilot.click("#onboarding-continue")
            await settle(pilot)
            assert app._setup_stage is ProfileSetupStage.REQUIRED
            assert app._field_by_key[path].value == value
            assert _live_overview().missing_required == app.overview.missing_required
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_blank_required_answer_can_be_corrected_without_losing_the_question(tmp_path) -> None:
    """A refused blank stays in the editor and a subsequent valid answer is saved."""
    with _registered(tmp_path):
        app = ProfileManagerScreen(_live_overview(), persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=(80, 24)) as pilot:
            await _reach_required(app, pilot)
            await pilot.click("#onboarding-continue")
            await settle(pilot)
            dialog = app.app.screen
            assert isinstance(dialog, FieldEditScreen)
            path = dialog._field.path
            await pilot.click("#btn-edit-save")
            await settle(pilot)
            assert app.app.screen is dialog
            assert path in _live_overview().missing_required
            assert str(dialog.query_one("#edit-refusal", Static).content)
            assert str(dialog.query_one("#edit-requirement", Static).content) == tr("flows.progress.required")
            await _answer(app, pilot)
            assert path not in _live_overview().missing_required
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_an_unfinished_profile_opens_on_only_its_required_answers(tmp_path) -> None:
    """The walk asks for what setup requires and folds every other section away."""
    with _registered(tmp_path):
        overview = _live_overview()
        assert overview.setup_state is ProfileSetupState.INCOMPLETE
        assert overview.missing_required, "the fixture must owe required answers, or this proves nothing"

        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            assert app._setup_stage is ProfileSetupStage.OVERVIEW
            assert not _visible_rows(app)
            assert not app.query_one("#manager-tools").display
            assert app.focused is app.query_one("#onboarding-continue", Button)
            await _reach_required(app, pilot)
            assert _visible_rows(app) == set(overview.missing_required)
            owing = {path.split(".", 1)[0] for path in overview.missing_required}
            assert _shown_folds(app) == owing
            for key in owing:
                assert not app.query_one(f"#fold-{key}", DisclosureGroup).collapsed
                summary = str(app.query_one(f"#summary-{key}", Static).content)
                assert summary and summary != f"profile.schema.section.{key}.summary"
            bar = app.query_one("#onboarding-progress", ProgressLine)
            assert (bar.progress, bar.total) == (0, len(overview.missing_required) + 1)
            assert app.focused is app.query_one("#onboarding-continue", Button)

            app.query_one("#manager-required-only", Checkbox).value = False
            await _until_filtered(app, pilot, required_only=False)
            assert len(_visible_rows(app)) == overview.total_count
            pilot.app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (160, 60)])
async def test_continue_walks_every_required_answer_then_finishes_setup(tmp_path, size) -> None:
    """Pressing Continue and answering each question is enough to finish setup."""
    with _registered(tmp_path):
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=size) as pilot:
            await settle(pilot)
            await _reach_required(app, pilot)
            await pilot.click("#onboarding-continue")
            await settle(pilot)
            dialog = app.app.screen
            assert isinstance(dialog, FieldEditScreen)
            context = str(dialog.query_one("#edit-context", Static).content)
            first = overview.missing_required_fields[0]
            first_section = next(section for section in overview.sections if first.path.startswith(f"{section.key}."))
            assert dialog._field.path == first.path
            assert context.splitlines() == [
                tr(
                    "flows.manager.onboarding.question",
                    number=1,
                    total=len(overview.missing_required),
                    section=first_section.title,
                ),
                first_section.summary,
            ]

            answered: list[str] = []
            # Each saved answer opens the next question without another press.
            for _ in range(len(overview.missing_required) * 3):
                if not isinstance(app.app.screen, FieldEditScreen):
                    break
                answered.append(await _answer(app, pilot))
                await settle(pilot, workers=False)
            assert set(answered) >= set(overview.missing_required)
            assert not app.overview.missing_required
            assert app._setup_stage is ProfileSetupStage.REVIEW
            assert app.overview.setup_state is ProfileSetupState.INCOMPLETE
            assert any(not field.present for section in app.overview.sections for field in section.fields)
            button = app.query_one("#onboarding-continue", Button)
            assert str(button.label) == tr("flows.manager.onboarding.finish")
            await settle(pilot)
            assert button.size.width >= len(str(button.label)), "the new action label is clipped to the old width"

            # The completion shortcut follows the same Review boundary as
            # the visible Finish button, even when every answer is saved.
            await pilot.click("#setup-stage-overview")
            await settle(pilot)
            await pilot.press("f8")
            await settle(pilot)
            assert app._setup_stage is ProfileSetupStage.OVERVIEW
            assert app.overview.setup_state is ProfileSetupState.INCOMPLETE
            await pilot.click("#setup-stage-review")
            await settle(pilot)

            await pilot.click("#onboarding-continue")
            await wait_until_settled(app, pilot)
            await settle_until(pilot, lambda: app._pending_completion is None, "setup completion to settle")
            assert app.overview.setup_state is ProfileSetupState.COMPLETE
            assert app._setup_stage is ProfileSetupStage.READY
            assert "✓" in str(app.query_one("#onboarding-checklist", Static).content)
            assert not _visible_rows(app), "the success stage must not mount unrelated profile tables"
            bar = app.query_one("#onboarding-progress", ProgressLine)
            assert bar.progress == bar.total
            assert str(button.label) == tr("flows.manager.onboarding.to_workbench")
            pilot.app.exit(None)

        with bundled_indexed_authority().operation():
            _create_context, decode_context = _profile_contexts_for_test()
            profile_id = require_active_bucket_id()
            stored = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=decode_context
            ).load(profile_id)
        assert stored.setup_state is ProfileSetupState.COMPLETE


@pytest.mark.asyncio
async def test_cancelling_a_question_stops_the_walk(tmp_path) -> None:
    """Escape leaves the walk; nothing reopens until Continue is pressed again."""
    with _registered(tmp_path):
        app = ProfileManagerScreen(_live_overview(), persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            await _reach_required(app, pilot)
            await pilot.click("#onboarding-continue")
            await settle(pilot)
            assert isinstance(app.app.screen, FieldEditScreen)
            await pilot.press("escape")
            await settle(pilot)
            assert app.app.screen is app
            assert not app._walking
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_search_narrows_the_page_and_says_when_nothing_matches(tmp_path) -> None:
    """A search shows the sections it matches, open, and names an empty result."""
    with _registered(tmp_path):
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            await _reach_required(app, pilot)
            app.query_one("#manager-required-only", Checkbox).value = False
            await _until_filtered(app, pilot, required_only=False)

            identity = next(section for section in overview.sections if section.key == "identity")
            app.query_one("#manager-search", Input).value = identity.title
            await _until_searched(app, pilot, identity.title)
            assert "identity" in _shown_folds(app)
            assert not app.query_one("#fold-identity", DisclosureGroup).collapsed
            assert {field.path for field in identity.fields} <= _visible_rows(app)
            assert len(_visible_rows(app)) < overview.total_count
            assert not app.query_one("#manager-search-empty", Static).display

            app.query_one("#manager-search", Input).value = "zzqx-no-such-setting"
            await _until_searched(app, pilot, "zzqx-no-such-setting")
            assert _shown_folds(app) == set()
            assert app.query_one("#manager-search-empty", Static).display
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_finished_profile_opens_without_the_walk(tmp_path) -> None:
    """Setup that is already complete shows the plain profile page, every field in reach."""
    with _registered(tmp_path):
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            assert not app.query("#manager-onboarding")
            assert not app.query_one("#manager-required-only", Checkbox).value
            assert len(_visible_rows(app)) == overview.total_count
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_choice_question_offers_words_and_refuses_an_empty_save(tmp_path) -> None:
    """Choices read as labels, and Save with nothing picked asks for a pick instead of cancelling."""
    with _registered(tmp_path):
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            await _reach_required(app, pilot)
            await pilot.click("#onboarding-continue")
            await settle(pilot)
            # The first required question is typed; answer it to reach a choice.
            for _ in range(len(overview.missing_required)):
                dialog = app.app.screen
                assert isinstance(dialog, FieldEditScreen)
                if dialog._field.choices:
                    break
                await _answer(app, pilot)
                await settle(pilot, workers=False)
            dialog = app.app.screen
            assert isinstance(dialog, FieldEditScreen)
            field = dialog._field
            assert field.choices, "the walk must reach a choice question, or this proves nothing"
            options = dialog.query_one("#edit-options", OptionList)
            prompts = [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]
            assert prompts == [choice.label for choice in field.choices]
            assert not {choice.value for choice in field.choices} & set(prompts), "raw tokens offered as labels"

            options.highlighted = None
            await pilot.click("#btn-edit-save")
            await settle(pilot)
            assert app.app.screen is dialog
            assert str(dialog.query_one("#edit-refusal", Static).content) == tr("flows.manager.edit.choose_one")
            assert app._walking
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_every_setup_question_explains_itself_and_the_page_explains_the_cursor_row(tmp_path) -> None:
    """Each question shows the setup wizard's copy as its help; so does the page."""
    with _registered(tmp_path):
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            await _reach_required(app, pilot)
            table = app._table_by_section["identity"]
            table.focus()
            table.move_cursor(row=0)
            await settle(pilot)
            panel = app.query_one("#manager-field-help", Static)
            assert panel.display
            tax_id = app._field_by_key["identity.tax_id"]
            assert tax_id.help is not None
            assert tax_id.help[0] == tr("wizard.setup.profile.tax-id.prompt")
            # The row under the cursor, not whichever section happened to be built last.
            assert str(panel.content) == field_help_text(tax_id) == "\n".join(tax_id.help)

            await pilot.click("#onboarding-continue")
            await settle(pilot)
            asked = 0
            for _ in range(20):
                dialog = app.app.screen
                if not isinstance(dialog, FieldEditScreen):
                    break
                help_fold = dialog.query_one("#edit-help-fold", DisclosureGroup)
                assert help_fold.collapsed
                assert await pilot.click("#edit-help-fold CollapsibleTitle")
                await settle(pilot)
                assert not help_fold.collapsed
                help_text = str(dialog.query_one("#edit-help", Static).content)
                assert dialog._field.help, dialog._field.path
                assert help_text == "\n".join(dialog._field.help), dialog._field.path
                asked += 1
                await _answer(app, pilot)
                await settle(pilot, workers=False)
            assert asked >= len(overview.missing_required)
            pilot.app.exit(None)
