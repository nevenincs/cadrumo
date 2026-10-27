"""The local model list record in its own capability: absent is empty, corrupt refuses, changes are guarded."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.extension_records import ExtensionRecordRefusal, ExtensionRecordReply
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...application.ports import (
    AbsentLocalModelList,
    StoredLocalModelList,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableLocalModelList,
)
from ...domain.record import (
    ListedModel,
    LocalModelListRecord,
    local_model_list_record_document,
    new_settings_generation,
    parse_local_model_list_record,
)
from ..store import (
    LOCAL_MODEL_LIST_CAPABILITY,
    LOCAL_MODEL_LIST_KEY,
    PROVIDER_RECORD_CAPABILITY,
    SecureLocalModelListStore,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_UPDATED_AT = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


class _Records:
    """Extension-record custody keyed by capability and object key, with the real reply contract and CAS."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, bytes]] = {}
        self.unreadable: set[str] = set()
        self.refusal: ExtensionRecordRefusal | None = None
        self.keys: list[str] = []
        self.capabilities: list[str] = []
        self.revisionless = False

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
            return self._reply("unreadable", revision=None if self.revisionless else row[0]), bytearray()
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


def _store(records: _Records) -> SecureLocalModelListStore:
    return SecureLocalModelListStore(client=cast(InstalledServiceClient, records))


def _record(*models: ListedModel) -> LocalModelListRecord:
    return LocalModelListRecord(
        schema_version=2, models=models, generation=new_settings_generation(), updated_at=_UPDATED_AT
    )


_ADDED = ListedModel(lane="local_api", model="custom-model:7b")
_OTHER = ListedModel(lane="local_api", model="another:1")


def _role_choices(*choices: tuple[str, str, str]) -> bytes:
    """A schema version 1 document as it was stored: the lane and model chosen per role."""
    return json.dumps(
        {
            "schema_version": 1,
            "selections": [{"role": role, "lane": lane, "model": model} for role, lane, model in choices],
            "generation": "e" * 64,
            "updated_at": "2026-10-25T09:00:00Z",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_the_record_keeps_the_capability_and_key_the_runtime_descriptor_declares() -> None:
    assert (LOCAL_MODEL_LIST_CAPABILITY, LOCAL_MODEL_LIST_KEY) == ("model-role-selections", "selections")


def test_no_stored_record_reads_as_absent_so_no_model_was_added() -> None:
    records = _Records()

    assert _store(records).read() == AbsentLocalModelList()
    assert records.keys == [LOCAL_MODEL_LIST_KEY]


def test_a_written_record_reads_back_whole_with_its_revision() -> None:
    records = _Records()
    store = _store(records)
    record = _record(_ADDED, _OTHER)

    assert store.write(record, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    read = store.read()

    assert isinstance(read, StoredLocalModelList)
    assert read.record == record
    assert read.revision == records.rows[LOCAL_MODEL_LIST_KEY][0]
    assert read.record.lane_models("local_api") == ("custom-model:7b", "another:1")
    assert read.record.lane_models("other_api") == ()


def test_a_stored_per_role_record_reads_as_the_models_it_chose_without_being_rewritten() -> None:
    records = _Records()
    stored = _role_choices(
        ("vision_transcription", "local_api", "custom-vision:1"),
        ("text_extraction", "local_api", "custom-text:1"),
        ("column_role_mapping", "local_api", "custom-text:1"),
        ("supply_nature_proposal", "example_api", "synthetic-text-1"),
    )
    records.rows[LOCAL_MODEL_LIST_KEY] = ("a" * 64, stored)

    read = _store(records).read()

    assert isinstance(read, StoredLocalModelList)
    assert read.revision == "a" * 64
    assert read.record.models == (
        ListedModel(lane="local_api", model="custom-vision:1"),
        ListedModel(lane="local_api", model="custom-text:1"),
        ListedModel(lane="example_api", model="synthetic-text-1"),
    )
    assert read.record.generation == "e" * 64
    assert records.rows[LOCAL_MODEL_LIST_KEY] == ("a" * 64, stored)


def test_a_write_or_delete_against_a_stale_revision_is_refused_and_changes_nothing() -> None:
    records = _Records()
    store = _store(records)
    assert store.write(_record(_ADDED), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    stored = records.rows[LOCAL_MODEL_LIST_KEY]

    conflict = StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
    assert store.write(_record(_OTHER), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) == conflict
    assert store.delete(expected_revision="f" * 64) == conflict
    assert records.rows[LOCAL_MODEL_LIST_KEY] == stored

    assert store.delete(expected_revision=stored[0]) is None
    assert store.read() == AbsentLocalModelList()


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"\xff\xfe",
        local_model_list_record_document(_record(_ADDED)).replace(b'"schema_version":2', b'"schema_version":3'),
        local_model_list_record_document(_record(_ADDED)).replace(b"local_api", b"Local API"),
        _role_choices(("Vision", "local_api", "custom-vision:1")),
    ],
    ids=["not-json", "not-utf8", "unknown-schema", "malformed-lane", "malformed-earlier-role"],
)
def test_a_stored_record_that_does_not_validate_is_unreadable_never_absent(payload: bytes) -> None:
    records = _Records()
    records.rows[LOCAL_MODEL_LIST_KEY] = ("a" * 64, payload)

    assert _store(records).read() == UnreadableLocalModelList(revision="a" * 64)


def test_a_record_the_runtime_reports_unreadable_stays_unreadable_with_its_revision() -> None:
    records = _Records()
    records.rows[LOCAL_MODEL_LIST_KEY] = ("b" * 64, b"{}")
    records.unreadable.add(LOCAL_MODEL_LIST_KEY)

    assert _store(records).read() == UnreadableLocalModelList(revision="b" * 64)


def test_a_lapsed_lease_refuses_the_read_rather_than_reading_as_empty() -> None:
    records = _Records()
    records.refusal = ExtensionRecordRefusal.LEASE_INACTIVE

    assert _store(records).read() == StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)


def test_a_lane_lists_a_model_at_most_once() -> None:
    with pytest.raises(ValidationError):
        _record(_ADDED, _ADDED)
    document = local_model_list_record_document(_record(_ADDED, _OTHER)).replace(b"another:1", b"custom-model:7b")
    with pytest.raises(ValidationError):
        parse_local_model_list_record(document)


def test_every_exchange_uses_the_list_capability_and_never_the_provider_records() -> None:
    """A list change must not move the provider-settings generation, so it never writes there."""
    records = _Records()
    store = _store(records)

    assert store.write(_record(_ADDED), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    read = store.read()
    assert isinstance(read, StoredLocalModelList)
    assert store.delete(expected_revision=read.revision) is None

    assert LOCAL_MODEL_LIST_CAPABILITY != PROVIDER_RECORD_CAPABILITY
    assert records.capabilities == [LOCAL_MODEL_LIST_CAPABILITY] * 3
    assert records.keys == [LOCAL_MODEL_LIST_KEY] * 3


def test_a_stored_record_reported_without_a_revision_refuses_rather_than_reading_unguarded() -> None:
    """Every unreadable record the store reports carries the revision its reset is guarded by."""
    records = _Records()
    records.rows[LOCAL_MODEL_LIST_KEY] = ("c" * 64, b"{}")
    records.unreadable.add(LOCAL_MODEL_LIST_KEY)
    records.revisionless = True

    assert _store(records).read() == StoreRefusal(code=StoreRefusalCode.UNKNOWN)
