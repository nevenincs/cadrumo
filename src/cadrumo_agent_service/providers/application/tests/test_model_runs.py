"""Which lane answers a tax model run, decided by the real resolver over the profile's settings."""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr

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
from ..contracts import ProviderSettingsActionAccepted, ProviderSettingsStatus
from ..model_runs import ModelRunService
from ..ports import StoreRefusal, StoreRefusalCode
from ..resolution import ProviderCredentialResolver
from ..service import ProviderSettingsService
from .memory_store import MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEY_LANE,
    OTHER_KEY_LANE,
    SIGN_IN_ONLY_LANE,
    ProvidedProviderCatalogSource,
    synthetic_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFAULT_MODELS = {KEY_LANE: "example-model-a", SIGN_IN_ONLY_LANE: "example-model-c", OTHER_KEY_LANE: "other-model"}


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
    resolver = ProviderCredentialResolver(
        store=store, catalog_source=source, environment={}, storage_mode=StorageMode.INSTALLED
    )
    settings = ProviderSettingsService(
        store=store, catalog_source=source, environment={}, storage_mode=StorageMode.INSTALLED
    )
    return ModelRunService(resolver=resolver, catalog_source=source, gateway=gateway), settings, gateway


def _revision(settings: ProviderSettingsService, lane: str) -> str:
    status = settings.status()
    assert isinstance(status, ProviderSettingsStatus)
    return next(entry.revision for entry in status.providers if entry.id == lane)


def _turn_off(settings: ProviderSettingsService, lane: str) -> None:
    assert isinstance(
        settings.turn_off(lane, expected_revision=_revision(settings, lane)), ProviderSettingsActionAccepted
    )


def _header(*, consent: ModelRunConsentBinding | None = None) -> ModelRunHeader:
    return ModelRunHeader(role="text_extraction", deadline_seconds=30, consent=consent)


_BODY = ModelRunBody(prompt="Read this invoice.", max_output_tokens=64)


def test_a_cli_lane_reached_by_its_own_sign_in_is_the_default_when_no_key_is_stored() -> None:
    """Parity: the default selection is the first reachable lane in catalog order, CLI or API."""
    runs, _, _ = _harness(MemoryProviderSettingsStore())

    assert runs.lookup("text_extraction") == ModelRunLane(
        provider_id="example", transport="cli", model="example-model-c"
    )


def test_an_earlier_lane_with_a_stored_key_wins() -> None:
    store = MemoryProviderSettingsStore()
    runs, settings, _ = _harness(store)
    stored = settings.set_credential(
        KEY_LANE, secret=SecretStr("synthetic-key"), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )
    assert isinstance(stored, ProviderSettingsActionAccepted)

    assert runs.lookup("text_extraction") == ModelRunLane(
        provider_id="example", transport="api", model="example-model-a"
    )


def test_a_lane_turned_off_is_never_chosen() -> None:
    store = MemoryProviderSettingsStore()
    runs, settings, _ = _harness(store)
    _turn_off(settings, SIGN_IN_ONLY_LANE)

    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)

    stored = settings.set_credential(
        OTHER_KEY_LANE, secret=SecretStr("synthetic-key"), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )
    assert isinstance(stored, ProviderSettingsActionAccepted)
    assert runs.lookup("text_extraction") == ModelRunLane(provider_id="other", transport="api", model="other-model")


def test_a_profile_that_is_not_signed_in_refuses_as_such() -> None:
    store = MemoryProviderSettingsStore()
    store.refusal = StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    runs, _, gateway = _harness(store)

    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)
    assert gateway.runs == []


def test_a_run_whose_consent_names_another_lane_is_refused_before_it_is_sent() -> None:
    runs, _, gateway = _harness(MemoryProviderSettingsStore())
    consent = ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id="example", transport="api", model="example-model-a"
    )

    assert runs.run(_header(consent=consent), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
    assert gateway.runs == []


def test_a_run_whose_consent_names_its_lane_goes_to_the_gateway_on_that_lane() -> None:
    runs, _, gateway = _harness(MemoryProviderSettingsStore())
    consent = ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id="example", transport="cli", model="example-model-c"
    )

    output = runs.run(_header(consent=consent), _BODY)

    assert isinstance(output, ModelRunOutput)
    ((lane, body, deadline),) = gateway.runs
    assert consent.matches(lane)
    assert body == _BODY
    assert deadline == 30


def test_the_lookup_carries_the_media_the_agent_reports_and_a_run_beyond_them_is_never_sent() -> None:
    runs, _, gateway = _harness(MemoryProviderSettingsStore())
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
    resolver = ProviderCredentialResolver(
        store=store, catalog_source=source, environment={}, storage_mode=StorageMode.INSTALLED
    )
    gateway = HostedBackgroundRuns(
        endpoint=lambda: None, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )
    runs = ModelRunService(resolver=resolver, catalog_source=source, gateway=gateway)

    lane = runs.lookup("text_extraction")
    assert isinstance(lane, ModelRunLane) and lane.accepted_media is None
    assert runs.run(_header(), _BODY) == ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
