"""The household destination adds and removes one person through the served controls, in served words."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

import pytest
from textual.containers import Vertical
from textual.pilot import Pilot
from textual.widgets import Button, Input, OptionList, Static

from cadrumo_client.transport.profile_mutations import ProfileMutationRunError

from .....application.operations.error_detail import build_operation_error_detail
from .....application.user_profile.family_rows import (
    ProfileFamilyLeafAsk,
    ProfileFamilyLeafAskEntry,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
    family_draft_item,
    family_row_items,
)
from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....core.i18n.render import tr
from .....core.operations import OperationEffect, OperationTerminalCondition
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.descendant_relacion_catalogue import (
    descendant_relacion_adoption_token,
    descendant_relacion_entitling_tokens,
    descendant_relacion_tokens,
)
from .....domain.user_profile.errors import UserProfileValidationError
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...refusal.panel import RefusalSlot
from ...tests.settling import settle, settle_until
from ..household import (
    HouseholdGroupView,
    HouseholdOutcome,
    HouseholdPersonScreen,
    HouseholdRemoveScreen,
    HouseholdRowChange,
    HouseholdScreen,
    HouseholdView,
    household_change_outcome,
)
from ..overview import ProfileManagerScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BORN = (date.today() - timedelta(days=1800)).isoformat()
_ENTRY = (date.today() - timedelta(days=1700)).isoformat()
_PROFILE = "6f1d1c9e-1f0b-4b8e-9d4c-2a0d7f3e5b11"
_DIGEST = "c" * 64
_OPERATION = "e" * 64
_DESCENDANTS = "renta_family.descendiente"
_ASCENDANTS = "renta_family.ascendiente"
_TWO_ASCENDANTS = {
    "renta_family.ascendientes_count": "2",
    "renta_family.ascendiente.0.birth_date": "1950-02-03",
    "renta_family.ascendiente.1.birth_date": "1948-07-09",
}


def _view(values: Mapping[str, str], *, revision: int = 3) -> HouseholdView:
    """The household the profile view serves for these stored facts, assembled group by group."""
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items(dict(values), schema=authority.profile_schema(), operation=authority)
    groups: list[tuple[ProfileViewFamilyGroupItem, list[ProfileViewFamilyRowItem]]] = []
    for item in items:
        if isinstance(item, ProfileViewFamilyGroupItem):
            groups.append((item, []))
        else:
            groups[-1][1].append(item)
    return HouseholdView(
        profile_id=_PROFILE,
        record_revision=revision,
        content_digest=_DIGEST,
        groups=tuple(HouseholdGroupView(group=group, rows=tuple(rows)) for group, rows in groups),
    )


def _group(view: HouseholdView, key: str) -> HouseholdGroupView:
    return next(entry for entry in view.groups if entry.group.group_key == key)


@dataclass
class _Port:
    """The host's doors with storage replaced by the next served household."""

    current: HouseholdView
    after: HouseholdView | None = None
    error: BaseException | None = None
    read_error: BaseException | None = None
    changes: list[HouseholdRowChange] = field(default_factory=list)
    drafts: list[dict[str, str]] = field(default_factory=list)
    draft_error: BaseException | None = None
    reads: int = 0

    def read(self) -> HouseholdView:
        self.reads += 1
        if self.read_error is not None:
            raise self.read_error
        return self.current

    def change(self, change: HouseholdRowChange, /) -> HouseholdView:
        self.changes.append(change)
        if self.error is not None:
            raise self.error
        assert self.after is not None
        self.current = self.after
        return self.after

    def read_draft(self, group_key: str, answers: Mapping[str, str], /) -> tuple[ProfileFamilyLeafAskEntry, ...]:
        self.drafts.append(dict(answers))
        if self.draft_error is not None:
            raise self.draft_error
        # The backend's own resolver, as the profile view serves it for an unsaved row.
        with bundled_indexed_authority().operation() as authority:
            item = family_draft_item(group_key, answers, operation=authority)
        assert item is not None
        return item.leaf_asks

    def accepts(self, operation_id: str, /) -> bool:
        return operation_id in {"user-profile.descendants", "user-profile.ascendants"}


def _run_error(effect: OperationEffect | None, condition: OperationTerminalCondition | None) -> ProfileMutationRunError:
    refused = UserProfileValidationError(translated_message="application.user_profile.errors.ascendant_row_not_stored")
    return ProfileMutationRunError(
        operation_id=_OPERATION,
        code="REFUSED_USER_PROFILE_VALIDATION",
        terminal_condition=condition,
        effect=effect,
        detail=build_operation_error_detail(refused),
    )


def _buttons(screen: HouseholdScreen) -> dict[str, Button]:
    return {str(button.label): button for button in screen.query(Button).results(Button)}


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (None, HouseholdOutcome.SAVED),
        (_run_error(OperationEffect.NONE, OperationTerminalCondition.FAILED), HouseholdOutcome.REFUSED),
        (_run_error(OperationEffect.NONE, OperationTerminalCondition.REFUSED), HouseholdOutcome.REFUSED),
        (_run_error(OperationEffect.UNKNOWN, OperationTerminalCondition.FAILED), HouseholdOutcome.UNKNOWN),
        (_run_error(None, None), HouseholdOutcome.UNKNOWN),
        (_run_error(OperationEffect.NONE, OperationTerminalCondition.TIMED_OUT), HouseholdOutcome.UNKNOWN),
        (RuntimeError("not submitted"), HouseholdOutcome.FAILED),
    ],
)
def test_a_change_is_told_by_what_is_known_to_be_written(
    error: BaseException | None, outcome: HouseholdOutcome
) -> None:
    assert household_change_outcome(error) is outcome


@pytest.mark.asyncio
async def test_groups_rows_and_controls_are_the_served_words() -> None:
    view = _view(_TWO_ASCENDANTS)
    ascendants = _group(view, _ASCENDANTS).group
    descendants = _group(view, _DESCENDANTS).group
    assert ascendants.add_row_action is not None and ascendants.remove_row_action is not None
    assert descendants.add_row_action is not None and descendants.remove_row_action is None
    screen = HouseholdScreen(_Port(view))
    async with ScreenHostApp(screen).run_test(size=(140, 50)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        text = "\n".join(str(widget.render()) for widget in screen.query(Static).results(Static))
        assert ascendants.label in text and descendants.label in text
        assert tr("flows.manager.household.state_unknown") in text
        labels = [str(button.label) for button in screen.query(".household-control").results(Button)]
        # One add per group that serves one, and one remove per stored person.
        assert labels.count(descendants.add_row_action.action_words) == 1
        assert labels.count(ascendants.add_row_action.action_words) == 1
        assert labels.count(ascendants.remove_row_action.action_words) == 2


@pytest.mark.asyncio
async def test_a_group_at_its_design_limit_serves_no_add_and_says_it_is_full() -> None:
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items({}, schema=authority.profile_schema(), operation=authority)
    limit = next(
        item for item in items if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == _ASCENDANTS
    )
    assert limit.max_rows is not None
    full = {"renta_family.ascendientes_count": str(limit.max_rows)} | {
        f"renta_family.ascendiente.{index}.birth_date": "1950-02-03" for index in range(limit.max_rows)
    }
    view = _view(full)
    ascendants = _group(view, _ASCENDANTS).group
    assert ascendants.add_row_action is None
    screen = HouseholdScreen(_Port(view))
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        text = "\n".join(str(widget.render()) for widget in screen.query(Static).results(Static))
        assert tr("flows.manager.household.full") in text


def _relation_tokens() -> tuple[str, str]:
    """The adoption token, which asks for the registry date, and one relation that asks for no date."""
    with bundled_indexed_authority().operation() as authority:
        adoption = descendant_relacion_adoption_token(authority=authority).value
        entitling = {token.value for token in descendant_relacion_entitling_tokens(authority=authority)}
        plain = next(
            token.value for token in descendant_relacion_tokens(authority=authority) if token.value not in entitling
        )
    return adoption, plain


async def _open_descendant_form(pilot: Pilot[bool | None], screen: HouseholdScreen) -> HouseholdPersonScreen:
    await settle_until(pilot, lambda: screen.view is not None, "the household read")
    assert screen.view is not None
    group = _group(screen.view, _DESCENDANTS).group
    assert group.add_row_action is not None
    _buttons(screen)[group.add_row_action.action_words].press()
    await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdPersonScreen), "the new-person form")
    form = pilot.app.screen
    assert isinstance(form, HouseholdPersonScreen)
    return form


def _choose(form: HouseholdPersonScreen, group: ProfileViewFamilyGroupItem, leaf: str, value: str) -> None:
    keys = [item.leaf for item in group.leaves]
    choices = [choice.value for choice in group.leaves[keys.index(leaf)].choices]
    form.query_one(f"#household-option-{keys.index(leaf)}", OptionList).highlighted = choices.index(value)


def _type(form: HouseholdPersonScreen, group: ProfileViewFamilyGroupItem, leaf: str, text: str) -> None:
    form.query_one(f"#household-input-{[item.leaf for item in group.leaves].index(leaf)}", Input).value = text


def _shown(form: HouseholdPersonScreen, group: ProfileViewFamilyGroupItem) -> set[str]:
    return {
        leaf.leaf
        for index, leaf in enumerate(group.leaves)
        if form.query_one(f"#household-leaf-{index}", Vertical).display
    }


@pytest.mark.asyncio
async def test_a_new_person_states_only_the_leaves_the_backend_serves_as_asked_through_the_served_add() -> None:
    view = _view({})
    descendants = _group(view, _DESCENDANTS).group
    adoption, _plain = _relation_tokens()
    after = _view(
        {"renta_family.descendientes_count": "1", "renta_family.descendiente.0.birth_date": "2020-01-02"}, revision=4
    )
    port = _Port(view, after=after)
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        form = await _open_descendant_form(pilot, screen)
        # A blank person is shown as the group served it: nothing waits on an answer that is not given.
        asked_blank = {entry.leaf for entry in descendants.new_row_leaves if entry.ask is ProfileFamilyLeafAsk.ASKED}
        assert _shown(form, descendants) == asked_blank
        assert "inscripcion_registro_civil" not in asked_blank and port.drafts == []
        _choose(form, descendants, "relacion", adoption)
        await settle_until(
            pilot, lambda: "inscripcion_registro_civil" in _shown(form, descendants), "the registry date asked"
        )
        assert port.drafts == [{"relacion": adoption}]
        _type(form, descendants, "birth_date", _BORN)
        await settle_until(pilot, lambda: len(port.drafts) == 2, "the asks read again")
        form.query_one("#household-person-save", Button).press()
        await settle_until(pilot, lambda: bool(port.changes) and screen.view is after, "the person added")
    assert port.changes == [
        HouseholdRowChange(
            operation_id="user-profile.descendants",
            expected_revision=3,
            expected_content_digest=_DIGEST,
            add_row={"birth_date": _BORN, "relacion": adoption},
        )
    ]


@pytest.mark.asyncio
async def test_a_dependent_leaf_is_asked_again_once_the_answer_it_waits_on_is_given() -> None:
    view = _view({})
    descendants = _group(view, _DESCENDANTS).group
    port = _Port(view)
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        form = await _open_descendant_form(pilot, screen)
        assert "dependencia_economica" not in _shown(form, descendants)
        _choose(form, descendants, "convivencia", "false")
        await settle_until(pilot, lambda: "dependencia_economica" in _shown(form, descendants), "dependence asked")
        _choose(form, descendants, "convivencia", "true")
        await settle_until(pilot, lambda: "dependencia_economica" not in _shown(form, descendants), "dependence gone")
    assert port.drafts == [{"convivencia": "false"}, {"convivencia": "true"}]


@pytest.mark.asyncio
async def test_save_pressed_before_the_asks_are_read_waits_for_them_and_drops_a_leaf_not_asked() -> None:
    view = _view({})
    descendants = _group(view, _DESCENDANTS).group
    _adoption, plain = _relation_tokens()
    after = _view(
        {"renta_family.descendientes_count": "1", "renta_family.descendiente.0.birth_date": _BORN}, revision=4
    )
    port = _Port(view, after=after)
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        form = await _open_descendant_form(pilot, screen)
        _type(form, descendants, "birth_date", _BORN)
        # Typed while the leaf was hidden: the backend, not the form, decides it counts for nothing.
        _type(form, descendants, "inscripcion_registro_civil", _ENTRY)
        _choose(form, descendants, "relacion", plain)
        form.query_one("#household-person-save", Button).press()
        await settle_until(pilot, lambda: bool(port.changes) and screen.view is after, "the person added")
    assert port.drafts
    assert port.changes[0].add_row == {"birth_date": _BORN, "relacion": plain}


@pytest.mark.asyncio
async def test_asks_that_cannot_be_read_are_told_and_nothing_is_sent() -> None:
    view = _view({})
    descendants = _group(view, _DESCENDANTS).group
    adoption, _plain = _relation_tokens()
    port = _Port(view, draft_error=RuntimeError("runtime unavailable"))
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        form = await _open_descendant_form(pilot, screen)
        refusal = form.query_one("#household-person-refusal", Static)
        _type(form, descendants, "birth_date", _BORN)
        _choose(form, descendants, "relacion", adoption)
        await settle_until(
            pilot, lambda: str(refusal.render()) == tr("flows.manager.household.read_failed"), "the read failure told"
        )
        form.query_one("#household-person-save", Button).press()
        await settle_until(pilot, lambda: len(port.drafts) >= 2, "the asks read once more")
    assert port.changes == []


@pytest.mark.asyncio
async def test_a_required_leaf_left_blank_is_refused_in_the_form_and_nothing_is_sent() -> None:
    view = _view({})
    ascendants = _group(view, _ASCENDANTS).group
    assert ascendants.add_row_action is not None
    port = _Port(view)
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        _buttons(screen)[ascendants.add_row_action.action_words].press()
        await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdPersonScreen), "the new-person form")
        form = pilot.app.screen
        form.query_one("#household-person-save", Button).press()
        required = next(leaf for leaf in ascendants.leaves if leaf.required)
        refusal = form.query_one("#household-person-refusal", Static)
        await settle_until(
            pilot,
            lambda: str(refusal.render()) == tr("flows.manager.edit.required_blank", field=required.label),
            "the blank refused",
        )
    assert port.changes == []


@pytest.mark.asyncio
async def test_a_person_is_removed_by_the_served_index_at_the_revision_that_served_it() -> None:
    view = _view(_TWO_ASCENDANTS)
    ascendants = _group(view, _ASCENDANTS)
    remove = ascendants.group.remove_row_action
    assert remove is not None
    after = _view(
        {"renta_family.ascendientes_count": "1", "renta_family.ascendiente.0.birth_date": "1948-07-09"}, revision=4
    )
    port = _Port(view, after=after)
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 50)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        target = ascendants.rows[0].row_index
        group_index = view.groups.index(ascendants)
        screen.query_one(f"#household-remove-{group_index}-{target}", Button).press()
        await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdRemoveScreen), "the confirmation")
        confirm = pilot.app.screen.query_one("#household-remove-confirm", Button)
        assert str(confirm.label) == remove.action_words
        confirm.press()
        await settle_until(pilot, lambda: screen.view is after, "the person removed")
        assert str(screen.query_one("#household-status", Static).render()) == tr("flows.manager.edit.saved")
    assert port.changes == [
        HouseholdRowChange(
            operation_id="user-profile.ascendants",
            expected_revision=3,
            expected_content_digest=_DIGEST,
            remove_row_index=target,
        )
    ]


@pytest.mark.asyncio
async def test_a_refused_removal_shows_the_served_refusal_and_keeps_the_household() -> None:
    view = _view(_TWO_ASCENDANTS)
    ascendants = _group(view, _ASCENDANTS)
    port = _Port(view, error=_run_error(OperationEffect.NONE, OperationTerminalCondition.FAILED))
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 50)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        group_index = view.groups.index(ascendants)
        screen.query_one(f"#household-remove-{group_index}-{ascendants.rows[0].row_index}", Button).press()
        await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdRemoveScreen), "the confirmation")
        pilot.app.screen.query_one("#household-remove-confirm", Button).press()
        slot = screen.query_one("#household-refusal", RefusalSlot)
        await settle_until(pilot, lambda: bool(slot.query("#refusal-words")), "the served refusal", workers=False)
        words = str(slot.query_one("#refusal-words", Static).render())
        assert words == tr("application.user_profile.errors.ascendant_row_not_stored")
        # Nothing was written: the household shown is the one read, and it can be changed again.
        assert screen.view is view
        assert all(not button.disabled for button in screen.query(".household-control").results(Button))


async def _remove_with_unknown_outcome(pilot: Pilot[bool | None], screen: HouseholdScreen, port: _Port) -> str:
    view = port.current
    ascendants = _group(view, _ASCENDANTS)
    group_index = view.groups.index(ascendants)
    screen.query_one(f"#household-remove-{group_index}-{ascendants.rows[0].row_index}", Button).press()
    await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdRemoveScreen), "the confirmation")
    pilot.app.screen.query_one("#household-remove-confirm", Button).press()
    status = screen.query_one("#household-status", Static)
    unknown = tr("flows.manager.household.unknown_outcome")
    await settle_until(pilot, lambda: str(status.render()) == unknown, "the unknown outcome", workers=False)
    controls = list(screen.query(".household-control").results(Button))
    assert controls and all(button.disabled for button in controls)
    assert not screen.query(RefusalSlot).first().query("#refusal-words")
    return unknown


@pytest.mark.asyncio
async def test_an_unknown_outcome_closes_changes_until_read_again_and_a_successful_read_clears_it() -> None:
    view = _view(_TWO_ASCENDANTS)
    port = _Port(view, error=_run_error(OperationEffect.UNKNOWN, OperationTerminalCondition.FAILED))
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 50)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        unknown = await _remove_with_unknown_outcome(pilot, screen, port)
        status = screen.query_one("#household-status", Static)
        reads = port.reads
        screen.query_one("#household-read", Button).press()
        await settle_until(pilot, lambda: port.reads > reads, "the household read again")
        await settle_until(
            pilot,
            lambda: all(not button.disabled for button in screen.query(".household-control").results(Button)),
            "changes open again",
        )
        # The household now shows what is stored, so the notice and the lock end together.
        assert str(status.render()) != unknown
        assert not status.has_class("household-unknown")


@pytest.mark.asyncio
async def test_a_failed_read_after_an_unknown_outcome_keeps_the_notice_and_the_lock() -> None:
    view = _view(_TWO_ASCENDANTS)
    port = _Port(view, error=_run_error(OperationEffect.UNKNOWN, OperationTerminalCondition.FAILED))
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 50)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        unknown = await _remove_with_unknown_outcome(pilot, screen, port)
        status = screen.query_one("#household-status", Static)
        port.read_error = RuntimeError("the runtime is unavailable")
        reads = port.reads
        screen.query_one("#household-read", Button).press()
        await settle_until(pilot, lambda: port.reads > reads, "the failed read")
        await settle_until(pilot, lambda: not screen.query_one("#household-read", Button).disabled, "the read settled")
        assert str(status.render()) == unknown
        assert status.has_class("household-unknown")
        assert all(button.disabled for button in screen.query(".household-control").results(Button))


@pytest.mark.asyncio
async def test_the_profile_page_opens_the_household_and_reads_the_profile_again_after_a_change() -> None:
    view = _view(_TWO_ASCENDANTS)
    ascendants = _group(view, _ASCENDANTS)
    after = _view(
        {"renta_family.ascendientes_count": "1", "renta_family.ascendiente.0.birth_date": "1948-07-09"}, revision=4
    )
    port = _Port(view, after=after)
    overview = ProfileOverview(
        profile_id=_PROFILE,
        record_revision=3,
        content_digest=_DIGEST,
        label="Synthetic profile",
        setup_state=ProfileSetupState.COMPLETE,
        sections=(
            ProfileSectionView(
                key="renta_family",
                title="Family",
                summary="",
                repeatable=False,
                fields=(
                    ProfileFieldView(
                        path="renta_family.ascendientes_count",
                        label="Ascendants",
                        value="2",
                        masked=False,
                        required=False,
                    ),
                ),
            ),
        ),
    )
    reads: list[int] = []

    def reread() -> ProfileOverview:
        reads.append(len(reads))
        return overview

    def unreachable(_path: str, _value: str, _revision: int, _digest: str) -> ProfileOverview:
        raise AssertionError("the household is changed through its own doors")

    manager = ProfileManagerScreen(overview, persist=unreachable, household=port, refresh_overview_language=reread)
    async with ScreenHostApp(manager).run_test(size=(140, 50)) as pilot:
        await settle(pilot)
        opened = len(reads)
        manager.query_one("#manager-household", Button).press()
        await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdScreen), "the household opened")
        household = pilot.app.screen
        assert isinstance(household, HouseholdScreen)
        await settle_until(pilot, lambda: household.view is not None, "the household read")
        group_index = view.groups.index(ascendants)
        household.query_one(f"#household-remove-{group_index}-{ascendants.rows[0].row_index}", Button).press()
        await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdRemoveScreen), "the confirmation")
        pilot.app.screen.query_one("#household-remove-confirm", Button).press()
        await settle_until(pilot, lambda: household.view is after, "the person removed")
        household.query_one("#household-close", Button).press()
        await settle_until(pilot, lambda: pilot.app.screen is manager and len(reads) > opened, "the profile read again")
