"""Observed generations stand until a push or this store's own change says they may have moved."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import uuid4

import pytest

from cadrumo_client.contracts.extension_records import ExtensionRecordReply
from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.transport.service_client import InstalledServiceClient

from ..store import SecureProviderSettingsStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _Runtime:
    """Count the round trips an observation costs; replies follow the real contracts."""

    def __init__(self) -> None:
        self.claims = 0
        self.generation_reads = 0
        self.records_generation = "1" * 64
        self.while_reading: Callable[[], None] | None = None
        self.lease: ServiceLease | None = ServiceLease(
            lease_id=uuid4(),
            session_id=uuid4(),
            profile_id=uuid4(),
            parent_session_id=uuid4(),
            descriptor_digest="2" * 64,
            service_id="cadrumo-agent-service",
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
        )

    def claim(self) -> ServiceLease | None:
        self.claims += 1
        return self.lease

    def observe_generation(self, capability: str) -> ExtensionRecordReply:
        assert capability == "provider-settings"
        self.generation_reads += 1
        if self.while_reading is not None:
            self.while_reading()
            self.while_reading = None
        assert self.lease is not None
        return ExtensionRecordReply(
            request_id=uuid4(),
            runtime_boot_id=self.lease.runtime_boot_id,
            connection_id=self.lease.connection_id,
            state="generation",
            custody_generation="c" * 64,
            records_generation=self.records_generation,
        )

    def record_delete(self, capability: str, object_key: str, *, expected_revision: str) -> ExtensionRecordReply:
        raise OSError("synthetic lost connection")


def _store(runtime: _Runtime) -> SecureProviderSettingsStore:
    return SecureProviderSettingsStore(client=cast(InstalledServiceClient, runtime))


def test_an_observation_stands_until_it_is_invalidated() -> None:
    runtime = _Runtime()
    store = _store(runtime)
    first = store.observe_generations()
    assert first is not None and first.provider_settings == "1" * 64
    assert store.observe_generations() == first
    assert (runtime.claims, runtime.generation_reads) == (1, 1), "a repeated observation must not ask the runtime"

    runtime.records_generation = "2" * 64
    store.invalidate_generations()
    second = store.observe_generations()
    assert second is not None and second.provider_settings == "2" * 64
    assert (runtime.claims, runtime.generation_reads) == (2, 2)


def test_a_push_during_an_observation_keeps_it_from_standing() -> None:
    runtime = _Runtime()
    store = _store(runtime)
    runtime.while_reading = store.invalidate_generations
    assert store.observe_generations() is not None
    assert store.observe_generations() is not None
    assert runtime.generation_reads == 2, "an observation overtaken by a push is never kept"


def test_a_failed_observation_is_never_kept_and_a_change_of_this_store_invalidates() -> None:
    runtime = _Runtime()
    store = _store(runtime)
    runtime.lease = None
    assert store.observe_generations() is None
    assert store.observe_generations() is None
    assert runtime.claims == 2

    runtime.lease = ServiceLease.model_validate(
        {
            "lease_id": uuid4(),
            "session_id": uuid4(),
            "profile_id": uuid4(),
            "parent_session_id": uuid4(),
            "descriptor_digest": "2" * 64,
            "service_id": "cadrumo-agent-service",
            "runtime_boot_id": uuid4(),
            "connection_id": uuid4(),
        }
    )
    assert store.observe_generations() is not None
    reads = runtime.generation_reads
    # Even a delete whose outcome is unknown may have moved the records generation.
    assert store.delete("synthetic-provider", expected_revision="0" * 64) is not None
    assert store.observe_generations() is not None
    assert runtime.generation_reads == reads + 1
