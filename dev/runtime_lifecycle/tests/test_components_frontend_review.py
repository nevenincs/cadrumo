"""A TUI person reviews an MCP submission through the real runtime."""

from __future__ import annotations

import asyncio
import json
from contextlib import ExitStack
from pathlib import Path

import pytest
from textual.widgets import Button, Input, Static

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.application.components_operations import COMPONENTS_OPERATION_SUBJECT, COMPONENTS_SETUP_OPERATION_ID
from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.operations.interactions import OperationModalReviewInteractionV1
from cadrumo.entrypoints.tui.operations.modal import OperationModal
from cadrumo.entrypoints.tui.setup.destination import SetupOperations
from cadrumo.entrypoints.tui.setup.screen import SetupScreen
from cadrumo.entrypoints.tui.tests.settling import settle_until
from cadrumo.tests.components_role_package import (
    CountingProxy,
    components_role_fixture,
    counting_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_mcp.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_mcp.mcp.server import build_server
from cadrumo_mcp.mcp.tests.agent_key_reads import tool_document
from cadrumo_mcp.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime
from dev.runtime_lifecycle.tests.test_components_review import _frontend, _waiting

__all__ = ["components_role_fixture", "counting_proxy_fixture", "staged_components_role_fixture"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.external_tool, pytest.mark.windows_only]


@pytest.mark.usefixtures("components_role")
def test_tui_claims_and_rejects_existing_mcp_setup(tmp_path: Path, counting_proxy: CountingProxy) -> None:
    with (
        service_record_runtime(tmp_path) as runtime,
        ExitStack() as scope,
        override_settings(cadrumo_output_language="en"),
    ):
        human = _frontend(runtime, OperationFrontendProjection.TUI)
        scope.callback(human.close)
        assert human.login_password(bytearray(PROFILE_INPUT, "utf-8")).status.denial is None
        external = _frontend(runtime, OperationFrontendProjection.EXTERNAL_CLIENT)
        scope.callback(external.close)
        assert human.attendance_inventory().candidates == ()
        ask = external.request_attendance()
        assert isinstance(ask, AttendancePending)
        assert human.decide_attendance(ask.attendance_id, approve=True).approved
        assert isinstance(external.attendance_status(ask.attendance_id), ProfileStatus)
        adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=external)

        async def scenario() -> None:
            try:
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    submitted = tool_document(
                        await sdk.call_tool(
                            "execute",
                            {
                                "definition_id": COMPONENTS_SETUP_OPERATION_ID,
                                "subject_ref": COMPONENTS_OPERATION_SUBJECT,
                                "payload": {},
                            },
                        )
                    )
                    operation_id = submitted["receipt"]["operation_id"]

                    async def read() -> OperationPublicProjectionV1:
                        document = tool_document(
                            await sdk.call_tool(
                                "observe",
                                {
                                    "observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32},
                                },
                            )
                        )
                        return OperationPublicProjectionV1.model_validate_json(
                            json.dumps(document["reply"]["observation"]["projection"])
                        )

                    waiting = await _waiting(external, read)
                    pending = waiting.pending_interaction
                    assert isinstance(pending, OperationReviewAvailableInteractionV1)
                    screen = SetupScreen(SetupOperations(client=human, session_id=human.session_id))
                    app = ScreenHostApp(screen)
                    async with app.run_test(size=(120, 50)) as pilot:
                        await settle_until(pilot, lambda: bool(screen.rows), "component status")
                        screen.query_one("#setup-review-reference", Input).value = operation_id
                        await pilot.click("#btn-setup-review")
                        await settle_until(
                            pilot, lambda: isinstance(app.screen, OperationModal), "existing review", workers=False
                        )
                        modal = app.screen
                        assert isinstance(modal, OperationModal)
                        await settle_until(
                            pilot,
                            lambda: modal.query_one("#btn-operation-claim", Button).display,
                            "review document",
                            workers=False,
                        )
                        assert "Browser for the tax agency website" in str(
                            modal.query_one("#operation-modal-review", Static).render()
                        )
                        assert modal.query_one("#btn-operation-reject", Button).disabled
                        assert not modal.query_one("#btn-operation-cancel", Button).display
                        assert not modal.query_one("#btn-operation-detach", Button).display
                        journal = OperationJournalRepository(storage_root=runtime.root)
                        before = await journal.load(operation_id)
                        assert before.revision == pending.revision
                        await modal._claim_review()
                        interaction = modal._interaction
                        assert isinstance(interaction, OperationModalReviewInteractionV1)
                        assert interaction.interaction.revision == pending.revision + 1
                        assert not modal.query_one("#btn-operation-reject", Button).disabled
                        claimed = await journal.load(operation_id)
                        await modal._request_cancel()
                        await modal._request_detach()
                        assert (await journal.load(operation_id)).revision == claimed.revision
                        assert (await read()).lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
                        await pilot.click("#btn-operation-reject")
                        terminal = await _waiting(external, read, target=OperationLifecycle.TERMINAL)
                        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                        assert terminal.effect is OperationEffect.NONE
                        stored = await journal.load(operation_id)
                        assert len(stored.consumed_interactions) == 1
                        decision = stored.consumed_interactions[0]
                        assert decision.response_action == "reject"
                        assert decision.checkpoint.review_claim is not None
                        assert decision.checkpoint.review_claim.session_id == human.session_id
                        page = await journal.inventory_page(after=None, limit=128)
                        assert not page.has_more
                        snapshots = [await journal.load(entry.operation_id) for entry in page.entries]
                        setups = [
                            item for item in snapshots if item.identity.definition_id == COMPONENTS_SETUP_OPERATION_ID
                        ]
                        assert len(setups) == 1 and setups[0].identity.operation_id == operation_id
                        assert counting_proxy.tunnels == {} and counting_proxy.unauthenticated == 0
            finally:
                await adapter.close()

        asyncio.run(scenario())
