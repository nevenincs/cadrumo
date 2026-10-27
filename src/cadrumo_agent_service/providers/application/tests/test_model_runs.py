"""Which lane and model answer a tax model run: the person's selected model, checked by capability, through the real resolver."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, override

import pytest
from pydantic import SecretStr

from cadrumo.core.model_roles import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import StorageMode
from cadrumo_client.contracts.model_runs import (
    ModelRunAttachment,
    ModelRunBody,
    ModelRunConsentBinding,
    ModelRunHeader,
    ModelRunLane,
    ModelRunLicence,
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
    ModelRunSelectedModel,
)

from ....adapters.agent_background_runs import HostedBackgroundRuns
from ...domain.catalog import BackgroundOption, ProviderCatalog, parse_provider_catalog
from ...domain.record import ListedModel, LocalModelListRecord, new_settings_generation
from ..contracts import ProviderSettingsActionAccepted, ProviderSettingsStatus
from ..model_runs import ROLE_CAPABILITIES, ModelRunService
from ..ports import LiveLaneBackground, LocalModelListRead, ProviderRecordRead, StoreRefusal, StoreRefusalCode
from ..resolution import ProviderCredentialResolver
from ..service import ProviderSettingsService
from .memory_store import MemoryLocalModelListStore, MemoryProviderSettingsStore
from .synthetic_catalog import (
    HOSTED_TEXT_MODELS,
    HOSTED_VISION_MODELS,
    KEY_LANE,
    KEYLESS_LANE,
    KEYLESS_TEXT_MODEL,
    KEYLESS_VISION_MODEL,
    OTHER_KEY_LANE,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    live_model,
    synthetic_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFAULT_MODELS = {KEY_LANE: "example-model-a", OTHER_KEY_LANE: "other-model"}
"""Catalogue defaults on two hosted lanes, so a test can show the lookup never reads one."""

_ADDED = "custom-model:test"
"""A model the person added by name; no catalogue declares it."""

_SPARE_LANE = "spare_api"
"""A second keyless lane, after the first in catalogue order."""

_HOSTED_TEXT = HOSTED_TEXT_MODELS[0]
_HOSTED_VISION = HOSTED_VISION_MODELS[0]


def _catalog_source(**local: Any) -> ProvidedProviderCatalogSource:
    """The synthetic catalog with hosted defaults, its keyless lane changed by ``local``, through the real parser.

    ``spare`` adds a second keyless lane declaring the same models.
    """
    document = json.loads(synthetic_document())
    spare = local.pop("spare", False)
    for lane in document["providers"]:
        if lane["id"] in _DEFAULT_MODELS:
            lane["default_model"] = _DEFAULT_MODELS[lane["id"]]
        if lane["id"] == KEYLESS_LANE:
            lane.update(local)
            if spare:
                document["providers"].append(lane | {"id": _SPARE_LANE, "provider": "spare", "display_name": "Spare"})
    return ProvidedProviderCatalogSource(parse_provider_catalog(json.dumps(document)))


class _RecordingGateway:
    def __init__(self) -> None:
        self.runs: list[tuple[ModelRunLane, ModelRunBody, int]] = []
        self.options: list[tuple[BackgroundOption, ...]] = []

    def run(
        self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int, options: tuple[BackgroundOption, ...]
    ) -> ModelRunOutput | ModelRunRefusal:
        self.runs.append((lane, body, deadline_seconds))
        self.options.append(options)
        return ModelRunOutput(
            text="{}", provider_id=lane.provider_id, transport=lane.transport, model=lane.model, agent_version="t"
        )


def _harness(
    store: MemoryProviderSettingsStore,
    model_list: MemoryLocalModelListStore,
    live: StaticLiveModels | None = None,
    source: ProvidedProviderCatalogSource | None = None,
) -> tuple[ModelRunService, ProviderSettingsService, _RecordingGateway]:
    source = _catalog_source() if source is None else source
    gateway = _RecordingGateway()
    resolver = ProviderCredentialResolver(store=store, catalog_source=source)
    settings = ProviderSettingsService(store=store, catalog_source=source, storage_mode=StorageMode.INSTALLED)
    runs = ModelRunService(
        model_list=model_list,
        resolver=resolver,
        catalog_source=source,
        live_models=StaticLiveModels() if live is None else live,
        gateway=gateway,
    )
    return runs, settings, gateway


def _store(model_list: MemoryLocalModelListStore, *added: tuple[str, str], reading: tuple[str, str] | None) -> None:
    """Store the models added to the local lists and the model the person selected to read with."""
    record = LocalModelListRecord(
        schema_version=2,
        models=tuple(ListedModel(lane=lane, model=model) for lane, model in added),
        reading=None if reading is None else ListedModel(lane=reading[0], model=reading[1]),
        generation=new_settings_generation(),
        updated_at=datetime(2026, 10, 27, 9, 0, tzinfo=UTC),
    )
    expected = model_list.stored.revision if model_list.stored is not None else ABSENT_SECURE_OBJECT_REVISION_ID
    assert model_list.write(record, expected_revision=expected) is None


def _selected(lane: str, model: str, *added: tuple[str, str]) -> MemoryLocalModelListStore:
    model_list = MemoryLocalModelListStore()
    _store(model_list, *added, reading=(lane, model))
    return model_list


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


def _header(*, role: str = "text_extraction", consent: ModelRunConsentBinding | None = None) -> ModelRunHeader:
    return ModelRunHeader(role=role, deadline_seconds=30, consent=consent)


def _consent(provider_id: str, model: str = KEYLESS_TEXT_MODEL, *, transport: str = "api") -> ModelRunConsentBinding:
    return ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id=provider_id, transport=transport, model=model
    )


_BODY = ModelRunBody(prompt="Read this invoice.", max_output_tokens=64)

_LICENCE = ModelRunLicence(spdx="MIT", name="Synthetic licence", digest="sha256:" + "0" * 64)


def _background(media: tuple[ModelRunMediaKind, ...] | None, *options: BackgroundOption) -> LiveLaneBackground:
    return LiveLaneBackground(accepted_media=media, options=options)


def _hosted(model: str, *, vision: bool | None) -> ModelRunLane:
    """The lane a declared synthetic hosted model resolves to: off-host, only its vision stated."""
    return ModelRunLane(
        provider_id="example",
        transport="api",
        model=model,
        reads_off_host=True,
        licence=None,
        size_bytes=None,
        vision=vision,
        context_length=None,
        installed=None,
    )


def _declared(model: str, *, vision: bool, provider_id: str = "local") -> ModelRunLane:
    """The lane a declared synthetic local model resolves to: its stated facts, installed state unknown."""
    return ModelRunLane(
        provider_id=provider_id,
        transport="api",
        model=model,
        reads_off_host=False,
        licence=_LICENCE,
        size_bytes=1_000_000,
        vision=vision,
        context_length=4096,
        installed=None,
    )


def _installed(*models: tuple[str, bool | None, bool | None]) -> StaticLiveModels:
    """A running agent whose local lane lists ``(model, vision, installed)`` entries."""
    return StaticLiveModels(
        {
            ("local", "api"): tuple(
                live_model(model, vision=vision, installed=installed) for model, vision, installed in models
            )
        }
    )


_NO_SELECTION = ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
_LANE_UNAVAILABLE = ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
_NOT_INSTALLED = ModelRunRefusal(code=ModelRunRefusalCode.MODEL_NOT_INSTALLED)
_NO_IMAGES = ModelRunRefusal(code=ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES)


def test_every_role_has_a_capability_and_only_vision_transcription_reads_images() -> None:
    assert set(ROLE_CAPABILITIES) == set(ModelRole)
    assert {role for role, capability in ROLE_CAPABILITIES.items() if capability.value == "vision"} == {
        ModelRole.VISION_TRANSCRIPTION
    }


def test_with_no_model_selected_every_role_refuses_and_no_recommended_model_stands_in() -> None:
    runs, settings, gateway = _harness(MemoryProviderSettingsStore(), MemoryLocalModelListStore())
    _store_key(settings, KEY_LANE)

    for role in ModelRole:
        assert runs.lookup(role.value) == _NO_SELECTION
    assert runs.run(_header(), _BODY) == _NO_SELECTION
    assert gateway.runs == []


def test_a_list_with_added_models_but_no_selection_still_refuses() -> None:
    model_list = MemoryLocalModelListStore()
    _store(model_list, (KEYLESS_LANE, _ADDED), reading=None)
    runs, _, _ = _harness(MemoryProviderSettingsStore(), model_list)

    for role in ModelRole:
        assert runs.lookup(role.value) == _NO_SELECTION


def test_a_selected_local_vision_model_serves_every_role() -> None:
    runs, _, _ = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_VISION_MODEL))

    for role in ModelRole:
        assert runs.lookup(role.value) == _declared(KEYLESS_VISION_MODEL, vision=True)


def test_a_selected_text_model_reads_text_and_refuses_images_in_plain_terms() -> None:
    """No other model stands in: the recommended vision model on the same lane is not used."""
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL))

    assert runs.lookup("vision_transcription") == _NO_IMAGES
    for role in ("text_extraction", "column_role_mapping", "supply_nature_proposal"):
        assert runs.lookup(role) == _declared(KEYLESS_TEXT_MODEL, vision=False)
    assert runs.run(_header(role="vision_transcription"), _BODY) == _NO_IMAGES
    assert gateway.runs == []


def test_a_selected_hosted_model_serves_with_a_stored_key_and_reads_off_host() -> None:
    runs, settings, _ = _harness(MemoryProviderSettingsStore(), _selected(KEY_LANE, _HOSTED_VISION))
    _store_key(settings, KEY_LANE)

    assert runs.lookup("vision_transcription") == _hosted(_HOSTED_VISION, vision=True)
    assert runs.lookup("text_extraction") == _hosted(_HOSTED_VISION, vision=True)


def test_a_selected_hosted_model_whose_vision_is_unstated_refuses_images_only() -> None:
    runs, settings, _ = _harness(MemoryProviderSettingsStore(), _selected(KEY_LANE, _HOSTED_TEXT))
    _store_key(settings, KEY_LANE)

    assert runs.lookup("vision_transcription") == _NO_IMAGES
    assert runs.lookup("text_extraction") == _hosted(_HOSTED_TEXT, vision=None)


def test_a_selected_hosted_model_without_its_key_is_unavailable_and_no_other_lane_stands_in() -> None:
    runs, settings, gateway = _harness(MemoryProviderSettingsStore(), _selected(KEY_LANE, _HOSTED_TEXT))
    _store_key(settings, OTHER_KEY_LANE)

    for role in ModelRole:
        assert runs.lookup(role.value) == _LANE_UNAVAILABLE
    assert runs.run(_header(), _BODY) == _LANE_UNAVAILABLE
    assert gateway.runs == []


def test_a_written_model_no_entry_lists_reads_text_with_no_facts_and_never_images() -> None:
    runs, settings, _ = _harness(MemoryProviderSettingsStore(), _selected(KEY_LANE, "written-model"))
    _store_key(settings, KEY_LANE)

    assert runs.lookup("text_extraction") == _hosted("written-model", vision=None)
    assert runs.lookup("vision_transcription") == _NO_IMAGES


def test_a_selected_local_model_the_server_lacks_refuses_as_not_installed() -> None:
    live = _installed((KEYLESS_TEXT_MODEL, False, True), (KEYLESS_VISION_MODEL, True, False))
    runs, _, _ = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_VISION_MODEL), live)

    assert runs.lookup("vision_transcription") == _NOT_INSTALLED
    states = runs.selections()
    assert isinstance(states, tuple)
    assert states[0] == ModelRunRoleSelection(
        role="vision_transcription",
        selected=ModelRunSelectedModel(lane_id=KEYLESS_LANE, model=KEYLESS_VISION_MODEL),
        refusal=ModelRunRefusalCode.MODEL_NOT_INSTALLED,
    )


def test_a_selected_added_model_the_server_holds_reads_text_and_its_unstated_vision_refuses_images() -> None:
    model_list = _selected(KEYLESS_LANE, _ADDED, (KEYLESS_LANE, _ADDED))
    live = _installed((KEYLESS_VISION_MODEL, True, True), (_ADDED, None, True))
    runs, _, _ = _harness(MemoryProviderSettingsStore(), model_list, live)

    text = runs.lookup("supply_nature_proposal")

    assert isinstance(text, ModelRunLane)
    assert (text.model, text.vision, text.installed) == (_ADDED, None, True)
    assert runs.lookup("vision_transcription") == _NO_IMAGES


def test_a_selected_added_model_marked_vision_reads_images() -> None:
    model_list = _selected(KEYLESS_LANE, _ADDED, (KEYLESS_LANE, _ADDED))
    live = _installed((_ADDED, True, True))
    runs, _, _ = _harness(MemoryProviderSettingsStore(), model_list, live)

    lane = runs.lookup("vision_transcription")

    assert isinstance(lane, ModelRunLane) and lane.model == _ADDED


def test_a_local_model_taken_off_its_list_is_no_longer_selected() -> None:
    """The server still holds it, but the person's list no longer offers it."""
    live = _installed((_ADDED, True, True))
    runs, _, _ = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, _ADDED), live)

    for role in ModelRole:
        assert runs.lookup(role.value) == _NO_SELECTION


def test_a_lane_whose_runs_take_no_image_cannot_read_images_with_a_vision_model() -> None:
    source = _catalog_source(background={"runnable": True, "inputs": ["text"], "options": []})
    model_list = _selected(KEYLESS_LANE, KEYLESS_VISION_MODEL)
    runs, _, _ = _harness(MemoryProviderSettingsStore(), model_list, source=source)

    assert runs.lookup("vision_transcription") == _NO_IMAGES
    assert isinstance(runs.lookup("text_extraction"), ModelRunLane)


def test_a_lane_that_runs_no_background_request_is_unavailable() -> None:
    source = _catalog_source(background={"runnable": False, "inputs": [], "options": []})
    model_list = _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL)
    runs, _, _ = _harness(MemoryProviderSettingsStore(), model_list, source=source)

    for role in ModelRole:
        assert runs.lookup(role.value) == _LANE_UNAVAILABLE


def test_a_selected_lane_the_catalogue_no_longer_reports_is_unavailable() -> None:
    document = json.loads(synthetic_document())
    document["providers"] = [lane for lane in document["providers"] if lane["id"] != KEYLESS_LANE]
    source = ProvidedProviderCatalogSource(parse_provider_catalog(json.dumps(document)))
    model_list = _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL)
    runs, settings, _ = _harness(MemoryProviderSettingsStore(), model_list, source=source)
    _store_key(settings, KEY_LANE)

    for role in ModelRole:
        assert runs.lookup(role.value) == _LANE_UNAVAILABLE


def test_a_selected_local_lane_turned_off_is_unavailable_and_another_local_lane_does_not_stand_in() -> None:
    source = _catalog_source(spare=True)
    runs, settings, _ = _harness(
        MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL), source=source
    )

    assert runs.lookup("text_extraction") == _declared(KEYLESS_TEXT_MODEL, vision=False)
    _turn_off(settings, KEYLESS_LANE)
    assert runs.lookup("text_extraction") == _LANE_UNAVAILABLE


def test_a_role_outside_the_vocabulary_refuses_as_unknown_not_as_unserved() -> None:
    runs, _, _ = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL))

    assert runs.lookup("unknown_role") == ModelRunRefusal(code=ModelRunRefusalCode.UNKNOWN_ROLE)
    assert runs.run(_header(role="unknown_role"), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.UNKNOWN_ROLE)


def test_an_unreadable_record_refuses_every_role_rather_than_reading_as_unselected() -> None:
    model_list = MemoryLocalModelListStore()
    model_list.unreadable = "c" * 64
    runs, _, _ = _harness(MemoryProviderSettingsStore(), model_list)

    for role in ModelRole:
        assert runs.lookup(role.value) == _LANE_UNAVAILABLE
    states = runs.selections()
    assert isinstance(states, tuple)
    assert {state.refusal for state in states} == {ModelRunRefusalCode.LANE_UNAVAILABLE}
    assert all(state.selected is None for state in states)


def test_a_profile_that_is_not_signed_in_refuses_as_such() -> None:
    model_list = MemoryLocalModelListStore()
    model_list.refusal = StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), model_list)

    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert runs.selections() == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert gateway.runs == []


def test_a_lane_the_catalogue_declares_on_host_runs_without_consent() -> None:
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL))

    output = runs.run(_header(), _BODY)

    assert isinstance(output, ModelRunOutput)
    ((ran_on, body, deadline),) = gateway.runs
    assert (ran_on.provider_id, ran_on.model, ran_on.reads_off_host) == ("local", KEYLESS_TEXT_MODEL, False)
    assert (body, deadline) == (_BODY, 30)


def test_consent_recorded_for_another_lane_does_not_carry_to_the_lane_the_role_resolves_to() -> None:
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL))

    refused = runs.run(_header(consent=_consent("example", transport="cli")), _BODY)

    assert refused == ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
    assert gateway.runs == []


def test_a_local_lane_the_catalogue_declares_off_host_needs_consent_bound_to_it() -> None:
    source = _catalog_source(reads_off_host=True)
    model_list = _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL)
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), model_list, source=source)

    lane = runs.lookup("text_extraction")
    assert isinstance(lane, ModelRunLane) and lane.reads_off_host is True
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
    assert runs.run(_header(consent=_consent("local", KEYLESS_VISION_MODEL)), _BODY) == ModelRunRefusal(
        code=ModelRunRefusalCode.CONSENT_MISSING
    )
    assert gateway.runs == []

    consent = _consent("local")
    assert isinstance(runs.run(_header(consent=consent), _BODY), ModelRunOutput)
    ((ran_on, _, _),) = gateway.runs
    assert consent.matches(ran_on)


def test_a_run_decided_on_host_is_refused_when_its_lane_now_reads_off_host() -> None:
    """The tax side bound no consent because its lookup found an on-host lane; the catalogue then changed."""
    model_list = _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL)
    store = MemoryProviderSettingsStore()
    runs, _, _ = _harness(store, model_list)
    looked_up = runs.lookup("text_extraction")
    assert isinstance(looked_up, ModelRunLane) and looked_up.reads_off_host is False
    changed, _, gateway = _harness(store, model_list, source=_catalog_source(reads_off_host=True))

    assert changed.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
    assert gateway.runs == []


def test_the_lookup_carries_the_media_the_agent_reports_and_a_run_beyond_them_is_never_sent() -> None:
    live = StaticLiveModels(backgrounds={("local", "api"): _background((ModelRunMediaKind.IMAGE,))})
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL), live)
    pdf = ModelRunAttachment(media_type="application/pdf", base64_data="JVBERi0=")

    lane = runs.lookup("text_extraction")

    assert isinstance(lane, ModelRunLane) and lane.accepted_media == (ModelRunMediaKind.IMAGE,)
    refused = runs.run(_header(), _BODY.model_copy(update={"attachments": (pdf,)}))
    assert refused == ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
    assert gateway.runs == []


def test_without_a_ready_agent_every_run_refuses_as_service_unavailable() -> None:
    source = _catalog_source()
    store = MemoryProviderSettingsStore()
    resolver = ProviderCredentialResolver(store=store, catalog_source=source)
    gateway = HostedBackgroundRuns(
        endpoint=lambda: None, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )
    runs = ModelRunService(
        model_list=_selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL),
        resolver=resolver,
        catalog_source=source,
        live_models=StaticLiveModels(),
        gateway=gateway,
    )

    lane = runs.lookup("text_extraction")
    assert isinstance(lane, ModelRunLane) and lane.accepted_media is None
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)


class _CountingList(MemoryLocalModelListStore):
    def __init__(self) -> None:
        super().__init__()
        self.list_reads = 0

    @override
    def read(self) -> LocalModelListRead | StoreRefusal:
        self.list_reads += 1
        return super().read()


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


def test_a_selections_read_reports_every_role_from_one_read_of_the_record_deciding_the_lane_once() -> None:
    store = _CountingProviderRecords()
    model_list = _CountingList()
    _store(model_list, reading=(KEYLESS_LANE, KEYLESS_TEXT_MODEL))
    source = _CountingCatalogSource(_catalog_source())
    live = StaticLiveModels(backgrounds={("local", "api"): _background((ModelRunMediaKind.IMAGE,))})
    runs, _, _ = _harness(store, model_list, live, source)
    source.fetches = 0

    states = runs.selections()

    assert model_list.list_reads == 1
    assert store.lanes_read == [KEYLESS_LANE]
    assert live.snapshots == 1
    # One fetch to find the lanes, and one inside the one credential resolution.
    assert source.fetches == 2
    text = _declared(KEYLESS_TEXT_MODEL, vision=False).model_copy(update={"accepted_media": (ModelRunMediaKind.IMAGE,)})
    text_selected = ModelRunSelectedModel(lane_id=KEYLESS_LANE, model=KEYLESS_TEXT_MODEL)
    assert states == (
        ModelRunRoleSelection(
            role="vision_transcription",
            selected=text_selected,
            refusal=ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES,
        ),
        ModelRunRoleSelection(role="text_extraction", selected=text_selected, lane=text),
        ModelRunRoleSelection(role="column_role_mapping", selected=text_selected, lane=text),
        ModelRunRoleSelection(role="supply_nature_proposal", selected=text_selected, lane=text),
    )


def test_one_run_reads_its_media_and_its_options_from_one_live_catalogue_snapshot() -> None:
    """The lookup a run repeats and the options it sends come from one snapshot; the next run takes its own."""
    live = StaticLiveModels(
        backgrounds={
            ("local", "api"): _background(
                (ModelRunMediaKind.IMAGE,), BackgroundOption.TEMPERATURE, BackgroundOption.RESPONSE_SCHEMA
            )
        }
    )
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL), live)
    image = ModelRunAttachment(media_type="image/png", base64_data="iVBORw0=")
    body = _BODY.model_copy(update={"attachments": (image,), "temperature": 0.0})

    assert isinstance(runs.run(_header(), body), ModelRunOutput)
    assert isinstance(runs.run(_header(), body), ModelRunOutput)

    assert live.snapshots == 2
    assert gateway.options == [(BackgroundOption.TEMPERATURE, BackgroundOption.RESPONSE_SCHEMA)] * 2
    assert gateway.runs[0][0].accepted_media == (ModelRunMediaKind.IMAGE,)


def test_a_run_on_a_lane_the_live_catalogue_does_not_describe_sends_no_option() -> None:
    runs, _, gateway = _harness(MemoryProviderSettingsStore(), _selected(KEYLESS_LANE, KEYLESS_TEXT_MODEL))

    assert isinstance(runs.run(_header(), _BODY), ModelRunOutput)

    assert gateway.options == [()]
    assert gateway.runs[0][0].accepted_media is None
