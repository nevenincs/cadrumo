"""The runtime manager preserves exact session and CAS intent across its doors."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.widgets import Button

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....adapters.local_runtime.frontend_client_contracts import ProfileViewCollection, RuntimeFrontendRefusedError
from .....adapters.local_runtime.profile_mutations import (
    ProfileMutationCompletion,
    ProfileMutationRequest,
    ProfileMutationRunError,
)
from .....application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .....application.user_profile.overview import ProfileOverview, ProfileSectionView
from .....application.user_profile.profile_operation_contracts import (
    ProfileCompleteSetupOperationProjection,
    ProfileCompleteSetupOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationProjection,
    ProfilePlantillaMediaOperationProjection,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaSet,
    ProfileRepeatableRowChangeOperationProjection,
    ProfileRepeatableRowMutationOperationProjection,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
)
from .....application.user_profile.view_operation import ProfileViewOperationProjection, ProfileViewPageKind
from .....core.errors.error_codes import get_registered_error_code
from .....core.errors.hierarchy import CadrumoError
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.identity.digest import ContentDigest
from .....core.operations import OperationEffect
from .....domain.user_profile.plantilla_media import PlantillaMediaState
from .....domain.user_profile.values import ProfileSetupState
from ...aeat_sync.models import AeatSyncOperationHandoffV1, AeatSyncOperationRequestV1
from ...components.host import ScreenHostApp
from ...components.status import PinnedStatusBar
from ...operations.controller_port import OperationControllerPort
from .. import runtime_manager
from ..runtime_errors import ProfileManagerCompletedViewUnavailableError
from ..runtime_manager import (
    RuntimeProfileManagerComposition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DIGEST = "a" * 64
_OPERATION_ID = "b" * 64


class _Client(RuntimeFrontendClient):
    """An exact-profile wire boundary with no local custody or operation behavior."""

    def __init__(
        self, profile_id: UUID, *, frontend: OperationFrontendProjection = OperationFrontendProjection.TUI
    ) -> None:
        self._profile_id = profile_id
        self._frontend = frontend
        self._session_id = uuid4()
        self.view_requests: list[tuple[ProfileViewPageKind, ...]] = []

    @override
    def read_profile_view(
        self,
        page_kinds: tuple[ProfileViewPageKind, ...],
        *,
        output_language: OutputLanguage = OutputLanguage.ES,
        expected_revision: int | None = None,
        expected_content_digest: ContentDigest | None = None,
        timeout: float = 60,
        max_pages: int = 512,
    ) -> ProfileViewCollection:
        assert output_language is OutputLanguage.ES
        assert expected_revision is None and expected_content_digest is None
        assert timeout > 0 and max_pages > 0
        self.view_requests.append(page_kinds)
        page = ProfileViewOperationProjection(
            profile_id=self.profile_id,
            page_kind=ProfileViewPageKind.FACTS,
            outcome="page",
            record_revision=4,
            content_digest=_DIGEST,
            setup_state=ProfileSetupState.INCOMPLETE,
            schema_version=1,
            valid=True,
            cursor=0,
            total_items=0,
        )
        return ProfileViewCollection(
            profile_id=self.profile_id,
            record_revision=4,
            content_digest=_DIGEST,
            setup_state=ProfileSetupState.INCOMPLETE,
            schema_version=1,
            valid=True,
            page_kinds=page_kinds,
            pages=(page,),
        )


def _overview(profile_id: UUID, revision: int, *, label: str = "Chosen profile") -> ProfileOverview:
    return ProfileOverview(
        profile_id=str(profile_id),
        record_revision=revision,
        content_digest=_DIGEST,
        label=label,
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(ProfileSectionView(key="identity", title="Identity", summary="", repeatable=False, fields=()),),
    )


def _projection(request: ProfileMutationRequest, revision: int) -> ProfileMutationOperationProjection:
    common = {"profile_id": request.profile_id, "record_revision": revision}
    if isinstance(request, ProfileRepeatableRowMutationOperationRequest):
        return ProfileRepeatableRowMutationOperationProjection(**common, section_key=request.section_key, row_index=0)
    if isinstance(request, (ProfileRepeatableRowUpdateOperationRequest, ProfileRepeatableRowRemoveOperationRequest)):
        return ProfileRepeatableRowChangeOperationProjection(
            **common, section_key=request.section_key, row_key=request.row_key, changed=True
        )
    if isinstance(request, ProfilePlantillaMediaOperationRequest):
        return ProfilePlantillaMediaOperationProjection(**common, year=request.year, changed=True)
    if isinstance(request, ProfileCompleteSetupOperationRequest):
        return ProfileCompleteSetupOperationProjection(**common, already_complete=False)
    return ProfileMutationOperationProjection(**common)


def _composition(
    client: _Client,
    *,
    runner: Callable[[RuntimeFrontendClient, ProfileMutationRequest], ProfileMutationCompletion],
    reader: Callable[[RuntimeFrontendClient, str, OutputLanguage], ProfileOverview],
) -> RuntimeProfileManagerComposition:
    return RuntimeProfileManagerComposition(
        client,
        profile_label="Chosen profile",
        output_language=OutputLanguage.ES,
        mutation_runner=runner,
        overview_reader=reader,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "definition"),
    [("censal_review", "user-profile.censo-review"), ("filed_history", "live.filed-history.pull")],
)
async def test_onboarding_source_buttons_reach_the_runtime_handoff(
    source: str, definition: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _Client(uuid4())
    requests: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1, /) -> OperationControllerPort:
        requests.append(request)
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    def compose(
        subject: RuntimeFrontendClient, *, output_root: Path
    ) -> tuple[AeatSyncOperationHandoffV1, OperationPublicContractSetV1 | None]:
        assert subject is client
        assert output_root
        return handoff, None

    def refuse_mutation(subject: RuntimeFrontendClient, request: ProfileMutationRequest) -> ProfileMutationCompletion:
        raise AssertionError("acquisition must use its own registered operation")

    monkeypatch.setattr(runtime_manager, "compose_runtime_aeat_sync_handoff", compose)
    composition = _composition(
        client, runner=refuse_mutation, reader=lambda _client, _label, _language: _overview(client.profile_id, 1)
    )
    screen = composition.compose()
    async with ScreenHostApp(screen).run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        await pilot.click("#setup-stage-get_data")
        await pilot.pause()
        button = screen.query_one(f"#source-{source} Button", Button)
        button.scroll_visible(immediate=True)
        await pilot.pause()
        assert button.display and not button.disabled
        await pilot.click(button)
        await pilot.pause()
        assert [str(request.operation) for request in requests] == [definition]
        assert not screen.disabled


def test_every_write_door_carries_exact_dialog_cas_and_reads_authorized_overview() -> None:
    client = _Client(uuid4())
    revision = [7]
    calls: list[ProfileMutationRequest] = []
    reads: list[tuple[UUID, str, OutputLanguage]] = []

    def reader(subject: RuntimeFrontendClient, label: str, language: OutputLanguage) -> ProfileOverview:
        reads.append((subject.profile_id, label, language))
        return _overview(subject.profile_id, revision[0], label=label)

    def run(_subject: RuntimeFrontendClient, request: ProfileMutationRequest) -> ProfileMutationCompletion:
        calls.append(request)
        revision[0] += 1
        return ProfileMutationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(request, revision[0]),
            effect=OperationEffect.UPDATED,
        )

    screen = _composition(client, runner=run, reader=reader).compose()
    assert screen._add_row is not None
    assert screen._update_row is not None
    assert screen._remove_row is not None
    assert screen._complete_setup is not None
    assert screen._set_plantilla_media is not None
    assert screen._remove_plantilla_media is not None
    field = screen._persist_field("identity.legal_name", "New name", 7, _DIGEST)
    assert isinstance(calls[-1], ProfileFieldMutationOperationRequest)
    assert calls[-1].expected_revision == 7 and calls[-1].expected_content_digest == _DIGEST
    assert calls[-1].value == "New name"

    added = screen._add_row("activities", {"description": "Trade"}, 8, _DIGEST)
    assert isinstance(calls[-1], ProfileRepeatableRowMutationOperationRequest)
    assert [(item.field_key, item.value) for item in calls[-1].values] == [("description", "Trade")]
    assert calls[-1].expected_revision == 8

    updated = screen._update_row("activities", "3", {"description": "Updated"}, ("code",), 9, _DIGEST)
    assert isinstance(calls[-1], ProfileRepeatableRowUpdateOperationRequest)
    assert calls[-1].row_key == "3" and calls[-1].clear_fields == ("code",)
    assert calls[-1].expected_revision == 9

    removed = screen._remove_row("activities", "3", 10, _DIGEST)
    assert isinstance(calls[-1], ProfileRepeatableRowRemoveOperationRequest)
    assert calls[-1].row_key == "3" and calls[-1].expected_revision == 10

    screen.overview = removed
    completed = screen._complete_setup()
    assert isinstance(calls[-1], ProfileCompleteSetupOperationRequest)
    assert calls[-1].expected_revision == 11

    screen.overview = completed
    workforce = screen._set_plantilla_media(2026, Decimal("1.25"), PlantillaMediaState.OBSERVED)
    assert isinstance(calls[-1], ProfilePlantillaMediaOperationRequest)
    assert calls[-1].expected_revision == 12 and calls[-1].year == 2026
    assert calls[-1].change == ProfilePlantillaMediaSet(average_workforce="1.25", state=PlantillaMediaState.OBSERVED)
    screen.overview = workforce
    screen._remove_plantilla_media(2026)
    assert isinstance(calls[-1], ProfilePlantillaMediaOperationRequest)
    assert calls[-1].expected_revision == 13
    assert calls[-1].change.kind == "remove"

    assert field.record_revision == 8 and added.record_revision == 9 and updated.record_revision == 10
    assert len(reads) == 8  # first overview plus each of seven settled writes
    assert all(read == (client.profile_id, "Chosen profile", OutputLanguage.ES) for read in reads)


def test_failed_mutation_does_not_read_again_and_preserves_original_run_error() -> None:
    client = _Client(uuid4())
    reads = [0]
    failure = ProfileMutationRunError(operation_id=_OPERATION_ID, code="refused")

    def reader(subject: RuntimeFrontendClient, _label: str, _language: OutputLanguage) -> ProfileOverview:
        reads[0] += 1
        return _overview(subject.profile_id, 4)

    def run(_subject: RuntimeFrontendClient, _request: ProfileMutationRequest) -> ProfileMutationCompletion:
        raise failure

    screen = _composition(client, runner=run, reader=reader).compose()
    with pytest.raises(ProfileMutationRunError) as caught:
        screen._persist_field("identity.legal_name", "No", 4, _DIGEST)
    assert caught.value is failure
    assert reads == [1]


def test_post_commit_read_refusal_retains_settled_identity_and_effect() -> None:
    client = _Client(uuid4())
    reads = [0]

    def reader(subject: RuntimeFrontendClient, _label: str, _language: OutputLanguage) -> ProfileOverview:
        reads[0] += 1
        if reads[0] > 1:
            raise RuntimeFrontendRefusedError("profile_view_unavailable")
        return _overview(subject.profile_id, 4)

    def run(_subject: RuntimeFrontendClient, request: ProfileMutationRequest) -> ProfileMutationCompletion:
        return ProfileMutationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(request, 5),
            effect=OperationEffect.UPDATED,
        )

    screen = _composition(client, runner=run, reader=reader).compose()
    with pytest.raises(ProfileManagerCompletedViewUnavailableError) as caught:
        screen._persist_field("identity.legal_name", "Saved", 4, _DIGEST)
    assert caught.value.operation_id == _OPERATION_ID
    assert caught.value.record_revision == 5
    assert caught.value.effect is OperationEffect.UPDATED
    assert reads == [2]


@pytest.mark.asyncio
@pytest.mark.parametrize("effect", [OperationEffect.UPDATED, OperationEffect.NONE])
async def test_completed_operation_without_refresh_reports_truthful_status(effect: OperationEffect) -> None:
    client = _Client(uuid4())

    def reader(subject: RuntimeFrontendClient, _label: str, _language: OutputLanguage) -> ProfileOverview:
        return _overview(subject.profile_id, 4)

    def run(_subject: RuntimeFrontendClient, _request: ProfileMutationRequest) -> ProfileMutationCompletion:
        raise AssertionError("status wording must not run a new operation")

    screen = _composition(client, runner=run, reader=reader).compose()
    completed = ProfileMutationCompletion(
        operation_id=_OPERATION_ID,
        projection=ProfileMutationOperationProjection(profile_id=client.profile_id, record_revision=5),
        effect=effect,
    )
    error = ProfileManagerCompletedViewUnavailableError(completed)
    assert isinstance(error, CadrumoError)
    registered = get_registered_error_code(error)
    assert registered.code == "FAIL_TUI_PROFILE_COMPLETED_VIEW_UNAVAILABLE"
    assert registered.message_key == "flows.manager.edit.completed_refresh_unavailable"
    assert registered.retryable is False
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen._refuse_worker(error, message_key="flows.manager.edit.write_failed")
        assert screen.query_one("#manager-status", PinnedStatusBar).message == tr(
            "flows.manager.edit.completed_refresh_unavailable"
        )
        assert error.operation_id == _OPERATION_ID and error.record_revision == 5 and error.effect is effect


def test_retargeted_profile_or_changed_session_refuses_before_mutation() -> None:
    client = _Client(uuid4())
    calls = [0]

    def reader(subject: RuntimeFrontendClient, _label: str, _language: OutputLanguage) -> ProfileOverview:
        return _overview(subject.profile_id, 4)

    def run(_subject: RuntimeFrontendClient, _request: ProfileMutationRequest) -> ProfileMutationCompletion:
        calls[0] += 1
        raise AssertionError("retargeted client reached the operation runner")

    screen = _composition(client, runner=run, reader=reader).compose()
    client._session_id = uuid4()
    with pytest.raises(RuntimeFrontendRefusedError, match="session_inactive"):
        screen._persist_field("identity.legal_name", "No", 4, _DIGEST)
    client._session_id = None
    client._profile_id = uuid4()
    with pytest.raises(RuntimeFrontendRefusedError, match="profile_mismatch"):
        screen._persist_field("identity.legal_name", "No", 4, _DIGEST)
    assert calls == [0]


def test_plantilla_listing_uses_only_the_exact_authorized_facts_stream() -> None:
    client = _Client(uuid4())

    def reader(subject: RuntimeFrontendClient, _label: str, _language: OutputLanguage) -> ProfileOverview:
        return _overview(subject.profile_id, 4)

    def run(_subject: RuntimeFrontendClient, _request: ProfileMutationRequest) -> ProfileMutationCompletion:
        raise AssertionError("listing must not submit a mutation")

    screen = _composition(client, runner=run, reader=reader).compose()
    assert screen._list_plantilla_media is not None
    assert screen._list_plantilla_media() == ()
    assert client.view_requests == [(ProfileViewPageKind.FACTS,)]


def test_preloaded_manager_uses_exact_profile_without_reading_on_ui_thread() -> None:
    client = _Client(uuid4())

    def reader(_subject: RuntimeFrontendClient, _label: str, _language: OutputLanguage) -> ProfileOverview:
        raise AssertionError("preloaded composition must not read")

    def run(_subject: RuntimeFrontendClient, _request: ProfileMutationRequest) -> ProfileMutationCompletion:
        raise AssertionError("composition must not write")

    composition = _composition(client, runner=run, reader=reader)
    overview = _overview(client.profile_id, 4)
    assert composition.compose_from_overview(overview).overview is overview
    with pytest.raises(RuntimeRefusalError) as wrong_profile:
        composition.compose_from_overview(_overview(uuid4(), 4))
    assert wrong_profile.value.reason is RuntimeRefusalCode.INVALID_FRAME
    client._session_id = uuid4()
    with pytest.raises(RuntimeFrontendRefusedError, match="session_inactive"):
        composition.compose_from_overview(overview)
