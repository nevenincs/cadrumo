"""Pruning OS credential-store entries that no record of this storage root names.

The Windows cases drive the real Credential Manager through the production
adapters under a service token and storage roots unique to each case, never
the production profile-session token, and remove only the targets they wrote.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo_client.contracts.automation_codes import AutomationCustodyCode

from ......core.profile_session import KeychainUnavailability
from ......tests.os_keychain_hook import require_os_credential_store
from ...errors import KeyringUnavailableError
from .. import acceleration_keychain, acceleration_receipt, automation_secret_store
from ..acceleration_keychain import read_acceleration_secret, store_acceleration_secret
from ..acceleration_receipt import (
    ReceiptDeletion,
    mint_profile_session,
    profile_session_path,
    revoke_profile_sign_in,
)
from ..acceleration_session_prune import prune_profile_session_entries
from ..automation_native_identity import CONTROL_NAMESPACE, WRAP_NAMESPACE, automation_native_account
from ..automation_retirement import prune_unowned_automation_entries
from ..automation_secret_store import WindowsAutomationSecretStore, WindowsCredentialManager
from .human_keyring_support import HumanKeyring, KeyringError
from .receipt_sign_in import RECEIPT_LOGIN_ID, sign_in_custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_EPOCH = "credential-prune-dek-epoch"


@dataclass
class _TestService:
    """A profile-session service token no production entry uses, and the profiles whose targets it wrote."""

    name: str
    profiles: set[UUID] = field(default_factory=set)


@pytest.fixture
def test_service(monkeypatch: pytest.MonkeyPatch) -> Iterator[_TestService]:
    require_os_credential_store()
    service = _TestService(f"cadrumo-test-credential-prune:{uuid4()}")
    assert service.name != acceleration_keychain.PROFILE_SESSION_KEYCHAIN_SERVICE
    monkeypatch.setattr(acceleration_keychain, "PROFILE_SESSION_KEYCHAIN_SERVICE", service.name)
    try:
        yield service
    finally:
        manager = WindowsCredentialManager()
        for profile_id in service.profiles:
            for name in manager.names(f"{profile_id}:"):
                if name.target.endswith(f"@{service.name}"):
                    manager.delete(name.target)


def _mint(root: Path, profile_id: UUID) -> UUID:
    sign_in = sign_in_custody(root, profile_id)
    record = mint_profile_session(
        storage_root=root,
        profile_id=profile_id,
        custody_generation=1,
        dek_epoch=_EPOCH,
        dek=secrets.token_bytes(32),
        now=datetime.now(UTC),
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=sign_in,
        generation=sign_in.establish().current,
    )
    return record.session_id


def _minted(root: Path, profile_id: UUID) -> set[UUID]:
    """Read the minted-session record as the plain document it is: session ids only."""
    record = profile_session_path(storage_root=root, profile_id=profile_id).with_name("session.v2.minted.json")
    if not record.exists():
        return set()
    document = json.loads(record.read_bytes())
    assert set(document) == {"schema_version", "session_ids"}
    return {UUID(value) for value in document["session_ids"]}


def _sign_out_with_keychain_refusing(monkeypatch: pytest.MonkeyPatch, root: Path, profile_id: UUID) -> None:
    """Sign out while the keychain refuses deletion: the receipt goes and its key stays behind, unnamed."""

    def refused(**_coordinates: object) -> None:
        raise KeyringUnavailableError("synthetic keychain refusal")

    with monkeypatch.context() as patch:
        patch.setattr(acceleration_receipt, "delete_acceleration_secret", refused)
        assert revoke_profile_sign_in(sign_in_custody(root, profile_id)) is ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_two_roots_with_one_profile_prune_only_what_each_root_minted(
    test_service: _TestService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Root A removes the key it minted and orphaned; root B's live key and an unrecorded key stay."""
    root_a, root_b = tmp_path / "a", tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    profile_id = uuid4()
    test_service.profiles.add(profile_id)
    orphaned = _mint(root_a, profile_id)
    _sign_out_with_keychain_refusing(monkeypatch, root_a, profile_id)
    live_a = _mint(root_a, profile_id)
    live_b = _mint(root_b, profile_id)
    unrecorded = uuid4()
    store_acceleration_secret(profile_id=profile_id, session_id=unrecorded, session_key=secrets.token_bytes(32))
    assert read_acceleration_secret(profile_id=profile_id, session_id=orphaned) is not None

    outcome_a = prune_profile_session_entries(root_a)
    outcome_b = prune_profile_session_entries(root_b)

    assert outcome_a.removed == ((profile_id, orphaned),)
    assert outcome_a.unavailability is None
    assert outcome_b.removed == ()
    assert read_acceleration_secret(profile_id=profile_id, session_id=orphaned) is None
    for kept in (live_a, live_b, unrecorded):
        assert read_acceleration_secret(profile_id=profile_id, session_id=kept) is not None
    assert _minted(root_a, profile_id) == {live_a}
    assert _minted(root_b, profile_id) == {live_b}


@pytest.fixture
def memory_keyring(monkeypatch: pytest.MonkeyPatch) -> HumanKeyring:
    keyring = HumanKeyring()
    monkeypatch.setattr(
        acceleration_keychain, "acceleration_keychain_keyring", lambda: (keyring, KeyringError, KeyringError)
    )
    return keyring


def test_journal_named_sessions_stay_and_the_record_holds_session_ids_only(
    memory_keyring: HumanKeyring, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A swap whose predecessor could not be retired keeps both sessions until its journal is recovered."""
    profile_id = uuid4()
    first = _mint(tmp_path, profile_id)

    def refused(**_coordinates: object) -> None:
        raise KeyringUnavailableError("synthetic keychain refusal")

    with monkeypatch.context() as patch:
        patch.setattr(acceleration_receipt, "delete_acceleration_secret", refused)
        second = _mint(tmp_path, profile_id)

    outcome = prune_profile_session_entries(tmp_path)

    assert outcome.removed == ()
    assert _minted(tmp_path, profile_id) == {first, second}


def test_unavailable_keychain_stops_the_pass_and_keeps_the_record(
    memory_keyring: HumanKeyring, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = uuid4()
    first = _mint(tmp_path, profile_id)
    second = _mint(tmp_path, profile_id)
    assert _minted(tmp_path, profile_id) == {first, second}

    def no_backend() -> object:
        raise KeyringUnavailableError("no keychain", unavailability=KeychainUnavailability.NO_BACKEND)

    with monkeypatch.context() as patch:
        patch.setattr(acceleration_keychain, "acceleration_keychain_keyring", no_backend)
        refused = prune_profile_session_entries(tmp_path)

    assert refused.removed == ()
    assert refused.retained == ((profile_id, first),)
    assert refused.unavailability is KeychainUnavailability.NO_BACKEND
    assert _minted(tmp_path, profile_id) == {first, second}

    settled = prune_profile_session_entries(tmp_path)

    assert settled.removed == ((profile_id, first),)
    assert _minted(tmp_path, profile_id) == {second}


def test_an_unrecorded_entry_of_an_owned_profile_is_never_deleted(memory_keyring: HumanKeyring, tmp_path: Path) -> None:
    profile_id = uuid4()
    live = _mint(tmp_path, profile_id)
    leaked = uuid4()
    store_acceleration_secret(profile_id=profile_id, session_id=leaked, session_key=secrets.token_bytes(32))

    outcome = prune_profile_session_entries(tmp_path)

    assert outcome.removed == ()
    assert read_acceleration_secret(profile_id=profile_id, session_id=leaked) is not None
    assert read_acceleration_secret(profile_id=profile_id, session_id=live) is not None


@pytest.mark.windows_only
def test_unavailable_credential_manager_stops_the_automation_prune_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def refused() -> object:
        raise OSError

    monkeypatch.setattr(automation_secret_store, "windows_credential_api", refused)

    outcome = prune_unowned_automation_entries(root=tmp_path, secrets_store=WindowsAutomationSecretStore())

    assert outcome.removed == 0
    assert outcome.failure is AutomationCustodyCode.UNAVAILABLE


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_automation_prune_removes_only_this_roots_entries_without_a_directory(tmp_path: Path) -> None:
    require_os_credential_store()
    store = WindowsAutomationSecretStore()
    root, other_root = tmp_path / "root", tmp_path / "other"
    root.mkdir()
    other_root.mkdir()
    installation, live_profile, gone_profile = uuid4(), uuid4(), uuid4()
    (root / ".automation-v1" / str(installation) / str(live_profile)).mkdir(parents=True)
    live = automation_native_account(root, installation, live_profile)
    gone = automation_native_account(root, installation, gone_profile)
    foreign = automation_native_account(other_root, installation, gone_profile)
    written = [
        (CONTROL_NAMESPACE, live),
        (WRAP_NAMESPACE, f"{live}/{uuid4()}"),
        (CONTROL_NAMESPACE, gone),
        (WRAP_NAMESPACE, f"{gone}/{uuid4()}"),
        (CONTROL_NAMESPACE, foreign),
    ]
    try:
        for namespace, account in written:
            store.replace(namespace, account, SecretBytes(b"synthetic"))

        outcome = prune_unowned_automation_entries(root=root, secrets_store=store)

        assert (outcome.removed, outcome.retained, outcome.failure) == (2, 0, None)
        assert [store.read(namespace, account) is not None for namespace, account in written] == [
            True,
            True,
            False,
            False,
            True,
        ]
    finally:
        for namespace, account in written:
            store.delete(namespace, account)
