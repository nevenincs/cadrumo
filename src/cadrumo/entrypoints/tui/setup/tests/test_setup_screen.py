"""Setup presents application rows and submits only admitted registered work."""

from __future__ import annotations

import pytest
from textual.widgets import Button, DataTable, Input

from cadrumo.tests.components_role_replay import transcript_lines

from .....adapters.outbound.components.protocol import ComponentsReviewLine, decode_components_line
from .....application.components_operations import ProvisionPlan
from .....application.dependency_contracts import DependencyItemKind
from .....core.config import override_settings
from ...components.host import ScreenHostApp
from ...tests.settling import settle_until
from ..review import setup_review_text
from ..screen import SetupScreen
from .operations_fixture import SetupFixture, StopSubmissionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_status_rows_are_application_rows_and_focus_is_preserved() -> None:
    operations = SetupFixture()
    screen = SetupScreen(operations, focus_item="browser")
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle_until(pilot, lambda: bool(screen.rows), "registered status rows")
            table = screen.query_one("#setup-items", DataTable)
            assert [row.item_id for row in screen.rows] == ["browser", "local_ai"]
            assert table.ordered_rows[table.cursor_row].key.value == "browser"
            assert "Not set up yet" in str(table.get_row_at(0)[1])
            assert not screen.query_one("#btn-setup-all", Button).disabled
    assert operations.reads == 1


@pytest.mark.asyncio
async def test_before_sign_in_status_gives_guidance_without_submitting() -> None:
    screen = SetupScreen()
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test() as pilot:
            await pilot.pause()
            assert screen.status_text == "Sign in first to check or set up components."
            assert screen.rows == ()
            assert screen.query_one("#btn-setup-check", Button).disabled
            assert screen.query_one("#btn-setup-all", Button).disabled


@pytest.mark.asyncio
@pytest.mark.parametrize("verify,items", [(False, (DependencyItemKind.BROWSER,)), (True, ())])
async def test_setup_and_verify_submit_through_the_profile_port(
    verify: bool, items: tuple[DependencyItemKind, ...]
) -> None:
    operations = SetupFixture()
    screen = SetupScreen(operations)
    async with ScreenHostApp(screen).run_test() as pilot:
        await settle_until(pilot, lambda: bool(screen.rows), "status")
        with pytest.raises(StopSubmissionError):
            await screen._open_operation(verify=verify, items=items)
    assert operations.submissions == [(verify, items)]


@pytest.mark.asyncio
async def test_local_ai_never_submits_browser_setup() -> None:
    operations = SetupFixture()
    screen = SetupScreen(operations)
    async with ScreenHostApp(screen).run_test() as pilot:
        await settle_until(pilot, lambda: bool(screen.rows), "status")
        screen.act_on("local_ai")
        screen.start_setup((DependencyItemKind.LOCAL_AI,))
    assert operations.submissions == []


def test_plan_wording_keeps_reviewed_sources_and_sizes() -> None:
    line = next(
        decode_components_line(raw) for raw in transcript_lines("setup_browser_completed") if b'"type":"review"' in raw
    )
    assert isinstance(line, ComponentsReviewLine)
    plan = ProvisionPlan.model_validate_json(line.plan.model_dump_json())
    with override_settings(cadrumo_output_language="en"):
        text = setup_review_text(plan)
    assert "Browser for the tax agency website" in text
    for entry in plan.entries:
        assert all(host in text for host in entry.source_hosts)


@pytest.mark.asyncio
async def test_malformed_reference_never_attaches_or_submits() -> None:
    operations = SetupFixture()
    screen = SetupScreen(operations)
    async with ScreenHostApp(screen).run_test() as pilot:
        await settle_until(pilot, lambda: bool(screen.rows), "status")
        screen.query_one("#setup-review-reference", Input).value = "not-a-reference"
        await screen._open_review()
        assert operations.reviews == []
        assert operations.submissions == []


@pytest.mark.asyncio
async def test_known_reference_attaches_without_submitting_or_starting() -> None:
    operations = SetupFixture()
    screen = SetupScreen(operations)
    async with ScreenHostApp(screen).run_test() as pilot:
        await settle_until(pilot, lambda: bool(screen.rows), "status")
        screen.query_one("#setup-review-reference", Input).value = "a" * 64
        with pytest.raises(StopSubmissionError):
            await screen._open_review()
        assert operations.reviews == ["a" * 64]
        assert operations.submissions == []
