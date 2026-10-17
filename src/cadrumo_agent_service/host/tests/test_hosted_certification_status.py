"""Hosted certification status comes only from the current authenticated lane catalog."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service as service_module
from ...providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from ...service import AgentService
from ..controller import AgentGenerations, AgentHostController, AgentHostState, AgentReady

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Controller:
    def __init__(self, *, ready: AgentReady | None, state: AgentHostState = AgentHostState.READY) -> None:
        self.ready = ready
        self.state = state

    def published(self) -> AgentReady | None:
        return self.ready


def _ready() -> AgentReady:
    return AgentReady(
        generations=AgentGenerations("synthetic-session", "synthetic-settings"),
        gateway_port=12345,
        agent_version="synthetic-agent",
        hosting_contract=1,
    )


def _service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentService:
    client = SimpleNamespace(lease=object())
    service = AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
        agent_source=None,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    # This credential-only fact is deliberately insufficient to prove hosted readiness.
    credential_status = {
        "development": False,
        "providers": [{"mode": "provider_sign_in", "cli_state": "installed_signed_in"}],
    }
    monkeypatch.setattr(
        service._providers,
        "status",
        lambda: SimpleNamespace(model_dump=lambda *, mode: credential_status),
    )
    return service


@pytest.mark.parametrize("certification", ["pending", "proven"])
@pytest.mark.parametrize("execution_mode", ["example-cli", "claude-agent-acp:node"])
def test_status_projects_only_valid_certification_from_the_current_served_catalog(
    certification: str,
    execution_mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path, monkeypatch)
    controller = _Controller(ready=_ready())
    service._controller = cast(AgentHostController, controller)
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: {
            "api_version": "v1",
            "providers": [
                {
                    "provider_id": "example",
                    "transport": "cli",
                    "execution_mode": execution_mode,
                    "hosted_certification": certification,
                    "private_catalog_detail": "must-not-be-projected",
                }
            ],
        },
    )
    catalog = service.admin("catalog")
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: pytest.fail("status must use the recently served catalog snapshot"),
    )

    result = service.admin("status")

    assert catalog["api_version"] == "v1"
    assert result == {
        "development": False,
        "providers": [{"mode": "provider_sign_in", "cli_state": "installed_signed_in"}],
        "hosted_certifications": [
            {
                "provider": "example",
                "transport": "cli",
                "execution_mode": execution_mode,
                "status": certification,
            }
        ],
    }


def test_live_older_lane_defaults_to_unknown_without_inventing_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    service._controller = cast(AgentHostController, _Controller(ready=_ready()))
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: {
            "api_version": "v1",
            "providers": [{"provider_id": "example", "transport": "api", "execution_mode": "example-api"}],
        },
    )
    service.admin("catalog")
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: pytest.fail("status must use the recently served catalog snapshot"),
    )

    result = service.admin("status")

    assert result["hosted_certifications"] == [
        {"provider": "example", "transport": "api", "execution_mode": "example-api", "status": "unknown"}
    ]


def test_saved_provider_sign_in_status_does_not_create_hosted_certification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    service._controller = cast(AgentHostController, _Controller(ready=None, state=AgentHostState.DETACHED))
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: pytest.fail("an unready service must not request hosted certification"),
    )

    result = service.admin("status")

    assert result["providers"][0]["cli_state"] == "installed_signed_in"
    assert result["hosted_certifications"] == []


def test_ready_but_unobserved_catalog_does_not_add_http_to_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    service._controller = cast(AgentHostController, _Controller(ready=_ready()))
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: pytest.fail("status must not fetch an unobserved catalog"),
    )

    result = service.admin("status")

    assert result["hosted_certifications"] == []


def test_catalog_failure_keeps_the_credential_status_and_reports_no_certification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    service._controller = cast(AgentHostController, _Controller(ready=_ready()))
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: {
            "api_version": "v1",
            "providers": [
                {
                    "provider_id": "example",
                    "transport": "cli",
                    "execution_mode": "example-cli",
                    "hosted_certification": "proven",
                }
            ],
        },
    )
    service.admin("catalog")

    def unavailable(_ready: AgentReady) -> dict[str, Any]:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED)

    monkeypatch.setattr(service, "_served_catalog", unavailable)
    with pytest.raises(ProviderCatalogUnavailableError):
        service.admin("catalog")

    result = service.admin("status")

    assert result["providers"][0]["cli_state"] == "installed_signed_in"
    assert result["hosted_certifications"] == []


def test_live_certification_does_not_hide_provider_status_catalog_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    service._controller = cast(AgentHostController, _Controller(ready=_ready()))
    monkeypatch.setattr(
        service._providers,
        "status",
        lambda: SimpleNamespace(model_dump=lambda *, mode: {"code": "catalog_unavailable"}),
    )
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: {
            "api_version": "v1",
            "providers": [
                {
                    "provider_id": "example",
                    "transport": "cli",
                    "execution_mode": "example-cli",
                    "hosted_certification": "pending",
                }
            ],
        },
    )
    service.admin("catalog")
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: pytest.fail("status must use the recently served catalog snapshot"),
    )

    result = service.admin("status")

    assert result == {
        "code": "catalog_unavailable",
        "hosted_certifications": [
            {
                "provider": "example",
                "transport": "cli",
                "execution_mode": "example-cli",
                "status": "pending",
            }
        ],
    }


@pytest.mark.parametrize(
    "lanes",
    [
        [
            {
                "provider_id": "example",
                "transport": "cli",
                "execution_mode": "example-cli",
                "hosted_certification": "unverified",
            }
        ],
        [
            {"provider_id": "example", "transport": "cli", "execution_mode": "example-cli"},
            {"provider_id": "example", "transport": "cli", "execution_mode": "example-cli"},
        ],
        [{"provider_id": "example", "transport": "cli", "execution_mode": "example-cli"}] * 65,
        [{"provider_id": "example", "transport": "cli", "execution_mode": "a" * 513}],
        [{"provider_id": "example", "transport": "cli", "execution_mode": "invalid\x00mode"}],
    ],
)
def test_malformed_duplicate_or_oversized_hosted_catalog_fails_closed(
    lanes: list[dict[str, str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    service._controller = cast(AgentHostController, _Controller(ready=_ready()))
    monkeypatch.setattr(service, "_served_catalog", lambda _ready: {"api_version": "v1", "providers": lanes})
    service.admin("catalog")
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: pytest.fail("status must not re-fetch malformed or oversized catalog data"),
    )

    result = service.admin("status")

    assert result["providers"][0]["cli_state"] == "installed_signed_in"
    assert result["hosted_certifications"] == []


def test_catalog_generation_change_drops_the_projection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path, monkeypatch)
    controller = _Controller(ready=_ready())
    service._controller = cast(AgentHostController, controller)

    def change_generation(_ready: AgentReady) -> dict[str, Any]:
        controller.ready = None
        return {
            "api_version": "v1",
            "providers": [
                {
                    "provider_id": "example",
                    "transport": "cli",
                    "execution_mode": "example-cli",
                    "hosted_certification": "proven",
                }
            ],
        }

    monkeypatch.setattr(service, "_served_catalog", change_generation)
    service.admin("catalog")

    result = service.admin("status")

    assert result["hosted_certifications"] == []


def test_cached_certification_expires_without_a_network_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    service._controller = cast(AgentHostController, _Controller(ready=_ready()))
    clock = [100.0]
    monkeypatch.setattr(service_module, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: {
            "api_version": "v1",
            "providers": [
                {
                    "provider_id": "example",
                    "transport": "cli",
                    "execution_mode": "example-cli",
                    "hosted_certification": "pending",
                }
            ],
        },
    )
    service.admin("catalog")
    monkeypatch.setattr(
        service,
        "_served_catalog",
        lambda _ready: pytest.fail("expired status must not trigger a network refresh"),
    )

    clock[0] = 104.9
    fresh = service.admin("status")
    assert fresh["hosted_certifications"][0]["status"] == "pending"
    fresh["hosted_certifications"][0]["status"] = "proven"
    assert service.admin("status")["hosted_certifications"][0]["status"] == "pending"

    clock[0] = 105.0
    assert service.admin("status")["hosted_certifications"] == []
