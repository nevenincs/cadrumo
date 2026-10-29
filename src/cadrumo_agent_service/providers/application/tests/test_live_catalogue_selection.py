"""Lookups read the running agent's live entries beside the declared ones.

While an agent runs, a lane's live catalogue states the models its local server
holds and what each can read. A selected model added to the list resolves with
the live entry's facts, a live entry decides vision over the declared one, and
without a running agent an added model nothing declares states nothing, so it
reads text with no facts and never images.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

import pytest

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ...domain.catalog import LiveCatalogModel
from ...domain.record import ListedModel, LocalModelListRecord, new_settings_generation
from ..lane_entries import merged_entries
from ..model_runs import ModelRunService
from ..resolution import ProviderCredentialResolver
from .memory_store import MemoryLocalModelListStore, MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEYLESS_LANE,
    KEYLESS_TEXT_MODEL,
    KEYLESS_VISION_MODEL,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    live_model,
    synthetic_catalog,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCAL: Final = ("local", "api")
"""The provider and transport of the synthetic keyless lane."""
_INSTALLED_TEXT: Final = "synthetic-installed:1"
_INSTALLED_VISION: Final = "synthetic-installed-vision:1"


def _held(*extra: LiveCatalogModel) -> tuple[LiveCatalogModel, ...]:
    """The recommended models the server does not hold, then ``extra``."""
    return (
        live_model(KEYLESS_TEXT_MODEL, vision=False, installed=False),
        live_model(KEYLESS_VISION_MODEL, vision=True, installed=False),
        *extra,
    )


def _installed_text() -> LiveCatalogModel:
    return live_model(_INSTALLED_TEXT, vision=False, installed=True)


class _NoMediaGateway:
    def run(self, *, lane: ModelRunLane, body: object, deadline_seconds: int, options: object) -> ModelRunRefusal:
        del lane, body, deadline_seconds, options
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)


def _runs(live: StaticLiveModels, reading: str, *added: str) -> ModelRunService:
    """A service whose person selected ``reading`` on the keyless lane and added ``added`` to its list."""
    store = MemoryLocalModelListStore()
    record = LocalModelListRecord(
        schema_version=2,
        models=tuple(ListedModel(lane=KEYLESS_LANE, model=model) for model in added),
        reading=ListedModel(lane=KEYLESS_LANE, model=reading),
        generation=new_settings_generation(),
        updated_at=datetime(2026, 10, 27, 9, 0, tzinfo=UTC),
    )
    assert store.write(record, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID) is None
    source = ProvidedProviderCatalogSource(synthetic_catalog())
    return ModelRunService(
        model_list=store,
        resolver=ProviderCredentialResolver(store=MemoryProviderSettingsStore(), catalog_source=source),
        catalog_source=source,
        live_models=live,
        gateway=_NoMediaGateway(),
    )


def test_an_added_model_only_the_running_agent_lists_resolves_on_its_lane() -> None:
    runs = _runs(StaticLiveModels({_LOCAL: _held(_installed_text())}), _INSTALLED_TEXT, _INSTALLED_TEXT)

    assert runs.lookup("text_extraction") == ModelRunLane(
        provider_id="local",
        transport="api",
        model=_INSTALLED_TEXT,
        reads_off_host=False,
    )


def test_a_declared_model_the_running_agent_does_not_list_resolves_on_its_lane() -> None:
    runs = _runs(StaticLiveModels({_LOCAL: ()}), KEYLESS_TEXT_MODEL)

    lane = runs.lookup("text_extraction")

    assert isinstance(lane, ModelRunLane)
    assert lane.model == KEYLESS_TEXT_MODEL


def test_without_a_running_agent_an_added_model_nothing_declares_reads_text_and_never_images() -> None:
    runs = _runs(StaticLiveModels(None), _INSTALLED_TEXT, _INSTALLED_TEXT)

    lane = runs.lookup("text_extraction")

    assert isinstance(lane, ModelRunLane)
    assert lane.model == _INSTALLED_TEXT
    assert runs.lookup("vision_transcription") == ModelRunRefusal(code=ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES)


@pytest.mark.parametrize(
    ("vision", "admitted"),
    [
        pytest.param(True, True, id="live-vision-true"),
        pytest.param(False, False, id="live-vision-false"),
        pytest.param(None, False, id="live-vision-unknown"),
    ],
)
def test_the_vision_role_reads_with_a_live_entry_only_when_it_is_marked_vision(
    vision: bool | None, admitted: bool
) -> None:
    held = live_model(_INSTALLED_VISION, vision=vision, installed=True)
    runs = _runs(StaticLiveModels({_LOCAL: _held(held)}), _INSTALLED_VISION, _INSTALLED_VISION)

    answer = runs.lookup("vision_transcription")

    if admitted:
        assert isinstance(answer, ModelRunLane) and answer.model == _INSTALLED_VISION
    else:
        assert answer == ModelRunRefusal(code=ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES)


def test_a_live_entry_for_a_declared_model_supplies_the_vision_decision() -> None:
    """The running agent's entry describes what this computer holds, so it wins over the declared one."""
    live = StaticLiveModels(
        {
            _LOCAL: (
                live_model(KEYLESS_TEXT_MODEL, vision=False, installed=False),
                live_model(KEYLESS_VISION_MODEL, vision=None, installed=True),
            )
        }
    )
    runs = _runs(live, KEYLESS_VISION_MODEL)

    assert runs.lookup("vision_transcription") == ModelRunRefusal(code=ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES)
    answered = runs.lookup("text_extraction")
    assert isinstance(answered, ModelRunLane)
    assert answered.model == KEYLESS_VISION_MODEL


def test_live_entries_come_first_and_win_over_declared_ones_of_the_same_model() -> None:
    declared = (live_model("synthetic-a:1", size_bytes=1), live_model("synthetic-b:1", size_bytes=2))
    live = (live_model("synthetic-c:1", size_bytes=3), live_model("synthetic-a:1", size_bytes=4))

    merged = merged_entries(declared, live)

    assert [(entry.id, entry.size_bytes) for entry in merged] == [
        ("synthetic-c:1", 3),
        ("synthetic-a:1", 4),
        ("synthetic-b:1", 2),
    ]
    assert merged_entries(declared, None) == declared
    assert merged_entries(declared, ()) == declared
