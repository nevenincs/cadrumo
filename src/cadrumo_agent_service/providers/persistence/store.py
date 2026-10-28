"""Provider and local model list record decoding over an admitted runtime's opaque encrypted custody."""

from __future__ import annotations

from threading import Lock
from typing import Final

from pydantic import ValidationError

from cadrumo.core.hashing import sha256_hex
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.contracts.extension_records import ExtensionRecordReply
from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.service_client import InstalledServiceClient

from ..application.ports import (
    AbsentLocalModelList,
    AbsentProviderRecord,
    LocalModelListRead,
    ProviderRecordRead,
    StoredLocalModelList,
    StoredProviderRecord,
    StoreGenerations,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableLocalModelList,
    UnreadableProviderRecord,
)
from ..domain.record import (
    LocalModelListRecord,
    ProviderSettingsRecord,
    local_model_list_record_document,
    parse_local_model_list_record,
    parse_provider_settings_record,
    provider_settings_record_document,
)

PROVIDER_RECORD_CAPABILITY: Final = "provider-settings"

LOCAL_MODEL_LIST_CAPABILITY: Final = "model-role-selections"
"""The model list record's own capability, apart from the provider records.

The value is the capability identity the runtime descriptor declares and the
stored records were written under. Its records generation is not the
provider-settings generation, so a list change never supersedes an agent tree
started under the provider records.
"""

LOCAL_MODEL_LIST_KEY: Final = "selections"
"""The one record the model list capability holds per profile, under its stored key."""


class SecureProviderSettingsStore:
    """Use only the exact descriptor capability and never open a profile repository."""

    def __init__(self, *, client: InstalledServiceClient) -> None:
        """Bind the store to one runtime-issued service lease."""
        self._client = client
        self._generations_guard = Lock()
        self._generations_epoch = 0
        self._generations: tuple[int, StoreGenerations] | None = None

    def invalidate_generations(self) -> None:
        """Forget the observed generations; the next observation asks the runtime again."""
        with self._generations_guard:
            self._generations_epoch += 1

    def read(
        self, provider_ids: tuple[str, ...], *, deadline: TimeoutDeadline | None = None
    ) -> tuple[ProviderRecordRead, ...] | StoreRefusal:
        """Decode bounded records while preserving absent and unreadable states."""
        values: list[ProviderRecordRead] = []
        try:
            for provider_id in provider_ids:
                reply, material = (
                    self._client.record_read(PROVIDER_RECORD_CAPABILITY, provider_id)
                    if deadline is None
                    else self._client.record_read(PROVIDER_RECORD_CAPABILITY, provider_id, timeout_deadline=deadline)
                )
                try:
                    refusal = _refusal(reply)
                    if refusal is not None:
                        return refusal
                    if reply.state == "absent":
                        values.append(AbsentProviderRecord(provider=provider_id))
                        continue
                    unreadable = UnreadableProviderRecord(provider=provider_id, revision=reply.revision)
                    if reply.state != "present" or reply.revision is None:
                        values.append(unreadable)
                        continue
                    try:
                        record = parse_provider_settings_record(bytes(material))
                    except (ValidationError, UnicodeDecodeError):
                        values.append(unreadable)
                        continue
                    values.append(
                        StoredProviderRecord(record=record, revision=reply.revision)
                        if record.provider == provider_id
                        else unreadable
                    )
                finally:
                    material[:] = b"\0" * len(material)
        except RefusalError as error:
            if deadline is not None and error.reason is RefusalCode.TIMEOUT:
                raise
            return StoreRefusal(code=StoreRefusalCode.UNKNOWN)
        except (FrontendRefusedError, OSError):
            return StoreRefusal(code=StoreRefusalCode.UNKNOWN)
        return tuple(values)

    def write(self, record: ProviderSettingsRecord, *, expected_revision: str) -> StoreRefusal | None:
        """Commit the original schema bytes through runtime repository CAS."""
        return self._write(record.provider, provider_settings_record_document(record), expected_revision)

    def delete(self, provider_id: str, *, expected_revision: str) -> StoreRefusal | None:
        """Delete only the exact revision the caller observed."""
        return self._delete(provider_id, expected_revision)

    def _write(self, object_key: str, document: bytes, expected_revision: str) -> StoreRefusal | None:
        try:
            return _record_write(self._client, PROVIDER_RECORD_CAPABILITY, object_key, document, expected_revision)
        finally:
            # Whatever the outcome, the records generation may have moved.
            self.invalidate_generations()

    def _delete(self, object_key: str, expected_revision: str) -> StoreRefusal | None:
        try:
            return _record_delete(self._client, PROVIDER_RECORD_CAPABILITY, object_key, expected_revision)
        finally:
            self.invalidate_generations()

    def observe_generations(self, *, deadline: TimeoutDeadline | None = None) -> StoreGenerations | None:
        """Observe the live lease and record generations without touching idle time.

        An observation stands until :meth:`invalidate_generations`: this store's own
        writes and deletes call it, and the service calls it for every frame the
        runtime pushes on its connection, which is how a lease or session change
        arrives. A failed observation is never kept.
        """
        with self._generations_guard:
            epoch, kept = self._generations_epoch, self._generations
        if kept is not None and kept[0] == epoch:
            return kept[1]
        observed = self._observe_generations(deadline)
        with self._generations_guard:
            if observed is not None and self._generations_epoch == epoch:
                self._generations = epoch, observed
        return observed

    def _observe_generations(self, deadline: TimeoutDeadline | None = None) -> StoreGenerations | None:
        try:
            lease = self._client.claim() if deadline is None else self._client.claim(timeout_deadline=deadline)
            if lease is None:
                return None
            binding = _lease_binding(lease)
            reply = (
                self._client.observe_generation(PROVIDER_RECORD_CAPABILITY)
                if deadline is None
                else self._client.observe_generation(PROVIDER_RECORD_CAPABILITY, timeout_deadline=deadline)
            )
            if (
                reply.state != "generation"
                or _refusal(reply) is not None
                or reply.custody_generation is None
                or reply.records_generation is None
                or self._client.lease is None
                or _lease_binding(self._client.lease) != binding
            ):
                return None
            sign_in = sha256_hex("\x1f".join((reply.custody_generation, *binding)).encode("utf-8"))
            return StoreGenerations(sign_in=sign_in, provider_settings=reply.records_generation)
        except RefusalError as error:
            if deadline is not None and error.reason is RefusalCode.TIMEOUT:
                raise
            return None
        except (FrontendRefusedError, OSError, ValidationError):
            return None


class SecureLocalModelListStore:
    """Keep the local model list in its own descriptor capability; never open a profile repository."""

    def __init__(self, *, client: InstalledServiceClient) -> None:
        """Bind the store to one runtime-issued service lease."""
        self._client = client

    def read(self) -> LocalModelListRead | StoreRefusal:
        """Decode the model list record, keeping absent and unreadable apart."""
        try:
            reply, material = self._client.record_read(LOCAL_MODEL_LIST_CAPABILITY, LOCAL_MODEL_LIST_KEY)
            try:
                refusal = _refusal(reply)
                if refusal is not None:
                    return refusal
                if reply.state == "absent":
                    return AbsentLocalModelList()
                if reply.revision is None:
                    # Every write stamps a revision, so a stored record without
                    # one is a runtime answer outside the contract, and no reset
                    # could be guarded by it.
                    return _unknown()
                unreadable = UnreadableLocalModelList(revision=reply.revision)
                if reply.state != "present":
                    return unreadable
                try:
                    record = parse_local_model_list_record(bytes(material))
                except (ValidationError, UnicodeDecodeError):
                    return unreadable
                return StoredLocalModelList(record=record, revision=reply.revision)
            finally:
                material[:] = b"\0" * len(material)
        except (RefusalError, FrontendRefusedError, OSError):
            return StoreRefusal(code=StoreRefusalCode.UNKNOWN)

    def write(self, record: LocalModelListRecord, *, expected_revision: str) -> StoreRefusal | None:
        """Commit the model list record through runtime repository CAS."""
        document = local_model_list_record_document(record)
        return _record_write(
            self._client, LOCAL_MODEL_LIST_CAPABILITY, LOCAL_MODEL_LIST_KEY, document, expected_revision
        )

    def delete(self, *, expected_revision: str) -> StoreRefusal | None:
        """Delete the model list record only at the exact revision the caller observed."""
        return _record_delete(self._client, LOCAL_MODEL_LIST_CAPABILITY, LOCAL_MODEL_LIST_KEY, expected_revision)


def _record_write(
    client: InstalledServiceClient, capability: str, object_key: str, document: bytes, expected_revision: str
) -> StoreRefusal | None:
    material = bytearray(document)
    try:
        reply = client.record_write(capability, object_key, payload=material, expected_revision=expected_revision)
        return _refusal(reply) if reply.state == "written" else _refusal(reply) or _unknown()
    except (RefusalError, FrontendRefusedError, OSError):
        return StoreRefusal(code=StoreRefusalCode.UNKNOWN)
    finally:
        material[:] = b"\0" * len(material)


def _record_delete(
    client: InstalledServiceClient, capability: str, object_key: str, expected_revision: str
) -> StoreRefusal | None:
    try:
        reply = client.record_delete(capability, object_key, expected_revision=expected_revision)
        return _refusal(reply) if reply.state == "deleted" else _refusal(reply) or _unknown()
    except (RefusalError, FrontendRefusedError, OSError):
        return StoreRefusal(code=StoreRefusalCode.UNKNOWN)


def _unknown() -> StoreRefusal:
    return StoreRefusal(code=StoreRefusalCode.UNKNOWN)


def _lease_binding(lease: ServiceLease) -> tuple[str, ...]:
    return (
        str(lease.parent_session_id),
        str(lease.runtime_boot_id),
        str(lease.profile_id),
        str(lease.connection_id),
        str(lease.lease_id),
        lease.descriptor_digest,
    )


def _refusal(reply: ExtensionRecordReply) -> StoreRefusal | None:
    if reply.state != "refused":
        return None
    if reply.refusal == "revision_conflict":
        return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
    if reply.refusal in {"profile_locked", "session_expired", "os_locked"}:
        return StoreRefusal(code=StoreRefusalCode.PROFILE_LOCKED)
    if reply.refusal in {"signed_out", "authentication_required", "session_inactive", "lease_inactive"}:
        return StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    return _unknown()
