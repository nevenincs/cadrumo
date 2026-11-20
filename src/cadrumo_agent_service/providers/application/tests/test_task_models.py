"""The lane, model and effort the person sets per task kind: stored beside the reading model, guarded, and served back."""

from __future__ import annotations

import pytest

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID

from ...domain.record import ListedModel, LocalEngine, LocalPlacement
from ..contracts import (
    LocalEngineStatus,
    LocalModelListStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    TaskModelEntry,
)
from ..local_model_list import LocalModelListService
from .memory_store import MemoryLocalModelListStore
from .synthetic_catalog import (
    HOSTED_TEXT_MODELS,
    KEY_LANE,
    KEYLESS_LANE,
    KEYLESS_TEXT_MODEL,
    MISSING_LANE,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    UnavailableCatalogSource,
    engine_catalog,
    synthetic_catalog,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLASSIFICATION = "classification"
_EXTRACTION = "extraction"
_HOSTED = ListedModel(lane=KEY_LANE, model=HOSTED_TEXT_MODELS[0])
_ABSENT = ABSENT_SECURE_OBJECT_REVISION_ID


def _service(store: MemoryLocalModelListStore, *, engines: bool = False) -> LocalModelListService:
    return LocalModelListService(
        store=store,
        catalog_source=ProvidedProviderCatalogSource(engine_catalog() if engines else synthetic_catalog()),
        live_models=StaticLiveModels(),
        default_engine=LocalEngine.LLAMACPP,
    )


def _status(result: LocalModelListStatus | ProviderSettingsRefusal) -> LocalModelListStatus:
    assert isinstance(result, LocalModelListStatus), result
    return result


def _unknown() -> ProviderSettingsRefusal:
    return ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.UNKNOWN)


def test_a_fresh_profile_sets_no_task_kind() -> None:
    assert _status(_service(MemoryLocalModelListStore()).status()).tasks == ()


def test_a_task_setting_is_stored_with_its_effort_and_served_back_in_the_order_set() -> None:
    store = MemoryLocalModelListStore()
    service = _service(store)

    first = _status(service.choose_task(_EXTRACTION, model=_HOSTED, effort="high", expected_revision=_ABSENT))
    local = ListedModel(lane=KEYLESS_LANE, model=KEYLESS_TEXT_MODEL)
    second = _status(service.choose_task(_CLASSIFICATION, model=local, effort=None, expected_revision=first.revision))

    assert second.tasks == (
        TaskModelEntry(task_kind=_EXTRACTION, lane=KEY_LANE, model=HOSTED_TEXT_MODELS[0], effort="high"),
        TaskModelEntry(task_kind=_CLASSIFICATION, lane=KEYLESS_LANE, model=KEYLESS_TEXT_MODEL, effort=None),
    )
    assert _status(service.status()) == second
    assert store.stored is not None and store.stored.record.schema_version == 4


def test_changing_a_task_setting_replaces_it_in_place_and_clearing_it_leaves_the_others() -> None:
    service = _service(MemoryLocalModelListStore())
    first = _status(service.choose_task(_EXTRACTION, model=_HOSTED, effort=None, expected_revision=_ABSENT))
    second = _status(service.choose_task(_CLASSIFICATION, model=_HOSTED, effort=None, expected_revision=first.revision))

    changed = _status(service.choose_task(_EXTRACTION, model=_HOSTED, effort="low", expected_revision=second.revision))
    assert [(task.task_kind, task.effort) for task in changed.tasks] == [(_EXTRACTION, "low"), (_CLASSIFICATION, None)]

    cleared = _status(service.choose_task(_EXTRACTION, model=None, effort=None, expected_revision=changed.revision))
    assert [task.task_kind for task in cleared.tasks] == [_CLASSIFICATION]


def test_a_task_setting_keeps_the_reading_model_the_list_and_the_engine_and_they_keep_it() -> None:
    service = _service(MemoryLocalModelListStore())
    read = _status(service.choose_reading(KEY_LANE, model=HOSTED_TEXT_MODELS[1], expected_revision=_ABSENT))
    added = _status(service.add(KEYLESS_LANE, model="custom-model:test", expected_revision=read.revision))
    tasked = _status(service.choose_task(_CLASSIFICATION, model=_HOSTED, effort=None, expected_revision=added.revision))

    assert tasked.reading == read.reading
    assert tasked.models == added.models

    engine = service.choose_engine(LocalEngine.OLLAMA, LocalPlacement.CPU_ONLY, expected_revision=tasked.revision)
    assert isinstance(engine, LocalEngineStatus)
    after = _status(service.status())
    assert after.tasks == tasked.tasks
    assert after.reading == tasked.reading


def test_storing_the_setting_already_stored_answers_unchanged() -> None:
    store = MemoryLocalModelListStore()
    service = _service(store)
    first = _status(service.choose_task(_CLASSIFICATION, model=_HOSTED, effort="high", expected_revision=_ABSENT))
    stored = store.stored

    again = _status(
        service.choose_task(_CLASSIFICATION, model=_HOSTED, effort="high", expected_revision=first.revision)
    )

    assert again == first
    assert store.stored is stored


@pytest.mark.parametrize(
    ("task_kind", "model", "effort"),
    [
        pytest.param("summary", _HOSTED, None, id="kind-the-catalogue-does-not-serve"),
        pytest.param("Classification", _HOSTED, None, id="malformed-kind"),
        pytest.param(_CLASSIFICATION, ListedModel(lane=MISSING_LANE, model="m"), None, id="lane-not-reported"),
        pytest.param(_CLASSIFICATION, ListedModel(lane=KEYLESS_LANE, model="not-listed:1"), None, id="local-unlisted"),
        pytest.param(_CLASSIFICATION, _HOSTED, "High", id="malformed-effort"),
        pytest.param(_CLASSIFICATION, None, "high", id="effort-without-a-model"),
    ],
)
def test_a_task_setting_outside_the_served_vocabulary_is_refused_and_nothing_is_written(
    task_kind: str, model: ListedModel | None, effort: str | None
) -> None:
    store = MemoryLocalModelListStore()

    assert _service(store).choose_task(task_kind, model=model, effort=effort, expected_revision=_ABSENT) == _unknown()
    assert store.stored is None


def test_a_task_setting_on_the_lane_of_an_engine_the_profile_does_not_run_is_refused() -> None:
    store = MemoryLocalModelListStore()
    other = ListedModel(lane=f"{LocalEngine.OLLAMA.value}_api", model=KEYLESS_TEXT_MODEL)

    refused = _service(store, engines=True).choose_task(
        _CLASSIFICATION, model=other, effort=None, expected_revision=_ABSENT
    )

    assert refused == _unknown()
    assert store.stored is None


def test_a_task_setting_against_a_stale_revision_is_refused() -> None:
    service = _service(MemoryLocalModelListStore())
    first = _status(service.choose_task(_CLASSIFICATION, model=_HOSTED, effort=None, expected_revision=_ABSENT))

    stale = service.choose_task(_EXTRACTION, model=_HOSTED, effort=None, expected_revision=_ABSENT)

    assert stale == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.REVISION_CONFLICT)
    assert _status(service.status()) == first


def test_without_the_catalogue_no_task_setting_is_stored() -> None:
    store = MemoryLocalModelListStore()
    service = LocalModelListService(
        store=store,
        catalog_source=UnavailableCatalogSource(),
        live_models=StaticLiveModels(),
        default_engine=LocalEngine.LLAMACPP,
    )

    refused = service.choose_task(_CLASSIFICATION, model=_HOSTED, effort=None, expected_revision=_ABSENT)

    assert refused == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE)
    assert store.stored is None


def test_an_unreadable_record_serves_no_task_setting_and_refuses_one() -> None:
    store = MemoryLocalModelListStore()
    store.unreadable = "d" * 64
    service = _service(store)

    assert _status(service.status()).tasks == ()
    assert service.choose_task(_CLASSIFICATION, model=_HOSTED, effort=None, expected_revision="d" * 64) == _unknown()
