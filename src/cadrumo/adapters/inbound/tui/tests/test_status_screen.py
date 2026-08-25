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
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
import yaml
from textual.widgets import DataTable, Static

from .....core import (
    ActionArgumentSource,
    ActionArgumentStatus,
)
from .....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from .....core.json_contract import (
    Notice,
    NoticeSeverity,
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedNoticeAction,
)
from .....entrypoints.tui.profile.status import (
    StatusApp,
    StatusAuthView,
    StatusFactRow,
    StatusPageData,
    StatusProfileRow,
)
from .....tests.locales_root_fixture import locales_root_scope

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
                "notices": "SEC-NOTICES",
            },
            "profile": {
                "none": "NO-ACTIVE-PROFILE",
                "column": {"field": "COL-FIELD", "value": "COL-VALUE"},
            },
            "profiles": {
                "none": "NO-PROFILES",
                "column": {"label": "COL-LABEL", "status": "COL-STATUS", "active": "COL-ACTIVE"},
                "status": {
                    "complete": "ST-COMPLETE",
                    "incomplete": "ST-INCOMPLETE",
                    "unknown": "ST-UNKNOWN",
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
    with locales_root_scope(root):
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
            StatusProfileRow(label="ada", setup_state="complete", active=True),
            StatusProfileRow(label="grace", setup_state="incomplete", active=False),
            StatusProfileRow(label="hedy", setup_state="complete", active=False),
        ),
        auth=StatusAuthView(
            provider="certificate",
            login_ready=True,
            subject="ADA LOVELACE",
            certificate_source="disk",
        ),
    )


def _all_cell_text(table: DataTable[str]) -> list[str]:
    return [str(cell) for index in range(table.row_count) for cell in table.get_row_at(index)]


@pytest.mark.asyncio
async def test_all_status_zones_render_as_bordered_panels() -> None:
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        panels = {
            "#panel-profile": "SEC-PROFILE",
            "#panel-profiles": "SEC-PROFILES",
            "#panel-auth": "SEC-AUTH",
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
        assert rows[2][1] == "ST-COMPLETE"


@pytest.mark.asyncio
async def test_unmapped_profile_status_renders_an_operator_label_not_the_token() -> None:
    # A future lifecycle token must remain visibly unknown without exposing
    # the storage vocabulary or being misrepresented as active.
    data = StatusPageData(profiles=(StatusProfileRow(label="mystery", setup_state="future_state", active=False),))
    app = StatusApp(data)
    async with app.run_test(size=_TERMINAL_SIZE):
        table = app.query_one("#profiles-table", DataTable)
        row = tuple(str(cell) for cell in table.get_row_at(0))
        assert row[1] == "ST-UNKNOWN"
        assert "future_state" not in row
        assert row[1] != "ST-COMPLETE"


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
@pytest.mark.asyncio
async def test_a_notice_paints_its_severity_glyph_message_and_resolved_action() -> None:
    """The band renders exactly what the typed Notice carries, glyph and all.

    Severity drives the glyph and the CSS class rather than only the
    colour, per the surface's own "colour is never the sole carrier of
    meaning" convention; a resolved action, when present, renders its typed
    target identity on its own line beneath the message.
    """
    data = StatusPageData(
        notices=(
            Notice(severity=NoticeSeverity.INFO, code="test.info", message="INFO-MESSAGE"),
            Notice(
                severity=NoticeSeverity.WARNING,
                code="test.warning",
                message="WARNING-MESSAGE",
                action=ResolvedNoticeAction(
                    action=ResolvedActionReference(
                        action_id="operator.profile.status",
                        target_command_key="config.profile.status",
                        cli_path=("config", "profile", "status"),
                    ),
                ),
            ),
            Notice(
                severity=NoticeSeverity.INFO,
                code="test.bound-action",
                message="BOUND-ACTION-MESSAGE",
                action=ResolvedNoticeAction(
                    action=ResolvedActionReference(
                        action_id="operator.profile.create",
                        target_command_key="config.profile.create",
                        cli_path=("config", "profile", "create"),
                    ),
                    argument_bindings=(
                        ResolvedActionArgument(
                            argument_name="profile_name",
                            status=ActionArgumentStatus.RESOLVED,
                            value="Taxpayer One",
                            source=ActionArgumentSource.REQUEST_CONTEXT,
                            source_key="profile_name",
                        ),
                    ),
                ),
            ),
        ),
    )
    app = StatusApp(data)
    async with app.run_test(size=_TERMINAL_SIZE):
        panel = app.query_one("#panel-notices", Static)
        assert str(panel.border_title) == "SEC-NOTICES"

        info_line = app.query_one("#notice-0", Static)
        assert "INFO-MESSAGE" in str(info_line.content)
        assert "info" in str(info_line.classes)
        assert not app.query("#notice-0-action")

        warning_line = app.query_one("#notice-1", Static)
        assert "WARNING-MESSAGE" in str(warning_line.content)
        assert "warning" in str(warning_line.classes)
        action_line = app.query_one("#notice-1-action", Static)
        assert str(action_line.content) == "aeat config profile status"
        assert not app.query("#notice-2-action"), (
            "an argument-bearing action must stay hidden until the canonical argv renderer can include its values"
        )

        # The class name alone is not the claim: the CSS the class selects
        # must actually resolve to two DIFFERENT colours, or "severity
        # drives presentation" is true of the markup and false on screen.
        # Only INFO has a real application-layer producer today
        # (``no_aeat_history_notice``); WARNING is exercised here at the
        # rendering layer only, with a hand-built Notice — there is no
        # shipped WARNING producer this suite can drive end to end yet.
        assert info_line.styles.color != warning_line.styles.color


@pytest.mark.asyncio
async def test_no_notices_leaves_no_empty_advisory_box() -> None:
    """A healthy profile carries no permanent 'nothing to report' placeholder."""
    app = StatusApp(_populated_data())
    async with app.run_test(size=_TERMINAL_SIZE):
        assert not app.query("#panel-notices")


_UNREASONABLE_NOTICE_PANEL_HEIGHT = 8
"""Row ceiling for a panel holding a single one-line notice.

Real content bounds this panel's height to a handful of rows regardless of
terminal size; the regression this test pins made it claim the ENTIRE
scroll column instead (measured 82-92 rows against a 2-row healthy render,
at both 100x50 and 140x60), which is what actually pushed every sibling
panel out of practical reach. A generous ceiling well above the honest
2-row render, but nowhere near what the regression produced."""


@pytest.mark.asyncio
async def test_a_notice_does_not_eliminate_the_other_panels() -> None:
    """A panel must never take over the whole scroll column and starve its siblings.

    Regression pin. ``NoticeBand`` inherited Textual's ``Vertical`` default
    height (``1fr``); inside the auto-height ``#panel-notices`` ``Static``,
    that resolved against the nearest ancestor with a definite size and grew
    the panel to consume nearly the entire scrollable column (measured 82-92
    rows for ONE notice line, against 2 once fixed) — burying every sibling
    panel far past any practically reachable scroll position, at every
    terminal size the operator's bug report and the fix commit tested.

    None of the earlier notice tests could catch this: each one only ever
    asserted what the band itself shows, never a property relating it to a
    SIBLING panel. This is that property, expressed the way that actually
    reproduces and reds under the defect — a plain ``query_one`` presence
    check does NOT: a widget the notice band buried is still fully present
    in the DOM, mounted, non-empty, row-count intact. Two independent shapes
    of size assertion were tried and rejected before this one: a bare
    ``size.height > 0`` on each sibling survived the reverted CSS unchanged
    (the siblings kept their own natural few-row heights even while pushed
    far down-column), and reading their screen ``region`` is viewport-size
    dependent. The height CEILING on the notices panel itself is what
    actually discriminates in both directions and at both terminal sizes
    tested, because it pins the one measurement that is grossly different
    between the two states — TENS of rows apart, not on/off.

    Mutation-proved by hand, both terminal sizes the original report and
    fix cited (100x50, 140x60): a live ``NoticeBand`` subclass overriding
    ``CSS`` with the ``height: auto`` rule stripped (subclassing was
    necessary — Textual compiles ``CSS`` once at class-body execution, so
    reassigning the attribute on the live class after the fact is a no-op)
    measured the notices panel at 82-92 rows and reds this test; the
    shipped, unmodified ``StatusApp`` measures 2 rows and passes. No tracked
    file was edited to prove this — the broken CSS lived only in a
    throwaway subclass in an ad-hoc verification script, never committed.
    """
    data = replace(
        _populated_data(),
        notices=(Notice(severity=NoticeSeverity.WARNING, code="test.regression", message="REGRESSION-NOTICE"),),
    )
    app = StatusApp(data)
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        # A DataTable's intrinsic auto-height is not settled by the single
        # implicit pass ``run_test`` performs on entry; unrelated to the
        # regression itself, but without this pause every panel measures
        # zero height on the FIXED code too, which would make the checks
        # below fail for the wrong reason.
        await pilot.pause()
        assert "REGRESSION-NOTICE" in str(app.query_one("#notice-0", Static).content)

        notices_panel = app.query_one("#panel-notices", Static)
        assert notices_panel.size.height <= _UNREASONABLE_NOTICE_PANEL_HEIGHT, (
            f"the notices panel claimed {notices_panel.size.height} rows for one notice "
            "line — it is starving the panels beneath it, the exact regression this pins"
        )

        profile_panel = app.query_one("#panel-profile", Static)
        assert str(profile_panel.border_title) == "SEC-PROFILE"
        assert app.query_one("#profile-facts", DataTable).row_count == 3

        profiles_panel = app.query_one("#panel-profiles", Static)
        assert str(profiles_panel.border_title) == "SEC-PROFILES"
        assert app.query_one("#profiles-table", DataTable).row_count == 3

        auth_panel = app.query_one("#panel-auth", Static)
        assert str(auth_panel.border_title) == "SEC-AUTH"
        assert "AUTH-READY" in str(app.query_one("#auth-lines", Static).content)


@pytest.mark.asyncio
async def test_a_notice_does_not_eliminate_the_other_panels_at_a_smaller_terminal() -> None:
    """The same property at 100x50 — the second size the original bug report named."""
    data = replace(
        _populated_data(),
        notices=(Notice(severity=NoticeSeverity.WARNING, code="test.regression", message="REGRESSION-NOTICE"),),
    )
    app = StatusApp(data)
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()
        notices_panel = app.query_one("#panel-notices", Static)
        assert notices_panel.size.height <= _UNREASONABLE_NOTICE_PANEL_HEIGHT
        assert app.query_one("#profile-facts", DataTable).row_count == 3
        assert app.query_one("#profiles-table", DataTable).row_count == 3
        assert "AUTH-READY" in str(app.query_one("#auth-lines", Static).content)


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
    from .....entrypoints.tui.profile import status

    return status.__file__
