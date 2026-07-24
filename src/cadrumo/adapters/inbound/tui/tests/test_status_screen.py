"""Pilot-driven structural tests for the read-only status page.

Every test drives the real :class:`StatusApp` through Textual's headless
Pilot over a hand-built :class:`StatusPageData`, and asserts against
widget ids, table row counts, and cell content — never rendered prose,
which is locale data and would make the assertion tautological. Copy
resolves through the sanctioned locale-root override against a fixture
catalogue, so the screen runs its production ``tr`` path without a test
string entering the packaged resources.

The masking assertion is the load-bearing one: a masked fact's raw value
must never reach any rendered cell.
"""

from __future__ import annotations

import ast
import pathlib
from typing import TYPE_CHECKING

import pytest
import yaml
from textual.widgets import DataTable, Static

from .....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, override_locales_root
from .. import (
    StatusApp,
    StatusAuthView,
    StatusFactRow,
    StatusPageData,
    StatusProfileRow,
    StatusRecoveryView,
)
from .._status_screen import _RECOVERY_COMMANDS

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

if TYPE_CHECKING:
    from collections.abc import Iterator

_TERMINAL_SIZE = (140, 60)

_MASK_MARKER = "MASK-TOKEN"
_HIDDEN_SENTINEL = "SENTINEL-SECRET-VALUE"

_STATUS_CATALOGUE: dict[str, object] = {
    "flows": {
        "status": {
            "title": "STATUS-TITLE",
            "binding_quit": "QUIT",
            "masked_value": _MASK_MARKER,
            "section": {
                "profile": "SEC-PROFILE",
                "profiles": "SEC-PROFILES",
                "auth": "SEC-AUTH",
                "recovery": "SEC-RECOVERY",
            },
            "profile": {
                "none": "NO-ACTIVE-PROFILE",
                "column": {"field": "COL-FIELD", "value": "COL-VALUE"},
            },
            "profiles": {
                "none": "NO-PROFILES",
                "column": {"label": "COL-LABEL", "status": "COL-STATUS", "active": "COL-ACTIVE"},
                "status": {
                    "active": "ST-ACTIVE",
                    "setup_incomplete": "ST-INCOMPLETE",
                    "tombstoned": "ST-TOMBSTONED",
                },
            },
            "auth": {
                "provider": "AUTH-PROVIDER",
                "status": "AUTH-STATUS",
                "subject": "AUTH-SUBJECT",
                "certificate_source": "AUTH-CERT-SOURCE",
                "provider_none": "AUTH-NONE",
                "login_ready": "AUTH-READY",
                "login_not_ready": "AUTH-NOT-READY",
            },
            "recovery": {
                "state": "REC-STATE",
                "enrolled": "REC-ENROLLED",
                "not_enrolled": "REC-NOT-ENROLLED",
                "fingerprint": "REC-FINGERPRINT",
                "commands_title": "REC-COMMANDS",
            },
        },
    },
}


@pytest.fixture(autouse=True)
def _status_copy_catalogue(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point copy resolution at a fixture catalogue carrying the status keys."""
    root = tmp_path_factory.mktemp("status-tui-locales")
    payload = yaml.safe_dump(_STATUS_CATALOGUE, allow_unicode=True)
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        (root / f"{language}.yml").write_text(payload, encoding="utf-8")
    with override_locales_root(root):
        yield


def _populated_data() -> StatusPageData:
    return StatusPageData(
        active_profile_label="ada",
        facts=(
            StatusFactRow(label="NIF", value="12345678Z", masked=False),
            StatusFactRow(label="Contraseña", value=_HIDDEN_SENTINEL, masked=True),
            StatusFactRow(label="Régimen IVA", value="general", masked=False),
        ),
        profiles=(
            StatusProfileRow(label="ada", status="active", active=True),
            StatusProfileRow(label="grace", status="setup_incomplete", active=False),
            StatusProfileRow(label="hedy", status="tombstoned", active=False),
        ),
        auth=StatusAuthView(
            provider="certificate",
            login_ready=True,
            subject="ADA LOVELACE",
            certificate_source="disk",
        ),
        recovery=StatusRecoveryView(enrolled=True, fingerprint="ab12cd34"),
    )


def _all_cell_text(table: DataTable) -> list[str]:
    return [str(cell) for index in range(table.row_count) for cell in table.get_row_at(index)]


@pytest.mark.asyncio
async def test_all_four_zones_render_as_bordered_panels() -> None:
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        panels = {
            "#panel-profile": "SEC-PROFILE",
            "#panel-profiles": "SEC-PROFILES",
            "#panel-auth": "SEC-AUTH",
            "#panel-recovery": "SEC-RECOVERY",
        }
        for panel_id, title in panels.items():
            panel = app.query_one(panel_id, Static)
            assert str(panel.border_title) == title
        assert str(app.query_one("#status-header", Static).content) == "STATUS-TITLE"


@pytest.mark.asyncio
async def test_profile_facts_table_has_one_row_per_fact() -> None:
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        table = app.query_one("#profile-facts", DataTable)
        assert table.row_count == 3
        labels = [str(table.get_row_at(index)[0]) for index in range(table.row_count)]
        assert labels == ["NIF", "Contraseña", "Régimen IVA"]


@pytest.mark.asyncio
async def test_masked_fact_never_renders_its_raw_value() -> None:
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        table = app.query_one("#profile-facts", DataTable)
        cells = _all_cell_text(table)
        assert _HIDDEN_SENTINEL not in cells
        assert _MASK_MARKER in cells
        # The unmasked fact still shows its real value beside the mask.
        assert "12345678Z" in cells


@pytest.mark.asyncio
async def test_empty_facts_show_the_no_profile_line_and_no_table() -> None:
    app = StatusApp(StatusPageData(active_profile_label=None))
    async with app.run_test(size=_TERMINAL_SIZE):
        assert not app.query(DataTable)
        panel = app.query_one("#panel-profile", Static)
        rendered = " ".join(str(child.content) for child in panel.query(Static))
        assert "NO-ACTIVE-PROFILE" in rendered


@pytest.mark.asyncio
async def test_profiles_table_rows_and_active_marker() -> None:
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        table = app.query_one("#profiles-table", DataTable)
        assert table.row_count == 3
        rows = [tuple(str(cell) for cell in table.get_row_at(index)) for index in range(table.row_count)]
        # active profile carries the marker glyph; the others do not.
        assert rows[0][0] == "ada"
        assert rows[0][2] == "●"
        assert rows[1] == ("grace", "ST-INCOMPLETE", "")
        assert rows[2][1] == "ST-TOMBSTONED"


@pytest.mark.asyncio
async def test_unmapped_profile_status_renders_the_raw_token_not_active() -> None:
    # A lifecycle token with no mapped label must render verbatim, never as a
    # reassuring "active" label on a status surface.
    data = StatusPageData(profiles=(StatusProfileRow(label="mystery", status="future_state", active=False),))
    app = StatusApp(data)
    async with app.run_test(size=_TERMINAL_SIZE):
        table = app.query_one("#profiles-table", DataTable)
        row = tuple(str(cell) for cell in table.get_row_at(0))
        assert row[1] == "future_state"
        assert row[1] != "ST-ACTIVE"


@pytest.mark.asyncio
async def test_auth_panel_reports_provider_and_login_state() -> None:
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        text = str(app.query_one("#auth-lines", Static).content)
        assert "certificate" in text
        assert "AUTH-READY" in text
        assert "ADA LOVELACE" in text


@pytest.mark.asyncio
async def test_auth_panel_reports_unconfigured_provider() -> None:
    app = StatusApp(StatusPageData(auth=StatusAuthView(provider=None, login_ready=False)))
    async with app.run_test(size=_TERMINAL_SIZE):
        text = str(app.query_one("#auth-lines", Static).content)
        assert "AUTH-NONE" in text
        assert "AUTH-NOT-READY" in text


@pytest.mark.asyncio
async def test_recovery_panel_shows_enrollment_and_copyable_commands() -> None:
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        state_text = str(app.query_one("#recovery-lines", Static).content)
        assert "REC-ENROLLED" in state_text
        assert "ab12cd34" in state_text
        commands_text = str(app.query_one("#recovery-commands", Static).content)
        for command in _RECOVERY_COMMANDS:
            assert command in commands_text
        assert all(command.startswith("aeat config") for command in _RECOVERY_COMMANDS)


def test_status_screen_never_imports_the_application_layer() -> None:
    """The read-only screen is an adapter: it must reach no application authority.

    A surface that cannot import the application layer cannot mutate it; the
    view-model is injected, so every zone is a projection with no write path.
    """
    source = pathlib.Path(_status_screen_path()).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert not any("cadrumo.application" in module for module in imported), imported


def _status_screen_path() -> str:
    from .. import _status_screen

    return _status_screen.__file__
