"""Operator sign-in prepares only a fixed profile-bound command, never provider credentials."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service as service_module
from ...adapters.agent_programs import AgentImage
from ...providers.application.contracts import (
    ProviderSettingsActionAccepted,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderStatusEntry,
)
from ...providers.application.tests.synthetic_catalog import synthetic_catalog
from ...service import AgentService
from ..launch_environment import EXTERNAL_BIN_DIRECTORIES_VARIABLE, HOSTED_ROOT_VARIABLE

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _entry() -> ProviderStatusEntry:
    return ProviderStatusEntry.model_validate(
        {
            "id": "example_cli",
            "provider": "example",
            "transport": "cli",
            "display_name": "Example",
            "auth_kind": "provider_sign_in_only",
            "consumers": ["assistant"],
            "mode": "provider_sign_in",
            "available": False,
            "source": "none",
            "readiness": "sign_in_required",
            "reason": None,
            "base_url": None,
            "default_base_url": None,
            "cli_state": None,
            "revision": "a" * 64,
        },
        strict=False,
    )


@pytest.mark.parametrize(
    "outcome", ("prepared", "prepared_node", "revision_conflict", "revoked", "unsupported", "api_lane")
)
def test_sign_in_preparation_preserves_authority_and_never_claims_login(
    outcome: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = SimpleNamespace(lease=SimpleNamespace(profile_id=uuid4()))
    service = AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
        agent_source=None,
        gateway_bearer=bytearray(b"synthetic-gateway"),
        emit=lambda _event: None,
    )
    image = AgentImage(tmp_path / "cadrumo-agent.exe", (), tmp_path / "agent")
    monkeypatch.setattr(service_module, "agent_image", lambda *_args, **_kwargs: image)
    python = None
    node_bin = None
    if outcome == "prepared_node":
        package = tmp_path / "package"
        package.mkdir()
        python = package / ("python.exe" if sys.platform == "win32" else "python")
        python.touch()
        packages = "cadrumo/site-packages" if sys.platform == "win32" else "lib/cadrumo/site-packages"
        (package / packages).mkdir(parents=True)
        node_bin = (package / packages).parent / "node"
        if sys.platform != "win32":
            node_bin /= "bin"
        node_bin.mkdir(parents=True)
        (node_bin / ("node.exe" if sys.platform == "win32" else "node")).touch()
        (package / "data").mkdir()
        (package / "data/package-manifest.json").write_text(
            json.dumps({"layout": {"paths": {"executable": python.name, "packages": packages}}})
        )
    monkeypatch.setattr(service_module, "hosted_python", lambda: python)
    monkeypatch.setattr(service._catalog, "catalog", synthetic_catalog)
    monkeypatch.setattr(service._catalog, "sign_in_providers", lambda: () if outcome == "unsupported" else ("example",))
    calls: list[str] = []

    def select_mode(provider: str, **_kwargs: object) -> ProviderSettingsActionAccepted | ProviderSettingsRefusal:
        calls.append(provider)
        if outcome == "revision_conflict":
            return ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.REVISION_CONFLICT)
        if outcome == "revoked":
            client.lease = None
        return ProviderSettingsActionAccepted(entry=_entry())

    monkeypatch.setattr(service._providers, "set_assistant_auth", select_mode)
    monkeypatch.setenv(EXTERNAL_BIN_DIRECTORIES_VARIABLE, str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", "must-not-cross")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-cross")
    lane = "example_api" if outcome == "api_lane" else "example_cli"
    answer = service.admin("sign_in", provider=lane, expected_revision="0" * 64)
    if outcome in {"unsupported", "api_lane"}:
        assert calls == []
        assert answer == {"kind": "refused", "code": "sign_in_unavailable"}
        assert not (tmp_path / "agent").exists()
        return
    assert calls == ["example_cli"]
    if outcome == "revision_conflict":
        assert answer == {"code": "revision_conflict"}
    elif outcome == "revoked":
        assert answer == {"kind": "refused", "code": "signed_out"}
    else:
        assert answer["kind"] == "sign_in_prepared"
        assert answer["entry"]["readiness"] == "sign_in_required"
        assert answer["launch"]["executable"] == str(image.executable)
        assert answer["launch"]["arguments"] == [
            "-m",
            "cadrumo_agent.cli.main",
            "auth",
            "login",
            "--provider",
            "example",
        ]
        assert set(answer["launch"]["environment"]) == {HOSTED_ROOT_VARIABLE, EXTERNAL_BIN_DIRECTORIES_VARIABLE}
        expected_directories = str(tmp_path) if node_bin is None else os.pathsep.join((str(node_bin), str(tmp_path)))
        assert answer["launch"]["environment"][EXTERNAL_BIN_DIRECTORIES_VARIABLE] == expected_directories
        assert answer["launch"]["environment"][HOSTED_ROOT_VARIABLE].startswith(str(tmp_path / "agent"))
        assert "must-not-cross" not in str(answer)


def test_signed_out_person_cannot_prepare_a_login(tmp_path: Path) -> None:
    service = AgentService(
        client=cast(InstalledServiceClient, SimpleNamespace(lease=None)),
        storage_root=tmp_path,
        agent_source=None,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    assert service.admin("sign_in", provider="example_cli", expected_revision="0" * 64) == {
        "kind": "refused",
        "code": "signed_out",
    }
