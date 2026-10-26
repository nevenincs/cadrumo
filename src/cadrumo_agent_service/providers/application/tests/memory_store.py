"""In-memory provider-settings and selections stores that keep the ports' revision contract.

It stands in for encrypted custody so service tests isolate the service's own
decisions: every write gets a fresh revision, and a write or delete whose guard
does not match the stored revision is refused, as the secure store refuses it.
"""

from __future__ import annotations

import secrets
from typing import override

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID

from ...domain.record import ModelRoleSelectionsRecord, ProviderSettingsRecord
from ..ports import (
    AbsentModelRoleSelections,
    AbsentProviderRecord,
    ModelRoleSelectionsRead,
    ModelRoleSelectionsStore,
    ProviderRecordRead,
    ProviderSettingsStore,
    StoredModelRoleSelections,
    StoredProviderRecord,
    StoreGenerations,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableModelRoleSelections,
    UnreadableProviderRecord,
)


class MemoryProviderSettingsStore(ProviderSettingsStore):
    """Records held in memory, guarded by per-write revisions."""

    def __init__(self) -> None:
        """Start with no records."""
        self.records: dict[str, StoredProviderRecord] = {}
        self.unreadable: dict[str, str] = {}
        self.refusal: StoreRefusal | None = None

    def put(self, record: ProviderSettingsRecord) -> str:
        """Store ``record`` directly, as an earlier build would have, and return its revision."""
        revision = secrets.token_hex(32)
        self.records[record.provider] = StoredProviderRecord(record=record, revision=revision)
        return revision

    @override
    def read(self, provider_ids: tuple[str, ...]) -> tuple[ProviderRecordRead, ...] | StoreRefusal:
        if self.refusal is not None:
            return self.refusal
        reads: list[ProviderRecordRead] = []
        for provider_id in provider_ids:
            if provider_id in self.unreadable:
                reads.append(UnreadableProviderRecord(provider=provider_id, revision=self.unreadable[provider_id]))
            elif provider_id in self.records:
                reads.append(self.records[provider_id])
            else:
                reads.append(AbsentProviderRecord(provider=provider_id))
        return tuple(reads)

    def _revision(self, provider_id: str) -> str:
        if provider_id in self.unreadable:
            return self.unreadable[provider_id]
        stored = self.records.get(provider_id)
        return stored.revision if stored is not None else ABSENT_SECURE_OBJECT_REVISION_ID

    @override
    def write(self, record: ProviderSettingsRecord, *, expected_revision: str) -> StoreRefusal | None:
        if self._revision(record.provider) != expected_revision:
            return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
        self.unreadable.pop(record.provider, None)
        self.put(record)
        return None

    @override
    def delete(self, provider_id: str, *, expected_revision: str) -> StoreRefusal | None:
        if self._revision(provider_id) != expected_revision:
            return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
        self.unreadable.pop(provider_id, None)
        self.records.pop(provider_id, None)
        return None

    @override
    def observe_generations(self) -> StoreGenerations | None:
        return None


class MemoryModelRoleSelectionsStore(ModelRoleSelectionsStore):
    """The selections record held in memory, guarded by per-write revisions."""

    def __init__(self) -> None:
        """Start with no record."""
        self.stored: StoredModelRoleSelections | None = None
        self.unreadable: str | None = None
        self.refusal: StoreRefusal | None = None

    @override
    def read(self) -> ModelRoleSelectionsRead | StoreRefusal:
        if self.refusal is not None:
            return self.refusal
        if self.unreadable is not None:
            return UnreadableModelRoleSelections(revision=self.unreadable)
        return self.stored if self.stored is not None else AbsentModelRoleSelections()

    def _revision(self) -> str:
        if self.unreadable is not None:
            return self.unreadable
        return self.stored.revision if self.stored is not None else ABSENT_SECURE_OBJECT_REVISION_ID

    @override
    def write(self, record: ModelRoleSelectionsRecord, *, expected_revision: str) -> StoreRefusal | None:
        if self.refusal is not None:
            return self.refusal
        if self._revision() != expected_revision:
            return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
        self.unreadable = None
        self.stored = StoredModelRoleSelections(record=record, revision=secrets.token_hex(32))
        return None

    @override
    def delete(self, *, expected_revision: str) -> StoreRefusal | None:
        if self.refusal is not None:
            return self.refusal
        if self._revision() != expected_revision:
            return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
        self.unreadable = None
        self.stored = None
        return None
