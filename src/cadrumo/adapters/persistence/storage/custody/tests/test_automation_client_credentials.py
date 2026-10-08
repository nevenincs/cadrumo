"""Exact client credential custody over an explicit synthetic native store."""

from __future__ import annotations

import base64
import json
import secrets
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import (
    MAX_CLIENT_CREDENTIAL_BYTES,
    NativeClientCredentialStore,
)
from cadrumo.adapters.persistence.storage.custody.automation_crypto import (
    API_KEY_PREFIX,
    CustodyAutomationKeyIssuer,
)
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import (
    CLIENT_NAMESPACE,
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.hashing import canonical_json_bytes

_REVIEW_DIGEST = "a" * 64

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _binding() -> ProfileAccessBinding:
    return ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-native-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )


def _store(
    native: MemoryNativePort,
    binding: ProfileAccessBinding,
    *,
    client_id: UUID,
    destination_id: UUID,
) -> NativeClientCredentialStore:
    return NativeClientCredentialStore(
        secrets_store=native,
        binding=binding,
        client_id=client_id,
        destination_id=destination_id,
    )


def _alternate_secret(key_id: UUID) -> SecretBytes:
    encoded = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=")
    credential = SecretBytes(API_KEY_PREFIX.encode() + b"." + str(key_id).encode() + b"." + encoded)
    assert CustodyAutomationKeyIssuer.verifier(credential)[0] == key_id
    return credential


def test_exact_native_reference_round_trips_idempotently_without_public_secret() -> None:
    native = MemoryNativePort()
    binding, client_id, destination_id = _binding(), uuid4(), uuid4()
    store = _store(native, binding, client_id=client_id, destination_id=destination_id)
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()

    metadata = store.replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    assert (metadata.credential_reference, metadata.profile_id, metadata.client_id, metadata.destination_id) == (
        reference,
        binding.profile_id,
        client_id,
        destination_id,
    )
    assert (metadata.grant_id, metadata.key_id) == (grant_id, key_id)
    assert metadata.review_digest == _REVIEW_DIGEST
    assert store.inspect(credential_reference=reference) == metadata
    assert credential.get_secret_value() not in repr(metadata).encode()
    assert (
        store.read(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
        == credential
    )
    stored = native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value()
    assert 0 < len(stored) <= MAX_CLIENT_CREDENTIAL_BYTES
    assert (CONTROL_NAMESPACE, str(reference)) not in native.items
    assert (WRAP_NAMESPACE, str(reference)) not in native.items

    repeated = store.replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    assert repeated == metadata
    assert native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value() == stored

    with pytest.raises(AutomationCustodyError, match="conflict"):
        store.replace(
            credential_reference=reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=_REVIEW_DIGEST,
            credential=_alternate_secret(key_id),
        )
    assert native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value() == stored
    store.delete(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
    store.delete(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
    with pytest.raises(AutomationCustodyError, match="missing"):
        store.read(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)


def test_fresh_process_can_resolve_only_one_current_reference_and_recheck_secret() -> None:
    class TracedNativePort(MemoryNativePort):
        def __init__(self) -> None:
            super().__init__()
            self.reads: list[tuple[str, str]] = []

        @override
        def read(self, namespace: str, account: str) -> SecretBytes | None:
            self.reads.append((namespace, account))
            return super().read(namespace, account)

    native = TracedNativePort()
    binding, client_id, destination_id = _binding(), uuid4(), uuid4()
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    _store(native, binding, client_id=client_id, destination_id=destination_id).replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    native.reads.clear()

    handle = NativeClientCredentialStore.resolve_reference(
        credential_reference=reference, binding=binding, secrets_store=native
    )
    assert handle.metadata.profile_id == binding.profile_id
    assert (handle.metadata.client_id, handle.metadata.destination_id) == (client_id, destination_id)
    assert (handle.metadata.grant_id, handle.metadata.key_id) == (grant_id, key_id)
    assert handle.read() == credential
    assert native.reads == [(CLIENT_NAMESPACE, str(reference))] * 2
    assert credential.get_secret_value() not in repr(handle).encode()
    assert "_store" not in repr(handle)


@pytest.mark.parametrize(
    "changed",
    ("profile_id", "installation_id", "os_owner_id", "custody_generation", "dek_epoch"),
)
def test_reference_resolution_refuses_wrong_current_custody(changed: str) -> None:
    native = MemoryNativePort()
    binding = _binding()
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    _store(native, binding, client_id=uuid4(), destination_id=uuid4()).replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    values = binding.model_dump(mode="python")
    values[changed] = (
        "different-owner" if changed == "os_owner_id" else 2 if changed == "custody_generation" else uuid4()
    )
    other = ProfileAccessBinding.model_validate(values)
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        NativeClientCredentialStore.resolve_reference(
            credential_reference=reference, binding=other, secrets_store=native
        )
    assert native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value()


def test_reference_handle_refuses_missing_replacement_and_unavailable_native_item() -> None:
    native = MemoryNativePort()
    binding = _binding()
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    _store(native, binding, client_id=uuid4(), destination_id=uuid4()).replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    with pytest.raises(AutomationCustodyError, match="missing"):
        NativeClientCredentialStore.resolve_reference(
            credential_reference=uuid4(), binding=binding, secrets_store=native
        )
    handle = NativeClientCredentialStore.resolve_reference(
        credential_reference=reference, binding=binding, secrets_store=native
    )
    raw = native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value()
    replacement = json.loads(raw)
    replacement["secret_b64"] = base64.b64encode(_alternate_secret(key_id).get_secret_value()).decode("ascii")
    native.items[(CLIENT_NAMESPACE, str(reference))] = SecretBytes(canonical_json_bytes(replacement))
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        handle.read()
    native.unavailable = True
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        handle.read()
    native.unavailable = False
    native.items.pop((CLIENT_NAMESPACE, str(reference)))
    with pytest.raises(AutomationCustodyError, match="missing"):
        handle.read()


def test_reference_resolver_refuses_rebound_identity_and_invalid_issuer_codec() -> None:
    native = MemoryNativePort()
    binding = _binding()
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    _store(native, binding, client_id=uuid4(), destination_id=uuid4()).replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    raw = native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value()
    rebound = json.loads(raw)
    rebound["credential_reference"] = str(uuid4())
    native.items[(CLIENT_NAMESPACE, str(reference))] = SecretBytes(canonical_json_bytes(rebound))
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        NativeClientCredentialStore.resolve_reference(
            credential_reference=reference, binding=binding, secrets_store=native
        )

    invalid = json.loads(raw)
    invalid["secret_b64"] = base64.b64encode(b"invalid-candidate").decode("ascii")
    native.items[(CLIENT_NAMESPACE, str(reference))] = SecretBytes(canonical_json_bytes(invalid))
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        NativeClientCredentialStore.resolve_reference(
            credential_reference=reference, binding=binding, secrets_store=native
        )


@pytest.mark.parametrize(
    "change",
    ("profile_id", "installation_id", "os_owner_id", "custody_generation", "dek_epoch", "client_id", "destination_id"),
)
def test_rebound_binding_or_client_cannot_read_replace_or_delete_existing_reference(change: str) -> None:
    native = MemoryNativePort()
    binding, client_id, destination_id = _binding(), uuid4(), uuid4()
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    original = _store(native, binding, client_id=client_id, destination_id=destination_id)
    original.replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    stored = native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value()

    if change == "client_id":
        client_id = uuid4()
    elif change == "destination_id":
        destination_id = uuid4()
    else:
        values = binding.model_dump(mode="python")
        values[change] = (
            "another-native-owner" if change == "os_owner_id" else 2 if change == "custody_generation" else uuid4()
        )
        binding = ProfileAccessBinding.model_validate(values)
    rebound = _store(native, binding, client_id=client_id, destination_id=destination_id)
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        rebound.read(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
    with pytest.raises(AutomationCustodyError, match="conflict"):
        rebound.replace(
            credential_reference=reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=_REVIEW_DIGEST,
            credential=credential,
        )
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        rebound.delete(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
    assert native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value() == stored


def test_reference_rejects_wrong_grant_key_corruption_and_oversize_before_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = MemoryNativePort()
    store = _store(native, _binding(), client_id=uuid4(), destination_id=uuid4())
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    store.replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    stored = native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value()
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        store.read(credential_reference=reference, grant_id=uuid4(), key_id=key_id, review_digest=_REVIEW_DIGEST)
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        store.read(credential_reference=reference, grant_id=grant_id, key_id=uuid4(), review_digest=_REVIEW_DIGEST)
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        store.read(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest="b" * 64)
    with pytest.raises(AutomationCustodyError, match="conflict"):
        store.replace(
            credential_reference=reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest="b" * 64,
            credential=credential,
        )
    with pytest.raises(AutomationCustodyError, match="conflict"):
        store.replace(
            credential_reference=reference,
            grant_id=uuid4(),
            key_id=key_id,
            review_digest=_REVIEW_DIGEST,
            credential=credential,
        )
    assert native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value() == stored

    native.items[(CLIENT_NAMESPACE, str(reference))] = SecretBytes(b'{"schema_version":2}')
    with pytest.raises(AutomationCustodyError, match="invalid"):
        store.read(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
    with pytest.raises(AutomationCustodyError, match="invalid"):
        store.replace(
            credential_reference=reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=_REVIEW_DIGEST,
            credential=credential,
        )
    assert native.items[(CLIENT_NAMESPACE, str(reference))].get_secret_value() == b'{"schema_version":2}'

    empty = uuid4()
    with monkeypatch.context() as patch:
        patch.setattr(
            "cadrumo.adapters.persistence.storage.custody.automation_client_credentials.MAX_CLIENT_CREDENTIAL_BYTES", 1
        )
        with pytest.raises(AutomationCustodyError, match="invalid"):
            store.replace(
                credential_reference=empty,
                grant_id=grant_id,
                key_id=key_id,
                review_digest=_REVIEW_DIGEST,
                credential=credential,
            )
    assert (CLIENT_NAMESPACE, str(empty)) not in native.items


@pytest.mark.parametrize("committed", [False, True])
def test_ambiguous_native_write_reconciles_only_exact_committed_item(committed: bool) -> None:
    native = MemoryNativePort()
    store = _store(native, _binding(), client_id=uuid4(), destination_id=uuid4())
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    native.fail_write = CLIENT_NAMESPACE
    native.commit_before_failure = committed
    if committed:
        metadata = store.replace(
            credential_reference=reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=_REVIEW_DIGEST,
            credential=credential,
        )
        assert metadata.key_id == key_id
        assert (
            store.read(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
            == credential
        )
    else:
        with pytest.raises(AutomationCustodyError) as error:
            store.replace(
                credential_reference=reference,
                grant_id=grant_id,
                key_id=key_id,
                review_digest=_REVIEW_DIGEST,
                credential=credential,
            )
        assert error.value.reason is AutomationCustodyCode.UNAVAILABLE
        assert (CLIENT_NAMESPACE, str(reference)) not in native.items
        native.fail_write = None
        store.replace(
            credential_reference=reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=_REVIEW_DIGEST,
            credential=credential,
        )


def test_ambiguous_native_delete_rechecks_absence_without_trusting_exception() -> None:
    class DeleteAfterCommit(MemoryNativePort):
        @override
        def delete(self, namespace: str, account: str) -> None:
            self.items.pop((namespace, account), None)
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    native = DeleteAfterCommit()
    store = _store(native, _binding(), client_id=uuid4(), destination_id=uuid4())
    reference, grant_id = uuid4(), uuid4()
    key_id, credential = CustodyAutomationKeyIssuer.generate()
    store.replace(
        credential_reference=reference,
        grant_id=grant_id,
        key_id=key_id,
        review_digest=_REVIEW_DIGEST,
        credential=credential,
    )
    store.delete(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
    with pytest.raises(AutomationCustodyError, match="missing"):
        store.read(credential_reference=reference, grant_id=grant_id, key_id=key_id, review_digest=_REVIEW_DIGEST)
