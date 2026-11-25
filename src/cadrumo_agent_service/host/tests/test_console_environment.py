"""The ``console_environment`` read names the signed-in profile's provider homes and agent workspace, nothing else.

The provider homes stand in for the installed agent's derivation, which the
agent checkout test exercises; everything else is the service's real read
through its administration entry, on a synthetic profile under a temporary root.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_console_environment as console_module
from ...adapters.agent_programs import profile_agent_root, profile_agent_workspace
from ...providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from ...providers.domain.record import LocalEngine
from ...service import AgentService
from ...service_console_environment import no_profile_answer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SYNTHETIC_CREDENTIAL = "sk-synthetic-console-credential-0123456789abcdef"
"""A credential-like string a provider home holds; no answer may carry it."""


def _lease(profile_id: UUID) -> ServiceLease:
    return ServiceLease(
        lease_id=uuid4(),
        session_id=UUID(int=2),
        profile_id=profile_id,
        parent_session_id=UUID(int=4),
        descriptor_digest="2" * 64,
        service_id="cadrumo-agent-service",
        runtime_boot_id=UUID(int=5),
        connection_id=UUID(int=6),
    )


def _service(root: Path, lease: ServiceLease | None) -> AgentService:
    return AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(lease=lease, connection=SimpleNamespace(close=lambda: None)),
        ),
        storage_root=root,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )


def _homes(agent_root: Path) -> dict[str, str]:
    """Homes beneath the agent root, each holding a credential file as a provider sign-in leaves one."""
    homes = {"CLAUDE_CONFIG_DIR": agent_root / "providers" / "claude", "CODEX_HOME": agent_root / "providers" / "codex"}
    for home in homes.values():
        home.mkdir(parents=True, exist_ok=True)
        (home / "credentials.json").write_text(json.dumps({"token": _SYNTHETIC_CREDENTIAL}), encoding="utf-8")
    return {name: str(home) for name, home in homes.items()}


@pytest.fixture(autouse=True)
def _agent_homes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(console_module, "console_provider_homes", _homes)


def test_the_answer_names_the_profiles_homes_and_agent_workspace(tmp_path: Path) -> None:
    profile = uuid4()

    answer = _service(tmp_path, _lease(profile)).admin("console_environment")

    assert set(answer) == {"kind", "environment", "working_directory", "revision"}
    assert answer["kind"] == "console_environment"
    agent_root = profile_agent_root(tmp_path, profile)
    assert answer["environment"] == _homes(agent_root)
    workspace = Path(answer["working_directory"])
    assert workspace == profile_agent_workspace(agent_root)
    assert workspace.is_dir()
    buckets = tmp_path / storage_location(StorageCategory.BUCKETS).subpath
    assert not workspace.is_relative_to(buckets)
    assert len(answer["revision"]) == 64
    assert int(answer["revision"], 16) >= 0


def test_no_answer_carries_a_refused_name_or_a_credential(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", _SYNTHETIC_CREDENTIAL)

    def named(agent_root: Path) -> dict[str, str]:
        return {
            **_homes(agent_root),
            "CADRUMO_STORAGE_ROOT": str(tmp_path),
            "cadrumo_agent_port": "1",
            "PYTHONPATH": str(tmp_path),
            "AEAT_CERTIFICATE": "x",
            "FINANCIAL_SOURCE": "x",
            "NOT=A NAME": "x",
        }

    monkeypatch.setattr(console_module, "console_provider_homes", named)

    answer = _service(tmp_path, _lease(uuid4())).admin("console_environment")

    assert set(answer["environment"]) == {"CLAUDE_CONFIG_DIR", "CODEX_HOME"}
    assert _SYNTHETIC_CREDENTIAL not in json.dumps(answer)


def test_the_revision_follows_the_profile(tmp_path: Path) -> None:
    first, second = uuid4(), uuid4()

    one = _service(tmp_path, _lease(first)).admin("console_environment")
    again = _service(tmp_path, _lease(first)).admin("console_environment")
    other = _service(tmp_path, _lease(second)).admin("console_environment")

    assert one == again
    assert other["revision"] != one["revision"]
    assert other["working_directory"] != one["working_directory"]
    assert set(other["environment"].values()).isdisjoint(one["environment"].values())


def test_no_profile_names_nothing_under_its_own_revision(tmp_path: Path) -> None:
    signed_in = _service(tmp_path, _lease(uuid4())).admin("console_environment")

    answer = _service(tmp_path, None).admin("console_environment")

    assert answer == {
        "kind": "console_environment",
        "environment": {},
        "working_directory": None,
        "revision": no_profile_answer()["revision"],
    }
    assert answer["revision"] != signed_in["revision"]


def test_after_sign_out_nothing_of_the_previous_profile_remains(tmp_path: Path) -> None:
    service = _service(tmp_path, _lease(uuid4()))
    before = service.admin("console_environment")
    previous = [*before["environment"].values(), before["working_directory"], before["revision"]]

    service.client.lease = None
    after = json.dumps(service.admin("console_environment"))

    assert previous
    for value in previous:
        assert json.dumps(value)[1:-1] not in after


def test_a_lease_that_changes_during_the_read_is_answered_as_no_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, _lease(uuid4()))
    replacement = _lease(uuid4())

    def switching(agent_root: Path) -> dict[str, str]:
        service.client.lease = replacement
        return _homes(agent_root)

    monkeypatch.setattr(console_module, "console_provider_homes", switching)

    answer: dict[str, Any] = service.admin("console_environment")

    assert answer == no_profile_answer()


def test_an_agent_that_cannot_name_its_homes_is_refused_and_a_closing_service_answers_stopping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(_agent_root: Path) -> dict[str, str]:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND)

    monkeypatch.setattr(console_module, "console_provider_homes", missing)
    service = _service(tmp_path, _lease(uuid4()))
    assert service.admin("console_environment") == {"kind": "refused", "code": "console_environment_unavailable"}

    service._closing.set()
    assert service.admin("console_environment") == {"kind": "refused", "code": "service_stopping"}
