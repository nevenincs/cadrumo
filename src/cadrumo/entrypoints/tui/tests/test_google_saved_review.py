"""The production native-review screen reaches human consent and exact registered results."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, Link, Static

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.export.google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GoogleReviewProjection,
    GoogleReviewRequest,
    GoogleReviewResult,
)
from ....application.export.publication_receipt import ReadablePayloadCategory
from ....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from ....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionSuccessV1,
)
from ....application.operations.models import OperationIdentity
from ....application.operations.persistence.replay import OperationReplayStatus
from ....application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ....application.runtime.contracts import RuntimeRefusalError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language
from ....core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...operation_composition import build_production_operation_registry
from ...review_publication_labels import GoogleReviewLabels
from ..google_saved_review import GoogleSavedReviewModal, GoogleSavedReviewScreen, validate_saved_google_review
from ..operations.interactions import OperationModalReviewInteractionV1
from ..operations.runtime_controller import RuntimeOperationController

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 10, 7, tzinfo=UTC)
_OPERATION = "a" * 64
_INTERACTION = "b" * 64


@lru_cache(maxsize=1)
def _contracts() -> OperationPublicContractSetV1:
    return build_production_operation_registry().public_contract_set


def _review(request: GoogleReviewRequest) -> GoogleReviewProjection:
    return GoogleReviewProjection(
        identity=OperationIdentity(
            operation_id=_OPERATION,
            definition_id=GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(request.profile_id)),
        ),
        revision=2,
        profile_id=request.profile_id,
        publication_id=request.publication_id,
        calculation_revision_id=request.calculation_revision_id,
        filing_record_id=request.filing_record_id,
        root_folder_id="managed-root",
        snapshot_digest="d" * 64,
        payload_categories=(ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER),
        reviewed_proposal_digest="e" * 64,
    )


class _Controller:
    operation_id = _OPERATION
    actor_ref = "operator:test-human"

    def __init__(self, request: GoogleReviewRequest, *, defect: str, client: SimpleNamespace) -> None:
        self.request = request
        self.review = _review(request)
        self.defect = defect
        self.client = client
        self.response: str | None = None
        self.starts = self.applies = self.rejects = self.reads = 0

    async def start(self) -> str:
        self.starts += 1
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        contracts = _contracts()
        contract = next(
            row for row in contracts.definitions if row.definition_id == GOOGLE_REVIEW_OPERATION_DEFINITION_ID
        )
        assert contract.review_projection_schema is not None and contract.interaction_response_schema is not None
        pending = OperationReviewAvailableInteractionV1(
            operation_id=self.operation_id,
            interaction_id=_INTERACTION,
            revision=2,
            presentation_code="google.review.readable-publication",
            response_schema=contract.interaction_response_schema,
            expires_at=None,
            review_reference=OperationReviewProjectionReferenceV1(
                operation_id=self.operation_id,
                interaction_id=_INTERACTION,
                revision=2,
                review_projection_schema=contract.review_projection_schema,
                definition_contract_digest=contract.definition_contract_digest,
                expires_at=None,
            ),
        )
        terminal = self.response is not None
        projection = OperationPublicProjectionV1(
            operation_id=self.operation_id,
            definition_id=contract.definition_id,
            subject_ref=profile_operation_subject(str(self.request.profile_id)),
            revision=3 if terminal else 2,
            anchor_cursor=0,
            definition_contract=contract,
            contract_set_digest=contracts.contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.WAITING_FOR_INTERACTION,
            terminal_condition=(
                OperationTerminalCondition.SUCCEEDED if self.response == "apply" else OperationTerminalCondition.REFUSED
            )
            if terminal
            else None,
            effect=OperationEffect.UPDATED if self.response == "apply" else OperationEffect.NONE,
            phase_code="export.google-review.prepare",
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=contract.close_policy,
            cancellation=contract.cancellation,
            cancellable_now=False,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1() if terminal else pending,
            result_ref="f" * 64 if self.response == "apply" else None,
            refusal_ref="response_authority_required" if self.response == "reject" else None,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        return OperationObservationSuccessV1(
            projection=projection,
            event_page=OperationPublicEventPageV1(
                operation_id=self.operation_id,
                anchor_cursor=0,
                requested_cursor=after_cursor,
                status=OperationReplayStatus.CAUGHT_UP,
                events=(),
                next_cursor=0,
                restart_cursor=None,
            ),
        )

    async def resolve_review(self, reference: OperationReviewProjectionReferenceV1, projection_type: type[BaseModel]):
        review = self.review
        if self.defect == "review":
            review = review.model_copy(update={"calculation_revision_id": "9" * 64})
        return OperationReviewProjectionSuccessV1[GoogleReviewProjection](
            projection_schema=reference.review_projection_schema,
            definition_contract_digest=reference.definition_contract_digest,
            projection=review,
        )

    async def response_control(self, *, interaction_id: str, revision: int):
        return self

    async def inspect(self) -> OperationResponseControlSuccessV1:
        return OperationResponseControlSuccessV1(
            operation_id=self.operation_id,
            interaction_id=_INTERACTION,
            revision=2,
            available=True,
            permitted_intents=frozenset({"apply", "reject"}),
        )

    async def apply(self, request: OperationResponseApplyRequestV1) -> OperationResponseMutationSuccessV1:
        self.applies += 1
        self.response = "apply"
        if self.defect == "session":
            self.client.session_id = UUID(int=99)
        return self._responded(request, "apply")

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationSuccessV1:
        self.rejects += 1
        self.response = "reject"
        return self._responded(request, "reject")

    def _responded(self, request, action: str) -> OperationResponseMutationSuccessV1:
        assert request.operation_id == self.operation_id and request.interaction_id == _INTERACTION
        assert request.revision == 2 and request.actor_ref == self.actor_ref
        return OperationResponseMutationSuccessV1(
            operation_id=self.operation_id,
            interaction_id=_INTERACTION,
            revision=2,
            response_action=action,
        )

    async def read_settled_result(self, projection, result_type, *, result_version: int) -> GoogleReviewResult:
        self.reads += 1
        assert (
            projection.operation_id == self.operation_id and result_type is GoogleReviewResult and result_version == 1
        )
        return GoogleReviewResult(
            profile_id=self.request.profile_id,
            publication_id=self.request.publication_id,
            snapshot_digest="0" * 64 if self.defect == "receipt" else self.review.snapshot_digest,
            root_folder_id=self.review.root_folder_id,
            spreadsheet_id="saved-review",
            spreadsheet_url="https://docs.google.com/spreadsheets/d/saved-review/edit",
        )


async def _until(pilot: Pilot[None], predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(10):
        while not predicate():
            await pilot.pause(0.02)
    await pilot.pause()


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["none", "receipt", "session", "review", "reject", "click"])
async def test_installed_screen_requires_exact_human_review_before_showing_registered_link(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    # Compile the production contract graph before timing UI observation;
    # first-use registry construction is independent of Textual polling.
    _contracts()
    client = SimpleNamespace(profile_id=UUID(int=1), session_id=UUID(int=2), frontend=OperationFrontendProjection.TUI)
    controllers: list[_Controller] = []

    async def submit(_client, *, definition_id, subject_ref, payload, expected_session_id):
        assert _client is client and definition_id == GOOGLE_REVIEW_OPERATION_DEFINITION_ID
        assert (
            subject_ref == profile_operation_subject(str(client.profile_id))
            and expected_session_id == client.session_id
        )
        controller = _Controller(payload, defect=defect, client=client)
        controllers.append(controller)
        return cast(RuntimeOperationController, controller)

    monkeypatch.setattr(RuntimeOperationController, "submit", submit)
    screen = GoogleSavedReviewScreen(cast(RuntimeFrontendClient, client), "c" * 64, filing_record_id="6" * 64)
    app: App[None] = App()
    async with app.run_test(size=(120, 45)) as pilot:
        app.push_screen(screen)
        await _until(pilot, lambda: isinstance(app.screen, GoogleSavedReviewModal))
        modal = app.screen
        assert isinstance(modal, GoogleSavedReviewModal)
        await _until(
            pilot,
            lambda: bool(
                modal.query_one(
                    "#operation-modal-status" if defect == "review" else "#operation-modal-review", Static
                ).content
            ),
        )
        controller = controllers[0]
        assert controller.request.calculation_revision_id == "c" * 64
        assert controller.request.filing_record_id == "6" * 64
        assert controller.starts == 1 and controller.applies == controller.reads == 0
        if defect == "review":
            assert modal.query_one("#btn-operation-apply", Button).disabled
            assert not screen.query_one(Link).url
            return
        text = str(modal.query_one("#operation-modal-review", Static).content)
        assert controller.review.snapshot_digest not in text and controller.review.calculation_revision_id not in text
        await pilot.press("t")
        assert controller.review.root_folder_id in str(modal.query_one("#operation-modal-review", Static).content)
        if defect == "click":
            interaction = modal._interaction
            assert isinstance(interaction, OperationModalReviewInteractionV1)
            modal._interaction = replace(
                interaction, projection=controller.review.model_copy(update={"root_folder_id": "substituted-root"})
            )
            await pilot.click("#btn-operation-apply")
            await pilot.pause()
            assert controller.applies == controller.reads == 0
            assert modal.query_one("#btn-operation-apply", Button).disabled
            assert not screen.query_one(Link).url
            return
        await pilot.click("#btn-operation-reject" if defect == "reject" else "#btn-operation-apply")
        await _until(pilot, lambda: app.screen is screen)
        await _until(pilot, lambda: bool(screen.query_one("#saved-google-review-notice", Static).content))
        link = screen.query_one(Link)
        assert link.disabled is (defect != "none")
        if defect == "none":
            assert link.url == "https://docs.google.com/spreadsheets/d/saved-review/edit"
        else:
            assert link.url == ""
        assert controller.applies == (0 if defect == "reject" else 1)
        assert controller.reads == (0 if defect in {"reject", "session"} else 1)


@pytest.mark.parametrize("defect", ["profile", "filing", "operation", "category"])
def test_native_disclosure_refuses_selection_or_payload_expansion(defect: str) -> None:
    request = GoogleReviewRequest(
        profile_id=UUID(int=1), calculation_revision_id="c" * 64, publication_id=UUID(int=2), filing_record_id="6" * 64
    )
    review = _review(request)
    updates = {
        "profile": {"profile_id": UUID(int=9)},
        "filing": {"filing_record_id": "7" * 64},
        "operation": {"identity": review.identity.model_copy(update={"operation_id": "8" * 64})},
        "category": {
            "payload_categories": (ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.ORIGINAL_ATTACHMENT)
        },
    }
    with pytest.raises(RuntimeRefusalError):
        validate_saved_google_review(request, review.model_copy(update=updates[defect]), operation_id=_OPERATION)


@pytest.mark.asyncio
async def test_delayed_first_observation_does_not_offer_an_unverified_response() -> None:
    _contracts()
    first_read = asyncio.Event()
    request = GoogleReviewRequest(profile_id=UUID(int=1), calculation_revision_id="c" * 64, publication_id=UUID(int=2))

    class DelayedController(_Controller):
        @override
        async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
            await first_read.wait()
            return await super().observe(after_cursor, page_limit=page_limit)

    controller = DelayedController(request, defect="none", client=SimpleNamespace(session_id=UUID(int=3)))
    modal = GoogleSavedReviewModal(cast(RuntimeOperationController, controller), request, lambda _: None)
    app: App[None] = App()
    async with app.run_test() as pilot:
        app.push_screen(modal)
        await pilot.pause()
        assert modal.query_one("#btn-operation-apply", Button).disabled
        assert modal.query_one("#btn-operation-reject", Button).disabled
        assert not modal.query_one("#btn-operation-close", Button).disabled
        assert not modal.query_one("#operation-modal-review", Static).content
        await pilot.click("#btn-operation-apply")
        assert controller.applies == 0
        first_read.set()
        await _until(pilot, lambda: not modal.query_one("#btn-operation-apply", Button).disabled)
        assert modal.query_one("#operation-modal-review", Static).content
        assert str(modal.query_one("#btn-operation-apply", Button).label) == GoogleReviewLabels(
            OutputLanguage(output_language())
        )("google_review.publish")
        await pilot.press("t")
        assert request.calculation_revision_id in str(modal.query_one("#operation-modal-review", Static).content)


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ("none", "session", "effect"))
async def test_prepublication_cleanup_rejects_only_original_untouched_review(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    _contracts()
    client = SimpleNamespace(profile_id=UUID(int=1), session_id=UUID(int=2), frontend=OperationFrontendProjection.TUI)
    controllers: list[_Controller] = []

    async def submit(_client, *, definition_id, subject_ref, payload, expected_session_id):
        controller = _Controller(payload, defect="none", client=client)
        controllers.append(controller)
        return cast(RuntimeOperationController, controller)

    monkeypatch.setattr(RuntimeOperationController, "submit", submit)
    screen = GoogleSavedReviewScreen(cast(RuntimeFrontendClient, client), "c" * 64)
    app: App[None] = App()
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await _until(pilot, lambda: isinstance(app.screen, GoogleSavedReviewModal))
        modal = app.screen
        await _until(pilot, lambda: bool(modal.query_one("#operation-modal-review", Static).content))
        controller = controllers[0]
        if defect == "session":
            client.session_id = UUID(int=99)
        elif defect == "effect":
            controller.response = "apply"
        if defect == "none":
            assert await screen.reject_pending_prepublication()
            assert not await screen.reject_pending_prepublication()
        else:
            with pytest.raises(RuntimeRefusalError):
                await screen.reject_pending_prepublication()
        assert controller.applies == controller.reads == 0
        assert controller.rejects == (1 if defect == "none" else 0)


@pytest.mark.parametrize("locale", tuple(OutputLanguage))
def test_production_disclosure_labels_are_present_without_key_echo(locale: OutputLanguage) -> None:
    labels = GoogleReviewLabels(locale)
    for key in (
        "google_review.offer.title",
        "google_review.notice.external_copy",
        "google_review.notice.evidence_index",
        "google_review.label.destination",
        "google_review.destination.managed_google_folder",
        "google_review.label.payload_categories",
        "google_review.category.calculation",
        "google_review.category.ledger",
        "google_review.label.calculation_revision_id",
        "google_review.label.root_folder_id",
        "google_review.label.snapshot_digest",
        "google_review.label.publication_id",
        "google_review.publish",
        "google_review.cancel",
        "google_review.close",
        "google_review.open_document",
        "google_review.publication.published",
        "google_review.notice.receipt_unavailable",
        "google_review.notice.submission_unresolved",
    ):
        assert labels(key).strip() and labels(key) != key
