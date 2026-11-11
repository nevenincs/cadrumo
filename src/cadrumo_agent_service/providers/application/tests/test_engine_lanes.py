"""The provider settings and the local model lists serve the selected engine's keyless lane, and not the other's.

The real services over in-memory stores and a catalogue that reports a keyless
lane for each local engine beside a keyless lane that is no engine's. One rule
scopes both, so both list the same lanes for each engine, and an engine setting
that cannot be read picks no engine.
"""

from __future__ import annotations

import pytest

from ...domain.record import LocalEngine, LocalPlacement
from ..contracts import (
    LocalEngineStatus,
    LocalModelListStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
)
from ..local_model_list import LocalModelListService, engine_lanes, serves_engine_lane
from ..service import ProviderSettingsService
from .memory_store import MemoryLocalModelListStore, MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEYLESS_LANE,
    KEYLESS_TEXT_MODEL,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    engine_catalog,
    synthetic_catalog,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ADDED = "custom-model:test"


def _lane(engine: LocalEngine) -> str:
    return f"{engine.value}_api"


def _other(engine: LocalEngine) -> LocalEngine:
    return next(held for held in LocalEngine if held is not engine)


def _services(
    default_engine: LocalEngine = LocalEngine.LLAMACPP,
) -> tuple[MemoryLocalModelListStore, LocalModelListService, ProviderSettingsService]:
    store = MemoryLocalModelListStore()
    source = ProvidedProviderCatalogSource(engine_catalog())
    models = LocalModelListService(
        store=store, catalog_source=source, live_models=StaticLiveModels(), default_engine=default_engine
    )
    settings = ProviderSettingsService(
        store=MemoryProviderSettingsStore(), catalog_source=source, selected_engine=models.selected_engine
    )
    return store, models, settings


def _choose(models: LocalModelListService, engine: LocalEngine) -> None:
    current = models.engine_status()
    assert isinstance(current, LocalEngineStatus), current
    chosen = models.choose_engine(engine, LocalPlacement.AUTO, expected_revision=current.revision)
    assert isinstance(chosen, LocalEngineStatus) and chosen.engine is engine, chosen


def _local_lanes(models: LocalModelListService) -> tuple[str, ...]:
    status = models.status()
    assert isinstance(status, LocalModelListStatus), status
    return status.local_lanes


def _settings_lanes(settings: ProviderSettingsService) -> tuple[str, ...]:
    status = settings.status()
    assert isinstance(status, ProviderSettingsStatus), status
    return tuple(entry.id for entry in status.providers)


@pytest.mark.parametrize("engine", list(LocalEngine))
def test_an_engine_lane_is_served_only_under_its_own_engine(engine: LocalEngine) -> None:
    assert serves_engine_lane(engine.value, engine)
    assert not serves_engine_lane(engine.value, _other(engine))
    assert not serves_engine_lane(engine.value, None)


@pytest.mark.parametrize("engine", [*LocalEngine, None])
def test_a_lane_that_is_no_engines_is_served_whatever_the_engine(engine: LocalEngine | None) -> None:
    for entry in synthetic_catalog().providers:
        assert serves_engine_lane(entry.provider, engine), entry.id


@pytest.mark.parametrize("engine", list(LocalEngine))
def test_the_local_lanes_and_the_settings_list_the_selected_engine_lane_alone(engine: LocalEngine) -> None:
    _, models, settings = _services()
    _choose(models, engine)

    every = tuple(entry.id for entry in engine_catalog().providers)
    expected = tuple(lane for lane in every if lane != _lane(_other(engine)))
    assert _settings_lanes(settings) == expected
    assert _local_lanes(models) == (KEYLESS_LANE, _lane(engine))
    assert set(_local_lanes(models)) <= set(_settings_lanes(settings))


@pytest.mark.parametrize("engine", list(LocalEngine))
def test_an_unchosen_record_serves_the_default_engine_lane(engine: LocalEngine) -> None:
    _, models, settings = _services(default_engine=engine)

    assert _local_lanes(models) == (KEYLESS_LANE, _lane(engine))
    assert _lane(_other(engine)) not in _settings_lanes(settings)


def test_an_unreadable_engine_record_picks_no_engine_and_serves_neither_engine_lane() -> None:
    store, models, settings = _services()
    store.unreadable = "f" * 64

    assert models.selected_engine() is None
    assert _local_lanes(models) == (KEYLESS_LANE,)
    lanes = _settings_lanes(settings)
    assert not {_lane(engine) for engine in LocalEngine} & set(lanes)
    assert KEYLESS_LANE in lanes


@pytest.mark.parametrize("engine", list(LocalEngine))
def test_the_other_engine_lane_takes_no_model_and_no_reading_choice(engine: LocalEngine) -> None:
    _, models, _ = _services()
    _choose(models, engine)
    status = models.status()
    assert isinstance(status, LocalModelListStatus)

    added = models.add(_lane(_other(engine)), model=_ADDED, expected_revision=status.revision)
    chosen = models.choose_reading(_lane(_other(engine)), model=KEYLESS_TEXT_MODEL, expected_revision=status.revision)

    assert added == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.UNKNOWN)
    assert chosen == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.UNKNOWN)
    taken = models.add(_lane(engine), model=_ADDED, expected_revision=status.revision)
    assert isinstance(taken, LocalModelListStatus), taken


def test_a_catalogue_with_no_engine_lane_is_served_whole_without_reading_the_engine() -> None:
    def unread() -> LocalEngine | None:
        raise AssertionError("the engine was read for a catalogue that reports no engine lane")

    catalog = synthetic_catalog()

    assert engine_lanes(catalog, unread) == catalog.providers
