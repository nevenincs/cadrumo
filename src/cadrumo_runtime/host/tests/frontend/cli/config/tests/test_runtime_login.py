"""Native worker behavior for the retained AEAT login command."""

from __future__ import annotations

import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt_store
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT as ENROLLMENT_PROFILE_INPUT,
)
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import administration_subject
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
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.login_session import (
    ProfileReceiptRefusedError,
    authenticate_profile_candidate,
    borrow_profile_receipt_key,
)
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
from cadrumo.application.user_profile.profile_pointer import (
    active_profile_pointer_transaction,
    observe_active_profile_pointer,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.adapters.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections

__all__ = ["_isolated_cli_backend"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


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


def _select(profile_id: UUID) -> None:
    with active_profile_pointer_transaction() as transaction:
        transaction.select(str(profile_id))


def test_installed_cli_resumes_other_profile_without_retiring_independent_api_session(
    monkeypatch: pytest.MonkeyPatch,
    _isolated_cli_backend: Path,
    run_cadrumo_cli,
) -> None:
    """A saved human sign-in resumes without prompting while another profile's API session survives."""
    for owner in (
        "cadrumo_client.commands.secure_input",
        "cadrumo_client.commands.custody",
        "cadrumo_client.commands.profile_admission",
    ):
        monkeypatch.setattr(f"{owner}.terminal_can_prompt_for_secrets", lambda: True)
        monkeypatch.setattr(f"{owner}.prompt_secret_no_echo", lambda _: pytest.fail("prompted"))
    keyring = _Keyring()
    monkeypatch.setattr(receipt_store, "_keyring", lambda: (keyring, _KeyringError, _KeyringError))
    passphrase = dev_test_database_password()
    endpoint = WindowsEndpoint(storage_root=_isolated_cli_backend)
    installed = installation(
        storage_root=_isolated_cli_backend,
        os_owner_id=owner_id(),
        storage_identity=endpoint.storage_identity,
    )
    with administration_subject(
        _isolated_cli_backend.parent,
        os_owner_id=owner_id(),
        installation_id=installed.installation_id,
        profile_label="Receipt profile A",
    ) as enrollment:
        assert enrollment.store.root == _isolated_cli_backend
        first_id = enrollment.store.binding.profile_id
        enrollment_id = uuid4()
        enrollment.service.request(enrollment_id, enrollment.proposal)
        enrollment.approve(enrollment_id)
        enrolled = next(
            record for record in enrollment.store.enrollment_state().requests if record.request_id == enrollment_id
        )
        credential = enrollment.owner.delivery.endpoint.possession(enrolled)
        assert credential is not None
        close_active_bucket_session()
        second_id = UUID(register_cli_profile(label="Receipt profile B", log_in=False))
        close_active_bucket_session()
        with (
            bundled_indexed_authority().operation() as authority,
            bind_profile_custody_port(build_profile_custody_port()),
            bind_profile_login_session_port(build_profile_login_session_port()),
        ):
            for profile_id, password in ((first_id, ENROLLMENT_PROFILE_INPUT), (second_id, passphrase)):
                with authenticate_profile_candidate(
                    bucket_id=profile_id,
                    passphrase_callback=lambda password=password: password,
                    profile_decode_context=authority.profile_decode_context(),
                ) as candidate:
                    # Bind each receipt to the login and custody binding the runtime below observes.
                    binding = current_automation_profile_binding(
                        profile_id=profile_id,
                        installation_id=installed.installation_id,
                        os_owner_id=owner_id(),
                        root=_isolated_cli_backend,
                    )
                    sign_in = SignInGenerationCustody(root=_isolated_cli_backend, binding=binding)
                    assert candidate.persist_acceleration_receipt(
                        login_id=_NativeLoginObservation.login_id,
                        binding=binding,
                        sign_in=sign_in.establish().current,
                    )
        _select(first_id)
        first_receipt = receipt_store.profile_session_path(storage_root=_isolated_cli_backend, profile_id=first_id)
        second_receipt = receipt_store.profile_session_path(storage_root=_isolated_cli_backend, profile_id=second_id)
        assert first_receipt.is_file() and second_receipt.is_file()
        before_second = second_receipt.read_bytes()
        second_keyring = {key: value for key, value in keyring.entries.items() if key[1].startswith(f"{second_id}:")}
        assert second_keyring
        second_metadata = json.loads(before_second)

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=_isolated_cli_backend,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _NativeLoginObservation(),
            secret_store=lambda: enrollment.native,
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
                    open_installed_client(profile_id=first_id, frontend=OperationFrontendProjection.CLI)
                )
                try:
                    proof = bytearray(credential.get_secret_value())
                    first_client.login_api_key(proof)
                    proof_wiped = not any(proof)
                    assert proof_wiped
                    first_session = first_client.session_id
                    result = run_cadrumo_cli(("--format", "json", "config", "login", str(second_id)))
                    assert result.exit_code == 0, result.output
                    payload = json.loads(result.stdout)["result"]
                    assert payload["active_profile"] == "Receipt profile B"
                    assert payload["already_authenticated"] is True
                    assert payload["session_persisted"] is True
                    assert observe_active_profile_pointer().bucket_id == str(second_id)
                    for key, source in (
                        ("authenticated_at", "issued_at"),
                        ("idle_deadline", "idle_deadline"),
                        ("absolute_deadline", "absolute_deadline"),
                    ):
                        assert datetime.fromisoformat(payload[key]) == datetime.fromisoformat(second_metadata[source])
                    assert first_client.status().status.session_id == first_session
                    shown = run_cadrumo_cli(
                        ("--format", "json", "--profile", "Receipt profile B", "config", "profile", "view")
                    )
                    assert shown.exit_code == 0, shown.output
                    assert json.loads(shown.stdout)["result"]["display_name"] == "Receipt profile B"
                    # A human sign-in retires other saved human proofs, while independent API authority survives.
                    assert not first_receipt.exists()
                    with pytest.raises(ProfileReceiptRefusedError), borrow_profile_receipt_key(bucket_id=first_id):
                        pytest.fail("another profile's revoked saved sign-in remained usable")
                    assert second_receipt.read_bytes() == before_second
                    proofs_unchanged = keyring.entries == second_keyring
                    assert proofs_unchanged
                    assert passphrase not in result.output + shown.output
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
