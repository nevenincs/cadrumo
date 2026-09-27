"""Custody protocol fault injection with real encrypted test profiles and files.

The native port is a test double here. Native replacement evidence has its own
test module; these cases prove crypto/protocol behavior, not platform readiness.
"""

from __future__ import annotations

import base64
import gzip
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, SecretBytes, ValidationError

from cadrumo.adapters.persistence.storage.custody.automation_crypto import (
    api_key_verifier,
    canonical_record,
    generate_api_key,
    open_automation,
    parse_record,
    seal_automation,
)
from cadrumo.adapters.persistence.storage.custody.automation_records import (
    ProtectedControlAnchor,
    SealedAutomationControl,
)
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import (
    WindowsAutomationSecretStore,
    native_automation_secret_store,
)
from cadrumo.adapters.persistence.storage.custody.automation_store import (
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
    AutomationControlStore,
)
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.zeroise import zeroise
from cadrumo.adapters.persistence.storage.master_key.active_session import get_active_master_key
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    ProfileAccessBinding,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyError,
    AutomationCustodyPort,
    AutomationGrantMaterial,
    AutomationKeyVerifier,
    NativeSecretBackend,
)
from cadrumo.application.user_profile.capsule_archive import (
    export_profile_capsule_archive,
    read_profile_capsule_archive,
)
from cadrumo.application.user_profile.capsule_restore import restore_profile_capsule_with_password
from cadrumo.application.user_profile.login_session import login_profile, logout_active_profile
from cadrumo.application.user_profile.registration import register_profile_with_credentials

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("authority_operation")]
NOW = datetime(2026, 9, 26, tzinfo=UTC)
_CREDENTIAL_INPUT = "synthetic-automation-profile-passphrase"


def changed[T: BaseModel](model: T, **values: object) -> T:
    model_type = model.__class__
    return model_type.model_validate({**{name: getattr(model, name) for name in model_type.model_fields}, **values})


@dataclass
class Subject:
    store: AutomationControlStore
    native: MemoryNativePort
    material: AutomationGrantMaterial
    credential: SecretBytes

    @property
    def dek(self) -> bytes:
        """This fixture starts with an active grant that owns unwrap material."""
        assert self.material.dek is not None
        return self.material.dek.get_secret_value()

    def publish(self, revision: int = 0, *, enabled: bool = True) -> int:
        return self.store.publish(
            grants=(self.material,), expected_revision=revision, profile_lock_generation=0, automation_enabled=enabled
        )


@pytest.fixture
def subject(tmp_path: Path) -> Iterator[Subject]:
    create, decode = profile_authority_contexts()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label="Automation test",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=create,
            profile_decode_context=decode,
        )
        profile_id = UUID(outcome.profile_id)
        password = load_committed_profile_password_material(profile_id)
        # The test-owned storage root is the ancestor of the buckets directory.
        root = password.capsule_path.parent.parent
        binding = ProfileAccessBinding(
            profile_id=profile_id,
            installation_id=uuid4(),
            os_owner_id="test-os-owner",
            custody_generation=password.envelope.password_generation,
            dek_epoch=UUID(bytes=base64.b64decode(password.envelope.dek_epoch)),
        )
        key_id, credential = generate_api_key()
        grant = AutomationGrant(
            grant_id=uuid4(),
            binding=binding,
            client_id=uuid4(),
            generation=1,
            profile_lock_generation=0,
            state=AuthorityState.ACTIVE,
            scope=AccessScope(
                operations=frozenset({"user-profile.field-mutation"}),
                actions=frozenset(AccessAction),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            valid_from=NOW - timedelta(days=1),
            expires_at=NOW + timedelta(days=364),
            unattended=True,
            allow_os_lock=False,
        )
        key = ApiKeyRecord(
            key_id=key_id,
            grant_id=grant.grant_id,
            binding=binding,
            generation=1,
            state=AuthorityState.ACTIVE,
            valid_from=grant.valid_from,
            expires_at=grant.expires_at,
        )
        material = AutomationGrantMaterial(
            grant=grant,
            keys=(AutomationKeyVerifier(key=key, verifier=api_key_verifier(credential)[1]),),
            dek=SecretBytes(get_active_master_key()),
        )
        native = MemoryNativePort()
        store = AutomationControlStore(root=root, binding=binding, secrets_store=native)
        yield Subject(store, native, material, credential)
        logout_active_profile()


def test_unlock_after_password_logout_proves_real_sentinel(subject: Subject) -> None:
    assert subject.publish() == 1
    custody: AutomationCustodyPort = subject.store
    snapshot = custody.snapshot()
    assert snapshot.grants == (subject.material.grant,)
    assert subject.material.keys[0].verifier not in snapshot.model_dump_json()
    logout_active_profile()
    dek = subject.store.unwrap(credential=subject.credential, now=NOW)
    try:
        assert bytes(dek) == subject.dek
        revision, payload = subject.store.read()
        assert revision == 1 and payload.grants[0].grant == subject.material.grant
    finally:
        zeroise(dek)
    assert not any(dek)


@pytest.mark.parametrize(
    "field,value",
    [
        ("profile_id", uuid4()),
        ("installation_id", uuid4()),
        ("os_owner_id", "other-owner"),
        ("custody_generation", 2),
        ("dek_epoch", uuid4()),
    ],
)
def test_binding_substitution_refuses(subject: Subject, field: str, value: object) -> None:
    subject.publish()
    substitute = AutomationControlStore(
        root=subject.store.root, binding=changed(subject.store.binding, **{field: value}), secrets_store=subject.native
    )
    with pytest.raises(AutomationCustodyError):
        substitute.unwrap(credential=subject.credential, now=NOW)


def test_incorrect_expired_revoked_and_suspended_authority(subject: Subject) -> None:
    subject.publish()
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=generate_api_key()[1], now=NOW)
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=subject.credential, now=subject.material.grant.expires_at)
    subject.material = changed(subject.material, grant=changed(subject.material.grant, state=AuthorityState.REVOKED))
    subject.publish(1)
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=subject.credential, now=NOW)
    subject.material = changed(subject.material, grant=changed(subject.material.grant, state=AuthorityState.ACTIVE))
    subject.publish(2, enabled=False)
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=subject.credential, now=NOW)


def test_wrong_dek_cannot_be_published(subject: Subject) -> None:
    subject.material = changed(subject.material, dek=SecretBytes(bytes(32)))
    with pytest.raises(AutomationCustodyError):
        subject.publish()
    assert not subject.native.items


def test_tampered_ciphertext_and_stale_disk_refuse(subject: Subject) -> None:
    subject.publish()
    old_pointer = (subject.store.directory / "current.json").read_bytes()
    subject.publish(1, enabled=False)
    (subject.store.directory / "current.json").write_bytes(old_pointer)
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=subject.credential, now=NOW)
    anchor = parse_record(
        ProtectedControlAnchor, subject.native.items[CONTROL_NAMESPACE, subject.store.account].get_secret_value()
    )
    (subject.store.directory / "current.json").write_bytes(canonical_record(anchor.witness))
    record_path = subject.store.directory / f"{anchor.witness.record_id}.json"
    record = parse_record(SealedAutomationControl, record_path.read_bytes())
    record_path.write_bytes(canonical_record(changed(record, ciphertext=record.ciphertext[:-4] + "AAAA")))
    with pytest.raises(AutomationCustodyError):
        subject.store.read()


@pytest.mark.parametrize(
    "namespace,committed,expected",
    [
        (WRAP_NAMESPACE, False, 1),
        (WRAP_NAMESPACE, True, 1),
        (CONTROL_NAMESPACE, False, 1),
        (CONTROL_NAMESPACE, True, 2),
    ],
)
def test_interrupted_native_publication_reconciles_exact_anchor(
    subject: Subject, namespace: str, committed: bool, expected: int
) -> None:
    subject.publish()
    subject.native.fail_write = namespace
    subject.native.commit_before_failure = committed
    with pytest.raises(AutomationCustodyError):
        subject.publish(1, enabled=False)
    subject.native.fail_write = None
    revision, payload = subject.store.read()
    assert revision == expected
    assert payload.automation_enabled is (expected == 1)
    assert not (subject.store.directory / "publication.json").exists()
    assert len([key for key in subject.native.items if key[0] == WRAP_NAMESPACE]) == 1


def test_cleanup_failure_keeps_recovery_intent_and_denies(subject: Subject) -> None:
    subject.publish()
    subject.native.fail_delete = True
    with pytest.raises(AutomationCustodyError):
        subject.publish(1, enabled=False)
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=subject.credential, now=NOW)
    assert (subject.store.directory / "publication.json").exists()
    subject.native.fail_delete = False
    assert subject.store.read()[0] == 2


def test_absent_or_unavailable_anchor_never_uses_files_as_authority(subject: Subject) -> None:
    subject.publish()
    subject.native.unavailable = True
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        subject.store.read()
    subject.native.unavailable = False
    subject.native.items.pop((CONTROL_NAMESPACE, subject.store.account))
    with pytest.raises(AutomationCustodyError):
        subject.store.read()


def test_private_material_is_not_in_files_or_representations(subject: Subject) -> None:
    subject.publish()
    raw = b"".join(path.read_bytes() for path in subject.store.directory.glob("*.json"))
    for private in (
        subject.credential.get_secret_value(),
        subject.dek,
        subject.material.keys[0].verifier.encode(),
        str(subject.material.grant.client_id).encode(),
    ):
        assert private not in raw
        assert private.decode("ascii", errors="replace") not in repr(subject.material)
    assert subject.dek not in subject.material.model_dump_json().encode()


def test_current_format_parsing_and_key_secrecy(subject: Subject) -> None:
    subject.publish()
    raw = subject.native.items[CONTROL_NAMESPACE, subject.store.account].get_secret_value()
    for malformed in (
        raw.replace(b'"schema_version":1', b'"schema_version":2'),
        raw[:-1] + b',"schema_version":1}',
        b"{}",
        b"x" * 1048577,
    ):
        with pytest.raises(AutomationCustodyError, match="invalid"):
            parse_record(ProtectedControlAnchor, malformed)
    for malformed in (b"password", subject.credential.get_secret_value() + b"=", b"cadrumo-api-v2.x.y"):
        with pytest.raises(AutomationCustodyError) as exc:
            api_key_verifier(SecretBytes(malformed))
        assert malformed.decode() not in str(exc.value)
    wrapping = SecretBytes(bytes(range(32)))
    sealed = seal_automation(subject.dek, wrapping, b"purpose-a")
    with pytest.raises(AutomationCustodyError):
        open_automation(sealed, wrapping, b"purpose-b")
    with pytest.raises(AutomationCustodyError):
        open_automation(sealed, SecretBytes(bytes(32)), b"purpose-a")


def test_backup_excludes_automation_and_restore_cannot_resurrect(subject: Subject, tmp_path: Path) -> None:
    subject.publish()
    archive = tmp_path / "profile.cadrumo-bucket.tar.gz"
    export_profile_capsule_archive(profile_id=subject.store.binding.profile_id, target=archive)
    expanded = gzip.decompress(archive.read_bytes())
    assert b"automation" not in expanded and subject.credential.get_secret_value() not in expanded
    assert str(subject.material.grant.grant_id).encode() not in expanded
    destination = tmp_path / "restored"
    _, decode = profile_authority_contexts()
    restore_profile_capsule_with_password(
        label="Restored",
        capsule=read_profile_capsule_archive(archive),
        password=_CREDENTIAL_INPUT,
        root=destination,
        profile_decode_context=decode,
    )
    restored = AutomationControlStore(root=destination, binding=subject.store.binding, secrets_store=subject.native)
    with pytest.raises(AutomationCustodyError, match="missing"):
        restored.unwrap(credential=subject.credential, now=NOW)
    subject.publish(1, enabled=False)
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=subject.credential, now=NOW)


def test_password_authentication_is_independent_of_broken_automation(subject: Subject) -> None:
    subject.publish()
    subject.native.unavailable = True
    (subject.store.directory / "current.json").write_bytes(b"broken")
    logout_active_profile()
    _, decode = profile_authority_contexts()
    result = login_profile(
        name=str(subject.store.binding.profile_id),
        passphrase_callback=lambda: _CREDENTIAL_INPUT,
        profile_decode_context=decode,
    )
    assert result.bucket_id == str(subject.store.binding.profile_id)


def test_unknown_backend_never_falls_back_to_keyring() -> None:
    with pytest.raises(AutomationCustodyError, match="unsupported"):
        native_automation_secret_store(NativeSecretBackend.LINUX_DBUS)


def test_duplicate_inventory_is_not_publishable(subject: Subject) -> None:
    with pytest.raises(ValidationError):
        subject.store.publish(
            grants=(subject.material, subject.material),
            expected_revision=0,
            profile_lock_generation=0,
            automation_enabled=True,
        )
    assert not subject.native.items


class InterruptedFileStore(AutomationControlStore):
    """Crash at one filesystem durability boundary, then allow recovery."""

    interrupt_at: str = ""
    after: bool = False

    @override
    def _write_file(self, name: str, raw: bytes, *, once: bool = False) -> None:
        door = "record" if once else name
        failing = door == self.interrupt_at
        if failing:
            self.interrupt_at = ""
        if failing and not self.after:
            raise OSError("synthetic power loss")
        super()._write_file(name, raw, once=once)
        if failing:
            raise OSError("synthetic power loss")


@pytest.mark.parametrize("door", ["record", "publication.json", "current.json"])
@pytest.mark.parametrize("after", [False, True])
def test_interrupted_filesystem_publication(subject: Subject, door: str, after: bool) -> None:
    subject.publish()
    interrupted = InterruptedFileStore(
        root=subject.store.root, binding=subject.store.binding, secrets_store=subject.native
    )
    interrupted.interrupt_at, interrupted.after = door, after
    with pytest.raises(OSError, match="synthetic power loss"):
        interrupted.publish(
            grants=(subject.material,), expected_revision=1, profile_lock_generation=0, automation_enabled=False
        )
    revision, payload = subject.store.read()
    assert revision == (2 if door == "current.json" else 1)
    assert payload.automation_enabled is (door != "current.json")


@pytest.mark.parametrize("committed", [False, True])
def test_first_publication_interruption(subject: Subject, committed: bool) -> None:
    subject.native.fail_write = CONTROL_NAMESPACE
    subject.native.commit_before_failure = committed
    with pytest.raises(AutomationCustodyError):
        subject.publish()
    subject.native.fail_write = None
    if committed:
        assert subject.store.read()[0] == 1
    else:
        with pytest.raises(AutomationCustodyError, match="missing"):
            subject.store.read()
        assert not subject.native.items
        assert subject.publish() == 1


def test_separate_wrap_keys_and_invalid_native_material(subject: Subject) -> None:
    subject.publish()
    accounts = [key for key in subject.native.items if key[0] == WRAP_NAMESPACE]
    assert len(accounts) == 1
    subject.native.items[accounts[0]] = SecretBytes(bytes(32))
    with pytest.raises(AutomationCustodyError, match="invalid"):
        subject.store.unwrap(credential=subject.credential, now=NOW)
    subject.native.items.pop(accounts[0])
    with pytest.raises(AutomationCustodyError, match="missing"):
        subject.store.unwrap(credential=subject.credential, now=NOW)


def test_two_grants_have_independent_wrapping_keys(subject: Subject) -> None:
    key_id, credential = generate_api_key()
    grant = changed(subject.material.grant, grant_id=uuid4(), client_id=uuid4())
    key = changed(subject.material.keys[0].key, key_id=key_id, grant_id=grant.grant_id)
    material = AutomationGrantMaterial(
        grant=grant,
        dek=subject.material.dek,
        keys=(AutomationKeyVerifier(key=key, verifier=api_key_verifier(credential)[1]),),
    )
    subject.store.publish(
        grants=(subject.material, material), expected_revision=0, profile_lock_generation=0, automation_enabled=True
    )
    payload = subject.store.read()[1]
    original = next(entry for entry in payload.grants if entry.grant.grant_id == subject.material.grant.grant_id)
    other = next(entry for entry in payload.grants if entry.grant.grant_id == grant.grant_id)
    first_key = subject.native.items[WRAP_NAMESPACE, subject.store.account + "/" + str(original.wrap_key_id)]
    second_key = subject.native.items[WRAP_NAMESPACE, subject.store.account + "/" + str(other.wrap_key_id)]
    assert first_key.get_secret_value() != second_key.get_secret_value()
    subject.native.items.pop((WRAP_NAMESPACE, subject.store.account + "/" + str(original.wrap_key_id)))
    with pytest.raises(AutomationCustodyError, match="missing"):
        subject.store.unwrap(credential=subject.credential, now=NOW)
    dek = subject.store.unwrap(credential=credential, now=NOW)
    assert dek == subject.dek
    zeroise(dek)


class TrackedWindowsStore(WindowsAutomationSecretStore):
    """Track only uniquely namespaced records created by this native test."""

    def __init__(self) -> None:
        self.created: set[tuple[str, str]] = set()

    @override
    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        self.created.add((namespace, account))
        super().replace(namespace, account, value)


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_windows_native_publication_replacement_and_deletion(subject: Subject) -> None:
    native = TrackedWindowsStore()
    store = AutomationControlStore(root=subject.store.root, binding=subject.store.binding, secrets_store=native)
    # The fixture supplies random installation/profile identities and a unique root.
    assert native.read(CONTROL_NAMESPACE, store.account) is None
    try:
        assert (
            store.publish(
                grants=(subject.material,), expected_revision=0, profile_lock_generation=0, automation_enabled=True
            )
            == 1
        )
        dek = store.unwrap(credential=subject.credential, now=NOW)
        try:
            assert dek == subject.dek
        finally:
            zeroise(dek)
        assert store.publish(grants=(), expected_revision=1, profile_lock_generation=0, automation_enabled=False) == 2
        assert store.read()[1].grants == ()
        with pytest.raises(AutomationCustodyError):
            store.unwrap(credential=subject.credential, now=NOW)
    finally:
        for namespace, account in native.created:
            native.delete(namespace, account)
            assert native.read(namespace, account) is None
