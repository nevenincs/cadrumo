"""The person's model record: add a local model by name, remove one, and select the reading model, each guarded."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ...domain.catalog import BackgroundOption
from ...domain.record import LOCAL_MODEL_LIST_MAX_MODELS, ListedModel, LocalModelListRecord, new_settings_generation
from ..contracts import (
    LocalModelListStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
)
from ..local_model_list import LocalModelListService, listed_models, local_lanes
from ..model_runs import ModelRunService
from ..ports import StoreRefusal, StoreRefusalCode
from ..resolution import ProviderCredentialResolver
from .memory_store import MemoryLocalModelListStore, MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEY_LANE,
    KEYLESS_LANE,
    KEYLESS_TEXT_MODEL,
    KEYLESS_VISION_MODEL,
    MISSING_LANE,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    UnavailableCatalogSource,
    live_model,
    synthetic_catalog,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ADDED = "custom-model:test"


def _service(store: MemoryLocalModelListStore) -> LocalModelListService:
    return LocalModelListService(store=store, catalog_source=ProvidedProviderCatalogSource(synthetic_catalog()))


def _status(result: LocalModelListStatus | ProviderSettingsRefusal) -> LocalModelListStatus:
    assert isinstance(result, LocalModelListStatus), result
    return result


def _added(status: LocalModelListStatus) -> list[tuple[str, str]]:
    return [(entry.lane, entry.model) for entry in status.models]


def _refused(code: ProviderSettingsRefusalCode) -> ProviderSettingsRefusal:
    return ProviderSettingsRefusal(code=code)


def _put(store: MemoryLocalModelListStore, *models: tuple[str, str], reading: ListedModel | None = None) -> str:
    record = LocalModelListRecord(
        schema_version=2,
        models=tuple(ListedModel(lane=lane, model=model) for lane, model in models),
        reading=reading,
        generation=new_settings_generation(),
        updated_at=datetime(2026, 10, 27, 9, 0, tzinfo=UTC),
    )
    assert store.write(record, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    assert store.stored is not None
    return store.stored.revision


def test_the_local_lanes_are_the_keyless_ones_and_list_the_recommended_models_before_the_added_ones() -> None:
    catalog = synthetic_catalog()

    (local,) = local_lanes(catalog)

    assert local.id == KEYLESS_LANE
    assert listed_models(local, ()) == (KEYLESS_TEXT_MODEL, KEYLESS_VISION_MODEL)
    assert listed_models(local, (_ADDED, KEYLESS_VISION_MODEL, _ADDED)) == (
        KEYLESS_TEXT_MODEL,
        KEYLESS_VISION_MODEL,
        _ADDED,
    )


def test_a_fresh_profile_lists_no_added_model() -> None:
    assert _service(MemoryLocalModelListStore()).status() == LocalModelListStatus(
        unreadable=False,
        models=(),
        reading=None,
        local_lanes=(KEYLESS_LANE,),
        revision=ABSENT_SECURE_OBJECT_REVISION_ID,
    )


def test_models_are_added_in_order_and_removing_one_keeps_the_others() -> None:
    service = _service(MemoryLocalModelListStore())
    first = _status(service.add(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID))
    second = _status(service.add(KEYLESS_LANE, model="another:1", expected_revision=first.revision))

    assert _added(second) == [(KEYLESS_LANE, _ADDED), (KEYLESS_LANE, "another:1")]
    assert service.status() == second

    removed = _status(service.remove(KEYLESS_LANE, model=_ADDED, expected_revision=second.revision))

    assert _added(removed) == [(KEYLESS_LANE, "another:1")]
    assert len({first.revision, second.revision, removed.revision}) == 3


@pytest.mark.parametrize("model", [KEYLESS_TEXT_MODEL, KEYLESS_VISION_MODEL, _ADDED])
def test_adding_a_model_the_list_already_holds_writes_nothing(model: str) -> None:
    store = MemoryLocalModelListStore()
    revision = _put(store, (KEYLESS_LANE, _ADDED))
    service = _service(store)

    unchanged = _status(service.add(KEYLESS_LANE, model=model, expected_revision=revision))

    assert unchanged.revision == revision
    assert _added(unchanged) == [(KEYLESS_LANE, _ADDED)]


def test_a_recommended_model_cannot_be_removed_from_the_list() -> None:
    service = _service(MemoryLocalModelListStore())

    refused = service.remove(KEYLESS_LANE, model=KEYLESS_TEXT_MODEL, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)

    assert refused == _refused(ProviderSettingsRefusalCode.UNKNOWN)


@pytest.mark.parametrize(
    ("lane", "model"),
    [
        (KEY_LANE, _ADDED),
        (MISSING_LANE, _ADDED),
        (KEYLESS_LANE, "has" + chr(9) + "tab"),
        (KEYLESS_LANE, "m" * 513),
        (KEYLESS_LANE, ""),
    ],
    ids=["keyed-lane", "unreported-lane", "model-with-control-character", "model-past-the-id-bound", "empty-model"],
)
def test_adding_to_a_lane_that_is_not_local_or_a_malformed_name_is_refused(lane: str, model: str) -> None:
    store = MemoryLocalModelListStore()

    refused = _service(store).add(lane, model=model, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)

    assert refused == _refused(ProviderSettingsRefusalCode.UNKNOWN)
    assert store.stored is None


def test_a_full_list_refuses_another_model() -> None:
    store = MemoryLocalModelListStore()
    revision = _put(store, *((KEYLESS_LANE, f"model-{index}") for index in range(LOCAL_MODEL_LIST_MAX_MODELS)))

    refused = _service(store).add(KEYLESS_LANE, model=_ADDED, expected_revision=revision)

    assert refused == _refused(ProviderSettingsRefusalCode.MODEL_LIST_FULL)


def test_a_change_against_a_stale_revision_is_refused_and_changes_nothing() -> None:
    service = _service(MemoryLocalModelListStore())
    status = _status(service.add(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID))
    conflict = _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)

    assert service.add(KEYLESS_LANE, model="another:1", expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) == conflict
    assert service.remove(KEYLESS_LANE, model=_ADDED, expected_revision="f" * 64) == conflict
    assert service.reset(expected_revision="f" * 64) == conflict
    assert service.add(KEYLESS_LANE, model="another:1", expected_revision="not-hex") == conflict
    assert service.status() == status


def test_a_write_drops_models_on_lanes_the_catalogue_reports_as_not_local_and_keeps_unreported_ones() -> None:
    store = MemoryLocalModelListStore()
    revision = _put(store, (KEY_LANE, "synthetic-text-1"), (MISSING_LANE, "kept:1"), (KEYLESS_LANE, _ADDED))

    written = _status(_service(store).add(KEYLESS_LANE, model="another:1", expected_revision=revision))

    assert _added(written) == [(MISSING_LANE, "kept:1"), (KEYLESS_LANE, _ADDED), (KEYLESS_LANE, "another:1")]


def test_a_catalogue_the_agent_cannot_report_refuses_changes() -> None:
    store = MemoryLocalModelListStore()
    service = LocalModelListService(store=store, catalog_source=UnavailableCatalogSource())
    unavailable = _refused(ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE)

    assert service.add(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) == unavailable
    assert store.stored is None
    assert _status(service.status()).models == ()
    assert _status(service.status()).local_lanes == ()


def test_an_unreadable_record_lists_no_model_refuses_changes_and_only_a_guarded_reset_clears_it() -> None:
    store = MemoryLocalModelListStore()
    store.unreadable = "d" * 64
    service = _service(store)

    assert service.status() == LocalModelListStatus(
        unreadable=True, models=(), reading=None, local_lanes=(KEYLESS_LANE,), revision="d" * 64
    )
    unknown = _refused(ProviderSettingsRefusalCode.UNKNOWN)
    assert service.add(KEYLESS_LANE, model=_ADDED, expected_revision="d" * 64) == unknown
    assert service.remove(KEYLESS_LANE, model=_ADDED, expected_revision="d" * 64) == unknown
    assert service.choose_reading(KEYLESS_LANE, model=_ADDED, expected_revision="d" * 64) == unknown

    reset = _status(service.reset(expected_revision="d" * 64))

    assert reset == LocalModelListStatus(
        unreadable=False,
        models=(),
        reading=None,
        local_lanes=(KEYLESS_LANE,),
        revision=ABSENT_SECURE_OBJECT_REVISION_ID,
    )


def test_a_profile_that_is_not_signed_in_refuses_reads_and_changes() -> None:
    store = MemoryLocalModelListStore()
    store.refusal = StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    service = _service(store)
    signed_out = _refused(ProviderSettingsRefusalCode.NOT_SIGNED_IN)

    assert service.status() == signed_out
    assert service.add(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) == signed_out


class _NoGateway:
    def run(
        self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int, options: tuple[BackgroundOption, ...]
    ) -> ModelRunOutput | ModelRunRefusal:
        del lane, body, deadline_seconds, options
        return ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)


def _reading(status: LocalModelListStatus) -> tuple[str, str] | None:
    return None if status.reading is None else (status.reading.lane, status.reading.model)


@pytest.mark.parametrize(
    ("lane", "model"),
    [(KEYLESS_LANE, KEYLESS_VISION_MODEL), (KEY_LANE, "synthetic-text-1")],
    ids=["local-lane", "keyed-lane"],
)
def test_the_reading_model_is_selected_on_any_reported_lane(lane: str, model: str) -> None:
    service = _service(MemoryLocalModelListStore())

    chosen = _status(service.choose_reading(lane, model=model, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID))

    assert _reading(chosen) == (lane, model)
    assert service.status() == chosen


def test_selecting_the_selected_reading_model_again_writes_nothing() -> None:
    store = MemoryLocalModelListStore()
    revision = _put(store, reading=ListedModel(lane=KEYLESS_LANE, model=KEYLESS_TEXT_MODEL))

    unchanged = _status(
        _service(store).choose_reading(KEYLESS_LANE, model=KEYLESS_TEXT_MODEL, expected_revision=revision)
    )

    assert unchanged.revision == revision


@pytest.mark.parametrize(
    ("lane", "model"),
    [(MISSING_LANE, _ADDED), (KEYLESS_LANE, "has" + chr(9) + "tab"), (KEYLESS_LANE, "")],
    ids=["unreported-lane", "model-with-control-character", "empty-model"],
)
def test_selecting_a_reading_model_on_an_unreported_lane_or_with_a_malformed_name_is_refused(
    lane: str, model: str
) -> None:
    store = MemoryLocalModelListStore()

    refused = _service(store).choose_reading(lane, model=model, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)

    assert refused == _refused(ProviderSettingsRefusalCode.UNKNOWN)
    assert store.stored is None


def test_selecting_a_reading_model_against_a_stale_revision_is_refused() -> None:
    service = _service(MemoryLocalModelListStore())
    status = _status(service.add(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID))

    refused = service.choose_reading(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)

    assert refused == _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
    assert service.status() == status


def test_adding_and_removing_models_keeps_the_reading_model_and_selecting_it_keeps_the_list() -> None:
    service = _service(MemoryLocalModelListStore())
    added = _status(service.add(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID))
    chosen = _status(service.choose_reading(KEYLESS_LANE, model=_ADDED, expected_revision=added.revision))
    assert _added(chosen) == [(KEYLESS_LANE, _ADDED)]

    more = _status(service.add(KEYLESS_LANE, model="another:1", expected_revision=chosen.revision))
    removed = _status(service.remove(KEYLESS_LANE, model="another:1", expected_revision=more.revision))

    assert _reading(more) == _reading(removed) == (KEYLESS_LANE, _ADDED)


def test_a_model_added_and_selected_through_the_service_is_the_one_a_model_run_resolves() -> None:
    store = MemoryLocalModelListStore()
    source = ProvidedProviderCatalogSource(synthetic_catalog())
    live = StaticLiveModels(
        {
            ("local", "api"): (
                live_model(KEYLESS_TEXT_MODEL, vision=False, installed=False),
                live_model(KEYLESS_VISION_MODEL, vision=True, installed=False),
                live_model(_ADDED, vision=False, installed=True),
            )
        }
    )
    runs = ModelRunService(
        model_list=store,
        resolver=ProviderCredentialResolver(store=MemoryProviderSettingsStore(), catalog_source=source),
        catalog_source=source,
        live_models=live,
        gateway=_NoGateway(),
    )
    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
    service = LocalModelListService(store=store, catalog_source=source)

    added = _status(service.add(KEYLESS_LANE, model=_ADDED, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID))
    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
    _status(service.choose_reading(KEYLESS_LANE, model=_ADDED, expected_revision=added.revision))

    assert runs.lookup("text_extraction") == ModelRunLane(
        provider_id="local",
        transport="api",
        model=_ADDED,
        reads_off_host=False,
    )
