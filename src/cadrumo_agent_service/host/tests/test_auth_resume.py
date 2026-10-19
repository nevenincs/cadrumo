"""A settled login resumes only once while its original authority is current."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ...service import AgentService
from ..auth_attempt import AuthAttempt

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("ending", ["current", "revoked", "closing", "stopped"])
def test_settlement_consumes_resume_only_under_original_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    lease = object()
    client = SimpleNamespace(lease=lease)
    service = AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    attempt = AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=tmp_path / "absent.exe",
        arguments=(),
        directory=tmp_path,
        environment={},
        valid=lambda: False,
    )
    attempt.close()
    service._auth_attempt = attempt
    service._auth_resume_valid = lambda: client.lease is lease and not service._closing.is_set()
    starts: list[bool] = []
    monkeypatch.setattr(service, "_background_start", lambda: starts.append(True))
    monkeypatch.setattr(service._store, "observe_generations", lambda: None)
    if ending == "revoked":
        client.lease = None
    elif ending == "closing":
        service._closing.set()
    elif ending == "stopped":
        assert service.admin("stop") == {"kind": "stopped"}
    service.observe()
    service.observe()
    assert starts == ([True] if ending == "current" else [])
