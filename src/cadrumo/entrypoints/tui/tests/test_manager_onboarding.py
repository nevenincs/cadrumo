"""Pilot-driven proofs for the profile setup walk on the manager page.

A profile whose setup is incomplete opens the manager as a guided walk: a
progress bar, one Continue button, and only the answers setup requires. These
tests drive the real registration, write and completion doors, so a walk that
only updated its own view, or that asked for more than the store requires,
fails here.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button, Checkbox, DataTable, Input, OptionList, ProgressBar, Static

from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.overview import build_profile_overview
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.values import ProfileSetupState
from ..components.host import ScreenHostApp
from ..components.widgets import DisclosureGroup
from ..profile.overview import FieldEditScreen, ProfileManagerScreen, field_help_text
from .manager_pilot import wait_until_settled
from .test_manager_screen import _CREDENTIAL_INPUT, _live_overview, _persist

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (160, 60)
_SYNTHETIC_NIF = "12345678Z"
"""A checksum-valid NIF that belongs to no one."""


def _register() -> None:
    with bundled_indexed_authority().operation():
        create_context, decode_context = _profile_contexts_for_test()
        register_profile_with_credentials(
            label="Manager Subject",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        )


def _complete_setup():
    """The repository completion door the installed session binds."""
    with bundled_indexed_authority().operation():
        _create_context, decode_context = _profile_contexts_for_test()
        profile_id = require_active_bucket_id()
        profiles = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode_context)
        current = profiles.load(profile_id)
        promoted = profiles.complete_setup(
            profile_id,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
        )
        return build_profile_overview(promoted, label="Manager Subject", schema=decode_context.schema)


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


@pytest.mark.asyncio
async def test_an_unfinished_profile_opens_on_only_its_required_answers(tmp_path) -> None:
    """The walk asks for what setup requires and folds every other section away."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register()
        overview = _live_overview()
        assert overview.setup_state is ProfileSetupState.INCOMPLETE
        assert overview.missing_required, "the fixture must owe required answers, or this proves nothing"

        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            assert _visible_rows(app) == set(overview.missing_required)
            owing = {path.split(".", 1)[0] for path in overview.missing_required}
            assert _shown_folds(app) == owing
            for key in owing:
                assert not app.query_one(f"#fold-{key}", DisclosureGroup).collapsed
                summary = str(app.query_one(f"#summary-{key}", Static).content)
                assert summary and summary != f"profile.schema.section.{key}.summary"
            bar = app.query_one("#onboarding-progress", ProgressBar)
            assert (bar.progress, bar.total) == (0, len(overview.missing_required) + 1)
            assert app.focused is app.query_one("#onboarding-continue", Button)

            app.query_one("#manager-required-only", Checkbox).value = False
            await pilot.pause()
            await pilot.pause()
            assert len(_visible_rows(app)) == overview.total_count
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_continue_walks_every_required_answer_then_finishes_setup(tmp_path) -> None:
    """Pressing Continue and answering each question is enough to finish setup."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register()
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#onboarding-continue")
            await pilot.pause()
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
                await pilot.pause()
            assert set(answered) >= set(overview.missing_required)
            assert not app.overview.missing_required
            button = app.query_one("#onboarding-continue", Button)
            assert str(button.label) == tr("flows.manager.onboarding.finish")
            await pilot.pause()
            assert button.size.width >= len(str(button.label)), "the new action label is clipped to the old width"

            await pilot.click("#onboarding-continue")
            await wait_until_settled(app, pilot)
            for _ in range(20):
                if app._pending_completion is None:
                    break
                await pilot.pause()
            await pilot.pause()
            assert app.overview.setup_state is ProfileSetupState.COMPLETE
            bar = app.query_one("#onboarding-progress", ProgressBar)
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
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register()
        app = ProfileManagerScreen(_live_overview(), persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#onboarding-continue")
            await pilot.pause()
            assert isinstance(app.app.screen, FieldEditScreen)
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert app.app.screen is app
            assert not app._walking
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_search_narrows_the_page_and_says_when_nothing_matches(tmp_path) -> None:
    """A search shows the sections it matches, open, and names an empty result."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register()
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            app.query_one("#manager-required-only", Checkbox).value = False
            await pilot.pause()

            identity = next(section for section in overview.sections if section.key == "identity")
            app.query_one("#manager-search", Input).value = identity.title
            await pilot.pause(0.4)
            await pilot.pause()
            assert "identity" in _shown_folds(app)
            assert not app.query_one("#fold-identity", DisclosureGroup).collapsed
            assert {field.path for field in identity.fields} <= _visible_rows(app)
            assert len(_visible_rows(app)) < overview.total_count
            assert not app.query_one("#manager-search-empty", Static).display

            app.query_one("#manager-search", Input).value = "zzqx-no-such-setting"
            await pilot.pause(0.4)
            await pilot.pause()
            assert _shown_folds(app) == set()
            assert app.query_one("#manager-search-empty", Static).display
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_finished_profile_opens_without_the_walk(tmp_path) -> None:
    """Setup that is already complete shows the plain profile page, every field in reach."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register()
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            assert not app.query("#manager-onboarding")
            assert not app.query_one("#manager-required-only", Checkbox).value
            assert len(_visible_rows(app)) == overview.total_count
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_choice_question_offers_words_and_refuses_an_empty_save(tmp_path) -> None:
    """Choices read as labels, and Save with nothing picked asks for a pick instead of cancelling."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register()
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#onboarding-continue")
            await pilot.pause()
            # The first required question is typed; answer it to reach a choice.
            for _ in range(len(overview.missing_required)):
                dialog = app.app.screen
                assert isinstance(dialog, FieldEditScreen)
                if dialog._field.choices:
                    break
                await _answer(app, pilot)
                await pilot.pause()
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
            await pilot.pause()
            assert app.app.screen is dialog
            assert str(dialog.query_one("#edit-refusal", Static).content) == tr("flows.manager.edit.choose_one")
            assert app._walking
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_every_setup_question_explains_itself_and_the_page_explains_the_cursor_row(tmp_path) -> None:
    """Each question says what it is, why it is asked and where to find it; so does the page."""
    headings = [tr(f"flows.manager.help.{part}") for part in ("what", "why", "where")]
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register()
        overview = _live_overview()
        app = ProfileManagerScreen(overview, persist=_persist, complete_setup=_complete_setup)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            table = app._table_by_section["identity"]
            table.focus()
            table.move_cursor(row=0)
            await pilot.pause()
            panel = app.query_one("#manager-field-help", Static)
            assert panel.display
            assert all(heading in str(panel.content) for heading in headings)
            # The row under the cursor, not whichever section happened to be built last.
            assert str(panel.content) == field_help_text(app._field_by_key["identity.tax_id"])

            await pilot.click("#onboarding-continue")
            await pilot.pause()
            asked = 0
            for _ in range(20):
                dialog = app.app.screen
                if not isinstance(dialog, FieldEditScreen):
                    break
                help_text = str(dialog.query_one("#edit-help", Static).content)
                assert [line.split(":", 1)[0] + ":" for line in help_text.splitlines()] == headings, dialog._field.path
                asked += 1
                await _answer(app, pilot)
                await pilot.pause()
            assert asked >= len(overview.missing_required)
            pilot.app.exit(None)
