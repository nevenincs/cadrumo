"""Turning a lane off keeps what is saved, and turning it on restores how it authenticated."""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import StorageMode

from ...domain.catalog import ProviderConsumer
from ...domain.record import AssistantAuth, CredentialState, ProviderSettingsRecord
from ..contracts import (
    ProviderReadiness,
    ProviderSettingsActionAccepted,
    ProviderSettingsActionResult,
    ProviderSettingsMode,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    ProviderStatusEntry,
    ProviderStatusReason,
)
from ..ports import StoreRefusal, StoreRefusalCode
from ..resolution import (
    ProviderCredentialResolver,
    ProviderCredentialUnavailable,
    ProviderCredentialUnavailableReason,
    ResolvedDirectCredential,
    ResolvedProviderSignIn,
)
from ..service import AssistantAuthChoice, ProviderSettingsService
from .memory_store import MemoryProviderSettingsStore
from .synthetic_catalog import KEY_LANE, OTHER_KEY_LANE, SIGN_IN_ONLY_LANE, StaticCatalogSource, development_variable

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KEY = "synthetic-profile-key"
_ENVIRONMENT_KEY = "synthetic-environment-key"


def _environment() -> dict[str, str]:
    return {development_variable(KEY_LANE): _ENVIRONMENT_KEY}


def _service(store: MemoryProviderSettingsStore, *, storage_mode: StorageMode) -> ProviderSettingsService:
    return ProviderSettingsService(
        store=store,
        catalog_source=StaticCatalogSource(),
        environment=_environment(),
        storage_mode=storage_mode,
    )


def _resolve(store: MemoryProviderSettingsStore, lane: str, *, storage_mode: StorageMode) -> object:
    resolver = ProviderCredentialResolver(
        store=store,
        catalog_source=StaticCatalogSource(),
        environment=_environment(),
        storage_mode=storage_mode,
    )
    return resolver.resolve(lane, ProviderConsumer.ASSISTANT)


def _entry(service: ProviderSettingsService, lane: str) -> ProviderStatusEntry:
    status = service.status()
    assert isinstance(status, ProviderSettingsStatus)
    return next(entry for entry in status.providers if entry.id == lane)


def _accepted(result: ProviderSettingsActionResult) -> ProviderStatusEntry:
    assert isinstance(result, ProviderSettingsActionAccepted), result
    return result.entry


def _assert_off(entry: ProviderStatusEntry) -> None:
    assert entry.mode is ProviderSettingsMode.DISABLED
    assert entry.readiness is ProviderReadiness.DISABLED
    assert entry.reason is ProviderStatusReason.TURNED_OFF
    assert not entry.available


@pytest.mark.parametrize("storage_mode", [StorageMode.DEVELOPMENT, StorageMode.INSTALLED])
def test_turning_a_key_lane_off_keeps_the_key_and_turning_it_on_uses_it_again(storage_mode: StorageMode) -> None:
    store = MemoryProviderSettingsStore()
    service = _service(store, storage_mode=storage_mode)
    stored = _accepted(
        service.set_credential(KEY_LANE, secret=SecretStr(_KEY), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)
    )
    assert stored.credential_saved

    off = _accepted(service.turn_off(KEY_LANE, expected_revision=stored.revision))

    _assert_off(off)
    assert off.credential_saved
    record = store.records[KEY_LANE].record
    assert record.assistant_auth is AssistantAuth.DISABLED
    assert record.credential_state is CredentialState.CONFIGURED
    assert record.credential is not None
    assert record.credential.secret.get_secret_value() == _KEY
    # Off wins over the stored key and over the development environment.
    refused = _resolve(store, KEY_LANE, storage_mode=storage_mode)
    assert isinstance(refused, ProviderCredentialUnavailable)
    assert refused.reason is ProviderCredentialUnavailableReason.PROVIDER_DISABLED
    assert service.turned_off_lanes() == frozenset({("example", "api")})

    on = _accepted(service.turn_on(KEY_LANE, expected_revision=off.revision))

    assert on.mode is ProviderSettingsMode.KEY
    assert on.credential_saved
    assert on.readiness is ProviderReadiness.NOT_VERIFIED
    resolved = _resolve(store, KEY_LANE, storage_mode=storage_mode)
    assert isinstance(resolved, ResolvedDirectCredential)
    assert resolved.secret.get_secret_value() == _KEY
    assert service.turned_off_lanes() == frozenset()


def test_turning_a_sign_in_lane_back_on_restores_provider_sign_in() -> None:
    store = MemoryProviderSettingsStore()
    service = _service(store, storage_mode=StorageMode.INSTALLED)
    chosen = _accepted(
        service.set_assistant_auth(
            SIGN_IN_ONLY_LANE,
            choice=AssistantAuthChoice.PROVIDER_SIGN_IN,
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )

    off = _accepted(service.turn_off(SIGN_IN_ONLY_LANE, expected_revision=chosen.revision))

    _assert_off(off)
    assert not off.credential_saved
    refused = _resolve(store, SIGN_IN_ONLY_LANE, storage_mode=StorageMode.INSTALLED)
    assert isinstance(refused, ProviderCredentialUnavailable)
    # The lane shares its provider with the key lane; only its own transport is off.
    assert service.turned_off_lanes() == frozenset({("example", "cli")})

    on = _accepted(service.turn_on(SIGN_IN_ONLY_LANE, expected_revision=off.revision))

    assert on.mode is ProviderSettingsMode.PROVIDER_SIGN_IN
    assert store.records[SIGN_IN_ONLY_LANE].record.assistant_auth is AssistantAuth.PROVIDER_SIGN_IN
    assert isinstance(_resolve(store, SIGN_IN_ONLY_LANE, storage_mode=StorageMode.INSTALLED), ResolvedProviderSignIn)


def test_a_lane_turned_off_with_nothing_saved_turns_back_on_as_unset() -> None:
    store = MemoryProviderSettingsStore()
    service = _service(store, storage_mode=StorageMode.DEVELOPMENT)
    unset = _entry(service, KEY_LANE)
    assert unset.mode is ProviderSettingsMode.UNSET
    assert not unset.credential_saved

    off = _accepted(service.turn_off(KEY_LANE, expected_revision=unset.revision))

    _assert_off(off)
    assert store.records[KEY_LANE].record.credential_state is CredentialState.UNSET
    # Off also blocks the development fallback.
    assert isinstance(_resolve(store, KEY_LANE, storage_mode=StorageMode.DEVELOPMENT), ProviderCredentialUnavailable)

    on = _accepted(service.turn_on(KEY_LANE, expected_revision=off.revision))

    assert on.mode is ProviderSettingsMode.UNSET
    assert on.revision == ABSENT_SECURE_OBJECT_REVISION_ID
    assert KEY_LANE not in store.records
    resolved = _resolve(store, KEY_LANE, storage_mode=StorageMode.DEVELOPMENT)
    assert isinstance(resolved, ResolvedDirectCredential)
    assert resolved.secret.get_secret_value() == _ENVIRONMENT_KEY


def test_a_record_an_earlier_build_removed_still_reads_off_and_turns_on_as_unset() -> None:
    store = MemoryProviderSettingsStore()
    revision = store.put(
        ProviderSettingsRecord.model_validate_json(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": OTHER_KEY_LANE,
                    "assistant_auth": "direct_api",
                    "credential_state": "disabled",
                    "generation": "a" * 64,
                    "updated_at": "2026-10-18T00:00:00Z",
                }
            )
        )
    )
    service = _service(store, storage_mode=StorageMode.INSTALLED)

    _assert_off(_entry(service, OTHER_KEY_LANE))
    assert service.turned_off_lanes() == frozenset({("other", "api")})

    on = _accepted(service.turn_on(OTHER_KEY_LANE, expected_revision=revision))

    assert on.mode is ProviderSettingsMode.UNSET
    assert OTHER_KEY_LANE not in store.records


def test_turning_on_a_lane_that_is_not_off_is_refused_and_changes_nothing() -> None:
    store = MemoryProviderSettingsStore()
    service = _service(store, storage_mode=StorageMode.INSTALLED)
    absent = service.turn_on(KEY_LANE, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)
    assert absent == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.UNKNOWN)
    stored = _accepted(
        service.set_credential(KEY_LANE, secret=SecretStr(_KEY), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)
    )

    refused = service.turn_on(KEY_LANE, expected_revision=stored.revision)

    assert refused == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.UNKNOWN)
    assert store.records[KEY_LANE].revision == stored.revision


def test_turning_on_or_off_with_a_stale_revision_is_a_conflict() -> None:
    store = MemoryProviderSettingsStore()
    service = _service(store, storage_mode=StorageMode.INSTALLED)
    stored = _accepted(
        service.set_credential(KEY_LANE, secret=SecretStr(_KEY), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)
    )
    off = _accepted(service.turn_off(KEY_LANE, expected_revision=stored.revision))

    conflict = ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.REVISION_CONFLICT)
    assert service.turn_on(KEY_LANE, expected_revision=stored.revision) == conflict
    assert service.turn_off(KEY_LANE, expected_revision=stored.revision) == conflict
    assert store.records[KEY_LANE].revision == off.revision


def test_an_unreadable_record_is_not_turned_off_over() -> None:
    store = MemoryProviderSettingsStore()
    store.unreadable[KEY_LANE] = "c" * 64
    service = _service(store, storage_mode=StorageMode.INSTALLED)

    refused = service.turn_off(KEY_LANE, expected_revision="c" * 64)

    assert refused == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.UNKNOWN)
    assert store.unreadable == {KEY_LANE: "c" * 64}
    assert service.turned_off_lanes() == frozenset()


def test_turned_off_lanes_is_unknown_when_the_store_refuses() -> None:
    store = MemoryProviderSettingsStore()
    store.refusal = StoreRefusal(code=StoreRefusalCode.PROFILE_LOCKED)

    assert _service(store, storage_mode=StorageMode.INSTALLED).turned_off_lanes() is None
