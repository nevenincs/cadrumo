"""The runtime's credential-store pass: what it removes, what it keeps, and that it never raises.

The Windows case drives the real Credential Manager through the production
adapters under a profile-session service token unique to the case, never the
production token, and removes only the targets it wrote.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody import acceleration_keychain, acceleration_receipt
from cadrumo.adapters.persistence.storage.custody.acceleration_keychain import (
    read_acceleration_secret,
    store_acceleration_secret,
)
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import (
    ReceiptDeletion,
    mint_profile_session,
    revoke_profile_sign_in,
)
from cadrumo.adapters.persistence.storage.custody.acceleration_session_prune import ProfileSessionPruneOutcome
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import (
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
    automation_native_account,
)
from cadrumo.adapters.persistence.storage.custody.automation_retirement import AutomationPruneOutcome
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import (
    WindowsAutomationSecretStore,
    WindowsCredentialManager,
)
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import RECEIPT_LOGIN_ID, sign_in_custody
from cadrumo.adapters.persistence.storage.errors import KeyringUnavailableError
from cadrumo.core.profile_session import KeychainUnavailability
from cadrumo.tests.os_keychain_hook import require_os_credential_store

from .. import credential_prune
from ..credential_prune import CredentialPruneReport, CredentialPruneSkipped, prune_owned_credentials

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture
def test_service(monkeypatch: pytest.MonkeyPatch) -> Iterator[set[UUID]]:
    require_os_credential_store()
    service = f"cadrumo-test-runtime-credential-prune:{uuid4()}"
    assert service != acceleration_keychain.PROFILE_SESSION_KEYCHAIN_SERVICE
    monkeypatch.setattr(acceleration_keychain, "PROFILE_SESSION_KEYCHAIN_SERVICE", service)
    profiles: set[UUID] = set()
    try:
        yield profiles
    finally:
        manager = WindowsCredentialManager()
        for profile_id in profiles:
            for name in manager.names(f"{profile_id}:"):
                if name.target.endswith(f"@{service}"):
                    manager.delete(name.target)


def _mint(root: Path, profile_id: UUID) -> UUID:
    sign_in = sign_in_custody(root, profile_id)
    return mint_profile_session(
        storage_root=root,
        profile_id=profile_id,
        custody_generation=1,
        dek_epoch="runtime-credential-prune-epoch",
        dek=secrets.token_bytes(32),
        now=datetime.now(UTC),
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=sign_in,
        generation=sign_in.establish().current,
    ).session_id


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_runtime_pass_removes_an_orphaned_minted_entry_and_keeps_the_live_and_unrecorded_ones(
    test_service: set[UUID], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = uuid4()
    test_service.add(owned)
    orphaned = _mint(tmp_path, owned)

    def refused(**_coordinates: object) -> None:
        raise KeyringUnavailableError("synthetic keychain refusal")

    with monkeypatch.context() as patch:
        patch.setattr(acceleration_receipt, "delete_acceleration_secret", refused)
        assert revoke_profile_sign_in(sign_in_custody(tmp_path, owned)) is ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED
    live = _mint(tmp_path, owned)
    unrecorded = uuid4()
    store_acceleration_secret(profile_id=owned, session_id=unrecorded, session_key=secrets.token_bytes(32))

    report = prune_owned_credentials(tmp_path)

    assert isinstance(report, CredentialPruneReport)
    assert report.profile_sessions.removed == ((owned, orphaned),)
    assert report.profile_sessions.unavailability is None
    assert report.automation.failure is None
    assert read_acceleration_secret(profile_id=owned, session_id=orphaned) is None
    assert read_acceleration_secret(profile_id=owned, session_id=live) is not None
    assert read_acceleration_secret(profile_id=owned, session_id=unrecorded) is not None


def test_runtime_pass_reports_an_unavailable_keychain_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    keyring_entries: dict[tuple[str, str], str] = {}

    class _Keyring:
        def set_password(self, service_name: str, username: str, password: str) -> None:
            keyring_entries[(service_name, username)] = password

        def get_password(self, service_name: str, username: str) -> str | None:
            return keyring_entries.get((service_name, username))

        def delete_password(self, service_name: str, username: str) -> None:
            keyring_entries.pop((service_name, username), None)

    with monkeypatch.context() as patch:
        patch.setattr(acceleration_keychain, "acceleration_keychain_keyring", lambda: (_Keyring(), KeyError, KeyError))
        profile_id = uuid4()
        first = _mint(tmp_path, profile_id)
        _mint(tmp_path, profile_id)

    def no_backend() -> object:
        raise KeyringUnavailableError("no keychain", unavailability=KeychainUnavailability.NO_BACKEND)

    monkeypatch.setattr(acceleration_keychain, "acceleration_keychain_keyring", no_backend)

    report = prune_owned_credentials(tmp_path)

    assert isinstance(report, CredentialPruneReport)
    assert report.profile_sessions.removed == ()
    assert report.profile_sessions.retained == ((profile_id, first),)
    assert report.profile_sessions.unavailability is KeychainUnavailability.NO_BACKEND


def test_runtime_pass_turns_an_unexpected_failure_into_a_typed_skip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _UnforeseenError(Exception):
        pass

    def unforeseen(_root: Path) -> object:
        raise _UnforeseenError("detail that must not be carried")

    monkeypatch.setattr(credential_prune, "profile_session_prune_has_work", lambda _root: True)
    monkeypatch.setattr(credential_prune, "prune_profile_session_entries", unforeseen)

    skipped = prune_owned_credentials(tmp_path)

    assert skipped == CredentialPruneSkipped(reason="unexpected_error", error_type="_UnforeseenError")


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_runtime_pass_leaves_a_root_with_nothing_to_prune_untouched(tmp_path: Path) -> None:
    """No recorded session and no native entry for this root: the pass takes no lock and writes nothing."""
    require_os_credential_store()
    root = tmp_path / "root"
    root.mkdir()

    report = prune_owned_credentials(root)

    assert report == CredentialPruneReport(
        profile_sessions=ProfileSessionPruneOutcome(removed=(), retained=(), unavailability=None),
        automation=AutomationPruneOutcome(removed=0, retained=0, failure=None),
    )
    assert list(root.iterdir()) == []


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_runtime_pass_prunes_a_wiped_roots_leftover_automation_entries_under_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A root whose automation directory is gone still has its leftover native entries removed, under the lock."""
    require_os_credential_store()
    root = tmp_path / "root"
    root.mkdir()
    store = WindowsAutomationSecretStore()
    control = automation_native_account(root, uuid4(), uuid4())
    written = [(CONTROL_NAMESPACE, control), (WRAP_NAMESPACE, f"{control}/{uuid4()}")]
    locked_roots: list[Path] = []
    real_lock = credential_prune.profile_custody_root_lock

    def observed_lock(lock_root: Path, *, timeout_seconds: float) -> object:
        locked_roots.append(lock_root)
        return real_lock(lock_root, timeout_seconds=timeout_seconds)

    monkeypatch.setattr(credential_prune, "profile_custody_root_lock", observed_lock)
    try:
        for namespace, account in written:
            store.replace(namespace, account, SecretBytes(b"synthetic"))

        report = prune_owned_credentials(root)

        assert isinstance(report, CredentialPruneReport)
        assert report.automation == AutomationPruneOutcome(removed=2, retained=0, failure=None)
        assert locked_roots == [root]
        assert [store.read(namespace, account) for namespace, account in written] == [None, None]
    finally:
        for namespace, account in written:
            store.delete(namespace, account)
