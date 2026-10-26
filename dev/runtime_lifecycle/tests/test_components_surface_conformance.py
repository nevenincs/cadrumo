"""Every surface shows the rows and binds the plan digest the one components engine reports for a storage root.

The CLI, the TUI and MCP reach the engine only through the shared components
client, which starts the built Cadrumo binary as the ``components`` role; the
desktop calls the same engine library in process. Parity is therefore a claim
about what each surface takes from the engine: the same rows, codes and all,
and the same plan digest, which is what an approval binds.

Recorded cases replay, on a real pipe, conversations the real role recorded
for one storage root (:mod:`cadrumo.tests.components_role_dispatch`), so each
surface's real client decodes real lines. The CLI runs through its real command
line, the TUI's setup screen headless under Textual's pilot with its real door,
and MCP through its setup tools' own implementation. Each surface's rows must be
the role's, and the digest each one approves must be the one the role reviewed.

Real-role cases (``external_tool``, run by ``just test-components-role IMAGE``)
start the built binary against one fresh storage root and compare what the
surfaces read from it.

The desktop window reads the snapshot its host composes from the same engine;
its host tests (``native/desktop/src-tauri/src/shell/setup/components_tests.rs``)
drive that engine against local servers. Here the desktop's own contract is
held to the engine's vocabulary: every state, reason, failure category and
button the rows carry is a value the desktop host's closed wire shapes admit,
so the window can show every row the engine reports.

Where it stops: each surface words the codes itself, and the words are not
compared. A real-role case reads status and plans only: a setup would need the
network and a download, which belong to ``dev/smoke/acquisition_lane.py``. The
desktop leg reads the host's wire source; that the host fills it from the
engine is its host tests' claim, not this file's.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

import pytest
from click.testing import Result
from textual.pilot import Pilot
from textual.widgets import Button, Static

from cadrumo.adapters.outbound.components import client as components_client
from cadrumo.adapters.outbound.components.protocol import (
    ComponentsApprove,
    ComponentsResultLine,
    ComponentsReviewLine,
    answer_line,
    decode_components_line,
)
from cadrumo.adapters.outbound.components.role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from cadrumo.application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
)
from cadrumo.application.dependency_wording import dependency_failure_key
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli, semantic_cli_text
from cadrumo.entrypoints.tui.components.dialogs import ConfirmScreen
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.setup.door import ComponentsSetupDoor
from cadrumo.entrypoints.tui.setup.screen import SetupScreen
from cadrumo.entrypoints.tui.tests.settling import settle_until
from cadrumo.tests.components_role_dispatch import RoleReplay
from cadrumo.tests.components_role_package import components_role_fixture, staged_components_role_fixture
from cadrumo.tests.components_role_replay import transcript_lines
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_mcp.mcp.component_setup import run_setup_tool, setup_request
from dev._paths import REPO_ROOT

__all__ = ["components_role_fixture", "staged_components_role_fixture"]

pytestmark = [pytest.mark.hex_entrypoint]

_SIZE: Final = (120, 40)
_DESKTOP_WIRE: Final = REPO_ROOT / "native" / "desktop" / "src-tauri" / "src" / "shell" / "setup" / "wire.rs"

#: The fields of a row that are the engine's own reading, in the order they are compared.
_ROW_FIELDS: Final = (
    "item_id",
    "mode",
    "state",
    "stale_reason",
    "blocked_reason",
    "failure_category",
    "version",
    "size_estimate_bytes",
    "recovery",
    "recovery_action_id",
)

type Row = tuple[object, ...]


def _row(fields: Mapping[str, object]) -> Row:
    return tuple(fields.get(name) for name in _ROW_FIELDS)


def _status_row(row: DependencyStatusRow) -> Row:
    return _row(row.model_dump(mode="json"))


def _recorded_result(name: str) -> ComponentsResultLine:
    (result,) = (
        line for line in map(decode_components_line, transcript_lines(name)) if isinstance(line, ComponentsResultLine)
    )
    return result


def _recorded_review(name: str) -> ComponentsReviewLine:
    (review,) = (
        line for line in map(decode_components_line, transcript_lines(name)) if isinstance(line, ComponentsReviewLine)
    )
    return review


# --------------------------------------------------------------------------
# What each surface reads
# --------------------------------------------------------------------------


def _cli_json(arguments: Sequence[str]) -> dict[str, Any]:
    result: Result = invoke_cached_cli(["--format", "json", *arguments])
    document = json.loads(result.stdout)
    assert isinstance(document, dict), result.output
    return document["result"]


def cli_rows() -> list[Row]:
    """The rows ``aeat config provision status`` reports."""
    document = _cli_json(["config", "provision", "status"])
    return [_row({**item, "mode": document["mode"]}) for item in document["items"]]


def mcp_reply(tool: str, arguments: Mapping[str, object]) -> dict[str, Any]:
    """What one MCP setup tool answers, through the tool's own implementation."""
    return asyncio.run(run_setup_tool(setup_request(tool, dict(arguments)), language="en", progress=None))


def mcp_rows() -> list[Row]:
    """The rows the MCP ``setup_status`` tool reports."""
    reply = mcp_reply("setup_status", {})
    return [_row({key: value for key, value in row.items() if key != "words"}) for row in reply["rows"]]


async def _tui_session(
    act: Callable[[SetupScreen, ScreenHostApp[None], Pilot[None]], Awaitable[None]] | None = None,
) -> SetupScreen:
    screen = SetupScreen(ComponentsSetupDoor())
    app = ScreenHostApp(screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=_SIZE) as pilot:
            await settle_until(
                pilot,
                lambda: not screen.query_one("#btn-setup-check", Button).disabled,
                "the setup check to be offered",
            )
            if act is not None:
                await act(screen, app, pilot)
                await settle_until(
                    pilot,
                    lambda: not screen.query_one("#btn-setup-check", Button).disabled,
                    "the setup to settle",
                )
    return screen


def tui_rows() -> list[Row]:
    """The rows the TUI's setup screen holds after its first read."""
    screen = asyncio.run(_tui_session())
    return [_status_row(row) for row in screen.rows]


def tui_status_text() -> str:
    """What the TUI's setup screen says beneath its rows after its first read."""
    said: list[str] = []

    async def read(screen: SetupScreen, _app: ScreenHostApp[None], _pilot: Pilot[None]) -> None:
        said.append(str(screen.query_one("#setup-status", Static).content))

    asyncio.run(_tui_session(read))
    return said[-1]


def cli_status_text() -> str:
    """What ``aeat config provision status`` prints."""
    return semantic_cli_text(invoke_cached_cli(["config", "provision", "status"]).stdout)


# --------------------------------------------------------------------------
# Recorded conversations of the real role
# --------------------------------------------------------------------------


@pytest.fixture(name="replay")
def replay_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., RoleReplay]:
    """Name a built binary, give every surface one storage root, and answer each role start from a recording."""
    image = tmp_path / "cadrumo.exe"
    image.write_bytes(b"")
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, str(image))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))

    def answer(**transcripts: Sequence[str]) -> RoleReplay:
        replay = RoleReplay(transcripts)
        monkeypatch.setattr(components_client, "launch_components_role", replay)
        return replay

    return answer


@pytest.mark.unit
@pytest.mark.parametrize("recording", ["status_quick", "status_quick_browser_ready"])
def test_every_surface_shows_the_rows_the_role_reports(replay: Callable[..., RoleReplay], recording: str) -> None:
    replay(status=[recording])
    engine = [_status_row(row.status_row()) for row in _recorded_result(recording).rows]

    shown = {"cli": cli_rows(), "tui": tui_rows(), "mcp": mcp_rows()}

    assert len(engine) == 2, "the recording names both items, so the comparison reads every row"
    for surface, rows in shown.items():
        assert rows == engine, surface


@pytest.mark.unit
def test_every_surface_words_a_check_the_role_refused_under_its_own_category(
    replay: Callable[..., RoleReplay],
) -> None:
    refused = _recorded_result("status_refused_blocked_by_network")
    assert refused.failure_category is not None and not refused.rows
    sentence = tr(dependency_failure_key(refused.failure_category), locale="en")

    replay(status=["status_refused_blocked_by_network"])
    with override_settings(cadrumo_output_language="en"):
        cli = cli_status_text()
    replay(status=["status_refused_blocked_by_network"])
    tui = tui_status_text()
    replay(status=["status_refused_blocked_by_network"])
    mcp = mcp_reply("setup_status", {})

    for surface, shown in {"cli": cli, "tui": tui}.items():
        assert sentence in shown, surface
        assert refused.failure_category.value not in shown, f"{surface} shows the category itself"
        assert "invalid_frame" not in shown.casefold(), f"{surface} read a classified refusal as a broken frame"
    assert (mcp["outcome"], mcp["failure_category"], mcp["failure"], mcp["rows"]) == (
        refused.outcome.value,
        refused.failure_category.value,
        sentence,
        [],
    )


@pytest.mark.unit
def test_every_surface_approves_exactly_the_plan_digest_the_role_reviewed(replay: Callable[..., RoleReplay]) -> None:
    reviewed = _recorded_review("setup_browser_completed")
    completed = _recorded_result("setup_browser_completed")
    assert completed.plan_digest == reviewed.plan_digest
    approval = answer_line(ComponentsApprove(plan_digest=reviewed.plan_digest))

    cli = replay(status=["status_quick"], setup=["setup_browser_completed"])
    cli_result = _cli_json(["config", "provision", "browser", "--yes"])

    tui = replay(status=["status_quick"], setup=["setup_browser_completed"])

    async def approve(screen: SetupScreen, app: ScreenHostApp[None], pilot: Pilot[None]) -> None:
        screen.act_on("browser")
        # The setup waits for the answer on the role's thread, so its worker is held on purpose.
        await settle_until(
            pilot, lambda: isinstance(app.screen, ConfirmScreen), "the plan to be shown for approval", workers=False
        )
        await pilot.click("#btn-confirm-accept")

    asyncio.run(_tui_session(approve))

    mcp = replay(plan=["plan_browser"], setup=["setup_browser_completed"])
    mcp_result = mcp_reply("setup", {"plan_digest": reviewed.plan_digest, "items": ["browser"]})

    assert cli_result["plan_digest"] == reviewed.plan_digest
    (cli_setup,) = [launch for launch in cli.launches if launch.arguments[2] == "setup"]
    assert cli_setup.written == approval, "the CLI approves exactly the reviewed digest"
    (tui_setup,) = [launch for launch in tui.launches if launch.arguments[2] == "setup"]
    assert tui_setup.written == approval, "the TUI approves exactly the reviewed digest"
    (mcp_setup,) = mcp.launches
    assert mcp_setup.arguments[2:] == ("setup", "--item", "browser", "--approve", reviewed.plan_digest)
    assert mcp_result["plan_digest"] == reviewed.plan_digest, "MCP binds the setup to the approved digest"


# --------------------------------------------------------------------------
# The desktop's contract admits every code the engine's rows carry
# --------------------------------------------------------------------------


def _wire_enum(source: str, name: str) -> frozenset[str]:
    """The serialised values of one ``snake_case`` serde enum in the desktop host's wire source."""
    match = re.search(rf"pub enum {name} \{{(?P<body>[^}}]*)\}}", source)
    assert match is not None, f"the desktop wire source declares no enum {name}"
    variants = re.findall(r"^\s*([A-Z][A-Za-z0-9]*)\s*[,(]", match.group("body"), flags=re.MULTILINE)
    return frozenset(re.sub(r"(?<!^)(?=[A-Z])", "_", variant).lower() for variant in variants)


@pytest.mark.unit
def test_the_desktop_wire_contract_admits_every_code_a_row_carries() -> None:
    source = _DESKTOP_WIRE.read_text(encoding="utf-8")
    families: dict[str, type[StrEnum]] = {
        "CheckMode": DependencyCheckMode,
        "State": DependencyState,
        "BlockedReason": DependencyBlockedReason,
        "StaleReason": DependencyStaleReason,
        "Failure": DependencyFailureCategory,
        "Recovery": DependencyRecoveryAction,
    }
    # The desktop's own engine is always admitted to provision the local AI, so its rows
    # never carry the recovery that sends a read-only surface to the desktop.
    never_on_the_desktop = {DependencyRecoveryAction.SET_UP_IN_DESKTOP.value}
    for name, family in families.items():
        engine = frozenset(member.value for member in family) - never_on_the_desktop
        assert _wire_enum(source, name) == engine, name


@pytest.mark.unit
def test_the_wire_reader_names_a_code_the_desktop_would_not_admit() -> None:
    fixture = "pub enum State {\n    Absent,\n    Ready,\n}\n"
    assert _wire_enum(fixture, "State") == {"absent", "ready"}
    assert _wire_enum(fixture, "State") != frozenset(member.value for member in DependencyState)


# --------------------------------------------------------------------------
# The real role, one storage root
# --------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.external_tool
@pytest.mark.usefixtures("components_role")
def test_every_surface_reads_the_same_rows_from_the_real_role() -> None:
    shown = {"cli": cli_rows(), "tui": tui_rows(), "mcp": mcp_rows()}

    assert {row[0] for row in shown["cli"]} == {"browser", "local_ai"}
    assert shown["tui"] == shown["cli"]
    assert shown["mcp"] == shown["cli"]


@pytest.mark.integration
@pytest.mark.external_tool
@pytest.mark.usefixtures("components_role")
def test_the_plan_digest_is_one_digest_for_one_root_whichever_surface_asks() -> None:
    first = mcp_reply("setup_plan", {})
    again = mcp_reply("setup_plan", {})
    direct = components_client.run_components_role(
        components_client.ComponentsRequest(components_client.ComponentsCommand.PLAN), timeout=60
    )

    assert first["outcome"] == "ok" and isinstance(first["plan_digest"], str)
    assert again["plan_digest"] == first["plan_digest"] == direct.plan_digest
