"""Provider record decoding over an admitted runtime's opaque encrypted custody."""

from __future__ import annotations

from typing import Final

from pydantic import ValidationError

from cadrumo.core.hashing import sha256_hex
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.extension_records import ExtensionRecordReply
from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.service_client import InstalledServiceClient

from ..application.ports import (
    AbsentProviderRecord,
    ProviderRecordRead,
    StoredProviderRecord,
    StoreGenerations,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableProviderRecord,
)
from ..domain.record import ProviderSettingsRecord, parse_provider_settings_record, provider_settings_record_document

PROVIDER_RECORD_CAPABILITY: Final = "provider-settings"


class SecureProviderSettingsStore:
    """Use only the exact descriptor capability and never open a profile repository."""

    def __init__(self, *, client: InstalledServiceClient) -> None:
        """Bind the store to one runtime-issued service lease."""
        self._client = client

    def read(self, provider_ids: tuple[str, ...]) -> tuple[ProviderRecordRead, ...] | StoreRefusal:
        """Decode bounded records while preserving absent and unreadable states."""
        values: list[ProviderRecordRead] = []
        try:
            for provider_id in provider_ids:
                reply, material = self._client.record_read(PROVIDER_RECORD_CAPABILITY, provider_id)
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
        except (RefusalError, FrontendRefusedError, OSError):
            return StoreRefusal(code=StoreRefusalCode.UNKNOWN)
        return tuple(values)

    def write(self, record: ProviderSettingsRecord, *, expected_revision: str) -> StoreRefusal | None:
        """Commit the original schema bytes through runtime repository CAS."""
        material = bytearray(provider_settings_record_document(record))
        try:
            reply = self._client.record_write(
                PROVIDER_RECORD_CAPABILITY, record.provider, payload=material, expected_revision=expected_revision
            )
            return _refusal(reply) if reply.state == "written" else _refusal(reply) or _unknown()
        except (RefusalError, FrontendRefusedError, OSError):
            return StoreRefusal(code=StoreRefusalCode.UNKNOWN)
        finally:
            material[:] = b"\0" * len(material)

    def delete(self, provider_id: str, *, expected_revision: str) -> StoreRefusal | None:
        """Delete only the exact revision the caller observed."""
        try:
            reply = self._client.record_delete(
                PROVIDER_RECORD_CAPABILITY, provider_id, expected_revision=expected_revision
            )
            return _refusal(reply) if reply.state == "deleted" else _refusal(reply) or _unknown()
        except (RefusalError, FrontendRefusedError, OSError):
            return StoreRefusal(code=StoreRefusalCode.UNKNOWN)

    def observe_generations(self) -> StoreGenerations | None:
        """Observe the live lease and record generations without touching idle time."""
        try:
            lease = self._client.claim()
            if lease is None:
                return None
            binding = _lease_binding(lease)
            reply = self._client.observe_generation(PROVIDER_RECORD_CAPABILITY)
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
        except (RefusalError, FrontendRefusedError, OSError, ValidationError):
            return None


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


def build_provider_settings_store(*, client: InstalledServiceClient) -> SecureProviderSettingsStore:
    """Construct the service's opaque runtime custody adapter."""
    return SecureProviderSettingsStore(client=client)
