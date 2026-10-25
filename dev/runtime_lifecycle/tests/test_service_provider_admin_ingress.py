"""Provider administration begins only after the private service bearer is verified."""

from __future__ import annotations

import json
import socket
import struct
import sys
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest
from pydantic import JsonValue, TypeAdapter

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_agent_service.adapters.agent_programs import PACKAGE_AGENT_VARIABLE
from cadrumo_agent_service.admin import AdminAction, AdminServer
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import KEY_LANE, synthetic_document
from cadrumo_agent_service.providers.persistence.store import (
    MODEL_ROLE_SELECTIONS_CAPABILITY,
    MODEL_ROLE_SELECTIONS_KEY,
    SecureProviderSettingsStore,
)
from cadrumo_agent_service.service import AgentService
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime

from .provider_catalog_support import (
    model_role_selections_capability,
    provider_record_capability,
    stand_in_agent_image,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


class _AdminRecorder:
    """Record whether the real admin ingress dispatched an authenticated request."""

    def __init__(self) -> None:
        self.calls: list[tuple[AdminAction, dict[str, str | bytearray | None]]] = []

    def admin(
        self,
        action: AdminAction,
        *,
        provider: str | None = None,
        expected_revision: str | None = None,
        base_url: str | None = None,
        choice: Literal["direct_api", "provider_sign_in"] | None = None,
        method: Literal["browser", "device"] | None = None,
        attempt_id: str | None = None,
        role: str | None = None,
        model: str | None = None,
        secret: bytearray | None = None,
    ) -> dict[str, JsonValue]:
        values: dict[str, str | bytearray | None] = {
            "provider": provider,
            "expected_revision": expected_revision,
            "base_url": base_url,
            "choice": choice,
            "method": method,
            "attempt_id": attempt_id,
            "role": role,
            "model": model,
            "secret": secret,
        }
        self.calls.append((action, values))
        return {"kind": "served", "action": action}


def _frame(stream: socket.socket, payload: bytes) -> None:
    stream.sendall(struct.pack("!I", len(payload)) + payload)


def _exact(stream: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.recv(size - len(chunks))
        if not part:
            raise EOFError("service admin closed before its response frame")
        chunks.extend(part)
    return bytes(chunks)


def _exchange(
    port: int, bearer: bytes, request: dict[str, JsonValue], *, secret: bytes | None = None, unauthorized: bool = False
) -> dict[str, JsonValue]:
    encoded = json.dumps(request, separators=(",", ":")).encode("utf-8")
    with socket.create_connection(("127.0.0.1", port), timeout=5) as stream:
        stream.settimeout(5)
        _frame(stream, bearer)
        if not unauthorized:
            _frame(stream, encoded)
        if secret is not None:
            (size,) = struct.unpack("!I", _exact(stream, 4))
            assert _JSON_OBJECT.validate_json(_exact(stream, size), strict=True) == {
                "event": "secret_ready",
                "request_id": request["request_id"],
            }
            _frame(stream, secret)
        (size,) = struct.unpack("!I", _exact(stream, 4))
        response = _JSON_OBJECT.validate_json(_exact(stream, size), strict=True)
    return response


def _request(action: str) -> dict[str, JsonValue]:
    request: dict[str, JsonValue] = {"version": 1, "request_id": str(uuid4()), "action": action}
    if action in {"set", "remove", "reset", "auth"}:
        request.update({"provider": "synthetic-provider", "expected_revision": "0" * 64})
    if action == "set":
        request["secret_bytes"] = 24
    if action == "auth":
        request["choice"] = "provider_sign_in"
    return request


def _provider_request(action: str, revision: str = "0" * 64) -> dict[str, JsonValue]:
    request = _request(action)
    if action in {"set", "remove", "reset", "auth"}:
        request.update(provider=KEY_LANE, expected_revision=revision)
    if action == "set":
        request["secret_bytes"] = len(b"synthetic-provider-secret")
    if action == "auth":
        request["choice"] = "direct_api"
    return request


def _provider_entry(status: dict[str, JsonValue]) -> dict[str, JsonValue]:
    providers = status["providers"]
    assert isinstance(providers, list)
    rows: list[dict[str, JsonValue]] = []
    for row in providers:
        assert isinstance(row, dict)
        assert isinstance(row.get("id"), str)
        rows.append(row)
    return next(row for row in rows if row["id"] == KEY_LANE)


def _entry_revision(entry: dict[str, JsonValue]) -> str:
    revision = entry["revision"]
    assert isinstance(revision, str)
    return revision


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker custody")
@pytest.mark.usefixtures("authority_operation")
def test_actual_service_provider_actions_require_parent_authority_and_live_encrypted_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image, _record = stand_in_agent_image(tmp_path, catalog_document=synthetic_document())
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(image))
    admin = bytearray(b"synthetic-parent-admin-authority")
    gateway = bytearray(b"synthetic-hosted-agent-gateway-authority")
    with service_record_runtime(tmp_path, record_capabilities=(provider_record_capability(),)) as runtime:
        client = runtime.connect_service()
        service = AgentService(
            client=client,
            storage_root=runtime.root,
            gateway_bearer=gateway,
            emit=lambda _event: None,
        )
        server = AdminServer(service, bearer=admin)
        try:
            for action in ("status", "set", "remove", "reset", "auth"):
                for unauthorized in (b"wrong-admin-authority", bytes(gateway)):
                    assert _exchange(server.port, unauthorized, _provider_request(action), unauthorized=True) == {
                        "kind": "refused",
                        "code": "unauthenticated",
                    }
                answer = _exchange(
                    server.port,
                    bytes(admin),
                    _provider_request(action),
                    secret=b"synthetic-provider-secret" if action == "set" else None,
                )
                assert answer["result"] == {"kind": "refused", "code": "signed_out"}

            assert isinstance(runtime.admit(client), ServiceConnected)
            assert client.claim() is not None
            status = _exchange(server.port, bytes(admin), _provider_request("status"))["result"]
            assert isinstance(status, dict)
            initial = _provider_entry(status)
            available = initial["available"]
            assert isinstance(available, bool)
            assert initial["mode"] == "unset" and not available
            revision = _entry_revision(initial)
            for action, expected_mode in (("set", "key"), ("auth", "key"), ("remove", "disabled"), ("reset", "unset")):
                reply = _exchange(
                    server.port,
                    bytes(admin),
                    _provider_request(action, revision),
                    secret=b"synthetic-provider-secret" if action == "set" else None,
                )
                result = reply["result"]
                assert isinstance(result, dict) and "entry" in result, result
                entry = result["entry"]
                assert isinstance(entry, dict)
                assert entry["mode"] == expected_mode
                if action == "set":
                    assert entry["source"] == "profile" and entry["readiness"] == "not_verified"
                    stale = _exchange(server.port, bytes(admin), _provider_request("remove", revision))
                    assert stale["result"] == {"code": "revision_conflict"}
                revision = _entry_revision(entry)
                reread = _exchange(server.port, bytes(admin), _provider_request("status"))["result"]
                assert isinstance(reread, dict)
                assert _provider_entry(reread) == entry
                assert "synthetic-provider-secret" not in json.dumps(reread)
        finally:
            server.close()
            service.close()
            admin[:] = bytes(len(admin))


def _selection_request(action: str, revision: str, **fields: str) -> dict[str, JsonValue]:
    request = _request(action)
    request.update(expected_revision=revision, **fields)
    return request


def _selections(answer: dict[str, JsonValue]) -> dict[str, JsonValue]:
    result = answer["result"]
    assert isinstance(result, dict) and result.get("unreadable") is False, result
    return result


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker custody")
@pytest.mark.usefixtures("authority_operation")
def test_a_role_selection_lives_in_its_own_capability_and_never_moves_the_provider_settings_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The agent tree is bound to the provider-settings generation, so a model choice must leave it as it is."""
    image, _record = stand_in_agent_image(tmp_path, catalog_document=synthetic_document())
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(image))
    admin = bytearray(b"synthetic-parent-admin-authority")
    capabilities = (provider_record_capability(), model_role_selections_capability())
    with service_record_runtime(tmp_path, record_capabilities=capabilities) as runtime:
        client = runtime.connect_service()
        service = AgentService(
            client=client,
            storage_root=runtime.root,
            gateway_bearer=bytearray(b"synthetic-gateway"),
            emit=lambda _: None,
        )
        server = AdminServer(service, bearer=admin)
        provider_records = SecureProviderSettingsStore(client=client)
        try:
            assert isinstance(runtime.admit(client), ServiceConnected)
            assert client.claim() is not None

            def provider_generation() -> str:
                provider_records.invalidate_generations()
                observed = provider_records.observe_generations()
                assert observed is not None
                return observed.provider_settings

            before = provider_generation()
            initial = _selections(_exchange(server.port, bytes(admin), _request("model_roles")))
            assert initial["revision"] == ABSENT_SECURE_OBJECT_REVISION_ID
            selected = _selections(
                _exchange(
                    server.port,
                    bytes(admin),
                    _selection_request(
                        "model_role_set",
                        ABSENT_SECURE_OBJECT_REVISION_ID,
                        role="text_extraction",
                        provider=KEY_LANE,
                        model="synthetic-text-1",
                    ),
                )
            )
            revision = selected["revision"]
            assert isinstance(revision, str) and revision != ABSENT_SECURE_OBJECT_REVISION_ID
            roles = selected["roles"]
            assert isinstance(roles, list)
            assert {"role": "text_extraction", "lane": KEY_LANE, "model": "synthetic-text-1"} in roles
            assert _selections(_exchange(server.port, bytes(admin), _request("model_roles"))) == selected
            assert provider_generation() == before

            cleared = _selections(
                _exchange(server.port, bytes(admin), _selection_request("model_roles_reset", revision))
            )
            assert cleared["revision"] == ABSENT_SECURE_OBJECT_REVISION_ID
            assert provider_generation() == before

            # The observation does see a provider-record change, so the equalities above are not vacuous.
            stored = _exchange(
                server.port,
                bytes(admin),
                _provider_request("set", ABSENT_SECURE_OBJECT_REVISION_ID),
                secret=b"synthetic-provider-secret",
            )
            assert isinstance(stored["result"], dict) and "entry" in stored["result"], stored
            assert provider_generation() != before
        finally:
            server.close()
            service.close()
            admin[:] = bytes(len(admin))


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker custody")
@pytest.mark.usefixtures("authority_operation")
def test_an_unreadable_selections_record_reports_its_guard_and_a_guarded_reset_clears_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record that does not validate is never read as no selection, and its reset is always reachable."""
    image, _record = stand_in_agent_image(tmp_path, catalog_document=synthetic_document())
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(image))
    admin = bytearray(b"synthetic-parent-admin-authority")
    capabilities = (provider_record_capability(), model_role_selections_capability())
    with service_record_runtime(tmp_path, record_capabilities=capabilities) as runtime:
        client = runtime.connect_service()
        service = AgentService(
            client=client,
            storage_root=runtime.root,
            gateway_bearer=bytearray(b"synthetic-gateway"),
            emit=lambda _: None,
        )
        server = AdminServer(service, bearer=admin)
        try:
            assert isinstance(runtime.admit(client), ServiceConnected)
            assert client.claim() is not None
            written = client.record_write(
                MODEL_ROLE_SELECTIONS_CAPABILITY,
                MODEL_ROLE_SELECTIONS_KEY,
                payload=bytearray(b'{"schema_version":99}'),
                expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
            )
            assert written.state == "written"

            unreadable = _exchange(server.port, bytes(admin), _request("model_roles"))["result"]
            assert isinstance(unreadable, dict)
            assert unreadable["unreadable"] is True and unreadable["roles"] == []
            assert unreadable["revision"] == written.revision
            refused = _exchange(
                server.port,
                bytes(admin),
                _selection_request(
                    "model_role_set", written.revision, role="text_extraction", provider=KEY_LANE, model="m-1"
                ),
            )
            assert refused["result"] == {"code": "unknown"}

            reset = _selections(
                _exchange(server.port, bytes(admin), _selection_request("model_roles_reset", written.revision))
            )
            assert reset["revision"] == ABSENT_SECURE_OBJECT_REVISION_ID
            roles = reset["roles"]
            assert isinstance(roles, list) and all(isinstance(role, dict) and role["lane"] is None for role in roles)
        finally:
            server.close()
            service.close()
            admin[:] = bytes(len(admin))


@pytest.mark.parametrize("action", ["status", "set", "remove", "reset", "auth"])
def test_provider_admin_rejects_every_action_before_metadata_or_secret_dispatch(action: str) -> None:
    service = _AdminRecorder()
    bearer = bytearray(b"synthetic-private-service-bearer")
    server = AdminServer(service, bearer=bearer)
    try:
        host, port = server._socket.getsockname()
        assert host == "127.0.0.1"
        answer = _exchange(port, b"wrong-private-service-bearer", _request(action), unauthorized=True)

        assert answer == {"kind": "refused", "code": "unauthenticated"}
        assert service.calls == []

        request = _request("status")
        accepted = _exchange(port, bytes(bearer), request)
        assert accepted == {
            "version": 1,
            "request_id": request["request_id"],
            "result": {"kind": "served", "action": "status"},
        }
        assert [action for action, _values in service.calls] == ["status"]
    finally:
        server.close()
        bearer[:] = bytes(len(bearer))
