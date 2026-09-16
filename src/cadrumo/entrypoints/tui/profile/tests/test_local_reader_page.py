"""The document reader page renders measured truth and submits only through its door."""

from __future__ import annotations

import pytest
from textual.widgets import Button, DataTable, Static

from .....application.local_reader import LocalReaderRoleStatus, LocalReaderStatus
from .....application.provisioning_contracts import (
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from .....application.provisioning_host import RuntimeHostPlatform, RuntimeHostStatus, RuntimeInstaller
from .....core.config import override_settings
from .....core.model_catalogue import ModelRole
from ...components.host import ScreenHostApp
from ...operations.controller import OperationController
from ..local_reader import LocalReaderScreen, local_reader_role_cells

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _unreachable_status() -> LocalReaderStatus:
    facts = {"runtime_reachable": False}
    host = RuntimeHostStatus.model_validate(
        {
            "platform": RuntimeHostPlatform.WINDOWS,
            "endpoint_url": "http://127.0.0.1",
            "endpoint_local": True,
            "executable_located": True,
            "reachable": False,
            "installer": RuntimeInstaller.WINGET,
            "available": False,
            "facts": facts,
            "precondition_verdict": provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE, facts=facts
            ),
        }
    )
    return LocalReaderStatus(
        host=host,
        roles=(
            LocalReaderRoleStatus(
                role=ModelRole.TEXT_EXTRACTION,
                model="qwen3:1.7b",
                ready=False,
                failed_condition_id=ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value,
            ),
        ),
        extraction_ready=False,
    )


class _Door:
    """Measures a fixed unreachable runtime; no test here presses an action."""

    def read_status(self) -> LocalReaderStatus:
        return _unreachable_status()

    async def start(self) -> OperationController:
        raise AssertionError("no action was pressed")

    async def pull(self, role: ModelRole) -> OperationController:
        raise AssertionError(f"no action was pressed for {role}")

    async def verify(self, role: ModelRole) -> OperationController:
        raise AssertionError(f"no action was pressed for {role}")


def test_an_unmeasured_answer_never_reads_as_not_installed() -> None:
    row = _unreachable_status().roles[0]
    with override_settings(cadrumo_output_language="en"):
        cells = local_reader_role_cells(row)
    assert cells[2] == "not measured"
    assert cells[3] == "not measured"
    assert cells[4] == "no"


@pytest.mark.asyncio
async def test_page_shows_the_measured_state_and_submits_per_selected_role() -> None:
    door = _Door()
    screen = LocalReaderScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 40)) as pilot:
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            summary = str(screen.query_one("#local-reader-summary", Static).render())
            assert "answering: no" in summary
            assert "can't be read" in summary
            assert screen.query_one("#local-reader-pull", Button).disabled
            assert not any(button.id == "local-reader-install" for button in screen.query(Button))
            table = screen.query_one("#local-reader-roles", DataTable)
            table.focus()
            await pilot.press("enter")
            assert screen.selected_role is ModelRole.TEXT_EXTRACTION
            assert not screen.query_one("#local-reader-pull", Button).disabled
