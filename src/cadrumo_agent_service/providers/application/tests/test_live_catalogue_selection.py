"""Selections and lookups read the running agent's live entries beside the declared ones.

While an agent runs, a lane's live catalogue adds the models installed on a
local server. A role may select one of those, its facts are the live entry's,
and without a running agent only declared models are selectable or resolvable.
"""

from __future__ import annotations

from typing import Final

import pytest

from cadrumo.core.model_roles import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunLicence, ModelRunRefusal, ModelRunRefusalCode

from ...domain.catalog import CatalogModelFacts
from ..contracts import ModelRoleSelectionsStatus, ProviderSettingsRefusal, ProviderSettingsRefusalCode
from ..lane_entries import merged_entries
from ..model_role_selections import ModelRoleSelectionsService
from ..model_runs import ModelRunService
from ..resolution import ProviderCredentialResolver
from .memory_store import MemoryModelRoleSelectionsStore, MemoryProviderSettingsStore
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
_INSTALLED_UNSTATED: Final = "synthetic-installed-unstated:1"
_SUPPLIED_DIGEST: Final = "sha256:" + "1" * 64


def _installed() -> tuple[CatalogModelFacts, ...]:
    return (
        live_model(
            _INSTALLED_TEXT,
            vision=False,
            size_bytes=2_000,
            context_length=8192,
            licence={"spdx": None, "name": "Licence supplied with the model", "digest": _SUPPLIED_DIGEST},
        ),
        live_model(_INSTALLED_VISION, vision=True, size_bytes=3_000, context_length=None, licence=None),
        live_model(_INSTALLED_UNSTATED),
    )


class _Harness:
    """One profile's selections and lookups over the synthetic catalog and the live entries ``live`` serves."""

    def __init__(self, live: StaticLiveModels) -> None:
        self.live = live
        self.store = MemoryModelRoleSelectionsStore()
        self._source = ProvidedProviderCatalogSource(synthetic_catalog())

    def selections(self) -> ModelRoleSelectionsService:
        return ModelRoleSelectionsService(store=self.store, catalog_source=self._source, live_models=self.live)

    def runs(self) -> ModelRunService:
        return ModelRunService(
            selections=self.store,
            resolver=ProviderCredentialResolver(store=MemoryProviderSettingsStore(), catalog_source=self._source),
            catalog_source=self._source,
            live_models=self.live,
            gateway=_NoMediaGateway(),
        )

    def select(self, role: ModelRole, model: str) -> ModelRoleSelectionsStatus | ProviderSettingsRefusal:
        revision = ABSENT_SECURE_OBJECT_REVISION_ID if self.store.stored is None else self.store.stored.revision
        return self.selections().select(role.value, lane=KEYLESS_LANE, model=model, expected_revision=revision)


class _NoMediaGateway:
    def run(self, *, lane: ModelRunLane, body: object, deadline_seconds: int, options: object) -> ModelRunRefusal:
        del lane, body, deadline_seconds, options
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)


def _running() -> StaticLiveModels:
    return StaticLiveModels({_LOCAL: _installed()})


def test_a_model_only_the_running_agent_lists_is_selectable_and_resolves_with_its_live_facts() -> None:
    harness = _Harness(_running())

    assert isinstance(harness.select(ModelRole.TEXT_EXTRACTION, _INSTALLED_TEXT), ModelRoleSelectionsStatus)

    assert harness.runs().lookup("text_extraction") == ModelRunLane(
        provider_id="local",
        transport="api",
        model=_INSTALLED_TEXT,
        reads_off_host=False,
        licence=ModelRunLicence(spdx=None, name="Licence supplied with the model", digest=_SUPPLIED_DIGEST),
        size_bytes=2_000,
        vision=False,
        context_length=8192,
    )


def test_without_a_running_agent_a_model_only_the_live_catalogue_lists_is_not_in_the_catalogue() -> None:
    harness = _Harness(StaticLiveModels(None))

    refused = harness.select(ModelRole.TEXT_EXTRACTION, _INSTALLED_TEXT)

    assert refused == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.MODEL_NOT_IN_CATALOGUE)
    assert harness.store.stored is None
    assert isinstance(harness.select(ModelRole.TEXT_EXTRACTION, KEYLESS_TEXT_MODEL), ModelRoleSelectionsStatus)


@pytest.mark.parametrize(
    ("model", "admitted"),
    [
        pytest.param(_INSTALLED_VISION, True, id="live-vision-true"),
        pytest.param(_INSTALLED_TEXT, False, id="live-vision-false"),
        pytest.param(_INSTALLED_UNSTATED, False, id="live-vision-unknown"),
    ],
)
def test_the_vision_role_admits_a_live_entry_only_when_it_is_marked_vision(model: str, admitted: bool) -> None:
    harness = _Harness(_running())

    answer = harness.select(ModelRole.VISION_TRANSCRIPTION, model)

    if admitted:
        assert isinstance(answer, ModelRoleSelectionsStatus), answer
    else:
        assert answer == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.VISION_REQUIRED)
        assert harness.store.stored is None


def test_a_live_entry_for_a_declared_model_supplies_the_facts_and_the_vision_decision() -> None:
    """The running agent's entry describes what this computer holds, so it wins over the declared one."""
    live = StaticLiveModels({_LOCAL: (live_model(KEYLESS_VISION_MODEL, vision=None, size_bytes=5_000),)})
    harness = _Harness(live)

    refused = harness.select(ModelRole.VISION_TRANSCRIPTION, KEYLESS_VISION_MODEL)
    assert isinstance(harness.select(ModelRole.TEXT_EXTRACTION, KEYLESS_VISION_MODEL), ModelRoleSelectionsStatus)
    answered = harness.runs().lookup("text_extraction")

    assert refused == ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.VISION_REQUIRED)
    assert isinstance(answered, ModelRunLane)
    assert (answered.size_bytes, answered.vision, answered.context_length, answered.licence) == (
        5_000,
        None,
        None,
        None,
    )


def test_a_selected_model_the_current_entries_no_longer_list_refuses_at_lookup_as_unavailable() -> None:
    harness = _Harness(_running())
    assert isinstance(harness.select(ModelRole.TEXT_EXTRACTION, _INSTALLED_TEXT), ModelRoleSelectionsStatus)
    assert isinstance(harness.select(ModelRole.COLUMN_ROLE_MAPPING, KEYLESS_TEXT_MODEL), ModelRoleSelectionsStatus)

    harness.live = StaticLiveModels(None)
    runs = harness.runs()

    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
    resolved = runs.lookup("column_role_mapping")
    assert isinstance(resolved, ModelRunLane) and resolved.model == KEYLESS_TEXT_MODEL
    read = runs.selections()
    assert isinstance(read, tuple)
    states = {state.role: state for state in read}
    assert states["text_extraction"].refusal is ModelRunRefusalCode.LANE_UNAVAILABLE
    assert states["text_extraction"].selected is not None
    assert states["column_role_mapping"].lane == resolved


def test_a_vision_selection_the_live_entry_no_longer_marks_vision_refuses_at_lookup_as_unavailable() -> None:
    """Selected against the declared entry; the running agent's entry for the same model states no vision."""
    harness = _Harness(StaticLiveModels(None))
    assert isinstance(harness.select(ModelRole.VISION_TRANSCRIPTION, KEYLESS_VISION_MODEL), ModelRoleSelectionsStatus)
    assert isinstance(harness.select(ModelRole.TEXT_EXTRACTION, KEYLESS_VISION_MODEL), ModelRoleSelectionsStatus)
    declared = harness.runs().lookup("vision_transcription")
    assert isinstance(declared, ModelRunLane) and declared.vision is True

    for stated in (None, False):
        harness.live = StaticLiveModels({_LOCAL: (live_model(KEYLESS_VISION_MODEL, vision=stated),)})
        runs = harness.runs()

        assert runs.lookup("vision_transcription") == ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        text = runs.lookup("text_extraction")
        assert isinstance(text, ModelRunLane) and text.vision is stated
        read = runs.selections()
        assert isinstance(read, tuple)
        assert {state.role: state.refusal for state in read}["vision_transcription"] is (
            ModelRunRefusalCode.LANE_UNAVAILABLE
        )


def test_a_selections_read_reads_each_lanes_live_entries_once() -> None:
    harness = _Harness(_running())
    assert isinstance(harness.select(ModelRole.TEXT_EXTRACTION, _INSTALLED_TEXT), ModelRoleSelectionsStatus)
    assert isinstance(harness.select(ModelRole.COLUMN_ROLE_MAPPING, KEYLESS_TEXT_MODEL), ModelRoleSelectionsStatus)
    before = harness.live.reads

    harness.runs().selections()

    assert harness.live.reads - before == 1


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
