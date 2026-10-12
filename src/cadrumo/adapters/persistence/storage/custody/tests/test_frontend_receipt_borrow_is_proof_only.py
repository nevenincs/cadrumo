"""A frontend's receipt borrow reads only the keychain proof and the receipt locator.

Gate: whatever state the receipt is in, the borrow leaves every byte of the
keystore directory and every keychain entry exactly as it found them, and it
never unwraps the DEK. Where the receipt should die, the runtime-side
supplied-key reader is the one that deletes it. Receipts come from the
production writer; the keychain is an in-memory store that records writes and
deletions, because this logon session cannot custody a key.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ......application.user_profile.login_session import (
    ProfileReceiptRefusedError,
    borrow_profile_receipt_key,
    profile_session_keychain_unavailability,
)
from ......application.user_profile.login_session_port import bind_profile_login_session_port
from ......core.base64_codec import b64_encode
from ......core.config import override_settings
from ......core.hashing import canonical_json_bytes
from ......core.profile_session import KeychainUnavailability, ProfileSessionRefusalReason
from ...errors import KeyringUnavailableError
from ...profile_login_session import build_profile_login_session_port
from .. import acceleration_receipt as receipt
from ..acceleration_receipt_crypto import PersistedProfileSession
from ..sign_in_generation import SignInGenerationCustody
from .receipt_sign_in import RECEIPT_LOGIN_ID, sign_in_custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_OPENED = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
_EPOCH = "proof-only-epoch"
_SERVICE = receipt.PROFILE_SESSION_KEYCHAIN_SERVICE


class _KeyringError(Exception):
    """Controlled keychain failure."""


class _Win32CredentialError(Exception):
    """The Windows credential store's error shape: the Win32 code first, then the call and its text."""


_NO_SUCH_LOGON_SESSION = _Win32CredentialError(
    1312, "CredRead", "A specified logon session does not exist. It may already have been terminated"
)


class _RecordingKeyring:
    """Exact service/account store that records every mutation it receives."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self.mutations: list[str] = []
        self.unavailable = False
        self.failure: Exception | None = None

    def get_password(self, service_name: str, username: str) -> str | None:
        if self.failure is not None:
            raise self.failure
        if self.unavailable:
            raise _KeyringError("unavailable")
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.mutations.append(f"set:{username}")
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.mutations.append(f"delete:{username}")
        self.entries.pop((service_name, username), None)


@pytest.fixture
def keychain(monkeypatch: pytest.MonkeyPatch) -> _RecordingKeyring:
    store = _RecordingKeyring()
    monkeypatch.setattr(receipt, "_keyring", lambda: (store, _KeyringError, _KeyringError))
    return store


def _mint(root: Path, profile_id: UUID) -> tuple[SignInGenerationCustody, PersistedProfileSession]:
    sign_in = sign_in_custody(root, profile_id)
    record = receipt.mint_profile_session(
        storage_root=root,
        profile_id=profile_id,
        custody_generation=sign_in.binding.custody_generation,
        dek_epoch=_EPOCH,
        dek=bytes(range(32)),
        now=_OPENED,
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=sign_in,
        generation=sign_in.establish().current,
    )
    return sign_in, record


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {entry.name: entry.read_bytes() for entry in sorted(directory.iterdir()) if entry.is_file()}


def _corrupt_ciphertext(root: Path, profile_id: UUID, record: PersistedProfileSession) -> None:
    flipped = bytes([record.ciphertext[0] ^ 0xFF]) + record.ciphertext[1:]
    path = receipt.profile_session_path(storage_root=root, profile_id=profile_id)
    receipt._write_acceleration_receipt(
        storage_root=root,
        profile_id=profile_id,
        record=record.model_copy(update={"ciphertext": flipped}),
        predecessor=path.read_bytes(),
    )


def _replace_receipt_bytes(root: Path, profile_id: UUID, payload: bytes) -> None:
    receipt.profile_session_path(storage_root=root, profile_id=profile_id).write_bytes(payload)


def _advance(root: Path, profile_id: UUID, record: PersistedProfileSession) -> None:
    del record
    sign_in_custody(root, profile_id).advance()


def _other_schema(root: Path, profile_id: UUID, record: PersistedProfileSession) -> None:
    document = json.loads(receipt.profile_session_path(storage_root=root, profile_id=profile_id).read_bytes())
    del record
    document["schema_version"] = 2
    del document["login_binding"]
    _replace_receipt_bytes(root, profile_id, canonical_json_bytes(document))


# Each of these receipts reaches the runtime, where only the supplied-key reader decides.
_LIVE_PROOF_STATES: dict[str, Callable[[Path, UUID, PersistedProfileSession], None]] = {
    "live": lambda *_: None,
    # The borrow keeps no clock: expiry is the runtime reader's decision.
    "expired": lambda *_: None,
    "generation_advanced": _advance,
    "ciphertext_corrupt": _corrupt_ciphertext,
    "other_schema": _other_schema,
}


@pytest.mark.parametrize("state", tuple(_LIVE_PROOF_STATES))
def test_borrow_reads_the_proof_without_touching_record_or_keychain(
    tmp_path: Path, keychain: _RecordingKeyring, state: str
) -> None:
    profile_id = uuid4()
    _, record = _mint(tmp_path, profile_id)
    _LIVE_PROOF_STATES[state](tmp_path, profile_id, record)
    directory = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id).parent
    files, entries, mutations = _snapshot(directory), dict(keychain.entries), list(keychain.mutations)

    outcome, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)

    assert outcome.resumed and outcome.record is None and key is not None
    try:
        # The proof is exactly the keychain half the locator names. A corrupt
        # ciphertext is still borrowed, so the borrow cannot have unwrapped it.
        assert b64_encode(bytes(key)) == entries[(_SERVICE, f"{profile_id}:{record.session_id}")]
        assert _snapshot(directory) == files
        assert keychain.entries == entries and keychain.mutations == mutations
    finally:
        receipt._zeroise(key)


def _remove_keychain_entry(keychain: _RecordingKeyring, profile_id: UUID, record: PersistedProfileSession) -> None:
    del keychain.entries[(_SERVICE, f"{profile_id}:{record.session_id}")]


def _malform_keychain_entry(keychain: _RecordingKeyring, profile_id: UUID, record: PersistedProfileSession) -> None:
    keychain.entries[(_SERVICE, f"{profile_id}:{record.session_id}")] = "not base64!"


def _keychain_unavailable(keychain: _RecordingKeyring, profile_id: UUID, record: PersistedProfileSession) -> None:
    del profile_id, record
    keychain.unavailable = True


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        (_remove_keychain_entry, ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING),
        (_malform_keychain_entry, ProfileSessionRefusalReason.MALFORMED),
        (_keychain_unavailable, ProfileSessionRefusalReason.KEYRING_UNAVAILABLE),
    ],
    ids=["keychain_entry_missing", "keychain_entry_malformed", "keychain_unavailable"],
)
def test_a_refused_borrow_deletes_nothing(
    tmp_path: Path,
    keychain: _RecordingKeyring,
    damage: Callable[[_RecordingKeyring, UUID, PersistedProfileSession], None],
    reason: ProfileSessionRefusalReason,
) -> None:
    profile_id = uuid4()
    _, record = _mint(tmp_path, profile_id)
    damage(keychain, profile_id, record)
    directory = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id).parent
    files, entries, mutations = _snapshot(directory), dict(keychain.entries), list(keychain.mutations)

    outcome, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)

    assert not outcome.resumed and outcome.refusal is reason and key is None
    assert outcome.deletion is receipt.ReceiptDeletion.NOT_REQUIRED
    assert _snapshot(directory) == files
    assert keychain.entries == entries and keychain.mutations == mutations


def test_a_malformed_or_foreign_receipt_is_refused_and_kept(tmp_path: Path, keychain: _RecordingKeyring) -> None:
    profile_id, other_id = uuid4(), uuid4()
    _mint(tmp_path, profile_id)
    _mint(tmp_path, other_id)
    path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    other_bytes = receipt.profile_session_path(storage_root=tmp_path, profile_id=other_id).read_bytes()
    entries = dict(keychain.entries)
    for payload, reason in ((b"{not a receipt", ProfileSessionRefusalReason.MALFORMED), (other_bytes, None)):
        path.write_bytes(payload)
        outcome, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
        assert key is None
        assert outcome.refusal is (reason or ProfileSessionRefusalReason.TAMPERED)
        assert path.read_bytes() == payload
        assert keychain.entries == entries


def test_the_application_borrow_refuses_typed_without_reading_custody(
    tmp_path: Path, keychain: _RecordingKeyring
) -> None:
    profile_id = uuid4()
    # No capsule exists for this profile: a borrow that still read the custody
    # envelope would fail on it before reporting absence.
    with (
        override_settings(cadrumo_local_storage_root=tmp_path),
        bind_profile_login_session_port(build_profile_login_session_port()),
        pytest.raises(ProfileReceiptRefusedError) as refused,
        borrow_profile_receipt_key(bucket_id=profile_id),
    ):
        pass
    assert refused.value.reason is ProfileSessionRefusalReason.ABSENT
    assert keychain.mutations == []


@pytest.mark.parametrize("state", ["expired", "generation_advanced", "other_schema"])
def test_the_runtime_reader_deletes_what_the_borrow_left(
    tmp_path: Path, keychain: _RecordingKeyring, state: str
) -> None:
    profile_id = uuid4()
    sign_in, record = _mint(tmp_path, profile_id)
    _LIVE_PROOF_STATES[state](tmp_path, profile_id, record)
    path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    _, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    assert key is not None and path.exists()

    refused, dek = receipt.resume_profile_session_with_key(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=sign_in.binding.custody_generation,
        dek_epoch=_EPOCH,
        now=_OPENED + timedelta(minutes=16 if state == "expired" else 1),
        receipt_key=key,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=sign_in,
    )

    assert not refused.resumed and dek is None
    assert refused.deletion is receipt.ReceiptDeletion.DELETED
    assert not path.exists()
    assert (_SERVICE, f"{profile_id}:{record.session_id}") not in keychain.entries
    receipt._zeroise(key)


def test_an_interrupted_key_swap_is_left_by_the_borrow_and_settled_by_the_runtime(
    tmp_path: Path, keychain: _RecordingKeyring
) -> None:
    profile_id = uuid4()
    sign_in, record = _mint(tmp_path, profile_id)
    path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    journal = receipt._profile_session_retirement_path(storage_root=tmp_path, profile_id=profile_id)
    # A first mint that died after publishing, before clearing its journal.
    journal.write_bytes(
        receipt._pending_retirement_bytes(profile_id=profile_id, predecessor=None, successor=path.read_bytes())
    )
    files = _snapshot(path.parent)

    _, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    assert key is not None
    assert _snapshot(path.parent) == files

    resumed, dek = receipt.resume_profile_session_with_key(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=sign_in.binding.custody_generation,
        dek_epoch=_EPOCH,
        now=_OPENED + timedelta(minutes=1),
        receipt_key=key,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=sign_in,
    )

    assert resumed.resumed and resumed.record == record and dek is not None
    assert not journal.exists() and path.exists()
    receipt._zeroise(dek)
    receipt._zeroise(key)


class NoKeyringError(Exception):
    """Named as the keyring library names its missing-backend error."""


def _raised_from(error: Exception, cause: Exception) -> Exception:
    try:
        raise error from cause
    except Exception as raised:
        return raised


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_NO_SUCH_LOGON_SESSION, KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS),
        (
            _raised_from(_KeyringError("wrapped"), _NO_SUCH_LOGON_SESSION),
            KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS,
        ),
        (_Win32CredentialError(5, "CredWrite", "Access is denied"), KeychainUnavailability.REFUSED),
        (NoKeyringError("no backend"), KeychainUnavailability.NO_BACKEND),
        (
            KeyringUnavailableError("typed", unavailability=KeychainUnavailability.NO_BACKEND),
            KeychainUnavailability.NO_BACKEND,
        ),
        (_KeyringError("anything else"), KeychainUnavailability.REFUSED),
    ],
    ids=["logon_1312", "logon_1312_wrapped", "other_win32_code", "no_backend", "typed", "other"],
)
def test_a_keychain_failure_names_its_failed_prerequisite(error: Exception, expected: KeychainUnavailability) -> None:
    assert receipt.keychain_unavailability(error) is expected


def test_the_probe_reads_one_unnamed_account_and_changes_nothing(keychain: _RecordingKeyring) -> None:
    assert receipt.probe_profile_session_keychain() is None
    keychain.failure = _NO_SUCH_LOGON_SESSION
    assert receipt.probe_profile_session_keychain() is KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS
    assert keychain.entries == {} and keychain.mutations == []


def test_the_probe_reports_a_missing_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_backend() -> None:
        raise KeyringUnavailableError("none", unavailability=KeychainUnavailability.NO_BACKEND)

    monkeypatch.setattr(receipt, "_keyring", no_backend)
    assert receipt.probe_profile_session_keychain() is KeychainUnavailability.NO_BACKEND


def test_an_absent_receipt_names_a_keychain_this_process_cannot_use(
    tmp_path: Path, keychain: _RecordingKeyring
) -> None:
    profile_id = uuid4()
    outcome, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    # Absence stays the reason; a usable keychain adds nothing to it.
    assert outcome.refusal is ProfileSessionRefusalReason.ABSENT and outcome.keychain is None and key is None

    keychain.failure = _NO_SUCH_LOGON_SESSION
    outcome, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    assert outcome.refusal is ProfileSessionRefusalReason.ABSENT and key is None
    assert outcome.keychain is KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS
    assert keychain.mutations == [] and not any(tmp_path.iterdir())


def test_an_unreadable_proof_names_why_the_keychain_refused(tmp_path: Path, keychain: _RecordingKeyring) -> None:
    profile_id = uuid4()
    _mint(tmp_path, profile_id)
    keychain.failure = _NO_SUCH_LOGON_SESSION
    outcome, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    assert outcome.refusal is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE and key is None
    assert outcome.keychain is KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS


def test_the_application_borrow_carries_the_keychain_reason(tmp_path: Path, keychain: _RecordingKeyring) -> None:
    keychain.failure = _NO_SUCH_LOGON_SESSION
    with (
        override_settings(cadrumo_local_storage_root=tmp_path),
        bind_profile_login_session_port(build_profile_login_session_port()),
    ):
        assert profile_session_keychain_unavailability() is KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS
        with pytest.raises(ProfileReceiptRefusedError) as refused, borrow_profile_receipt_key(bucket_id=uuid4()):
            pass
    assert refused.value.reason is ProfileSessionRefusalReason.ABSENT
    assert refused.value.keychain is KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS
