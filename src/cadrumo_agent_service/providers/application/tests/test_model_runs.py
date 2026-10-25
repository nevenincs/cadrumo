"""Which lane answers a tax model run: the person's selection for its role, through the real resolver."""

from __future__ import annotations

import json
from datetime import UTC, datetime

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
)

from ....adapters.agent_background_runs import HostedBackgroundRuns
from ...domain.catalog import parse_provider_catalog
from ...domain.record import ModelRoleSelection, ModelRoleSelectionsRecord, new_settings_generation
from ..contracts import ProviderSettingsActionAccepted, ProviderSettingsStatus
from ..model_runs import ModelRunService
from ..ports import StoreRefusal, StoreRefusalCode
from ..resolution import ProviderCredentialResolver
from ..service import ProviderSettingsService
from .memory_store import MemoryProviderSettingsStore
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

    def accepted_media(self, lane: ModelRunLane) -> tuple[ModelRunMediaKind, ...] | None:
        del lane
        return self.accepts

    def run(self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int) -> ModelRunOutput | ModelRunRefusal:
        self.runs.append((lane, body, deadline_seconds))
        return ModelRunOutput(
            text="{}", provider_id=lane.provider_id, transport=lane.transport, model=lane.model, agent_version="t"
        )


def _harness(
    store: MemoryProviderSettingsStore,
) -> tuple[ModelRunService, ProviderSettingsService, _RecordingGateway]:
    source = _catalog_source()
    gateway = _RecordingGateway()
    resolver = ProviderCredentialResolver(store=store, catalog_source=source)
    settings = ProviderSettingsService(store=store, catalog_source=source, storage_mode=StorageMode.INSTALLED)
    runs = ModelRunService(store=store, resolver=resolver, catalog_source=source, gateway=gateway)
    return runs, settings, gateway


def _select(store: MemoryProviderSettingsStore, *selections: tuple[ModelRole, str, str]) -> None:
    record = ModelRoleSelectionsRecord(
        schema_version=1,
        selections=tuple(ModelRoleSelection(role=role, lane=lane, model=model) for role, lane, model in selections),
        generation=new_settings_generation(),
        updated_at=datetime(2026, 10, 25, 9, 0, tzinfo=UTC),
    )
    expected = store.selections.revision if store.selections is not None else ABSENT_SECURE_OBJECT_REVISION_ID
    assert store.write_role_selections(record, expected_revision=expected) is None


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
    runs, settings, gateway = _harness(store)
    _store_key(settings, KEY_LANE)

    for role in ModelRole:
        assert runs.lookup(role.value) == _NO_SELECTION
    assert runs.run(_header(), _BODY) == _NO_SELECTION
    assert gateway.runs == []


def test_each_role_gets_the_lane_and_model_selected_for_it() -> None:
    store = MemoryProviderSettingsStore()
    runs, settings, _ = _harness(store)
    _store_key(settings, KEY_LANE)
    _select(
        store,
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
    runs, _, _ = _harness(store)
    _select(store, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))

    assert runs.lookup("column_role_mapping") == _NO_SELECTION
    assert runs.lookup("supply_nature_proposal") == _NO_SELECTION
    assert runs.lookup("vision_transcription") == _NO_SELECTION


def test_a_role_outside_the_vocabulary_has_no_selection() -> None:
    store = MemoryProviderSettingsStore()
    runs, _, _ = _harness(store)
    _select(store, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))

    assert runs.lookup("unknown_role") == _NO_SELECTION


def test_a_selected_lane_turned_off_refuses_and_no_other_lane_is_used() -> None:
    store = MemoryProviderSettingsStore()
    runs, settings, gateway = _harness(store)
    _store_key(settings, OTHER_KEY_LANE)
    _select(store, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    _turn_off(settings, SIGN_IN_ONLY_LANE)

    assert runs.lookup("text_extraction") == _LANE_UNAVAILABLE
    assert runs.run(_header(), _BODY) == _LANE_UNAVAILABLE
    assert gateway.runs == []


def test_a_selected_key_lane_with_no_stored_key_refuses_as_unavailable() -> None:
    store = MemoryProviderSettingsStore()
    runs, _, _ = _harness(store)
    _select(store, (ModelRole.TEXT_EXTRACTION, KEY_LANE, "synthetic-text-1"))

    assert runs.lookup("text_extraction") == _LANE_UNAVAILABLE


def test_a_selected_lane_the_agent_no_longer_reports_refuses_as_unavailable() -> None:
    store = MemoryProviderSettingsStore()
    runs, _, _ = _harness(store)
    _select(store, (ModelRole.TEXT_EXTRACTION, MISSING_LANE, "synthetic-text-1"))

    assert runs.lookup("text_extraction") == _LANE_UNAVAILABLE


def test_an_unreadable_selections_record_refuses_every_role_rather_than_reading_as_none() -> None:
    store = MemoryProviderSettingsStore()
    runs, _, _ = _harness(store)
    store.unreadable_selections = "c" * 64

    for role in ModelRole:
        assert runs.lookup(role.value) == _LANE_UNAVAILABLE


def test_a_profile_that_is_not_signed_in_refuses_as_such() -> None:
    store = MemoryProviderSettingsStore()
    store.refusal = StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    runs, _, gateway = _harness(store)

    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert gateway.runs == []


def test_a_run_whose_consent_names_another_lane_is_refused_before_it_is_sent() -> None:
    store = MemoryProviderSettingsStore()
    runs, _, gateway = _harness(store)
    _select(store, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    consent = ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id="example", transport="api", model="synthetic-text-1"
    )

    assert runs.run(_header(consent=consent), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
    assert gateway.runs == []


def test_a_run_whose_consent_names_its_lane_goes_to_the_gateway_on_that_lane() -> None:
    store = MemoryProviderSettingsStore()
    runs, _, gateway = _harness(store)
    _select(store, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
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
    runs, _, gateway = _harness(store)
    _select(store, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
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
    _select(store, (ModelRole.TEXT_EXTRACTION, SIGN_IN_ONLY_LANE, "synthetic-text-1"))
    resolver = ProviderCredentialResolver(store=store, catalog_source=source)
    gateway = HostedBackgroundRuns(
        endpoint=lambda: None, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )
    runs = ModelRunService(store=store, resolver=resolver, catalog_source=source, gateway=gateway)

    lane = runs.lookup("text_extraction")
    assert isinstance(lane, ModelRunLane) and lane.accepted_media is None
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
