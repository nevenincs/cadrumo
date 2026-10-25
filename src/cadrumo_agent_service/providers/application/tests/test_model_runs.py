"""Which lane answers a tax model run: the person's selection for its role, through the real resolver."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import override

import pytest
from pydantic import SecretStr

from cadrumo.core.model_catalogue import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import StorageMode
from cadrumo_client.contracts.model_runs import (
    ModelRunAttachment,
    ModelRunBody,
    ModelRunConsentBinding,
    ModelRunHeader,
    ModelRunLane,
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
    ModelRunSelectedModel,
)

from ....adapters.agent_background_runs import HostedBackgroundRuns
from ...domain.catalog import ProviderCatalog, parse_provider_catalog
from ...domain.record import ModelRoleSelection, ModelRoleSelectionsRecord, new_settings_generation
from ..contracts import ProviderSettingsActionAccepted, ProviderSettingsStatus
from ..model_runs import ModelRunService
from ..ports import ModelRoleSelectionsRead, ProviderRecordRead, StoreRefusal, StoreRefusalCode
from ..resolution import ProviderCredentialResolver
from ..service import ProviderSettingsService
from .memory_store import MemoryModelRoleSelectionsStore, MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEY_LANE,
    MISSING_LANE,
    OTHER_KEY_LANE,
    SIGN_IN_ONLY_LANE,
    ProvidedProviderCatalogSource,
    synthetic_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFAULT_MODELS = {KEY_LANE: "example-model-a", SIGN_IN_ONLY_LANE: "example-model-c", OTHER_KEY_LANE: "other-model"}
"""Catalogue defaults on three lanes, so a test can show the lookup never reads one."""


def _catalog_source() -> ProvidedProviderCatalogSource:
    """The synthetic catalog, with a default model on three lanes, through the real parser."""
    document = json.loads(synthetic_document())
    for lane in document["providers"]:
        if lane["id"] in _DEFAULT_MODELS:
            lane["default_model"] = _DEFAULT_MODELS[lane["id"]]
    return ProvidedProviderCatalogSource(parse_provider_catalog(json.dumps(document)))


class _RecordingGateway:
    def __init__(self) -> None:
        self.runs: list[tuple[ModelRunLane, ModelRunBody, int]] = []
        self.accepts: tuple[ModelRunMediaKind, ...] | None = None
        self.media_asked: list[tuple[str, str]] = []

    def accepted_media(self, lane: ModelRunLane) -> tuple[ModelRunMediaKind, ...] | None:
        self.media_asked.append((lane.provider_id, lane.transport))
        return self.accepts

    def run(self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int) -> ModelRunOutput | ModelRunRefusal:
        self.runs.append((lane, body, deadline_seconds))
        return ModelRunOutput(
            text="{}", provider_id=lane.provider_id, transport=lane.transport, model=lane.model, agent_version="t"
        )


def _harness(
    store: MemoryProviderSettingsStore, selections: MemoryModelRoleSelectionsStore
) -> tuple[ModelRunService, ProviderSettingsService, _RecordingGateway]:
    source = _catalog_source()
    gateway = _RecordingGateway()
    resolver = ProviderCredentialResolver(store=store, catalog_source=source)
    settings = ProviderSettingsService(store=store, catalog_source=source, storage_mode=StorageMode.INSTALLED)
    runs = ModelRunService(selections=selections, resolver=resolver, catalog_source=source, gateway=gateway)
    return runs, settings, gateway


def _select(store: MemoryModelRoleSelectionsStore, *selections: tuple[ModelRole, str, str]) -> None:
    record = ModelRoleSelectionsRecord(
        schema_version=1,
        selections=tuple(ModelRoleSelection(role=role, lane=lane, model=model) for role, lane, model in selections),
        generation=new_settings_generation(),
        updated_at=datetime(2026, 10, 25, 9, 0, tzinfo=UTC),
    )
    expected = store.stored.revision if store.stored is not None else ABSENT_SECURE_OBJECT_REVISION_ID
    assert store.write(record, expected_revision=expected) is None


def _revision(settings: ProviderSettingsService, lane: str) -> str:
    status = settings.status()
    assert isinstance(status, ProviderSettingsStatus)
    return next(entry.revision for entry in status.providers if entry.id == lane)


def _turn_off(settings: ProviderSettingsService, lane: str) -> None:
    assert isinstance(
        settings.turn_off(lane, expected_revision=_revision(settings, lane)), ProviderSettingsActionAccepted
    )


def _store_key(settings: ProviderSettingsService, lane: str) -> None:
    stored = settings.set_credential(
        lane, secret=SecretStr("synthetic-key"), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )
    assert isinstance(stored, ProviderSettingsActionAccepted)


def _header(*, consent: ModelRunConsentBinding | None = None) -> ModelRunHeader:
    return ModelRunHeader(role="text_extraction", deadline_seconds=30, consent=consent)


_BODY = ModelRunBody(prompt="Read this invoice.", max_output_tokens=64)
_NO_SELECTION = ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
_LANE_UNAVAILABLE = ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)


def test_with_no_selection_every_role_refuses_although_reachable_lanes_declare_defaults() -> None:
    """No fallback: a reachable lane with a catalogue default is never chosen for an unselected role."""
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, settings, gateway = _harness(store, selections)
    _store_key(settings, KEY_LANE)

    for role in ModelRole:
        assert runs.lookup(role.value) == _NO_SELECTION
    assert runs.run(_header(), _BODY) == _NO_SELECTION
    assert gateway.runs == []


def test_each_role_gets_the_lane_and_model_selected_for_it() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, settings, _ = _harness(store, selections)
    _store_key(settings, KEY_LANE)
    _select(
        selections,
        (ModelRole.TEXT_EXTRACTION, KEY_LANE, "synthetic-text-1"),
        (ModelRole.VISION_TRANSCRIPTION, SIGN_IN_ONLY_LANE, "synthetic-vision-1"),
    )

    assert runs.lookup("text_extraction") == ModelRunLane(
        provider_id="example", transport="api", model="synthetic-text-1"
    )
    assert runs.lookup("vision_transcription") == ModelRunLane(
        provider_id="example", transport="cli", model="synthetic-vision-1"
    )


def test_a_role_without_a_selection_refuses_while_other_roles_are_selected() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, _ = _harness(store, selections)
    _select(selections, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))

    assert runs.lookup("column_role_mapping") == _NO_SELECTION
    assert runs.lookup("supply_nature_proposal") == _NO_SELECTION
    assert runs.lookup("vision_transcription") == _NO_SELECTION


def test_a_role_outside_the_vocabulary_refuses_as_unknown_not_as_unselected() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, _ = _harness(store, selections)
    _select(selections, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))

    assert runs.lookup("unknown_role") == ModelRunRefusal(code=ModelRunRefusalCode.UNKNOWN_ROLE)
    assert runs.run(ModelRunHeader(role="unknown_role", deadline_seconds=30), _BODY) == ModelRunRefusal(
        code=ModelRunRefusalCode.UNKNOWN_ROLE
    )


def test_a_selected_lane_turned_off_refuses_and_no_other_lane_is_used() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, settings, gateway = _harness(store, selections)
    _store_key(settings, OTHER_KEY_LANE)
    _select(selections, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    _turn_off(settings, SIGN_IN_ONLY_LANE)

    assert runs.lookup("text_extraction") == _LANE_UNAVAILABLE
    assert runs.run(_header(), _BODY) == _LANE_UNAVAILABLE
    assert gateway.runs == []


def test_a_selected_key_lane_with_no_stored_key_refuses_as_unavailable() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, _ = _harness(store, selections)
    _select(selections, (ModelRole.TEXT_EXTRACTION, KEY_LANE, "synthetic-text-1"))

    assert runs.lookup("text_extraction") == _LANE_UNAVAILABLE


def test_a_selected_lane_the_agent_no_longer_reports_refuses_as_unavailable() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, _ = _harness(store, selections)
    _select(selections, (ModelRole.TEXT_EXTRACTION, MISSING_LANE, "synthetic-text-1"))

    assert runs.lookup("text_extraction") == _LANE_UNAVAILABLE


def test_an_unreadable_selections_record_refuses_every_role_rather_than_reading_as_none() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, _ = _harness(store, selections)
    selections.unreadable = "c" * 64

    for role in ModelRole:
        assert runs.lookup(role.value) == _LANE_UNAVAILABLE


def test_a_profile_that_is_not_signed_in_refuses_as_such() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    selections.refusal = StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    runs, _, gateway = _harness(store, selections)

    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert gateway.runs == []


def test_a_run_whose_consent_names_another_lane_is_refused_before_it_is_sent() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, gateway = _harness(store, selections)
    _select(selections, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    consent = ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id="example", transport="api", model="synthetic-text-1"
    )

    assert runs.run(_header(consent=consent), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
    assert gateway.runs == []


def test_a_run_whose_consent_names_its_lane_goes_to_the_gateway_on_that_lane() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, gateway = _harness(store, selections)
    _select(selections, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    consent = ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id="example", transport="cli", model="synthetic-text-1"
    )

    output = runs.run(_header(consent=consent), _BODY)

    assert isinstance(output, ModelRunOutput)
    ((lane, body, deadline),) = gateway.runs
    assert consent.matches(lane)
    assert body == _BODY
    assert deadline == 30


def test_the_lookup_carries_the_media_the_agent_reports_and_a_run_beyond_them_is_never_sent() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    runs, _, gateway = _harness(store, selections)
    _select(selections, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    gateway.accepts = (ModelRunMediaKind.IMAGE,)
    pdf = ModelRunAttachment(media_type="application/pdf", base64_data="JVBERi0=")

    lane = runs.lookup("text_extraction")

    assert isinstance(lane, ModelRunLane) and lane.accepted_media == (ModelRunMediaKind.IMAGE,)
    refused = runs.run(_header(), _BODY.model_copy(update={"attachments": (pdf,)}))
    assert refused == ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
    assert gateway.runs == []


def test_without_a_ready_agent_every_run_refuses_as_service_unavailable() -> None:
    source = _catalog_source()
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    _select(selections, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    resolver = ProviderCredentialResolver(store=store, catalog_source=source)
    gateway = HostedBackgroundRuns(
        endpoint=lambda: None, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )
    runs = ModelRunService(selections=selections, resolver=resolver, catalog_source=source, gateway=gateway)

    lane = runs.lookup("text_extraction")
    assert isinstance(lane, ModelRunLane) and lane.accepted_media is None
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)


class _CountingSelections(MemoryModelRoleSelectionsStore):
    def __init__(self) -> None:
        super().__init__()
        self.selection_reads = 0

    @override
    def read(self) -> ModelRoleSelectionsRead | StoreRefusal:
        self.selection_reads += 1
        return super().read()


def test_a_selections_read_reports_every_role_from_one_read_of_the_record() -> None:
    selections = _CountingSelections()
    runs, _, _ = _harness(MemoryProviderSettingsStore(), selections)
    _select(
        selections,
        (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"),
        (ModelRole.COLUMN_ROLE_MAPPING, KEY_LANE, "synthetic-text-2"),
    )

    states = runs.selections()

    assert selections.selection_reads == 1
    assert states == (
        ModelRunRoleSelection(role="vision_transcription", refusal=ModelRunRefusalCode.NO_SELECTION),
        ModelRunRoleSelection(
            role="text_extraction",
            selected=ModelRunSelectedModel(lane_id=SIGN_IN_ONLY_LANE, model="synthetic-text-1"),
            lane=ModelRunLane(provider_id="example", transport="cli", model="synthetic-text-1"),
        ),
        ModelRunRoleSelection(
            role="column_role_mapping",
            selected=ModelRunSelectedModel(lane_id=KEY_LANE, model="synthetic-text-2"),
            refusal=ModelRunRefusalCode.LANE_UNAVAILABLE,
        ),
        ModelRunRoleSelection(role="supply_nature_proposal", refusal=ModelRunRefusalCode.NO_SELECTION),
    )


def test_a_selections_read_of_a_signed_out_profile_refuses_whole() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    selections.refusal = StoreRefusal(code=StoreRefusalCode.PROFILE_LOCKED)
    runs, _, _ = _harness(store, selections)

    assert runs.selections() == ModelRunRefusal(code=ModelRunRefusalCode.PROFILE_LOCKED)


def test_a_selections_read_of_an_unreadable_record_reports_no_selection_as_known() -> None:
    store = MemoryProviderSettingsStore()
    selections = MemoryModelRoleSelectionsStore()
    selections.unreadable = "e" * 64
    runs, _, _ = _harness(store, selections)

    states = runs.selections()

    assert isinstance(states, tuple)
    assert {state.refusal for state in states} == {ModelRunRefusalCode.LANE_UNAVAILABLE}
    assert all(state.selected is None for state in states)


class _CountingProviderRecords(MemoryProviderSettingsStore):
    """Count the provider records read: each read is one decrypted credential record."""

    def __init__(self) -> None:
        super().__init__()
        self.lanes_read: list[str] = []

    @override
    def read(self, provider_ids: tuple[str, ...]) -> tuple[ProviderRecordRead, ...] | StoreRefusal:
        self.lanes_read.extend(provider_ids)
        return super().read(provider_ids)


class _CountingCatalogSource(ProvidedProviderCatalogSource):
    def __init__(self, source: ProvidedProviderCatalogSource) -> None:
        super().__init__(source.catalog())
        self.fetches = 0

    @override
    def catalog(self) -> ProviderCatalog:
        self.fetches += 1
        return super().catalog()


def test_a_selections_read_decides_each_lane_once_however_many_roles_share_it() -> None:
    """Three roles on one lane and one on another read two credential records and ask for media twice."""
    store = _CountingProviderRecords()
    selections = MemoryModelRoleSelectionsStore()
    source = _CountingCatalogSource(_catalog_source())
    gateway = _RecordingGateway()
    gateway.accepts = (ModelRunMediaKind.IMAGE,)
    resolver = ProviderCredentialResolver(store=store, catalog_source=source)
    settings = ProviderSettingsService(store=store, catalog_source=source, storage_mode=StorageMode.INSTALLED)
    runs = ModelRunService(selections=selections, resolver=resolver, catalog_source=source, gateway=gateway)
    _store_key(settings, KEY_LANE)
    _select(
        selections,
        (ModelRole.VISION_TRANSCRIPTION, KEY_LANE, "synthetic-vision-1"),
        (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"),
        (ModelRole.COLUMN_ROLE_MAPPING, SIGN_IN_ONLY_LANE, "synthetic-text-2"),
        (ModelRole.SUPPLY_NATURE_PROPOSAL, SIGN_IN_ONLY_LANE, "synthetic-text-3"),
    )
    store.lanes_read.clear()
    source.fetches = 0

    states = runs.selections()

    assert isinstance(states, tuple)
    assert sorted(store.lanes_read) == sorted([KEY_LANE, SIGN_IN_ONLY_LANE])
    assert sorted(gateway.media_asked) == [("example", "api"), ("example", "cli")]
    # One fetch to find the lanes, and one inside each of the two credential resolutions.
    assert source.fetches == 3
    lanes = {state.role: state.lane for state in states}
    assert lanes["column_role_mapping"] == ModelRunLane(
        provider_id="example", transport="cli", model="synthetic-text-2", accepted_media=(ModelRunMediaKind.IMAGE,)
    )
    assert lanes["supply_nature_proposal"] == ModelRunLane(
        provider_id="example", transport="cli", model="synthetic-text-3", accepted_media=(ModelRunMediaKind.IMAGE,)
    )
    assert "synthetic-key" not in repr(states)
