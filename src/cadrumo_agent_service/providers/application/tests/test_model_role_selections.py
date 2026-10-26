"""The person's per-role model selection: read every role, set and clear one, each under its revision guard."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cadrumo.core.model_roles import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunLicence, ModelRunRefusal, ModelRunRefusalCode

from ...domain.catalog import ProviderCatalog, parse_provider_catalog
from ..contracts import (
    ModelRoleSelectionEntry,
    ModelRoleSelectionsStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
)
from ..model_role_selections import ModelRoleSelectionsService, selection_refusal
from ..model_runs import ModelRunService
from ..ports import StoreRefusal, StoreRefusalCode
from ..resolution import ProviderCredentialResolver
from .memory_store import MemoryModelRoleSelectionsStore, MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEY_LANE,
    KEYLESS_LANE,
    KEYLESS_TEXT_MODEL,
    KEYLESS_VISION_MODEL,
    MISSING_LANE,
    SIGN_IN_ONLY_LANE,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    synthetic_catalog,
    synthetic_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _service(store: MemoryModelRoleSelectionsStore) -> ModelRoleSelectionsService:
    return ModelRoleSelectionsService(
        store=store, catalog_source=ProvidedProviderCatalogSource(synthetic_catalog()), live_models=StaticLiveModels()
    )


def _status(result: ModelRoleSelectionsStatus | ProviderSettingsRefusal) -> ModelRoleSelectionsStatus:
    assert isinstance(result, ModelRoleSelectionsStatus), result
    return result


def _guard(status: ModelRoleSelectionsStatus) -> str:
    assert status.revision is not None
    return status.revision


def _selected(status: ModelRoleSelectionsStatus) -> dict[str, tuple[str, str]]:
    return {
        entry.role.value: (entry.lane, entry.model)
        for entry in status.roles
        if entry.lane is not None and entry.model is not None
    }


def _refused(code: ProviderSettingsRefusalCode) -> ProviderSettingsRefusal:
    return ProviderSettingsRefusal(code=code)


def test_a_fresh_profile_lists_every_role_with_no_selection() -> None:
    status = _status(_service(MemoryModelRoleSelectionsStore()).status())

    assert status == ModelRoleSelectionsStatus(
        unreadable=False,
        roles=tuple(ModelRoleSelectionEntry(role=role, lane=None, model=None) for role in ModelRole),
        revision=ABSENT_SECURE_OBJECT_REVISION_ID,
    )


def test_setting_one_role_leaves_the_others_and_replaces_only_its_own_selection() -> None:
    service = _service(MemoryModelRoleSelectionsStore())
    first = _status(
        service.select(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )
    second = _status(
        service.select(
            "vision_transcription", lane=SIGN_IN_ONLY_LANE, model="synthetic-vision-1", expected_revision=_guard(first)
        )
    )
    third = _status(
        service.select(
            "text_extraction", lane=SIGN_IN_ONLY_LANE, model="synthetic-text-2", expected_revision=_guard(second)
        )
    )

    assert _selected(third) == {
        "vision_transcription": (SIGN_IN_ONLY_LANE, "synthetic-vision-1"),
        "text_extraction": (SIGN_IN_ONLY_LANE, "synthetic-text-2"),
    }
    assert [entry.role for entry in third.roles] == list(ModelRole)
    assert service.status() == third
    assert len({first.revision, second.revision, third.revision}) == 3


def test_clearing_a_role_removes_only_that_selection() -> None:
    service = _service(MemoryModelRoleSelectionsStore())
    status = _status(
        service.select(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )
    status = _status(
        service.select("column_role_mapping", lane=KEY_LANE, model="synthetic-text-1", expected_revision=_guard(status))
    )

    cleared = _status(service.clear("text_extraction", expected_revision=_guard(status)))

    assert _selected(cleared) == {"column_role_mapping": (KEY_LANE, "synthetic-text-1")}


def test_a_change_against_a_stale_revision_is_refused_and_changes_nothing() -> None:
    service = _service(MemoryModelRoleSelectionsStore())
    status = _status(
        service.select(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )
    conflict = _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)

    assert (
        service.select(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-2",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        == conflict
    )
    assert service.clear("text_extraction", expected_revision="f" * 64) == conflict
    assert service.reset(expected_revision="f" * 64) == conflict
    assert (
        service.select("text_extraction", lane=KEY_LANE, model="synthetic-text-1", expected_revision="not-hex")
        == conflict
    )
    assert service.status() == status


@pytest.mark.parametrize(
    ("role", "lane", "model"),
    [
        ("unknown_role", KEY_LANE, "synthetic-text-1"),
        ("text_extraction", MISSING_LANE, "synthetic-text-1"),
        ("text_extraction", KEY_LANE, "has" + chr(9) + "tab"),
        ("text_extraction", KEY_LANE, "m" * 513),
        ("text_extraction", KEY_LANE, ""),
    ],
    ids=["unknown-role", "unreported-lane", "model-with-control-character", "model-past-the-id-bound", "empty-model"],
)
def test_a_selection_naming_an_unknown_role_lane_or_malformed_model_is_refused(
    role: str, lane: str, model: str
) -> None:
    store = MemoryModelRoleSelectionsStore()
    service = _service(store)

    refused = service.select(role, lane=lane, model=model, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)

    assert refused == _refused(ProviderSettingsRefusalCode.UNKNOWN)
    assert store.stored is None


def test_an_unreadable_record_lists_no_role_refuses_changes_and_only_a_guarded_reset_clears_it() -> None:
    store = MemoryModelRoleSelectionsStore()
    store.unreadable = "d" * 64
    service = _service(store)

    assert service.status() == ModelRoleSelectionsStatus(unreadable=True, roles=(), revision="d" * 64)
    unknown = _refused(ProviderSettingsRefusalCode.UNKNOWN)
    assert (
        service.select("text_extraction", lane=KEY_LANE, model="synthetic-text-1", expected_revision="d" * 64)
        == unknown
    )
    assert service.clear("text_extraction", expected_revision="d" * 64) == unknown

    reset = _status(service.reset(expected_revision="d" * 64))

    assert not reset.unreadable and _selected(reset) == {}
    assert reset.revision == ABSENT_SECURE_OBJECT_REVISION_ID


def test_a_profile_that_is_not_signed_in_refuses_reads_and_changes() -> None:
    store = MemoryModelRoleSelectionsStore()
    store.refusal = StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    service = _service(store)
    signed_out = _refused(ProviderSettingsRefusalCode.NOT_SIGNED_IN)

    assert service.status() == signed_out
    assert (
        service.select(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        == signed_out
    )


def test_a_selection_made_through_the_service_is_the_lane_a_model_run_resolves() -> None:
    store = MemoryModelRoleSelectionsStore()
    source = ProvidedProviderCatalogSource(synthetic_catalog())
    service = ModelRoleSelectionsService(store=store, catalog_source=source, live_models=StaticLiveModels())
    runs = ModelRunService(
        selections=store,
        resolver=ProviderCredentialResolver(store=MemoryProviderSettingsStore(), catalog_source=source),
        catalog_source=source,
        live_models=StaticLiveModels(),
        gateway=_NoMediaGateway(),
    )
    status = _status(
        service.select(
            "vision_transcription",
            lane=SIGN_IN_ONLY_LANE,
            model="synthetic-vision-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )

    assert runs.lookup("vision_transcription") == ModelRunLane(
        provider_id="example",
        transport="cli",
        model="synthetic-vision-1",
        reads_off_host=True,
        licence=None,
        size_bytes=None,
        vision=True,
        context_length=None,
        installed=None,
    )
    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)

    _status(service.clear("vision_transcription", expected_revision=_guard(status)))
    assert runs.lookup("vision_transcription") == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)


class _NoMediaGateway:
    def run(self, *, lane: ModelRunLane, body: object, deadline_seconds: int, options: object) -> ModelRunRefusal:
        del lane, body, deadline_seconds, options
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)


def _catalog_with(lane_id: str, **fields: Any) -> ProviderCatalog:
    """The synthetic catalog with ``fields`` replaced on one lane, through the real parser."""
    document = json.loads(synthetic_document())
    for lane in document["providers"]:
        if lane["id"] == lane_id:
            lane.update(fields)
    return parse_provider_catalog(json.dumps(document))


def _catalog_service(store: MemoryModelRoleSelectionsStore, catalog: ProviderCatalog) -> ModelRoleSelectionsService:
    return ModelRoleSelectionsService(
        store=store, catalog_source=ProvidedProviderCatalogSource(catalog), live_models=StaticLiveModels()
    )


_NOT_RUNNABLE = {"runnable": False, "inputs": [], "options": []}
_TEXT_ONLY = {"runnable": True, "inputs": ["text"], "options": []}


@pytest.mark.parametrize(
    ("catalog", "role", "lane", "model", "code"),
    [
        pytest.param(
            synthetic_catalog(),
            "text_extraction",
            KEY_LANE,
            "synthetic-absent-1",
            ProviderSettingsRefusalCode.MODEL_NOT_IN_CATALOGUE,
            id="model-not-in-catalogue",
        ),
        pytest.param(
            synthetic_catalog(),
            "text_extraction",
            KEYLESS_LANE,
            "synthetic-text-1",
            ProviderSettingsRefusalCode.MODEL_NOT_IN_CATALOGUE,
            id="model-of-another-lane",
        ),
        pytest.param(
            _catalog_with(KEY_LANE, background=_NOT_RUNNABLE),
            "text_extraction",
            KEY_LANE,
            "synthetic-text-1",
            ProviderSettingsRefusalCode.LANE_NOT_RUNNABLE,
            id="lane-not-runnable",
        ),
        pytest.param(
            synthetic_catalog(),
            "vision_transcription",
            KEY_LANE,
            "synthetic-text-1",
            ProviderSettingsRefusalCode.VISION_REQUIRED,
            id="vision-role-on-unstated-model",
        ),
        pytest.param(
            synthetic_catalog(),
            "vision_transcription",
            KEYLESS_LANE,
            KEYLESS_TEXT_MODEL,
            ProviderSettingsRefusalCode.VISION_REQUIRED,
            id="vision-role-on-text-model",
        ),
        pytest.param(
            _catalog_with(KEYLESS_LANE, background=_TEXT_ONLY),
            "vision_transcription",
            KEYLESS_LANE,
            KEYLESS_VISION_MODEL,
            ProviderSettingsRefusalCode.VISION_REQUIRED,
            id="vision-role-on-lane-taking-no-image",
        ),
        pytest.param(
            synthetic_catalog(),
            "text_extraction",
            MISSING_LANE,
            "synthetic-text-1",
            ProviderSettingsRefusalCode.UNKNOWN,
            id="lane-not-in-catalogue",
        ),
    ],
)
def test_a_selection_the_lanes_catalogue_entries_cannot_serve_is_refused_and_nothing_is_stored(
    catalog: ProviderCatalog, role: str, lane: str, model: str, code: ProviderSettingsRefusalCode
) -> None:
    store = MemoryModelRoleSelectionsStore()

    refused = _catalog_service(store, catalog).select(
        role, lane=lane, model=model, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )

    assert refused == _refused(code)
    assert store.stored is None


@pytest.mark.parametrize(
    ("role", "lane", "model"),
    [
        pytest.param("vision_transcription", KEYLESS_LANE, KEYLESS_VISION_MODEL, id="vision-role-on-vision-model"),
        pytest.param("text_extraction", KEYLESS_LANE, KEYLESS_TEXT_MODEL, id="text-role-on-text-model"),
        pytest.param("text_extraction", KEYLESS_LANE, KEYLESS_VISION_MODEL, id="text-role-on-vision-model"),
        pytest.param("column_role_mapping", KEY_LANE, "synthetic-text-2", id="text-role-on-unstated-model"),
        pytest.param("vision_transcription", KEY_LANE, "synthetic-vision-2", id="vision-role-on-hosted-vision-model"),
    ],
)
def test_a_selection_the_lanes_catalogue_entries_serve_is_stored(role: str, lane: str, model: str) -> None:
    store = MemoryModelRoleSelectionsStore()

    status = _status(
        _service(store).select(role, lane=lane, model=model, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)
    )

    assert _selected(status) == {role: (lane, model)}


def test_the_admission_check_reads_whatever_entries_it_is_given() -> None:
    """A model another source lists is admitted once that source's entries are passed with the lane's own."""
    keyless = synthetic_catalog().entry(KEYLESS_LANE)
    hosted = synthetic_catalog().entry(KEY_LANE)
    assert keyless is not None and hosted is not None
    vision = hosted.model("synthetic-vision-1")
    assert vision is not None

    alone = selection_refusal(
        ModelRole.VISION_TRANSCRIPTION, "synthetic-vision-1", background=keyless.background, entries=keyless.models
    )
    joined = selection_refusal(
        ModelRole.VISION_TRANSCRIPTION,
        "synthetic-vision-1",
        background=keyless.background,
        entries=(*keyless.models, vision),
    )

    assert alone is ProviderSettingsRefusalCode.MODEL_NOT_IN_CATALOGUE
    assert joined is None


def test_a_lookup_carries_the_catalogue_facts_of_the_selected_model() -> None:
    store = MemoryModelRoleSelectionsStore()
    source = ProvidedProviderCatalogSource(synthetic_catalog())
    service = ModelRoleSelectionsService(store=store, catalog_source=source, live_models=StaticLiveModels())
    runs = ModelRunService(
        selections=store,
        resolver=ProviderCredentialResolver(store=MemoryProviderSettingsStore(), catalog_source=source),
        catalog_source=source,
        live_models=StaticLiveModels(),
        gateway=_NoMediaGateway(),
    )
    _status(
        service.select(
            "vision_transcription",
            lane=KEYLESS_LANE,
            model=KEYLESS_VISION_MODEL,
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )

    assert runs.lookup("vision_transcription") == ModelRunLane(
        provider_id="local",
        transport="api",
        model=KEYLESS_VISION_MODEL,
        reads_off_host=False,
        licence=ModelRunLicence(spdx="MIT", name="Synthetic licence", digest="sha256:" + "0" * 64),
        size_bytes=1_000_000,
        vision=True,
        context_length=4096,
        installed=None,
    )
    for role in ModelRole:
        if role is not ModelRole.VISION_TRANSCRIPTION:
            assert runs.lookup(role.value) == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
