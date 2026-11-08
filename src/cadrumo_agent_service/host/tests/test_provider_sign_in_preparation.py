"""Operator sign-in prepares only a fixed profile-bound command, never provider credentials."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, override
from uuid import uuid4

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_startup as service_module
from ...adapters.agent_programs import AgentImage
from ...adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from ...providers.application.contracts import (
    ProviderSettingsActionAccepted,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    ProviderStatusEntry,
)
from ...providers.application.tests.synthetic_catalog import synthetic_catalog
from ...service import AgentService
from ..auth_attempt import AuthAttempt
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
            "credential_saved": False,
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
    "outcome",
    (
        "prepared",
        "prepared_node",
        "revision_conflict",
        "revoked",
        "unsupported",
        "api_lane",
        "keyless_lane",
        "gui_keyless_lane",
        "gui_unsupported",
        "gui_method_unsupported",
    ),
)
def test_sign_in_preparation_preserves_authority_and_never_claims_login(
    outcome: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = SimpleNamespace(lease=SimpleNamespace(profile_id=uuid4()), connection=SimpleNamespace(close=lambda: None))
    service = AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
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
    monkeypatch.setattr(
        service._catalog, "sign_in_providers", lambda: () if outcome == "unsupported" else ("example", "local")
    )
    monkeypatch.setattr(
        service._catalog, "gui_sign_in_providers", lambda: () if outcome == "gui_unsupported" else ("example", "local")
    )
    monkeypatch.setattr(
        service._catalog,
        "gui_sign_in_methods",
        lambda: (
            {}
            if outcome == "gui_unsupported"
            else {
                "example": ("device",) if outcome == "gui_method_unsupported" else ("browser",),
                "local": ("browser",),
            }
        ),
    )
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
    # A keyless lane is refused by its kind alone, although its provider is listed as signing in.
    lane = {"api_lane": "example_api", "keyless_lane": "local_api", "gui_keyless_lane": "local_api"}.get(
        outcome, "example_cli"
    )
    answer = service.admin(
        "connect" if outcome.startswith("gui_") else "sign_in",
        provider=lane,
        expected_revision="0" * 64,
        method="browser",
    )
    if outcome in {
        "unsupported",
        "api_lane",
        "keyless_lane",
        "gui_keyless_lane",
        "gui_unsupported",
        "gui_method_unsupported",
    }:
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
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=None, connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    assert service.admin("sign_in", provider="example_cli", expected_revision="0" * 64) == {
        "kind": "refused",
        "code": "signed_out",
    }


def test_submit_code_rejects_stale_attempt_and_retired_owner(tmp_path: Path) -> None:
    service = AgentService(
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
        ),
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
    for attempt_id in (str(uuid4()), attempt.id):
        result = service.admin("connect_submit_code", attempt_id=attempt_id, secret=bytearray(b"synthetic-code"))
        assert result == {"kind": "refused", "code": "invalid_request"}


@pytest.mark.parametrize("code", list(ProviderSettingsRefusalCode))
def test_status_preserves_refusal_without_adding_success_metadata(
    code: ProviderSettingsRefusalCode, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = AgentService(
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(lease=SimpleNamespace(profile_id=uuid4()), connection=SimpleNamespace(close=lambda: None)),
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    monkeypatch.setattr(service._providers, "status", lambda: ProviderSettingsRefusal(code=code))

    assert service.admin("status") == {"code": code.value}


class _CountingProbe(AgentProviderAuthStatusProbe):
    """The real probe, counting how often its kept read is dropped."""

    forgotten = 0

    @override
    def forget(self) -> None:
        type(self).forgotten += 1
        super().forget()


def _service(tmp_path: Path, *, woken: list[str] | None = None) -> AgentService:
    client = SimpleNamespace(lease=SimpleNamespace(profile_id=uuid4()), connection=SimpleNamespace(close=lambda: None))
    return AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
        wake=(lambda: woken.append("woken")) if woken is not None else (lambda: None),
    )


def test_status_answer_serves_the_console_command_template_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(service._providers, "status", lambda: ProviderSettingsStatus(providers=(_entry(),)))
    monkeypatch.setattr(service._catalog, "gui_sign_in_methods", lambda: {})
    answer = service.admin("status")
    assert answer["console_sign_in_command"] == "aeat config provider-login --provider {provider}"
    assert "providers" in answer
    assert all("console_sign_in_command" not in provider for provider in answer["providers"])


def test_connect_asks_for_causes_confirms_status_and_forgets_reads_at_both_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    woken: list[str] = []
    service = _service(tmp_path, woken=woken)
    captured: dict[str, Any] = {}

    class _Attempt:
        id = "attempt"

        def __init__(self, **keywords: Any) -> None:
            captured.update(keywords)

        def observe(self) -> dict[str, str]:
            return {"event": "starting"}

    monkeypatch.setattr(service_module, "AuthAttempt", _Attempt)
    monkeypatch.setattr(service._catalog, "catalog", synthetic_catalog)
    monkeypatch.setattr(service._catalog, "gui_sign_in_methods", lambda: {"example": ("browser",)})
    monkeypatch.setattr(service._credentials, "current_generations", lambda **_k: object())
    image = AgentImage(tmp_path / "cadrumo-agent.exe", (), tmp_path / "agent")
    monkeypatch.setattr(
        service,
        "_prepare_sign_in",
        lambda *_a, **_k: {
            "kind": "sign_in_prepared",
            "entry": {"provider": "example"},
            "launch": {"executable": str(image.executable), "directory": str(image.directory), "environment": {}},
        },
    )
    service._login_status = _CountingProbe(context=lambda: None)
    service.admin("connect", provider="example_cli", expected_revision="0" * 64, method="browser")
    assert captured["arguments"][-3:] == ("--timeout", "300", "--causes")
    assert _CountingProbe.forgotten == 1
    captured["settled"]()
    assert _CountingProbe.forgotten == 2
    assert woken == ["woken"]
    assert callable(captured["confirm"])
