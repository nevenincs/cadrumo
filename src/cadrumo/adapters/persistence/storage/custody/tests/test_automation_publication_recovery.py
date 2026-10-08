"""Adversarial multi-grant publication through real encrypted profile custody.

The injected native port models uncertain writes. These tests prove publication
and recovery behavior, not native credential-store availability or durability.
"""

from __future__ import annotations

from typing import override
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_crypto import api_key_verifier, generate_api_key
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CONTROL_NAMESPACE, WRAP_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.zeroise import zeroise
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationGrantMaterial,
    AutomationKeyVerifier,
)

from .automation_support import MemoryNativePort
from .test_automation_store import NOW, Subject, changed
from .test_automation_store import subject as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("authority_operation")]


class InterruptedNativeWrites(MemoryNativePort):
    """Fail a selected replacement before or after committing its value."""

    fail_at: int = 0
    after: bool = False
    writes: int = 0

    @override
    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        self.writes += 1
        failing = self.writes == self.fail_at
        if not failing or self.after:
            super().replace(namespace, account, value)
        if failing:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)


def another_grant(subject: Subject) -> tuple[AutomationGrantMaterial, SecretBytes]:
    """Enroll a distinct synthetic client over the same real profile DEK."""
    key_id, credential = generate_api_key()
    grant = changed(subject.material.grant, grant_id=uuid4(), client_id=uuid4())
    key = changed(subject.material.keys[0].key, key_id=key_id, grant_id=grant.grant_id)
    return (
        AutomationGrantMaterial(
            grant=grant,
            dek=subject.material.dek,
            keys=(AutomationKeyVerifier(key=key, verifier=api_key_verifier(credential)[1]),),
        ),
        credential,
    )


def assert_unlock(subject: Subject, credential: SecretBytes) -> None:
    """Check a real sentinel-backed unwrap and release the returned key buffer."""
    dek = subject.store.unwrap(credential=credential, now=NOW)
    try:
        assert subject.material.dek is not None
        assert bytes(dek) == subject.material.dek.get_secret_value()
    finally:
        zeroise(dek)


@pytest.mark.parametrize("fail_at", [1, 2, 3])
@pytest.mark.parametrize("after", [False, True])
@pytest.mark.parametrize("initial", [False, True])
def test_two_grant_uncertain_writes_recover_only_the_protected_revision(
    subject: Subject, fail_at: int, after: bool, initial: bool
) -> None:
    second, credential = another_grant(subject)
    materials = (subject.material, second)
    if not initial:
        subject.store.publish(grants=materials, expected_revision=0, profile_lock_generation=0, automation_enabled=True)
    native = InterruptedNativeWrites()
    native.items.update(subject.native.items)
    previous_items = dict(native.items)
    subject.store.secrets = native
    native.fail_at, native.after = fail_at, after

    with pytest.raises(AutomationCustodyError) as failure:
        subject.store.publish(
            grants=materials,
            expected_revision=0 if initial else 1,
            profile_lock_generation=0,
            automation_enabled=initial,
        )
    assert failure.value.reason is AutomationCustodyCode.UNAVAILABLE
    committed = fail_at == 3 and after

    if initial and not committed:
        with pytest.raises(AutomationCustodyError) as missing:
            subject.store.read()
        assert missing.value.reason is AutomationCustodyCode.MISSING
        assert not native.items
        for candidate in (subject.credential, credential):
            with pytest.raises(AutomationCustodyError):
                subject.store.unwrap(credential=candidate, now=NOW)
    else:
        revision, payload = subject.store.read()
        assert revision == (1 if initial or not committed else 2)
        assert payload.automation_enabled is (initial or not committed)
        if not committed:
            assert native.items == previous_items
        expected_wraps = {
            (WRAP_NAMESPACE, subject.store.account + "/" + str(item.wrap_key_id)) for item in payload.grants
        }
        assert set(native.items) == expected_wraps | {(CONTROL_NAMESPACE, subject.store.account)}
        for candidate in (subject.credential, credential):
            if payload.automation_enabled:
                assert_unlock(subject, candidate)
            else:
                with pytest.raises(AutomationCustodyError) as denied:
                    subject.store.unwrap(credential=candidate, now=NOW)
                assert denied.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED

    assert not (subject.store.directory / "publication.json").exists()
    native.fail_at = 0
    if initial and not committed:
        assert (
            subject.store.publish(
                grants=materials, expected_revision=0, profile_lock_generation=0, automation_enabled=True
            )
            == 1
        )
        assert_unlock(subject, subject.credential)
        assert_unlock(subject, credential)


def test_replayed_valid_pending_publication_cannot_undo_later_revocation(subject: Subject) -> None:
    subject.publish()
    native = InterruptedNativeWrites()
    native.items.update(subject.native.items)
    subject.store.secrets = native
    native.fail_at, native.after = 2, True
    with pytest.raises(AutomationCustodyError):
        subject.publish(1, enabled=False)
    interrupted_files = {path.name: path.read_bytes() for path in subject.store.directory.glob("*.json")}
    assert "publication.json" in interrupted_files
    assert subject.store.read()[0] == 2
    assert (
        subject.store.publish(grants=(), expected_revision=2, profile_lock_generation=0, automation_enabled=False) == 3
    )
    protected_state = dict(native.items)

    # Replay an actually emitted intent, pointer and ciphertext together, while
    # retaining the current protected anchor. All writes stay in this fixture.
    for name, raw in interrupted_files.items():
        (subject.store.directory / name).write_bytes(raw)
    with pytest.raises(AutomationCustodyError) as denied:
        subject.store.unwrap(credential=subject.credential, now=NOW)
    assert denied.value.reason is AutomationCustodyCode.INVALID
    assert native.items == protected_state
    assert (subject.store.directory / "publication.json").exists()


def test_stale_writer_and_lock_generation_rollback_cannot_replace_current_authority(subject: Subject) -> None:
    subject.publish()
    assert (
        subject.store.publish(
            grants=(subject.material,), expected_revision=1, profile_lock_generation=1, automation_enabled=True
        )
        == 2
    )
    protected_state = dict(subject.native.items)
    current_files = {path.name: path.read_bytes() for path in subject.store.directory.glob("*.json")}
    for expected_revision, generation in ((1, 1), (2, 0)):
        with pytest.raises(AutomationCustodyError) as conflict:
            subject.store.publish(
                grants=(subject.material,),
                expected_revision=expected_revision,
                profile_lock_generation=generation,
                automation_enabled=True,
            )
        assert conflict.value.reason is AutomationCustodyCode.CONFLICT
        assert subject.native.items == protected_state
        assert {path.name: path.read_bytes() for path in subject.store.directory.glob("*.json")} == current_files
        with pytest.raises(AutomationCustodyError) as denied:
            subject.store.unwrap(credential=subject.credential, now=NOW)
        assert denied.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
