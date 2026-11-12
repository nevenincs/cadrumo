"""The household destination adds and removes one person through the served controls, in served words."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest
from textual.widgets import Button, Input, OptionList, Static

from cadrumo_client.transport.profile_mutations import ProfileMutationRunError

from .....application.operations.error_detail import build_operation_error_detail
from .....application.user_profile.family_rows import (
    ProfileFamilyLeaf,
    ProfileFamilyLeafCondition,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
    family_row_items,
)
from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....core.i18n.render import tr
from .....core.operations import OperationEffect, OperationTerminalCondition
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.user_profile.errors import UserProfileValidationError
from .....domain.user_profile.schema import ProfileFieldType
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
    shown_leaves,
)
from ..overview import ProfileManagerScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

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
    changes: list[HouseholdRowChange] = field(default_factory=list)
    reads: int = 0

    def read(self) -> HouseholdView:
        self.reads += 1
        return self.current

    def change(self, change: HouseholdRowChange, /) -> HouseholdView:
        self.changes.append(change)
        if self.error is not None:
            raise self.error
        assert self.after is not None
        self.current = self.after
        return self.after

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


def test_a_leaf_is_asked_only_while_an_answer_it_is_served_after_holds() -> None:
    def leaf(key: str, *conditions: ProfileFamilyLeafCondition) -> ProfileFamilyLeaf:
        return ProfileFamilyLeaf(
            leaf=key,
            label=key,
            help=None,
            field_type=ProfileFieldType.STRING,
            required=False,
            choices=(),
            shown_when=conditions,
        )

    leaves = (
        leaf("relacion"),
        leaf("inscripcion", ProfileFamilyLeafCondition(leaf="relacion", equals="adoptado")),
        leaf("meses", ProfileFamilyLeafCondition(leaf="relacion", contains="b")),
        leaf("nested", ProfileFamilyLeafCondition(leaf="inscripcion", equals="x")),
    )

    def asked(answers: Mapping[str, str]) -> list[str]:
        return [item.leaf for item in shown_leaves(leaves, answers)]

    assert asked({}) == ["relacion"]
    assert asked({"relacion": "adoptado"}) == ["relacion", "inscripcion"]
    assert asked({"relacion": "a, b"}) == ["relacion", "meses"]
    assert asked({"relacion": "adoptado", "inscripcion": "x"}) == ["relacion", "inscripcion", "nested"]
    # An answer to a leaf no longer asked counts for nothing.
    assert asked({"relacion": "other", "inscripcion": "x"}) == ["relacion"]


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


@pytest.mark.asyncio
async def test_a_new_person_states_only_the_asked_leaves_through_the_served_add() -> None:
    view = _view({})
    descendants = _group(view, _DESCENDANTS).group
    assert descendants.add_row_action is not None
    after = _view(
        {"renta_family.descendientes_count": "1", "renta_family.descendiente.0.birth_date": "2020-01-02"}, revision=4
    )
    port = _Port(view, after=after)
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
        _buttons(screen)[descendants.add_row_action.action_words].press()
        await settle_until(pilot, lambda: isinstance(pilot.app.screen, HouseholdPersonScreen), "the new-person form")
        form = pilot.app.screen
        assert isinstance(form, HouseholdPersonScreen)
        conditional = next(leaf for leaf in descendants.leaves if leaf.shown_when)
        condition = conditional.shown_when[0]
        assert condition.equals is not None
        assert conditional.leaf not in {leaf.leaf for leaf in form.asked()}
        leaves = [leaf.leaf for leaf in descendants.leaves]
        on = descendants.leaves[leaves.index(condition.leaf)]
        options = form.query_one(f"#household-option-{leaves.index(condition.leaf)}", OptionList)
        options.highlighted = [choice.value for choice in on.choices].index(condition.equals)
        await settle_until(
            pilot, lambda: conditional.leaf in {leaf.leaf for leaf in form.asked()}, "the conditional leaf asked"
        )
        form.query_one(f"#household-input-{leaves.index('birth_date')}", Input).value = "2020-01-02"
        form.query_one("#household-person-save", Button).press()
        await settle_until(pilot, lambda: bool(port.changes) and screen.view is after, "the person added")
    assert port.changes == [
        HouseholdRowChange(
            operation_id="user-profile.descendants",
            expected_revision=3,
            expected_content_digest=_DIGEST,
            add_row={"birth_date": "2020-01-02", condition.leaf: condition.equals or ""},
        )
    ]


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


@pytest.mark.asyncio
async def test_an_unknown_outcome_stays_unknown_and_closes_changes_until_read_again() -> None:
    view = _view(_TWO_ASCENDANTS)
    ascendants = _group(view, _ASCENDANTS)
    port = _Port(view, error=_run_error(OperationEffect.UNKNOWN, OperationTerminalCondition.FAILED))
    screen = HouseholdScreen(port)
    async with ScreenHostApp(screen).run_test(size=(140, 50)) as pilot:
        await settle_until(pilot, lambda: screen.view is not None, "the household read")
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
        reads = port.reads
        screen.query_one("#household-read", Button).press()
        await settle_until(pilot, lambda: port.reads > reads, "the household read again")
        await settle_until(
            pilot,
            lambda: all(not button.disabled for button in screen.query(".household-control").results(Button)),
            "changes open again",
        )
        # Reading again shows what is stored; it never claims the change landed or not.
        assert str(status.render()) == unknown


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
