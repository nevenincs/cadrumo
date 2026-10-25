"""A keyless lane is usable with no stored record, takes no credential or sign-in, and hands over no secret."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from cadrumo.core.model_catalogue import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import StorageMode
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunLane,
    ModelRunLicence,
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ...domain.catalog import ProviderAuthKind, ProviderConsumer
from ...domain.record import (
    AssistantAuth,
    CredentialKind,
    CredentialState,
    ModelRoleSelection,
    ModelRoleSelectionsRecord,
    ProviderCredential,
    ProviderSettingsRecord,
    new_settings_generation,
)
from ..contracts import (
    ProviderCredentialSource,
    ProviderReadiness,
    ProviderSettingsActionAccepted,
    ProviderSettingsMode,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    ProviderStatusEntry,
    ProviderStatusReason,
)
from ..model_runs import ModelRunService
from ..resolution import (
    ProviderCredentialResolution,
    ProviderCredentialResolver,
    ProviderCredentialUnavailable,
    ProviderCredentialUnavailableReason,
    ResolvedKeyless,
)
from ..service import AssistantAuthChoice, BaseUrlChange, ProviderSettingsService
from .memory_store import MemoryModelRoleSelectionsStore, MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEYLESS_DEFAULT_URL,
    KEYLESS_LANE,
    KEYLESS_TEXT_MODEL,
    StaticCatalogSource,
    StaticLiveModels,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNKNOWN = ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.UNKNOWN)


def _service(store: MemoryProviderSettingsStore) -> ProviderSettingsService:
    return ProviderSettingsService(
        store=store, catalog_source=StaticCatalogSource(), storage_mode=StorageMode.INSTALLED
    )


def _resolve(store: MemoryProviderSettingsStore) -> ProviderCredentialResolution:
    resolver = ProviderCredentialResolver(store=store, catalog_source=StaticCatalogSource())
    return resolver.resolve(KEYLESS_LANE, ProviderConsumer.ASSISTANT)


def _entry(service: ProviderSettingsService) -> ProviderStatusEntry:
    status = service.status()
    assert isinstance(status, ProviderSettingsStatus)
    return next(entry for entry in status.providers if entry.id == KEYLESS_LANE)


class _UnreachableGateway:
    """A gateway with no running agent: the lookup needs none, and a run is refused."""

    def accepted_media(self, lane: ModelRunLane) -> tuple[ModelRunMediaKind, ...] | None:
        del lane
        return None

    def run(self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int) -> ModelRunOutput | ModelRunRefusal:
        del lane, body, deadline_seconds
        return ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)


def _record(**fields: object) -> ProviderSettingsRecord:
    values: dict[str, object] = {
        "schema_version": 1,
        "provider": KEYLESS_LANE,
        "assistant_auth": AssistantAuth.DIRECT_API,
        "credential_state": CredentialState.UNSET,
        "generation": new_settings_generation(),
        "updated_at": datetime(2026, 10, 25, 9, 0, tzinfo=UTC),
    }
    values.update(fields)
    return ProviderSettingsRecord.model_validate(values)


def test_a_keyless_lane_with_no_record_resolves_usable_without_a_secret() -> None:
    resolved = _resolve(MemoryProviderSettingsStore())

    assert isinstance(resolved, ResolvedKeyless)
    assert (resolved.provider, resolved.consumer) == (KEYLESS_LANE, ProviderConsumer.ASSISTANT)
    assert set(ResolvedKeyless.model_fields) == {"provider", "consumer", "generation"}


def test_a_keyless_lane_reads_usable_in_status_with_no_key_and_no_sign_in() -> None:
    entry = _entry(_service(MemoryProviderSettingsStore()))

    assert entry.auth_kind is ProviderAuthKind.NONE
    assert entry.available
    assert (entry.mode, entry.source, entry.readiness, entry.reason) == (
        ProviderSettingsMode.UNSET,
        ProviderCredentialSource.NONE,
        ProviderReadiness.NOT_VERIFIED,
        None,
    )
    assert not entry.credential_saved
    assert (entry.base_url, entry.default_base_url, entry.cli_state) == (None, KEYLESS_DEFAULT_URL, None)


@pytest.mark.parametrize("base_url", [BaseUrlChange.KEEP, BaseUrlChange.CLEAR, "http://127.0.0.1:41001"])
def test_a_credential_is_refused_on_a_keyless_lane_and_nothing_is_stored(base_url: str | BaseUrlChange) -> None:
    store = MemoryProviderSettingsStore()

    refused = _service(store).set_credential(
        KEYLESS_LANE,
        secret=SecretStr("synthetic-key"),
        expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        base_url=base_url,
    )

    assert refused == _UNKNOWN
    assert store.records == {}


@pytest.mark.parametrize("choice", list(AssistantAuthChoice))
def test_no_way_of_authenticating_can_be_chosen_on_a_keyless_lane(choice: AssistantAuthChoice) -> None:
    store = MemoryProviderSettingsStore()

    refused = _service(store).set_assistant_auth(
        KEYLESS_LANE, choice=choice, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )

    assert refused == _UNKNOWN
    assert store.records == {}


def test_turning_a_keyless_lane_off_refuses_it_and_turning_it_on_restores_it_unset() -> None:
    store = MemoryProviderSettingsStore()
    service = _service(store)

    off = service.turn_off(KEYLESS_LANE, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)

    assert isinstance(off, ProviderSettingsActionAccepted)
    assert (off.entry.available, off.entry.readiness, off.entry.reason) == (
        False,
        ProviderReadiness.DISABLED,
        ProviderStatusReason.TURNED_OFF,
    )
    assert _resolve(store) == ProviderCredentialUnavailable(
        provider=KEYLESS_LANE,
        consumer=ProviderConsumer.ASSISTANT,
        reason=ProviderCredentialUnavailableReason.PROVIDER_DISABLED,
    )

    on = service.turn_on(KEYLESS_LANE, expected_revision=off.entry.revision)

    assert isinstance(on, ProviderSettingsActionAccepted)
    assert on.entry.available
    assert store.records == {}
    assert isinstance(_resolve(store), ResolvedKeyless)


def test_a_credential_an_older_record_holds_never_reaches_a_keyless_lane() -> None:
    store = MemoryProviderSettingsStore()
    store.put(
        _record(
            credential_state=CredentialState.CONFIGURED,
            credential=ProviderCredential(kind=CredentialKind.API_KEY, secret=SecretStr("stale-key"), base_url=None),
        )
    )

    resolved = _resolve(store)
    entry = _entry(_service(store))

    assert isinstance(resolved, ResolvedKeyless)
    assert resolved.generation == store.records[KEYLESS_LANE].record.generation
    assert (entry.mode, entry.credential_saved, entry.base_url, entry.available) == (
        ProviderSettingsMode.UNSET,
        False,
        None,
        True,
    )


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"assistant_auth": AssistantAuth.DISABLED}, id="assistant-off"),
        pytest.param(
            {"assistant_auth": AssistantAuth.PROVIDER_SIGN_IN, "credential_state": CredentialState.DISABLED},
            id="credential-off",
        ),
    ],
)
def test_an_older_record_that_turns_a_keyless_lane_off_keeps_it_off(fields: dict[str, object]) -> None:
    store = MemoryProviderSettingsStore()
    store.put(_record(**fields))

    resolved = _resolve(store)
    entry = _entry(_service(store))

    assert isinstance(resolved, ProviderCredentialUnavailable)
    assert resolved.reason is ProviderCredentialUnavailableReason.PROVIDER_DISABLED
    assert (entry.mode, entry.available, entry.reason) == (
        ProviderSettingsMode.DISABLED,
        False,
        ProviderStatusReason.TURNED_OFF,
    )


def test_a_role_selected_on_a_keyless_lane_is_answered_without_any_stored_record() -> None:
    selections = MemoryModelRoleSelectionsStore()
    record = ModelRoleSelectionsRecord(
        schema_version=1,
        selections=(ModelRoleSelection(role=ModelRole.TEXT_EXTRACTION, lane=KEYLESS_LANE, model=KEYLESS_TEXT_MODEL),),
        generation=new_settings_generation(),
        updated_at=datetime(2026, 10, 25, 9, 0, tzinfo=UTC),
    )
    assert selections.write(record, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    store = MemoryProviderSettingsStore()
    source = StaticCatalogSource()

    runs = ModelRunService(
        selections=selections,
        resolver=ProviderCredentialResolver(store=store, catalog_source=source),
        catalog_source=source,
        live_models=StaticLiveModels(),
        gateway=_UnreachableGateway(),
    )

    assert runs.lookup("text_extraction") == ModelRunLane(
        provider_id="local",
        transport="api",
        model=KEYLESS_TEXT_MODEL,
        reads_off_host=False,
        licence=ModelRunLicence(spdx="MIT", name="Synthetic licence", digest="sha256:" + "0" * 64),
        size_bytes=1_000_000,
        vision=False,
        context_length=4096,
    )
    assert store.records == {}
