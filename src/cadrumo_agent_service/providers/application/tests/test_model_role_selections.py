"""The person's per-role model selection: read every role, set and clear one, each under its revision guard."""

from __future__ import annotations

import pytest

from cadrumo.core.model_catalogue import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import StorageMode
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ..contracts import (
    ModelRoleSelectionEntry,
    ModelRoleSelectionsStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
)
from ..model_runs import ModelRunService
from ..ports import StoreRefusal, StoreRefusalCode
from ..resolution import ProviderCredentialResolver
from ..service import ProviderSettingsService
from .memory_store import MemoryProviderSettingsStore
from .synthetic_catalog import (
    KEY_LANE,
    MISSING_LANE,
    SIGN_IN_ONLY_LANE,
    ProvidedProviderCatalogSource,
    synthetic_catalog,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _service(store: MemoryProviderSettingsStore) -> ProviderSettingsService:
    return ProviderSettingsService(
        store=store,
        catalog_source=ProvidedProviderCatalogSource(synthetic_catalog()),
        storage_mode=StorageMode.INSTALLED,
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
    status = _status(_service(MemoryProviderSettingsStore()).model_roles())

    assert status == ModelRoleSelectionsStatus(
        unreadable=False,
        roles=tuple(ModelRoleSelectionEntry(role=role, lane=None, model=None) for role in ModelRole),
        revision=ABSENT_SECURE_OBJECT_REVISION_ID,
    )


def test_setting_one_role_leaves_the_others_and_replaces_only_its_own_selection() -> None:
    service = _service(MemoryProviderSettingsStore())
    first = _status(
        service.set_model_role(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )
    second = _status(
        service.set_model_role(
            "vision_transcription", lane=SIGN_IN_ONLY_LANE, model="synthetic-vision-1", expected_revision=_guard(first)
        )
    )
    third = _status(
        service.set_model_role(
            "text_extraction", lane=SIGN_IN_ONLY_LANE, model="synthetic-text-2", expected_revision=_guard(second)
        )
    )

    assert _selected(third) == {
        "vision_transcription": (SIGN_IN_ONLY_LANE, "synthetic-vision-1"),
        "text_extraction": (SIGN_IN_ONLY_LANE, "synthetic-text-2"),
    }
    assert [entry.role for entry in third.roles] == list(ModelRole)
    assert service.model_roles() == third
    assert len({first.revision, second.revision, third.revision}) == 3


def test_clearing_a_role_removes_only_that_selection() -> None:
    service = _service(MemoryProviderSettingsStore())
    status = _status(
        service.set_model_role(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )
    status = _status(
        service.set_model_role(
            "column_role_mapping", lane=KEY_LANE, model="synthetic-text-1", expected_revision=_guard(status)
        )
    )

    cleared = _status(service.clear_model_role("text_extraction", expected_revision=_guard(status)))

    assert _selected(cleared) == {"column_role_mapping": (KEY_LANE, "synthetic-text-1")}


def test_a_change_against_a_stale_revision_is_refused_and_changes_nothing() -> None:
    service = _service(MemoryProviderSettingsStore())
    status = _status(
        service.set_model_role(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )
    conflict = _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)

    assert (
        service.set_model_role(
            "text_extraction",
            lane=KEY_LANE,
            model="synthetic-text-2",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        == conflict
    )
    assert service.clear_model_role("text_extraction", expected_revision="f" * 64) == conflict
    assert service.reset_model_roles(expected_revision="f" * 64) == conflict
    assert service.set_model_role("text_extraction", lane=KEY_LANE, model="m", expected_revision="not-hex") == conflict
    assert service.model_roles() == status


@pytest.mark.parametrize(
    ("role", "lane", "model"),
    [
        ("unknown_role", KEY_LANE, "synthetic-text-1"),
        ("text_extraction", MISSING_LANE, "synthetic-text-1"),
        ("text_extraction", KEY_LANE, "has space"),
        ("text_extraction", KEY_LANE, ""),
    ],
    ids=["unknown-role", "unreported-lane", "model-with-space", "empty-model"],
)
def test_a_selection_naming_an_unknown_role_lane_or_malformed_model_is_refused(
    role: str, lane: str, model: str
) -> None:
    store = MemoryProviderSettingsStore()
    service = _service(store)

    refused = service.set_model_role(role, lane=lane, model=model, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)

    assert refused == _refused(ProviderSettingsRefusalCode.UNKNOWN)
    assert store.selections is None


def test_an_unreadable_record_lists_no_role_refuses_changes_and_only_a_guarded_reset_clears_it() -> None:
    store = MemoryProviderSettingsStore()
    store.unreadable_selections = "d" * 64
    service = _service(store)

    assert service.model_roles() == ModelRoleSelectionsStatus(unreadable=True, roles=(), revision="d" * 64)
    unknown = _refused(ProviderSettingsRefusalCode.UNKNOWN)
    assert service.set_model_role("text_extraction", lane=KEY_LANE, model="m", expected_revision="d" * 64) == unknown
    assert service.clear_model_role("text_extraction", expected_revision="d" * 64) == unknown

    reset = _status(service.reset_model_roles(expected_revision="d" * 64))

    assert not reset.unreadable and _selected(reset) == {}
    assert reset.revision == ABSENT_SECURE_OBJECT_REVISION_ID


def test_a_profile_that_is_not_signed_in_refuses_reads_and_changes() -> None:
    store = MemoryProviderSettingsStore()
    store.refusal = StoreRefusal(code=StoreRefusalCode.NOT_SIGNED_IN)
    service = _service(store)
    signed_out = _refused(ProviderSettingsRefusalCode.NOT_SIGNED_IN)

    assert service.model_roles() == signed_out
    assert (
        service.set_model_role(
            "text_extraction", lane=KEY_LANE, model="m", expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        == signed_out
    )


def test_a_selection_made_through_the_service_is_the_lane_a_model_run_resolves() -> None:
    store = MemoryProviderSettingsStore()
    source = ProvidedProviderCatalogSource(synthetic_catalog())
    service = ProviderSettingsService(store=store, catalog_source=source, storage_mode=StorageMode.INSTALLED)
    runs = ModelRunService(
        store=store,
        resolver=ProviderCredentialResolver(store=store, catalog_source=source),
        catalog_source=source,
        gateway=_NoMediaGateway(),
    )
    status = _status(
        service.set_model_role(
            "vision_transcription",
            lane=SIGN_IN_ONLY_LANE,
            model="synthetic-vision-1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    )

    assert runs.lookup("vision_transcription") == ModelRunLane(
        provider_id="example", transport="cli", model="synthetic-vision-1"
    )
    assert runs.lookup("text_extraction") == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)

    _status(service.clear_model_role("vision_transcription", expected_revision=_guard(status)))
    assert runs.lookup("vision_transcription") == ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)


class _NoMediaGateway:
    def accepted_media(self, lane: ModelRunLane) -> None:
        del lane

    def run(self, *, lane: ModelRunLane, body: object, deadline_seconds: int) -> ModelRunRefusal:
        del lane, body, deadline_seconds
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)
