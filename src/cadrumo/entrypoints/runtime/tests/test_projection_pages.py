"""Native result paging retains canonical projection and per-page authority."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.operation_access import RuntimeOperationPage, RuntimeOperationResultPage
from cadrumo.application.runtime.projection_pages import PROJECTION_PAGE_BYTES, ProjectionPageRequest
from cadrumo.application.user_profile.automation_enrollment import AutomationInventoryProjection
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import OperationTerminalCondition

from ..profile_connections import RuntimeProfileConnections
from .test_automation_enrollment import _connect, _LoginObservation, _submit_operation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_native_paged_inventory_refuses_continuation_after_global_lock(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        requested = {uuid4() for _ in range(36)}
        for identity in requested:
            subject.service.request(identity, subject.proposal)
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    raw, control_raw = _connect(endpoint), _connect(endpoint)
                    client, control = (
                        RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI),
                        RuntimeFrontendClient(
                            control_raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                        ),
                    )
                    cleanup.callback(client.close)
                    cleanup.callback(control.close)
                    client.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)
                    control.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)
                    contract, submitted, observed = _submit_operation(
                        raw,
                        profile_id=profile_id,
                        session_id=client.session_id,
                        definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()),
                    )
                    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    schema = contract.contract.result_schema
                    assert schema is not None
                    result = OperationResultProjectionRequestV1(
                        operation_id=submitted.receipt.operation_id,
                        terminal_revision=observed.projection.revision,
                        definition_contract_digest=contract.contract.definition_contract_digest,
                        result_schema=schema,
                    )
                    document = client.read_result_document(result, timeout=30)
                    encoded = canonical_json_bytes(document)
                    assert len(encoded) > PROJECTION_PAGE_BYTES
                    inventory = (
                        OperationResultProjectionSuccessV1[AutomationInventoryProjection]
                        .model_validate_json(encoded)
                        .projection
                    )
                    assert {item.receipt.request_id for item in inventory.requests} == requested
                    first = client.operation(
                        RuntimeOperationResultPage(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=client.session_id,
                            result=result,
                            page=ProjectionPageRequest(),
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(first, RuntimeOperationPage)
                    control.deny_automation(AutomationDenialKind.PROFILE_LOCK)
                    with pytest.raises(RuntimeFrontendRefusedError):
                        client.operation(
                            RuntimeOperationResultPage(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=client.session_id,
                                result=result,
                                page=ProjectionPageRequest(
                                    offset=len(first.page.decode()), expected_digest=first.page.document_digest
                                ),
                            ),
                            deadline=time.monotonic() + 10,
                        )
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
