"""Focused lifecycle and wire-contract tests for the shared service fixture."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from queue import Queue
from threading import Event
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

import dev.runtime_lifecycle.agent_service_session as session_module
from cadrumo_agent_service.admin import AdminAction, AdminServer
from cadrumo_client.contracts.service_access import ServiceConnected, ServiceLease
from dev.runtime_lifecycle.caller_owned_root import Programs
from dev.runtime_lifecycle.proof_support import Profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("contract", [1, "1", True, 2])
def test_ready_event_uses_the_services_integer_hosting_contract(contract: object) -> None:
    event = {
        "event": "agent_ready",
        "gateway_port": 45678,
        "agent_version": "0.1.0",
        "hosting_contract": contract,
        "workspace_root": "synthetic-workspace",
    }
    if type(contract) is int and contract == 1:
        session_module._validate_agent_event(event)
    else:
        with pytest.raises(session_module.AcceptanceError, match="hosting contract"):
            session_module._validate_agent_event(event)


def test_service_shutdown_drains_pending_events_before_the_stop_acknowledgement() -> None:
    process = object.__new__(session_module._PackagedServiceProcess)
    process._closed = False
    process._stdin = BytesIO()
    process._stdout = process._stderr = None
    process._stdout_thread = process._stderr_thread = None
    process._reader_stop = Event()
    process._scope = None
    process._bearer = bytearray(b"test-admin-authority")
    process._process = SimpleNamespace(wait=lambda **_kwargs: 0)
    process._events = Queue()
    process._events.put(b'{"event":"refused","code":"agent_service_failed"}\n')
    process._events.put(b'{"event":"stopped"}\n')

    process.close()

    assert process._closed
    assert process._events.empty()
    assert not any(process._bearer)


_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_BOOT_ID = UUID("22222222-2222-4222-8222-222222222222")
_SESSION_ID = UUID("33333333-3333-4333-8333-333333333333")
_HOLDER_CONNECTION_ID = UUID("44444444-4444-4444-8444-444444444444")
_SERVICE_CONNECTION_ID = UUID("55555555-5555-4555-8555-555555555555")
_SERVICE_SESSION_ID = UUID("66666666-6666-4666-8666-666666666666")
_LEASE_ID = UUID("77777777-7777-4777-8777-777777777777")


class _Runtime:
    def __init__(self, steps: list[str], *, fail_ready: bool = False) -> None:
        self.steps = steps
        self.fail_ready = fail_ready

    def ready(self) -> dict[str, str]:
        self.steps.append("runtime.ready")
        if self.fail_ready:
            raise session_module.AcceptanceError("controlled runtime readiness failure")
        return {"kind": "runtime_ready", "product_version": "test-version"}

    def stop(self) -> int:
        self.steps.append("runtime.stop")
        return 64


class _Holder:
    def __init__(self, steps: list[str], **values: Any) -> None:
        self.steps = steps
        self.profile_id = values["profile_id"]
        self.identity = {
            "kind": "session_held",
            "profile_id": str(self.profile_id),
            "session_id": str(_SESSION_ID),
            "runtime_boot_id": str(_BOOT_ID),
            "connection_id": str(_HOLDER_CONNECTION_ID),
        }
        self.closed = False
        supplied_password = values["password"]
        assert supplied_password == bytearray(b"test-profile-password")
        supplied_password[:] = bytes(len(supplied_password))
        assert supplied_password == bytearray(len(supplied_password))
        self.steps.append("holder.start")

    def command(self, action: str, **fields: Any) -> dict[str, Any]:
        self.steps.append(f"holder.{action}")
        if action == "close":
            return {"kind": "session_closed"}
        assert action == "service_admission"
        assert fields == {
            "recipient_connection_id": str(_SERVICE_CONNECTION_ID),
            "service_id": "cadrumo-agent-service",
        }
        lease = ServiceLease(
            lease_id=_LEASE_ID,
            session_id=_SERVICE_SESSION_ID,
            profile_id=_PROFILE_ID,
            parent_session_id=_SESSION_ID,
            descriptor_digest="a" * 64,
            service_id="cadrumo-agent-service",
            runtime_boot_id=_BOOT_ID,
            connection_id=_SERVICE_CONNECTION_ID,
        )
        connected = ServiceConnected(
            request_id=uuid4(),
            runtime_boot_id=_BOOT_ID,
            connection_id=_HOLDER_CONNECTION_ID,
            profile_id=_PROFILE_ID,
            service_id="cadrumo-agent-service",
            lease=lease,
        )
        return connected.model_dump(mode="json")

    def close(self) -> None:
        self.steps.append("holder.close")
        self.closed = True


class _Service:
    def __init__(self, steps: list[str], *, fail_agent_event: bool = False, **_values: Any) -> None:
        self.steps = steps
        self.events = 0
        self.fail_agent_event = fail_agent_event
        self.stderr_machine_codes = ("native_launch_profile:launch_value_missing",)
        self.steps.append("service.start")

    def event(self) -> dict[str, Any]:
        self.events += 1
        self.steps.append(f"service.event.{self.events}")
        if self.events == 1:
            return {
                "event": "service_ready",
                "protocol": 1,
                "admin_port": 45678,
                "runtime_boot_id": str(_BOOT_ID),
                "connection_id": str(_SERVICE_CONNECTION_ID),
                "profile_id": str(_PROFILE_ID),
                "service_id": "cadrumo-agent-service",
            }
        if self.fail_agent_event:
            raise session_module.AcceptanceError("controlled event failure")
        return {"event": "refused", "code": "agent_provider_credential_missing"}

    def admin(self, port: int, action: str) -> dict[str, Any]:
        self.steps.append(f"service.admin.{action}")
        assert port == 45678
        return {"kind": action, "rows": []}

    def close(self) -> None:
        self.steps.append("service.close")

    def settle_refusal_diagnostics(self) -> None:
        self.steps.append("service.diagnostics")


def _install_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    fail_runtime: bool = False,
    fail_agent_event: bool = False,
    login_persisted: bool = False,
) -> list[str]:
    steps: list[str] = []
    package = tmp_path / "package"
    (package / "bin").mkdir(parents=True)
    (package / "bin" / "cadrumo-agent-service.exe").touch()
    programs = Programs(
        package / "bin" / "aeat.exe", package / "bin" / "cadrumo-runtime.exe", package / "bin" / "cadrumo-mcp.exe"
    )
    profile = Profile("session-profile", "test-profile-password", _PROFILE_ID)

    monkeypatch.setattr(session_module.Programs, "of", classmethod(lambda _cls, _package: programs))
    monkeypatch.setattr(session_module, "mark_development_root", lambda _root: steps.append("root.mark"))
    monkeypatch.setattr(
        session_module,
        "consumer_environment",
        lambda root, secrets: {"CADRUMO_LOCAL_STORAGE_ROOT": str(root), "CADRUMO_SECRET_STORE_DIR": str(secrets)},
    )
    monkeypatch.setattr(session_module, "create_profile", lambda *_args: steps.append("profile.create") or profile)
    monkeypatch.setattr(
        session_module, "login_profile", lambda *_args: steps.append("profile.login") or login_persisted
    )
    monkeypatch.setattr(session_module, "identify_profile", lambda *_args: steps.append("profile.identify") or profile)
    monkeypatch.setattr(session_module, "state_taxpayer", lambda *_args: steps.append("profile.setup"))

    @contextmanager
    def fake_runtime(*_args: Any) -> Generator[_Runtime]:
        steps.append("runtime.start")
        try:
            yield _Runtime(steps, fail_ready=fail_runtime)
        finally:
            steps.append("runtime.exit")

    class FakeHolder(_Holder):
        def __init__(self, *_args: Any, **values: Any) -> None:
            super().__init__(steps, **values)

    class FakeService(_Service):
        def __init__(self, *_args: Any, **values: Any) -> None:
            super().__init__(steps, fail_agent_event=fail_agent_event, **values)

    monkeypatch.setattr(session_module, "caller_owned_runtime", fake_runtime)
    monkeypatch.setattr(session_module, "WindowsRuntimeSessionHolder", FakeHolder)
    monkeypatch.setattr(session_module, "_PackagedServiceProcess", FakeService)
    monkeypatch.setattr(session_module, "run_cli", lambda *args, **kwargs: (0, {"status": "success"}))
    return steps


def test_shared_session_starts_runtime_first_and_reuses_one_profile_holder_and_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    steps = _install_lifecycle(monkeypatch, tmp_path)
    package = tmp_path / "package"
    scratch = tmp_path / "owned-run"

    with session_module.agent_service_session(package, scratch) as shared:
        assert shared.runtime_ready["kind"] == "runtime_ready"
        assert shared.service_ready["connection_id"] == str(_SERVICE_CONNECTION_ID)
        assert shared.holder_identity["connection_id"] == str(_HOLDER_CONNECTION_ID)
        assert shared.admission["lease"]["connection_id"] == str(_SERVICE_CONNECTION_ID)
        assert shared.agent_event == {"event": "refused", "code": "agent_provider_credential_missing"}
        assert shared.first_refusal_code == "agent_provider_credential_missing"
        assert shared.native_refusal_codes == ("native_launch_profile:launch_value_missing",)
        assert shared.login_session_persisted is False
        assert shared.environment["CADRUMO_LOG_STDERR_LEVEL"] == "WARNING"
        assert shared.setup_counts == {
            "runtime_start": 1,
            "profile_create": 1,
            "profile_setup": 1,
            "profile_login": 1,
            "holder_start": 1,
            "service_start": 1,
            "service_admission": 1,
        }
        assert set(shared.timings) == {
            "runtime_ready",
            "profile_setup_and_login",
            "holder_start",
            "service_ready",
            "service_admission_and_agent_event",
            "setup_total",
        }
        assert shared.catalog() == {"kind": "catalog", "rows": []}
        assert shared.status() == {"kind": "status", "rows": []}

        calls: list[tuple[tuple[str, ...], Mapping[str, str], Mapping[str, str] | None]] = []

        def cli(
            _programs: Programs,
            environment: Mapping[str, str],
            *arguments: str,
            secret: Mapping[str, str] | None,
        ) -> tuple[int, dict[str, Any]]:
            calls.append((arguments, environment, secret))
            return 0, {"status": "success"}

        monkeypatch.setattr(session_module, "run_cli", cli)
        assert shared.cli_read("app", "ledger", "list", reveal_identifiers=True) == (0, {"status": "success"})
        arguments, environment, secret = calls[0]
        assert arguments[0] == "--profile-secrets-stdin"
        assert environment["CADRUMO_CLI_REVEAL_IDENTIFIERS"] == "true"
        assert secret == {"profile_passphrase": "test-profile-password"}

        shared.cli_read("app", "ledger", "list", reveal_identifiers=False)
        assert calls[1][0][0] == "--profile-secrets-stdin"
        assert "CADRUMO_CLI_REVEAL_IDENTIFIERS" not in calls[1][1]

    assert steps.index("runtime.ready") < steps.index("profile.create")
    assert steps.index("profile.create") < steps.index("profile.login") < steps.index("holder.start")
    assert steps.index("service.start") < steps.index("holder.service_admission") < steps.index("service.event.2")
    assert steps.index("service.close") < steps.index("holder.close") < steps.index("runtime.exit")


def test_failure_after_service_start_closes_service_holder_and_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    steps = _install_lifecycle(monkeypatch, tmp_path, fail_agent_event=True)

    with (
        pytest.raises(session_module.AcceptanceError, match="controlled event failure"),
        session_module.agent_service_session(tmp_path / "package", tmp_path / "owned-run"),
    ):
        pytest.fail("fixture yielded before the service event was validated")

    assert steps.index("service.close") < steps.index("holder.close") < steps.index("runtime.exit")
    assert steps[-1] == "runtime.exit"


def test_persisted_sign_in_is_logged_out_after_service_and_holder_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    steps = _install_lifecycle(monkeypatch, tmp_path, fail_agent_event=True, login_persisted=True)

    def logout_cli(
        _programs: Programs,
        _environment: Mapping[str, str],
        *arguments: str,
        secret: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        assert arguments == ("config", "logout")
        assert secret is None
        steps.append("profile.logout")
        return 0, {"status": "success"}

    monkeypatch.setattr(session_module, "run_cli", logout_cli)

    with (
        pytest.raises(session_module.AcceptanceError, match="controlled event failure"),
        session_module.agent_service_session(tmp_path / "package", tmp_path / "owned-run"),
    ):
        pytest.fail("fixture yielded before the service event was validated")

    assert steps.index("service.close") < steps.index("holder.close") < steps.index("profile.logout")
    assert steps.index("profile.logout") < steps.index("runtime.stop") < steps.index("runtime.exit")


def test_runtime_readiness_failure_does_not_create_profile_or_holder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    steps = _install_lifecycle(monkeypatch, tmp_path, fail_runtime=True)

    with (
        pytest.raises(session_module.AcceptanceError, match="controlled runtime readiness failure"),
        session_module.agent_service_session(tmp_path / "package", tmp_path / "owned-run"),
    ):
        pytest.fail("fixture yielded without runtime readiness")

    assert "profile.create" not in steps
    assert "holder.start" not in steps
    assert steps[-1] == "runtime.exit"


def test_admin_uses_the_actual_typed_service_request_and_bounded_wire(tmp_path: Path) -> None:
    class AdminTarget:
        def admin(self, action: AdminAction, **_fields: object) -> dict[str, Any]:
            return {"kind": action, "providers": []}

    bearer = bytearray(b"synthetic-test-admin-authority")
    server = AdminServer(AdminTarget(), bearer=bearer)
    process = object.__new__(session_module._PackagedServiceProcess)
    process._bearer = bearer
    try:
        result = process.admin(server.port, "status")
        assert result == {"kind": "status", "providers": []}
        with pytest.raises(session_module.AcceptanceError, match="permits catalog and status"):
            process.admin(server.port, "set")
    finally:
        server.close()
        bearer[:] = bytes(len(bearer))


def test_service_lease_mismatch_is_rejected_before_exposing_session() -> None:
    holder = object.__new__(session_module.WindowsRuntimeSessionHolder)
    holder.identity = {
        "runtime_boot_id": str(_BOOT_ID),
        "session_id": str(_SESSION_ID),
    }

    lease = ServiceLease(
        lease_id=_LEASE_ID,
        session_id=_SERVICE_SESSION_ID,
        profile_id=_PROFILE_ID,
        parent_session_id=_SESSION_ID,
        descriptor_digest="a" * 64,
        service_id="cadrumo-agent-service",
        runtime_boot_id=_BOOT_ID,
        connection_id=UUID("88888888-8888-4888-8888-888888888888"),
    )
    reply = ServiceConnected(
        request_id=uuid4(),
        runtime_boot_id=_BOOT_ID,
        connection_id=_HOLDER_CONNECTION_ID,
        profile_id=_PROFILE_ID,
        service_id="cadrumo-agent-service",
        lease=lease,
    ).model_dump(mode="json")

    with pytest.raises(session_module.AcceptanceError, match="service lease connection differs"):
        session_module._validate_service_lease(
            reply,
            holder,
            {"connection_id": str(_SERVICE_CONNECTION_ID)},
            Profile("session-profile", "test-profile-password", _PROFILE_ID),
        )


def test_service_stderr_retains_only_bounded_native_machine_codes() -> None:
    process = object.__new__(session_module._PackagedServiceProcess)
    process._stderr = BytesIO(
        b"private-prefix password=password-value: agent launch refused by the native host exit=125 "
        b'native_refusal=launch_value_malformed subject=PACKAGE_SLOT | {"token":"bearer-value"} private-suffix\n'
        b"private-prefix: agent startup refused reason=credentials_unavailable "
        b"agent_code=provider_unsupported password=password-value bearer=bearer-value\n"
        b"private-prefix: agent startup refused reason=agent_refused agent_code=NOT_A_MACHINE_CODE "
        b"private-suffix\n"
        b"private-prefix: agent startup refused reason=private_payload agent_code=safe_machine_code private-suffix\n"
        b"private-prefix: agent stores not brought to current step=version outcome=timed_out "
        b"failed_stage=private-stage-token private-suffix\n"
        b"private-prefix: agent stores not brought to current step=private_step outcome=timed_out "
        b"failed_stage=private-stage-token private-suffix\n"
        b"2026 [ERROR] native_refusal=unrecognized subject=private-value\n"
        + b"x" * 5000
        + b"agent launch refused by the native host exit=125 native_refusal=launch_value_missing subject=SLOT\n"
    )
    process._stderr_machine_codes = []
    process._stderr_machine_codes_lock = session_module.Lock()
    process._stderr_diagnostics_ready = Event()

    process._drain_stderr()

    assert process.stderr_machine_codes == (
        "native_launch_profile:launch_value_malformed",
        "agent_host_reason:credentials_unavailable",
        "agent_host_code:provider_unsupported",
        "agent_host_reason:agent_refused",
        "agent_store_step:version",
        "agent_store_outcome:timed_out",
    )
    assert "password-value" not in repr(process.stderr_machine_codes)
    assert "bearer-value" not in repr(process.stderr_machine_codes)
    assert "private-prefix" not in repr(process.stderr_machine_codes)
    assert "private-suffix" not in repr(process.stderr_machine_codes)
    assert "private_payload" not in repr(process.stderr_machine_codes)
    assert "private-stage-token" not in repr(process.stderr_machine_codes)


@pytest.mark.parametrize("persisted", [True, False], ids=["stored-sign-in", "profile-input"])
def test_cli_read_uses_exactly_one_authority_for_person_owned_read(
    monkeypatch: pytest.MonkeyPatch, persisted: bool
) -> None:
    session = object.__new__(session_module.AgentServiceSession)
    session.programs = Programs(Path("aeat"), Path("runtime"), Path("mcp"))
    session.environment = {"CADRUMO_LOCAL_STORAGE_ROOT": "synthetic-root"}
    session.profile = Profile("session-profile", "test-profile-password", _PROFILE_ID)
    session.login_session_persisted = persisted
    calls: list[tuple[tuple[str, ...], Mapping[str, str], Mapping[str, str] | None]] = []

    def cli(
        _programs: Programs,
        environment: Mapping[str, str],
        *arguments: str,
        secret: Mapping[str, str] | None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append((arguments, environment, secret))
        return 1, {"status": "refused", "code": "sign_in_required"}

    monkeypatch.setattr(session_module, "run_cli", cli)
    result = session.cli_read("app", "ledger", "list", reveal_identifiers=True)

    assert result == (1, {"status": "refused", "code": "sign_in_required"})
    assert len(calls) == 1
    arguments, environment, secret = calls[0]
    assert ("--profile-secrets-stdin" in arguments) is (not persisted)
    assert secret == ({"profile_passphrase": "test-profile-password"} if not persisted else None)
    assert environment["CADRUMO_CLI_REVEAL_IDENTIFIERS"] == "true"
