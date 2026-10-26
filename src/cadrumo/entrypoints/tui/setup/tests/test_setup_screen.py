"""The setup screen reads the component engine's rows, sets items up under the person's approval of their plan.

The screen runs headless under Textual's test pilot with its real door and the
real components client. Only the role's process is replaced: each start
replays a conversation the real role recorded (:mod:`.role_replay`), so the
client decodes real lines and the test reads what the screen sent back. What is
checked is the screen's own part: the rows and sentences it shows, the plan it
words, the answer it sends for exactly the reviewed digest, the progress and
stop it offers, and that an engine that cannot be started is reported rather
than acted around.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, override

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Static

from cadrumo.tests.components_role_dispatch import RoleReplay
from cadrumo.tests.components_role_replay import transcript_lines

from .....adapters.outbound.components.protocol import (
    CANCEL_LINE,
    ComponentsApprove,
    ComponentsDecline,
    ComponentsReviewLine,
    answer_line,
    decode_components_line,
)
from .....adapters.outbound.components.role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from .....application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyItemKind,
    DependencyState,
)
from .....application.dependency_registry import dependency_item_declarations
from .....application.dependency_wording import dependency_row_wording
from .....core.config import override_settings
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_path
from ...components.dialogs import ConfirmScreen
from ...components.host import ScreenHostApp
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ...tests.settling import settle, settle_until
from ..door import ComponentsSetupDoor
from ..focus import setup_item_focus, setup_item_target
from ..screen import SetupScreen, setup_review_text
from .role_replay import role_replay_fixture

__all__ = ["role_replay_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (120, 40)
_BROWSER = "Browser for the tax agency website"
type _Replay = Callable[..., RoleReplay]


def _review(name: str) -> ComponentsReviewLine:
    line = next(decode_components_line(raw) for raw in transcript_lines(name) if b'"type":"review"' in raw)
    assert isinstance(line, ComponentsReviewLine)
    return line


async def _settled(pilot: Pilot[Any], screen: SetupScreen) -> None:
    await settle_until(
        pilot, lambda: not screen.query_one("#btn-setup-check", Button).disabled, "the setup check to be offered again"
    )


async def _dialog(pilot: Pilot[Any], app: _Host) -> ConfirmScreen:
    # The setup waits for the answer on the role's thread, so its worker is held on purpose.
    await settle_until(
        pilot, lambda: isinstance(app.screen, ConfirmScreen), "the plan to be shown for approval", workers=False
    )
    assert isinstance(app.screen, ConfirmScreen)
    return app.screen


class _Host(ScreenHostApp[None]):
    """Hosts the screen and keeps every notice it shows the person."""

    def __init__(self, screen: SetupScreen) -> None:
        super().__init__(screen)
        self.notices: list[str] = []

    @override
    def notify(self, message: str, **kwargs: Any) -> None:
        self.notices.append(message)
        super().notify(message, **kwargs)


def _notices(app: _Host) -> list[str]:
    return app.notices


@pytest.mark.asyncio
async def test_the_screen_shows_every_row_the_role_reports_with_its_plain_sentence_and_action(
    role_replay: _Replay,
) -> None:
    replay = role_replay(status=["status_quick"])
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            table = screen.query_one("#setup-items", DataTable)
            shown = [tuple(str(cell) for cell in table.get_row_at(index)) for index in range(table.row_count)]

            assert [row.item_id for row in screen.rows] == ["browser", "local_ai"]
            assert {row.state for row in screen.rows} == {DependencyState.ABSENT}
            for row, cells in zip(screen.rows, shown, strict=True):
                declaration = next(d for d in dependency_item_declarations() if d.item_id == row.item_id)
                wording = dependency_row_wording(row, declaration)
                assert cells == (wording.name, wording.sentence, wording.action or "")
            assert shown[0] == (_BROWSER, "Not set up yet.", "Set up")
            assert shown[1] == ("Local AI", "Not set up yet.", "Set up in the Cadrumo desktop app")
            assert screen.status_text == "Some components are not ready yet."
            assert screen.query_one("#btn-setup-all", Button).disabled is False
            assert screen.query_one("#btn-setup-stop", Button).display is False
    assert replay.commands() == [("status",)]


@pytest.mark.asyncio
async def test_the_rows_are_software_only_and_the_local_ai_is_one_row(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"])
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            table = screen.query_one("#setup-items", DataTable)
            names = [str(table.get_row_at(index)[0]) for index in range(table.row_count)]

            assert names == [_BROWSER, "Local AI"]
            screen.act_on("google")
            await settle(pilot)
    assert replay.commands() == [("status",)]


@pytest.mark.asyncio
async def test_setting_up_shows_the_plan_and_approves_exactly_the_reviewed_digest(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"], setup=["setup_browser_completed"])
    reviewed = _review("setup_browser_completed")
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            screen.act_on("browser")
            dialog = await _dialog(pilot, app)
            shown = str(dialog.query_one("#confirm-message", Static).render())
            plan_text = setup_review_text(reviewed.plan)
            assert shown == plan_text
            assert plan_text.splitlines()[:3] == [
                "Cadrumo will set up:",
                f"{_BROWSER}: 317 MB from cdn.playwright.dev, playwright.download.prss.microsoft.com, "
                "storage.googleapis.com",
                f"  Stored in {storage_path(StorageCategory.PLAYWRIGHT_BROWSERS)}",
            ]
            await pilot.click("#btn-confirm-accept")
            await settle_until(pilot, lambda: "Setup finished." in _notices(app), "the setup to settle")
            await _settled(pilot, screen)

    setup = replay.launches[1]
    assert replay.commands() == [("status",), ("setup", "--item", "browser"), ("status",)]
    assert setup.written == answer_line(ComponentsApprove(plan_digest=reviewed.plan_digest))


@pytest.mark.asyncio
async def test_declining_the_plan_sends_the_decline_and_nothing_is_downloaded(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"], setup=["setup_declined"])
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            screen.start_setup((DependencyItemKind.BROWSER,))
            await _dialog(pilot, app)
            await pilot.click("#btn-confirm-cancel")
            await settle_until(pilot, lambda: "Nothing was downloaded." in _notices(app), "the decline to settle")

    assert replay.launches[1].written == answer_line(ComponentsDecline())


@pytest.mark.asyncio
async def test_a_running_setup_shows_its_progress_and_stop_asks_the_role_to_stop(role_replay: _Replay) -> None:
    # The recorded setup stops writing after its first two byte figures, as a slow download would.
    replay = role_replay(
        status=["status_quick"], setup=["setup_browser_completed"], stall_after={"setup_browser_completed": 7}
    )
    reviewed = _review("setup_browser_completed")
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            screen.start_setup(())
            await _dialog(pilot, app)
            await pilot.click("#btn-confirm-accept")
            await settle_until(
                pilot, lambda: "downloading" in screen.status_text, "the download's progress", workers=False
            )

            assert screen.status_text == f"{_BROWSER}: downloading 3 MB of 317 MB (1%)"
            stop = screen.query_one("#btn-setup-stop", Button)
            setup = replay.launches[1]
            assert stop.display is True
            assert screen.query_one("#btn-setup-all", Button).disabled is True
            await pilot.click("#btn-setup-stop")
            await settle_until(pilot, lambda: CANCEL_LINE in setup.written, "the stop to reach the role", workers=False)
            assert setup.written == answer_line(ComponentsApprove(plan_digest=reviewed.plan_digest)) + CANCEL_LINE
            assert screen.status_text == "Stopping the setup…"

            # The role goes away without its result: the screen says the engine is unavailable.
            setup.end()
            await _settled(pilot, screen)
            assert screen.status_text.startswith("Cadrumo could not start its component engine")
            assert stop.display is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("written_lines", "shown"),
    [
        (2, f"{_BROWSER}: following a setup that is already running…"),
        (4, f"{_BROWSER}: downloading 1 MB of 317 MB (0%)"),
    ],
)
async def test_a_setup_already_running_elsewhere_is_followed_without_a_dialog(
    role_replay: _Replay, written_lines: int, shown: str
) -> None:
    # The recorded follower stops writing early, while the setup it follows goes on elsewhere.
    replay = role_replay(
        status=["status_quick"],
        setup=["setup_followed_completed"],
        stall_after={"setup_followed_completed": written_lines},
    )
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            screen.start_setup((DependencyItemKind.BROWSER,))
            await settle_until(pilot, lambda: screen.status_text == shown, "the followed setup shown", workers=False)
            assert not isinstance(app.screen, ConfirmScreen)
            assert screen.query_one("#btn-setup-stop", Button).display is True
            follower = replay.launches[1]
            # The follower is sent no review and answers none.
            assert follower.written == b""
            follower.end()
            await _settled(pilot, screen)


@pytest.mark.asyncio
async def test_a_followed_setup_reports_its_result_and_a_stopped_following_says_it_carries_on(
    role_replay: _Replay,
) -> None:
    role_replay(status=["status_quick"], setup=["setup_followed_completed", "setup_follow_stopped"])
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            screen.start_setup((DependencyItemKind.BROWSER,))
            await settle_until(pilot, lambda: "Setup finished." in _notices(app), "the followed setup to finish")
            await _settled(pilot, screen)
            screen.start_setup((DependencyItemKind.BROWSER,))
            stopped = "You stopped following the other setup. It carries on by itself."
            await settle_until(pilot, lambda: stopped in _notices(app), "the following to stop")
            dialogs = [shown for shown in app.screen_stack if isinstance(shown, ConfirmScreen)]

    assert dialogs == []


@pytest.mark.asyncio
async def test_a_screen_opened_on_an_item_selects_its_row_so_enter_sets_up_that_item(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"], setup=["setup_refused_blocked_by_network"])
    screen = SetupScreen(ComponentsSetupDoor(), focus_item="browser")
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            table = screen.query_one("#setup-items", DataTable)

            assert table.ordered_rows[table.cursor_row].key.value == "browser"
            assert screen.focused is table

            await pilot.press("enter")
            expected = f"{_BROWSER}: Your network blocked the download."
            await settle_until(pilot, lambda: expected in _notices(app), "the refused setup to settle")
            # Refused before any review: nothing was asked and nothing was answered.
            assert not isinstance(app.screen, ConfirmScreen)

    assert replay.commands()[1] == ("setup", "--item", "browser")
    assert replay.launches[1].written == b""


@pytest.mark.asyncio
async def test_the_local_ai_row_points_to_the_desktop_and_enter_starts_no_setup(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"])
    screen = SetupScreen(ComponentsSetupDoor(), focus_item="local_ai")
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            table = screen.query_one("#setup-items", DataTable)

            assert table.ordered_rows[table.cursor_row].key.value == "local_ai"
            await pilot.press("enter")
            await settle(pilot)
            assert _notices(app) == ["Set it up in the Cadrumo desktop app."]
            assert not isinstance(app.screen, ConfirmScreen)

    assert replay.commands() == [("status",)], "no setup of the local AI is ever asked of the role"


@pytest.mark.asyncio
async def test_set_up_everything_is_offered_only_while_the_role_has_something_to_set_up(role_replay: _Replay) -> None:
    role_replay(status=["status_quick_browser_ready"])
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)

            # Only the desktop sets up the local AI, so the ready browser leaves nothing to run here.
            assert [None if row.recovery is None else row.recovery.value for row in screen.rows] == [
                None,
                "set_up_in_desktop",
            ]
            assert screen.query_one("#btn-setup-all", Button).disabled is True


@pytest.mark.asyncio
async def test_a_resume_under_an_approved_digest_asks_again_only_when_the_plan_changed(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"], setup=["setup_plan_changed", "setup_browser_completed"])
    approved = "0" * 64
    reviewed = _review("setup_browser_completed")
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        app = _Host(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            screen.start_setup((DependencyItemKind.BROWSER,), approved=approved)
            await _dialog(pilot, app)
            await pilot.click("#btn-confirm-accept")
            await settle_until(pilot, lambda: "Setup finished." in _notices(app), "the setup to settle")

    assert replay.commands()[1:3] == [
        ("setup", "--item", "browser", "--approve", approved),
        ("setup", "--item", "browser"),
    ]
    assert replay.launches[1].written == b""
    assert replay.launches[2].written == answer_line(ComponentsApprove(plan_digest=reviewed.plan_digest))


@pytest.mark.asyncio
async def test_an_engine_that_cannot_be_started_is_reported_and_nothing_is_set_up(role_replay: _Replay) -> None:
    role_replay(unstartable=True)
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)

            assert screen.status_text == (
                "Cadrumo could not start its component engine, so components cannot be checked or set up right now."
            )
            assert screen.rows == ()
            assert screen.query_one("#btn-setup-all", Button).disabled is True


@pytest.mark.asyncio
async def test_a_build_without_the_engine_reads_every_item_as_not_in_this_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, raising=False)
    screen = SetupScreen(ComponentsSetupDoor())
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            table = screen.query_one("#setup-items", DataTable)
            sentences = [str(table.get_row_at(index)[1]) for index in range(table.row_count)]
            set_up_all = screen.query_one("#btn-setup-all", Button).disabled

    assert [row.blocked_reason for row in screen.rows] == [DependencyBlockedReason.NOT_IN_THIS_BUILD] * 2
    assert sentences == ["This version of Cadrumo does not include this."] * 2
    assert set_up_all is True


def test_the_review_words_the_browser_plan_before_approval() -> None:
    plan = _review("setup_browser_completed").plan

    with override_settings(cadrumo_output_language="en"):
        text = setup_review_text(plan)

    assert text.splitlines() == [
        "Cadrumo will set up:",
        f"{_BROWSER}: 317 MB from cdn.playwright.dev, playwright.download.prss.microsoft.com, storage.googleapis.com",
        f"  Stored in {storage_path(StorageCategory.PLAYWRIGHT_BROWSERS)}",
        "Total download: 317 MB.",
    ]


def test_only_a_declared_item_is_a_setup_page_focus() -> None:
    for declaration in dependency_item_declarations():
        target = setup_item_target(declaration.item_id)
        context = TuiScreenContextV1(destination=target.destination, focus=target.focus)
        assert setup_item_focus(context) == declaration.item_id
    with pytest.raises(ValueError, match="unknown setup item"):
        setup_item_target("google")
    page = TuiScreenContextV1(
        destination="workbench.setup",
        focus=TuiFocusIdentityV1(destination="workbench.setup", semantic_key="presentation.setup"),
    )
    undeclared = TuiScreenContextV1(
        destination="workbench.setup",
        focus=TuiFocusIdentityV1(destination="workbench.setup", semantic_key="setup.item.google"),
    )
    assert setup_item_focus(page) is None
    assert setup_item_focus(undeclared) is None
    assert setup_item_focus(TuiScreenContextV1(destination="workbench.setup")) is None
