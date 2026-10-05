"""CLI login admission preserves exact profile selection and protected proof ownership."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import typer
from typer.core import TyperCommand

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt_store
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import RECEIPT_LOGIN_ID, committed_sign_in
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    dev_test_database_password,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.profile_access import RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.login_session import (
    ProfileHumanLoginReceipt,
    ProfileReceiptRefusedError,
    authenticate_profile_candidate,
)
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
from cadrumo.application.user_profile.profile_pointer import (
    ActiveProfilePointerTransactionError,
    active_profile_pointer_transaction,
    observe_active_profile_pointer,
)
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.cli.config.custody import _login_through_the_prompt
from cadrumo.entrypoints.cli.config.secure_input import MachineSecretChannel, MachineSecretSelection
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest import MonkeyPatch

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSWORD = "runtime-login-test-passphrase"  # noqa: S105 - synthetic test input


def _receipt(*, resumed: bool = False, persisted: bool = True) -> ProfileHumanLoginReceipt:
    opened = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    return ProfileHumanLoginReceipt(
        authenticated_at=opened,
        idle_deadline=opened + timedelta(minutes=15),
        absolute_deadline=opened + timedelta(hours=4),
        session_persisted=persisted,
        resumed=resumed,
    )


class _RuntimeClient:
    """Only the four CLI admission calls, with an exact typed runtime reply."""

    def __init__(self, profile_id: UUID, *, receipt: ProfileHumanLoginReceipt | None = None) -> None:
        self.profile_id = profile_id
        self.session_id = uuid4()
        self.receipt = receipt or _receipt()
        self.resume_refusal = True
        self.on_status: Callable[[], None] | None = None
        self.calls: list[str] = []
        self.password_bytes: bytes | None = None
        self.password_buffer: bytearray | None = None
        self.persist_receipt: bool | None = None
        self.closed = 0
        self.refusal_code: str | None = None

    def _reply(self, *, human_login: ProfileHumanLoginReceipt | None) -> RuntimeProfileStatus:
        return RuntimeProfileStatus(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            human_login=human_login,
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=self.receipt.absolute_deadline,
                grant_state=None,
                grant_expires_at=None,
                grant_valid=False,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.NOT_REQUIRED,
                published_authority=Availability.AVAILABLE,
                provider=Availability.NOT_REQUIRED,
                effective_scope=AccessScope(
                    operations=frozenset(),
                    actions=frozenset(),
                    disclosures=frozenset(),
                    periods=frozenset(),
                    allow_period_independent=False,
                    allow_delegation=False,
                ),
                denial=None,
            ),
        )

    def resume_receipt(self) -> RuntimeProfileStatus:
        self.calls.append("resume")
        if self.resume_refusal:
            raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT)
        return self._reply(human_login=self.receipt)

    def login_password(self, proof: bytearray, *, persist_receipt: bool) -> RuntimeProfileStatus:
        self.calls.append("password")
        self.password_bytes = bytes(proof)
        self.password_buffer = proof
        self.persist_receipt = persist_receipt
        if self.refusal_code is not None:
            raise RuntimeFrontendRefusedError(self.refusal_code)
        return self._reply(human_login=self.receipt)

    def status(self) -> RuntimeProfileStatus:
        self.calls.append("status")
        if self.on_status is not None:
            self.on_status()
        return self._reply(human_login=None)

    def close(self) -> None:
        self.calls.append("close")
        self.closed += 1


class _KeyringError(Exception):
    """Synthetic native-store error type for a protected receipt fixture."""


class _Keyring:
    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.entries.pop((service_name, username), None)


def _install_client(monkeypatch: MonkeyPatch, client: _RuntimeClient) -> None:
    async def _open(*, profile_id: UUID, frontend: OperationFrontendProjection) -> _RuntimeClient:
        assert profile_id == client.profile_id
        assert frontend is OperationFrontendProjection.CLI
        return client

    monkeypatch.setattr("cadrumo.adapters.local_runtime.runtime_client.open_installed_runtime_client", _open)


def _ctx() -> typer.Context:
    return typer.Context(TyperCommand("login"))


def test_unknown_target_leaves_protected_descriptor_unread(monkeypatch: MonkeyPatch) -> None:
    async def _unexpected_open(*, profile_id: UUID, frontend: OperationFrontendProjection) -> None:
        pytest.fail(f"opened runtime for missing target {profile_id} {frontend}")

    monkeypatch.setattr("cadrumo.adapters.local_runtime.runtime_client.open_installed_runtime_client", _unexpected_open)
    reader, writer = os.pipe()
    payload = json.dumps({"passphrase": _PASSWORD}).encode()
    try:
        os.write(writer, payload)
        os.close(writer)
        result = invoke_cached_cli(
            ("--format", "json", "config", "login", "missing-profile", "--secrets-fd", str(reader))
        )
        assert result.exit_code == 2, result.output
        assert _PASSWORD not in result.output
        assert os.read(reader, len(payload)) == payload
        assert observe_active_profile_pointer().bucket_id is None
    finally:
        os.close(reader)


def test_explicit_password_reads_once_wipes_and_persists(monkeypatch: MonkeyPatch) -> None:
    profile_id = UUID(register_cli_profile(label="Login password", log_in=False))
    client = _RuntimeClient(profile_id)
    _install_client(monkeypatch, client)
    reader, writer = os.pipe()
    try:
        os.write(writer, json.dumps({"passphrase": _PASSWORD}).encode())
        os.close(writer)
        outcome = _login_through_the_prompt(
            _ctx(),
            name=str(profile_id),
            machine_secret=MachineSecretSelection(MachineSecretChannel.FILE_DESCRIPTOR, reader),
        )
        assert outcome.bucket_id == str(profile_id)
        assert outcome.session_persisted and not outcome.already_authenticated
        assert outcome.idle_deadline == client.receipt.idle_deadline
        assert client.calls == ["password", "status", "close"]
        assert client.password_bytes == _PASSWORD.encode()
        assert client.password_buffer is not None and not any(client.password_buffer)
        assert client.persist_receipt is True
        assert observe_active_profile_pointer().bucket_id == str(profile_id)
        with pytest.raises(OSError):
            os.read(reader, 1)
    finally:
        with suppress(OSError):
            os.close(reader)


def test_receipt_resume_avoids_prompt_and_preserves_deadlines(monkeypatch: MonkeyPatch) -> None:
    profile_id = UUID(register_cli_profile(label="Login receipt", log_in=False))
    client = _RuntimeClient(profile_id, receipt=_receipt(resumed=True))
    client.resume_refusal = False
    _install_client(monkeypatch, client)
    monkeypatch.setattr(
        "cadrumo.entrypoints.cli.config.secure_input.prompt_secret_no_echo", lambda _: pytest.fail("prompted")
    )

    outcome = _login_through_the_prompt(_ctx(), name=str(profile_id), machine_secret=None)

    assert client.calls == ["resume", "status", "close"]
    assert outcome.already_authenticated and outcome.session_persisted
    assert outcome.authenticated_at == client.receipt.authenticated_at
    assert outcome.idle_deadline == client.receipt.idle_deadline
    assert outcome.absolute_deadline == client.receipt.absolute_deadline


def test_absent_receipt_and_no_console_refuse_before_password(monkeypatch: MonkeyPatch) -> None:
    profile_id = UUID(register_cli_profile(label="No console", log_in=False))
    original = observe_active_profile_pointer()
    client = _RuntimeClient(profile_id)
    _install_client(monkeypatch, client)
    monkeypatch.setattr("cadrumo.entrypoints.cli.config.secure_input.terminal_can_prompt_for_secrets", lambda: False)

    with pytest.raises(CliRefusedBoundaryError):
        _login_through_the_prompt(_ctx(), name=str(profile_id), machine_secret=None)

    assert client.calls == ["resume", "close"]
    assert client.password_buffer is None
    assert observe_active_profile_pointer() == original


def test_candidate_selection_conflict_keeps_other_profile_selected(monkeypatch: MonkeyPatch) -> None:
    first_id = UUID(register_cli_profile(label="First login target", log_in=False))
    second_id = UUID(register_cli_profile(label="Second login target", log_in=False))
    _select(first_id)
    client = _RuntimeClient(first_id, receipt=_receipt(resumed=True))
    client.resume_refusal = False
    client.on_status = lambda: _select(second_id)
    _install_client(monkeypatch, client)

    with pytest.raises(ActiveProfilePointerTransactionError):
        _login_through_the_prompt(_ctx(), name=str(first_id), machine_secret=None)

    assert observe_active_profile_pointer().bucket_id == str(second_id)
    assert client.calls == ["resume", "status", "close"]
    assert client.closed == 1


def test_failed_candidate_keeps_prior_profile_receipt_and_other_client(
    monkeypatch: MonkeyPatch, _isolated_cli_backend: Path
) -> None:
    first_id = UUID(register_cli_profile(label="Existing login", log_in=False))
    second_id = UUID(register_cli_profile(label="Failed candidate", log_in=False))
    _select(first_id)
    original = observe_active_profile_pointer()
    keyring = _Keyring()
    monkeypatch.setattr(receipt_store, "_keyring", lambda: (keyring, _KeyringError, _KeyringError))
    synthetic_receipt = receipt_store.mint_profile_session(
        storage_root=_isolated_cli_backend,
        profile_id=first_id,
        custody_generation=1,
        dek_epoch="synthetic-first-profile-epoch",
        dek=bytes(range(32)),
        now=datetime.now(UTC),
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=committed_sign_in(_isolated_cli_backend, first_id),
    )
    receipt_path = receipt_store.profile_session_path(storage_root=_isolated_cli_backend, profile_id=first_id)
    original_receipt = receipt_path.read_bytes()
    original_key = keyring.entries[
        (receipt_store.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{first_id}:{synthetic_receipt.session_id}")
    ]
    existing_client = _RuntimeClient(first_id, receipt=_receipt(resumed=True))
    candidate = _RuntimeClient(second_id)
    candidate.refusal_code = "authentication_required"
    _install_client(monkeypatch, candidate)
    reader, writer = os.pipe()
    try:
        os.write(writer, json.dumps({"passphrase": _PASSWORD}).encode())
        os.close(writer)
        with pytest.raises(CliRefusedBoundaryError):
            _login_through_the_prompt(
                _ctx(),
                name=str(second_id),
                machine_secret=MachineSecretSelection(MachineSecretChannel.FILE_DESCRIPTOR, reader),
            )
    finally:
        with suppress(OSError):
            os.close(reader)
    assert observe_active_profile_pointer() == original
    assert candidate.calls == ["password", "close"] and candidate.closed == 1
    assert candidate.password_buffer is not None and not any(candidate.password_buffer)
    assert existing_client.closed == 0 and existing_client.calls == []
    assert receipt_path.read_bytes() == original_receipt
    assert (
        keyring.entries[(receipt_store.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{first_id}:{synthetic_receipt.session_id}")]
        == original_key
    )


def _select(profile_id: UUID) -> None:
    with active_profile_pointer_transaction() as transaction:
        transaction.select(str(profile_id))


class _NativeLoginObservation:
    login_id = "cli-runtime-receipt-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile worker and protected pipes")
@pytest.mark.usefixtures("authority_operation")
def test_installed_cli_resumes_other_profile_without_retiring_original(
    monkeypatch: MonkeyPatch, _isolated_cli_backend: Path
) -> None:
    """One process owns the in-memory keyring; runtime, pipes and worker remain real."""
    keyring = _Keyring()
    monkeypatch.setattr(receipt_store, "_keyring", lambda: (keyring, _KeyringError, _KeyringError))
    passphrase = dev_test_database_password()
    first_id = UUID(register_cli_profile(label="Receipt profile A", log_in=False))
    close_active_bucket_session()
    second_id = UUID(register_cli_profile(label="Receipt profile B", log_in=False))
    close_active_bucket_session()
    with (
        bundled_indexed_authority().operation() as authority,
        bind_profile_custody_port(build_profile_custody_port()),
        bind_profile_login_session_port(build_profile_login_session_port()),
    ):
        for profile_id in (first_id, second_id):
            with authenticate_profile_candidate(
                bucket_id=profile_id,
                passphrase_callback=lambda: passphrase,
                profile_decode_context=authority.profile_decode_context(),
            ) as candidate:
                assert candidate.persist_acceleration_receipt(
                    login_id=RECEIPT_LOGIN_ID,
                    binding=committed_sign_in(_isolated_cli_backend, profile_id).binding,
                )
    _select(first_id)
    first_receipt = receipt_store.profile_session_path(storage_root=_isolated_cli_backend, profile_id=first_id)
    second_receipt = receipt_store.profile_session_path(storage_root=_isolated_cli_backend, profile_id=second_id)
    assert first_receipt.is_file() and second_receipt.is_file()
    before_first, before_second = first_receipt.read_bytes(), second_receipt.read_bytes()
    before_first_keyring = dict(keyring.entries)
    second_metadata = json.loads(before_second)

    endpoint = WindowsRuntimeEndpoint(storage_root=_isolated_cli_backend)
    runtime_installation(
        storage_root=_isolated_cli_backend, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    stop, boot, native = Event(), uuid4(), MemoryNativePort()
    profiles = RuntimeProfileConnections(
        storage_root=_isolated_cli_backend,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=lambda _channel: _NativeLoginObservation(),
        secret_store=lambda: native,
    )
    profiles.prepare_registry()
    server = RetainedRuntimeTransportServer(
        endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(server.serve)
        primary: BaseException | None = None
        try:
            assert server.ready.wait(3)
            first_client = asyncio.run(
                open_installed_runtime_client(profile_id=first_id, frontend=OperationFrontendProjection.CLI)
            )
            try:
                first_client.login_password(bytearray(passphrase.encode()))
                first_session = first_client.session_id
                result = invoke_cached_cli(("--format", "json", "config", "login", str(second_id)))
                assert result.exit_code == 0, result.output
                payload = json.loads(result.stdout)["result"]
                assert payload["active_profile"] == "Receipt profile B"
                assert payload["already_authenticated"] is True
                assert payload["session_persisted"] is True
                for key, source in (
                    ("authenticated_at", "issued_at"),
                    ("idle_deadline", "idle_deadline"),
                    ("absolute_deadline", "absolute_deadline"),
                ):
                    assert datetime.fromisoformat(payload[key]) == datetime.fromisoformat(second_metadata[source])
                assert observe_active_profile_pointer().bucket_id == str(second_id)
                assert first_client.status().status.session_id == first_session
                shown = invoke_cached_cli(
                    ("--format", "json", "--profile", str(second_id), "config", "profile", "view")
                )
                assert shown.exit_code == 0, shown.output
                assert json.loads(shown.stdout)["result"]["display_name"] == "Receipt profile B"
                assert first_receipt.read_bytes() == before_first
                assert second_receipt.read_bytes() == before_second
                assert keyring.entries == before_first_keyring
                assert _PASSWORD not in result.output + shown.output
            finally:
                first_client.close()
        except BaseException as error:
            primary = error
            raise
        finally:
            stop.set()
            try:
                running.result(timeout=20)
            except Exception as cleanup:
                if primary is None:
                    raise
                primary.add_note(f"runtime cleanup also failed: {type(cleanup).__name__}")
            finally:
                endpoint.close()
