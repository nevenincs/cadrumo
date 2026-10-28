"""A native desktop person finds and answers an MCP setup over the real Windows pipe.

The desktop host test uses production NativeSession and runtime_client.Connection,
with canonical password admission on a marked disposable development root.
Only OS login observation and secret custody use the service fixture's test ports.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from contextlib import ExitStack
from pathlib import Path
from threading import Thread
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.application.components_operations import COMPONENTS_OPERATION_SUBJECT, COMPONENTS_SETUP_DEFINITION_ID
from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.tests.components_role_package import (
    CountingProxy,
    components_role_fixture,
    counting_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.operation_access import OperationClaimableReviews
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.windows_process import WindowsProcessScope
from cadrumo_mcp.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_mcp.mcp.server import build_server
from cadrumo_mcp.mcp.tests.agent_key_reads import tool_document
from cadrumo_mcp.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.application.development_root import mark_development_root, verify_development_root
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime

from .test_components_review import _frontend, _waiting

__all__ = ["components_role_fixture", "counting_proxy_fixture", "staged_components_role_fixture"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.external_tool, pytest.mark.windows_only]


def _run_desktop_fixture(environment: dict[str, str], log_file: Path) -> tuple[int, str]:
    """Contain CMake and its descendants, drain both pipes and bound retained output."""
    executable = shutil.which("cmake")
    assert executable is not None, "CMake must be available for the native desktop proof"
    process_scope = WindowsProcessScope()
    with ExitStack() as cleanup:
        cleanup.callback(process_scope.terminate, timeout=5)
        process, standard_input, standard_output, standard_error = process_scope.launch_with_standard_pipes(
            executable=Path(executable).resolve(strict=True),
            arguments=("--build", "build/windows-x64", "--config", "Debug", "--target", "desktop-host-unit-test"),
            directory=Path(__file__).resolve().parents[3],
            environment=environment,
        )
        for stream in (standard_input, standard_output, standard_error):
            cleanup.callback(stream.close)
        standard_input.close()
        outputs = [bytearray(), bytearray()]
        failures: list[BaseException] = []

        def drain(stream: BinaryIO, output: bytearray) -> None:
            try:
                while chunk := stream.read(64 * 1024):
                    # Continue draining after the retained diagnostic bound.
                    output.extend(chunk[: max(0, 4 * 1024 * 1024 - len(output))])
            except BaseException as error:
                failures.append(error)

        readers = [
            Thread(target=drain, args=(stream, output), daemon=True)
            for stream, output in zip((standard_output, standard_error), outputs, strict=True)
        ]
        for reader in readers:
            reader.start()
        try:
            return_code = process.wait(timeout=300)
        finally:
            # Also reap descendants that retained pipe handles after CMake exits.
            process_scope.terminate(timeout=5)
            for reader in readers:
                reader.join(timeout=5)
            transcript = "\n".join(output.decode("utf-8", errors="replace") for output in outputs)
            log_file.write_text(transcript, encoding="utf-8")
            assert all(not reader.is_alive() for reader in readers), "native build output drains did not stop"
        assert not failures, failures
        return return_code, transcript


@pytest.mark.usefixtures("components_role")
def test_native_desktop_claims_and_rejects_existing_mcp_setup(tmp_path: Path, counting_proxy: CountingProxy) -> None:
    with service_record_runtime(tmp_path) as runtime, ExitStack() as scope:
        # Use the checkout desktop's canonical native-person admission. This
        # binds the disposable root to its real native endpoint; the runtime
        # still verifies the desktop process identity and profile password.
        mark_development_root(runtime.root)
        assert verify_development_root(runtime.root, runtime.endpoint.storage_identity)
        parent = _frontend(runtime, OperationFrontendProjection.TUI)
        scope.callback(parent.close)
        assert parent.login_password(bytearray(PROFILE_INPUT, "utf-8")).status.denial is None
        external = _frontend(runtime, OperationFrontendProjection.EXTERNAL_CLIENT)
        scope.callback(external.close)
        assert parent.attendance_inventory().candidates == ()
        ask = external.request_attendance()
        assert isinstance(ask, AttendancePending)
        assert parent.decide_attendance(ask.attendance_id, approve=True).approved
        assert isinstance(external.attendance_status(ask.attendance_id), ProfileStatus)
        adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=external)

        async def scenario() -> None:
            try:
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    submitted = tool_document(
                        await sdk.call_tool(
                            "execute",
                            {
                                "definition_id": COMPONENTS_SETUP_DEFINITION_ID,
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
                                {"observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}},
                            )
                        )
                        return OperationPublicProjectionV1.model_validate_json(
                            json.dumps(document["reply"]["observation"]["projection"])
                        )

                    waiting = await _waiting(external, read)
                    pending = waiting.pending_interaction
                    assert isinstance(pending, OperationReviewAvailableInteractionV1)
                    for action in ("inspect", "apply", "reject"):
                        refused = await sdk.call_tool(
                            "respond",
                            {
                                "action": action,
                                "operation_id": operation_id,
                                "interaction_id": pending.interaction_id,
                                "revision": pending.revision,
                            },
                        )
                        assert refused.is_error is True, refused
                        assert refused.structured_content is not None
                        assert refused.structured_content["code"] == "person_act_required"

                    # Only a desktop person learns which setup reviews it may claim: the TUI
                    # person and the MCP client asking for the same listing are refused.
                    for client, code in (
                        (parent, AccessDenialCode.HUMAN_AUTHORITY_REQUIRED),
                        (external, AccessDenialCode.PERSON_ACT_REQUIRED),
                    ):
                        with pytest.raises(FrontendRefusedError) as refusal:
                            client.operation(
                                OperationClaimableReviews(
                                    request_id=uuid4(), profile_id=runtime.profile_id, session_id=client.session_id
                                ),
                                deadline=time.monotonic() + 10,
                            )
                        assert refusal.value.reason == code.value
                    journal = OperationJournalRepository(storage_root=runtime.root)
                    before = await journal.load(operation_id)
                    assert before.admission_provenance_reference is not None
                    output_file = tmp_path / "native-desktop-review-result.json"
                    config_file = tmp_path / "native-desktop-review-fixture.json"
                    config_file.write_text(
                        json.dumps(
                            {
                                "storage_root": str(runtime.root),
                                "profile_id": str(runtime.profile_id),
                                "operation_id": operation_id,
                                "password": PROFILE_INPUT,
                                "output_file": str(output_file),
                            }
                        ),
                        encoding="utf-8",
                    )
                    environment = os.environ.copy()
                    environment["CADRUMO_DESKTOP_REVIEW_RUNTIME_FIXTURE"] = str(config_file)
                    return_code, transcript = await asyncio.to_thread(
                        _run_desktop_fixture,
                        environment,
                        tmp_path / "native-desktop-review-build.log",
                    )
                    assert return_code == 0, transcript
                    # A skipped/unselected Rust fixture must never make this proof pass.
                    assert output_file.is_file(), transcript
                    result = json.loads(output_file.read_text(encoding="utf-8"))
                    identity, review, claimed = result["identity"], result["review"], result["claimed"]
                    assert review["operation_id"] == claimed["operation_id"] == operation_id
                    assert review["revision"] == pending.revision
                    assert claimed["revision"] == pending.revision + 1
                    assert review["review_digest"] == content_hash_hex(review["document"])
                    assert claimed["review_digest"] == content_hash_hex(claimed["document"])
                    assert result["responded"]["decision"] == "reject"
                    # Listed while claimable and while this person holds it; gone once answered.
                    assert result["listed_before"] == [operation_id]
                    assert result["listed_claimed"] == [operation_id]
                    assert result["listed_after"] == []
                    terminal = await _waiting(external, read, target=OperationLifecycle.TERMINAL)
                    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert terminal.effect is OperationEffect.NONE
                    stored = await journal.load(operation_id)
                    assert stored.admission_provenance_reference == before.admission_provenance_reference
                    assert len(stored.consumed_interactions) == 1
                    decision = stored.consumed_interactions[0]
                    assert decision.response_action == "reject"
                    claim = decision.checkpoint.review_claim
                    assert claim is not None and claim.frontend == "desktop"
                    assert claim.session_id == UUID(identity["session_id"])
                    assert claim.connection_id == UUID(identity["connection_id"])
                    assert claim.profile_id == runtime.profile_id
                    assert claim.runtime_boot_id == UUID(identity["runtime_boot_id"])
                    assert claim.session_id not in {parent.session_id, external.session_id}
                    assert claim.displayed_revision == pending.revision
                    assert claim.reviewed_document_digest == review["review_digest"]
                    page = await journal.inventory_page(after=None, limit=128)
                    assert not page.has_more
                    snapshots = [await journal.load(entry.operation_id) for entry in page.entries]
                    setups = [
                        item for item in snapshots if item.identity.definition_id == COMPONENTS_SETUP_DEFINITION_ID
                    ]
                    assert len(setups) == 1 and setups[0].identity.operation_id == operation_id
                    assert counting_proxy.tunnels == {} and counting_proxy.unauthenticated == 0
            finally:
                await adapter.close()

        asyncio.run(scenario())
