"""Protected references use the established cold profile admission budget."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime import deadline_budget
from cadrumo.application.runtime.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS

from .. import runtime_credentials
from ..frontend_client import RuntimeFrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.anyio
@pytest.mark.parametrize("explicit_timeout", [None, 2.5])
async def test_protected_reference_uses_profile_admission_budget_and_preserves_explicit_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_timeout: float | None
) -> None:
    profile_id, reference = uuid4(), uuid4()
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=profile_id))
    opened: list[float] = []
    authenticated: list[float] = []

    async def open_client(
        *, profile_id: UUID, frontend: OperationFrontendProjection, timeout: float
    ) -> RuntimeFrontendClient:
        assert profile_id == client.profile_id and frontend is OperationFrontendProjection.MCP
        opened.append(timeout)
        return client

    def authenticate(
        current: RuntimeFrontendClient,
        *,
        root: Path,
        credential_reference: UUID,
        secrets_store: object,
        deadline: float,
    ) -> None:
        assert current is client and root == tmp_path and credential_reference == reference
        authenticated.append(deadline)

    monkeypatch.setattr(runtime_credentials, "effective_storage_root", lambda: tmp_path)
    monkeypatch.setattr(runtime_credentials, "open_installed_runtime_client", open_client)
    monkeypatch.setattr(runtime_credentials, "_authenticate_reference", authenticate)
    monkeypatch.setattr(deadline_budget, "time", SimpleNamespace(monotonic=lambda: 100.0))
    if explicit_timeout is None:
        admitted = await runtime_credentials.open_installed_credential_client(
            profile_id=profile_id,
            credential_reference=reference,
            frontend=OperationFrontendProjection.MCP,
        )
    else:
        admitted = await runtime_credentials.open_installed_credential_client(
            profile_id=profile_id,
            credential_reference=reference,
            frontend=OperationFrontendProjection.MCP,
            timeout=explicit_timeout,
        )
    expected = PROFILE_ADMISSION_TIMEOUT_SECONDS if explicit_timeout is None else explicit_timeout
    assert admitted is client
    assert opened == [expected] and authenticated == [100.0 + expected]
    assert inspect.signature(RuntimeFrontendClient.login_api_key).parameters["timeout"].default == (
        PROFILE_ADMISSION_TIMEOUT_SECONDS
    )
