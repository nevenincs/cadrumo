"""An in-memory provider-settings store that keeps the port's revision contract.

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
        self.selections: StoredModelRoleSelections | None = None
        self.unreadable_selections: str | None = None

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
    def read_role_selections(self) -> ModelRoleSelectionsRead | StoreRefusal:
        if self.refusal is not None:
            return self.refusal
        if self.unreadable_selections is not None:
            return UnreadableModelRoleSelections(revision=self.unreadable_selections)
        return self.selections if self.selections is not None else AbsentModelRoleSelections()

    def _selections_revision(self) -> str:
        if self.unreadable_selections is not None:
            return self.unreadable_selections
        return self.selections.revision if self.selections is not None else ABSENT_SECURE_OBJECT_REVISION_ID

    @override
    def write_role_selections(
        self, record: ModelRoleSelectionsRecord, *, expected_revision: str
    ) -> StoreRefusal | None:
        if self.refusal is not None:
            return self.refusal
        if self._selections_revision() != expected_revision:
            return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
        self.unreadable_selections = None
        self.selections = StoredModelRoleSelections(record=record, revision=secrets.token_hex(32))
        return None

    @override
    def delete_role_selections(self, *, expected_revision: str) -> StoreRefusal | None:
        if self.refusal is not None:
            return self.refusal
        if self._selections_revision() != expected_revision:
            return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
        self.unreadable_selections = None
        self.selections = None
        return None

    @override
    def observe_generations(self) -> StoreGenerations | None:
        return None
