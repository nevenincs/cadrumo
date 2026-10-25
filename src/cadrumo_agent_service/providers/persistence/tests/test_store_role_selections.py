"""The per-role selections record in its own capability: absent is none, corrupt refuses, changes are guarded."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.core.model_catalogue import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.extension_records import ExtensionRecordRefusal, ExtensionRecordReply
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...application.ports import (
    AbsentModelRoleSelections,
    StoredModelRoleSelections,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableModelRoleSelections,
)
from ...domain.record import (
    ModelRoleSelection,
    ModelRoleSelectionsRecord,
    model_role_selections_record_document,
    new_settings_generation,
    parse_model_role_selections_record,
)
from ..store import (
    MODEL_ROLE_SELECTIONS_CAPABILITY,
    MODEL_ROLE_SELECTIONS_KEY,
    PROVIDER_RECORD_CAPABILITY,
    SecureModelRoleSelectionsStore,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_UPDATED_AT = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


class _Records:
    """Extension-record custody keyed by capability and object key, with the real reply contract and CAS."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, bytes]] = {}
        self.unreadable: set[str] = set()
        self.refusal: ExtensionRecordRefusal | None = None
        self.keys: list[str] = []
        self.capabilities: list[str] = []

    def _reply(self, state: str, *, revision: str | None = None, byte_count: int = 0) -> ExtensionRecordReply:
        return ExtensionRecordReply.model_validate(
            {
                "request_id": uuid4(),
                "runtime_boot_id": uuid4(),
                "connection_id": uuid4(),
                "state": state,
                "revision": revision,
                "byte_count": byte_count,
                "refusal": self.refusal if state == "refused" else None,
            }
        )

    def _revision(self, object_key: str) -> str:
        row = self.rows.get(object_key)
        return row[0] if row is not None else ABSENT_SECURE_OBJECT_REVISION_ID

    def record_read(self, capability: str, object_key: str) -> tuple[ExtensionRecordReply, bytearray]:
        self.capabilities.append(capability)
        self.keys.append(object_key)
        if self.refusal is not None:
            return self._reply("refused"), bytearray()
        row = self.rows.get(object_key)
        if row is None:
            return self._reply("absent"), bytearray()
        if object_key in self.unreadable:
            return self._reply("unreadable", revision=row[0]), bytearray()
        return self._reply("present", revision=row[0], byte_count=len(row[1])), bytearray(row[1])

    def record_write(
        self, capability: str, object_key: str, payload: bytearray, *, expected_revision: str
    ) -> ExtensionRecordReply:
        self.capabilities.append(capability)
        self.keys.append(object_key)
        if self.refusal is not None:
            return self._reply("refused")
        if self._revision(object_key) != expected_revision:
            self.refusal = ExtensionRecordRefusal.REVISION_CONFLICT
            try:
                return self._reply("refused")
            finally:
                self.refusal = None
        revision = secrets.token_hex(32)
        self.rows[object_key] = (revision, bytes(payload))
        self.unreadable.discard(object_key)
        return self._reply("written", revision=revision)

    def record_delete(self, capability: str, object_key: str, *, expected_revision: str) -> ExtensionRecordReply:
        self.capabilities.append(capability)
        self.keys.append(object_key)
        if self._revision(object_key) != expected_revision:
            self.refusal = ExtensionRecordRefusal.REVISION_CONFLICT
            try:
                return self._reply("refused")
            finally:
                self.refusal = None
        self.rows.pop(object_key, None)
        self.unreadable.discard(object_key)
        return self._reply("deleted")


def _store(records: _Records) -> SecureModelRoleSelectionsStore:
    return SecureModelRoleSelectionsStore(client=cast(InstalledServiceClient, records))


def _record(*selections: ModelRoleSelection) -> ModelRoleSelectionsRecord:
    return ModelRoleSelectionsRecord(
        schema_version=1, selections=selections, generation=new_settings_generation(), updated_at=_UPDATED_AT
    )


_VISION = ModelRoleSelection(role=ModelRole.VISION_TRANSCRIPTION, lane="example_api", model="synthetic-vision-1")
_TEXT = ModelRoleSelection(role=ModelRole.TEXT_EXTRACTION, lane="other_cli", model="synthetic-text-1")


def test_no_stored_record_reads_as_absent_so_no_role_has_a_selection() -> None:
    records = _Records()

    assert _store(records).read() == AbsentModelRoleSelections()
    assert records.keys == [MODEL_ROLE_SELECTIONS_KEY]


def test_a_written_record_reads_back_whole_with_its_revision() -> None:
    records = _Records()
    store = _store(records)
    record = _record(_VISION, _TEXT)

    assert store.write(record, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    read = store.read()

    assert isinstance(read, StoredModelRoleSelections)
    assert read.record == record
    assert read.revision == records.rows[MODEL_ROLE_SELECTIONS_KEY][0]
    assert read.record.selection(ModelRole.VISION_TRANSCRIPTION) == _VISION
    assert read.record.selection(ModelRole.COLUMN_ROLE_MAPPING) is None


def test_a_write_or_delete_against_a_stale_revision_is_refused_and_changes_nothing() -> None:
    records = _Records()
    store = _store(records)
    assert store.write(_record(_VISION), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    stored = records.rows[MODEL_ROLE_SELECTIONS_KEY]

    conflict = StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
    assert store.write(_record(_TEXT), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) == conflict
    assert store.delete(expected_revision="f" * 64) == conflict
    assert records.rows[MODEL_ROLE_SELECTIONS_KEY] == stored

    assert store.delete(expected_revision=stored[0]) is None
    assert store.read() == AbsentModelRoleSelections()


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"\xff\xfe",
        model_role_selections_record_document(_record(_VISION)).replace(b"vision_transcription", b"unknown_role"),
        model_role_selections_record_document(_record(_VISION)).replace(b'"schema_version":1', b'"schema_version":2'),
    ],
    ids=["not-json", "not-utf8", "unknown-role", "unknown-schema"],
)
def test_a_stored_record_that_does_not_validate_is_unreadable_never_absent(payload: bytes) -> None:
    records = _Records()
    records.rows[MODEL_ROLE_SELECTIONS_KEY] = ("a" * 64, payload)

    assert _store(records).read() == UnreadableModelRoleSelections(revision="a" * 64)


def test_a_record_the_runtime_reports_unreadable_stays_unreadable_with_its_revision() -> None:
    records = _Records()
    records.rows[MODEL_ROLE_SELECTIONS_KEY] = ("b" * 64, b"{}")
    records.unreadable.add(MODEL_ROLE_SELECTIONS_KEY)

    assert _store(records).read() == UnreadableModelRoleSelections(revision="b" * 64)


def test_a_lapsed_lease_refuses_the_read_rather_than_reading_as_no_selection() -> None:
    records = _Records()
    records.refusal = ExtensionRecordRefusal.LEASE_INACTIVE

    assert _store(records).read() == StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)


def test_a_role_carries_at_most_one_selection() -> None:
    second = ModelRoleSelection(role=ModelRole.VISION_TRANSCRIPTION, lane="other_cli", model="synthetic-vision-2")
    with pytest.raises(ValidationError):
        _record(_VISION, second)
    document = model_role_selections_record_document(_record(_VISION, _TEXT)).replace(
        b"text_extraction", b"vision_transcription"
    )
    with pytest.raises(ValidationError):
        parse_model_role_selections_record(document)


def test_every_exchange_uses_the_selections_capability_and_never_the_provider_records() -> None:
    """A selection change must not move the provider-settings generation, so it never writes there."""
    records = _Records()
    store = _store(records)

    assert store.write(_record(_VISION), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    read = store.read()
    assert isinstance(read, StoredModelRoleSelections)
    assert store.delete(expected_revision=read.revision) is None

    assert MODEL_ROLE_SELECTIONS_CAPABILITY != PROVIDER_RECORD_CAPABILITY
    assert records.capabilities == [MODEL_ROLE_SELECTIONS_CAPABILITY] * 3
    assert records.keys == [MODEL_ROLE_SELECTIONS_KEY] * 3
