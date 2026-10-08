"""Read-only status follows receipt, generation and positive native observation."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipts
from cadrumo.adapters.persistence.storage.custody.capsule import (
    load_committed_profile_password_material,
    replace_committed_profile_custody_envelope,
)
from cadrumo.adapters.persistence.storage.custody.records import ProfileCustodyEnvelope
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import RECEIPT_LOGIN_ID, publish_sign_in_custody
from cadrumo.application.runtime.sign_in import SignInPresence
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.core.base64_codec import b64_encode
from cadrumo.core.hashing import prefixed_digest
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.runtime.sign_in_status import observe_sign_in
from cadrumo.entrypoints.runtime.sign_in_sweep import sweep_saved_sign_ins

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Keyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[service, account] = value

    def delete_password(self, service: str, account: str) -> None:
        self.values.pop((service, account), None)


@pytest.mark.parametrize(
    ("case", "presence"),
    [
        ("present", SignInPresence.PRESENT),
        ("expired", SignInPresence.ABSENT),
        ("locked", SignInPresence.ABSENT),
        ("unknown", SignInPresence.UNKNOWN),
        ("generation_advanced", SignInPresence.ABSENT),
        ("generation_unreadable", SignInPresence.UNKNOWN),
        ("login_mismatch", SignInPresence.ABSENT),
        ("sign_out", SignInPresence.ABSENT),
        ("sign_out_delete_failure", SignInPresence.ABSENT),
        ("sign_out_retirement_failure", SignInPresence.ABSENT),
        ("sign_out_keyring_unavailable", SignInPresence.ABSENT),
        ("sweep_locked", SignInPresence.ABSENT),
        ("sweep_unknown", SignInPresence.UNKNOWN),
        ("sweep_custody_changed", SignInPresence.ABSENT),
        ("sweep_absent_complete", SignInPresence.ABSENT),
        ("sweep_absent_incomplete", SignInPresence.PRESENT),
    ],
)
def test_status_never_reads_keychain_or_changes_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, presence: SignInPresence
) -> None:
    profile_id = uuid4()
    custody = publish_sign_in_custody(tmp_path, profile_id)
    installation = runtime_installation(
        storage_root=tmp_path, os_owner_id=custody.binding.os_owner_id, storage_identity="a" * 64
    )
    custody = SignInGenerationCustody(
        root=tmp_path, binding=custody.binding.model_copy(update={"installation_id": installation.installation_id})
    )
    keyring = _Keyring()
    monkeypatch.setattr(receipts, "_keyring", lambda: (keyring, RuntimeError, KeyError))
    instant = now()
    receipts.mint_profile_session(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=custody.binding.custody_generation,
        dek_epoch=b64_encode(custody.binding.dek_epoch.bytes),
        dek=bytes(range(32)),
        now=instant,
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=custody,
        generation=custody.establish().current,
    )

    def forbidden_keychain() -> None:
        pytest.fail("status read the keychain")

    monkeypatch.setattr(receipts, "_keyring", forbidden_keychain)
    path = receipts.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    before = path.read_bytes()
    if case in {"sign_out", "sign_out_delete_failure", "sign_out_retirement_failure", "sign_out_keyring_unavailable"}:
        monkeypatch.setattr(receipts, "_keyring", lambda: (keyring, RuntimeError, KeyError))
        if case == "sign_out_delete_failure":
            monkeypatch.setattr(receipts, "_clear_captured_receipt", lambda *_args, **_kwargs: False)
        if case == "sign_out_retirement_failure":

            def fail_retirement(**_kwargs: object) -> bool:
                raise receipts.StorageValidationError("synthetic interrupted retirement")

            monkeypatch.setattr(receipts, "_recover_pending_retirement", fail_retirement)
        if case == "sign_out_keyring_unavailable":

            def fail_keychain(_service: str, _account: str) -> None:
                raise RuntimeError("synthetic unavailable keyring")

            monkeypatch.setattr(keyring, "delete_password", fail_keychain)
        captured_generation = custody.observe().current
        deletion = receipts.revoke_profile_sign_in(custody)
        assert custody.observe().current != captured_generation
        assert (
            deletion
            is {
                "sign_out": receipts.ReceiptDeletion.DELETED,
                "sign_out_delete_failure": receipts.ReceiptDeletion.RECEIPT_RETAINED,
                "sign_out_retirement_failure": receipts.ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED,
                "sign_out_keyring_unavailable": receipts.ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED,
            }[case]
        )
        monkeypatch.setattr(receipts, "_keyring", forbidden_keychain)
    if case == "generation_advanced":
        custody.advance()
    elif case == "generation_unreadable":
        custody.path.write_bytes(b"unreadable synthetic generation")
    lock_state = {
        "locked": OsLockState.LOCKED,
        "unknown": OsLockState.UNKNOWN,
        "sweep_locked": OsLockState.LOCKED,
        "sweep_unknown": OsLockState.UNKNOWN,
        "sweep_custody_changed": OsLockState.UNKNOWN,
    }.get(case, OsLockState.UNLOCKED)
    login = OsLoginContext(
        login_id="other-login" if case == "login_mismatch" else RECEIPT_LOGIN_ID,
        os_owner_id=custody.binding.os_owner_id,
        active=True,
        lock_state=lock_state,
        unattended=LoginEligibility.ELIGIBLE,
        credential_facilities=Availability.UNAVAILABLE,
    )
    if case.startswith("sweep_"):
        monkeypatch.setattr(receipts, "_keyring", lambda: (keyring, RuntimeError, KeyError))
        prior_generation = custody.observe().current
        if case == "sweep_custody_changed":
            envelope = load_committed_profile_password_material(profile_id, root=tmp_path).envelope
            successor = ProfileCustodyEnvelope.create(
                profile_id=profile_id,
                password_generation=envelope.password_generation + 1,
                dek_epoch=envelope.dek_epoch,
                kdf=envelope.kdf,
                wrapped_dek=envelope.wrapped_dek,
                previous_envelope_digest=envelope.self_digest,
            )
            replace_committed_profile_custody_envelope(
                profile_id,
                successor.canonical_json_bytes(),
                expected_sha256=prefixed_digest(envelope.canonical_json_bytes()),
                root=tmp_path,
            )
        retired = sweep_saved_sign_ins(
            root=tmp_path,
            installation=installation,
            logins=() if case.startswith("sweep_absent") else (login,),
            inventory_complete=case != "sweep_absent_incomplete",
        )
        revoked = case in {"sweep_locked", "sweep_absent_complete", "sweep_custody_changed"}
        assert retired == ((profile_id,) if revoked else ())
        assert (custody.observe().current != prior_generation) is revoked
        monkeypatch.setattr(receipts, "_keyring", forbidden_keychain)
    status = observe_sign_in(
        root=tmp_path,
        storage_identity="a" * 64,
        profile_id=profile_id,
        login=login,
        instant=instant + timedelta(minutes=16 if case == "expired" else 1),
    )
    assert status.presence is presence
    if case in {
        "sign_out",
        "sign_out_retirement_failure",
        "sign_out_keyring_unavailable",
        "sweep_locked",
        "sweep_absent_complete",
        "sweep_custody_changed",
    }:
        assert not path.exists()
    else:
        assert path.read_bytes() == before
    if presence is SignInPresence.PRESENT:
        assert status.idle_deadline == instant + timedelta(minutes=15)
        assert status.absolute_deadline == instant + timedelta(minutes=240)
    else:
        assert status.idle_deadline is None and status.absolute_deadline is None
