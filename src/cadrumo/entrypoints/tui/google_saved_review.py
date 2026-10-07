"""Publish one selected saved calculation through the registered human review door."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import monotonic
from typing import ClassVar, override
from uuid import uuid4

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Link, Static

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.export.google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING,
    GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING,
    GoogleReviewProjection,
    GoogleReviewRequest,
    GoogleReviewResult,
)
from ...application.export.publication_receipt import ReadablePayloadCategory
from ...application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from ...application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from ...application.operations.interactions import OperationResponseIntentValue
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.errors.error_codes import resolve_error_message
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.hex import Hex64Str
from ...core.i18n.render import output_language
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..review_publication_labels import GoogleReviewLabels
from .operations.interactions import OperationModalReviewInteractionV1
from .operations.modal import OperationModal, OperationModalSettledOutcomeV1
from .operations.runtime_controller import RuntimeOperationController


def validate_saved_google_review(
    request: GoogleReviewRequest, review: GoogleReviewProjection, *, operation_id: str
) -> None:
    """Bind the readable disclosure to this selected revision, filing and invocation."""
    if (
        review.identity.operation_id != operation_id
        or review.identity.definition_id != GOOGLE_REVIEW_OPERATION_DEFINITION_ID
        or review.identity.subject_ref != profile_operation_subject(str(request.profile_id))
        or review.profile_id != request.profile_id
        or review.publication_id != request.publication_id
        or review.calculation_revision_id != request.calculation_revision_id
        or review.filing_record_id != request.filing_record_id
        or not review.root_folder_id.strip()
        or not review.readable_by_authorized_users
        or ReadablePayloadCategory.CALCULATION not in review.payload_categories
        or not set(review.payload_categories) <= {ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER}
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


class GoogleSavedReviewModal(OperationModal):
    """Keep canonical response controls while presenting the exact disclosure in plain words."""

    BINDINGS: ClassVar = [*OperationModal.BINDINGS, Binding("t", "technical", "", show=False)]

    def __init__(
        self,
        controller: RuntimeOperationController,
        request: GoogleReviewRequest,
        reviewed: Callable[[GoogleReviewProjection], None],
    ) -> None:
        """Retain the admitted request; this modal never manufactures response authority."""
        super().__init__(controller)
        self._request = request
        self._reviewed = reviewed
        self._technical = False
        self._labels = GoogleReviewLabels(OutputLanguage(output_language()))

    def _disclosure(self) -> GoogleReviewProjection | None:
        interaction = self._interaction
        if not isinstance(interaction, OperationModalReviewInteractionV1):
            return None
        if (
            interaction.interaction.review_reference.review_projection_schema
            != GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING.identity
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        review = GoogleReviewProjection.model_validate_json(interaction.projection.model_dump_json())
        validate_saved_google_review(self._request, review, operation_id=self._controller.operation_id)
        if review.revision != interaction.interaction.revision:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._reviewed(review)
        return review

    @override
    def _refresh_view_state(self) -> None:
        super()._refresh_view_state()
        try:
            disclosure = self._disclosure()
        except (CadrumoError, ValueError):
            self._runtime_access_lost(RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME))
            return
        if disclosure is None:
            return
        labels = self._labels
        categories = ", ".join(
            labels(f"google_review.category.{category.value}") for category in disclosure.payload_categories
        )
        lines = [
            labels("google_review.offer.title"),
            labels("google_review.notice.external_copy"),
            labels("google_review.notice.evidence_index"),
            labels("google_review.label.destination")
            + ": "
            + labels("google_review.destination.managed_google_folder"),
            labels("google_review.label.payload_categories") + ": " + categories,
        ]
        if self._technical:
            lines.extend(
                (
                    labels("google_review.label.calculation_revision_id") + ": " + disclosure.calculation_revision_id,
                    labels("google_review.label.root_folder_id") + ": " + disclosure.root_folder_id,
                    labels("google_review.label.snapshot_digest") + ": " + disclosure.snapshot_digest,
                    labels("google_review.label.publication_id") + ": " + str(disclosure.publication_id),
                )
            )
        widget = self.query_one("#operation-modal-review", Static)
        widget.update(Text("\n".join(lines)))
        self.query_one("#btn-operation-apply", Button).label = labels("google_review.publish")
        self.query_one("#btn-operation-reject", Button).label = labels("google_review.cancel")

    def action_technical(self) -> None:
        """Show the selected source and destination identities only on request."""
        self._technical = not self._technical
        self._refresh_view_state()

    @override
    async def _send_response(self, *, intent: OperationResponseIntentValue) -> None:
        # Recheck at the click boundary as well as during each observation.
        try:
            disclosure = self._disclosure()
        except (CadrumoError, ValueError):
            self._runtime_access_lost(RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME))
            return
        if disclosure is not None:
            await super()._send_response(intent=intent)


class GoogleSavedReviewScreen(Screen[None]):
    """Prepare an exact saved selection, await human consent, and show its verified link."""

    def __init__(
        self,
        client: RuntimeFrontendClient,
        calculation_revision_id: CalculationRevisionId,
        *,
        filing_record_id: Hex64Str | None = None,
    ) -> None:
        """Capture the profile/session and immutable calculation before any operation starts."""
        super().__init__()
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id, self._session_id = client.profile_id, client.session_id
        self._request = GoogleReviewRequest(
            profile_id=self._profile_id,
            calculation_revision_id=calculation_revision_id,
            filing_record_id=filing_record_id,
            publication_id=uuid4(),
        )
        self._started = False
        self._review: GoogleReviewProjection | None = None
        self._controller: RuntimeOperationController | None = None
        self._labels = GoogleReviewLabels(OutputLanguage(output_language()))

    @override
    def compose(self) -> ComposeResult:
        yield Static(self._labels("google_review.offer.title"), markup=False)
        yield Static(self._labels("google_review.notice.external_copy"), markup=False)
        yield Static("", id="saved-google-review-notice", markup=False)
        yield Link(self._labels("google_review.open_document"), url="", id="saved-google-review-link", disabled=True)
        yield Button(self._labels("google_review.close"), id="saved-google-review-close")

    def on_mount(self) -> None:
        """Submit local preparation once; the registered checkpoint still requires a human response."""
        if not self._started:
            self._started = True
            self.run_worker(self._prepare(), group="saved-google-review-prepare")

    def _require_session(self) -> None:
        if self._client.profile_id != self._profile_id or self._client.session_id != self._session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def _notice(self, text: str) -> None:
        self.query_one("#saved-google-review-notice", Static).update(text)

    def _record_review(self, review: GoogleReviewProjection) -> None:
        self._require_session()
        if self._review is not None and self._review != review:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._review = review

    async def _prepare(self) -> None:
        try:
            self._require_session()
            controller = await RuntimeOperationController.submit(
                self._client,
                definition_id=GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(self._profile_id)),
                payload=self._request,
                expected_session_id=self._session_id,
            )
            self._controller = controller
            self._require_session()
            if await controller.start() != controller.operation_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            self._require_session()
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return

        def settled(outcome: object) -> None:
            if isinstance(outcome, OperationModalSettledOutcomeV1):
                self.run_worker(self._read_result(controller, outcome), group="saved-google-review-result")
            else:
                self._notice(self._labels("google_review.notice.submission_unresolved"))

        self.app.push_screen(GoogleSavedReviewModal(controller, self._request, self._record_review), settled)

    async def reject_pending_prepublication(self) -> bool:
        """Reject this session's untouched review through its original response proof.

        Automation uses this only after a failed prepublication acceptance stage.
        Foreign, consumed or effectful work cannot be reclaimed by this door.
        """
        controller = self._controller
        if controller is None:
            return False
        deadline = monotonic() + 20
        rejection_sent = False
        while True:
            self._require_session()
            observed = await controller.observe(0, page_limit=1)
            if not isinstance(observed, OperationObservationSuccessV1):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            projection = observed.projection
            if (
                projection.operation_id != controller.operation_id
                or projection.definition_id != GOOGLE_REVIEW_OPERATION_DEFINITION_ID
                or projection.subject_ref != profile_operation_subject(str(self._profile_id))
                or projection.effect is not OperationEffect.NONE
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if projection.lifecycle is OperationLifecycle.TERMINAL:
                if rejection_sent and projection.terminal_condition is not OperationTerminalCondition.REFUSED:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return rejection_sent
            pending = projection.pending_interaction
            if not rejection_sent and isinstance(pending, OperationReviewAvailableInteractionV1):
                if pending.response_schema != GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING.identity:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                control = await controller.response_control(
                    interaction_id=pending.interaction_id, revision=pending.revision
                )
                allowed = await control.inspect()
                if (
                    not isinstance(allowed, OperationResponseControlSuccessV1)
                    or "reject" not in allowed.permitted_intents
                    or (allowed.operation_id, allowed.interaction_id, allowed.revision)
                    != (controller.operation_id, pending.interaction_id, pending.revision)
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                self._require_session()
                rejected = await control.reject(
                    OperationResponseRejectRequestV1(
                        operation_id=controller.operation_id,
                        interaction_id=pending.interaction_id,
                        revision=pending.revision,
                        actor_ref=controller.actor_ref,
                        responded_at=now(),
                    )
                )
                if not isinstance(rejected, OperationResponseMutationSuccessV1) or (
                    rejected.operation_id,
                    rejected.interaction_id,
                    rejected.response_action,
                ) != (controller.operation_id, pending.interaction_id, "reject"):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                rejection_sent = True
                continue
            if monotonic() >= deadline:
                raise TimeoutError("the original prepublication review did not become rejectable")
            await asyncio.sleep(0.1)

    async def _read_result(
        self, controller: RuntimeOperationController, outcome: OperationModalSettledOutcomeV1
    ) -> None:
        projection = outcome.view_model.projection
        if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            self._notice(outcome.error_explanation or self._labels("google_review.notice.receipt_unavailable"))
            return
        try:
            self._require_session()
            review = self._review
            if review is None or projection.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            result = await controller.read_settled_result(projection, GoogleReviewResult, result_version=1)
            self._require_session()
            if (
                result.profile_id != self._request.profile_id
                or result.publication_id != self._request.publication_id
                or result.snapshot_digest != review.snapshot_digest
                or result.root_folder_id != review.root_folder_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return
        self._notice(self._labels("google_review.publication.published"))
        link = self.query_one("#saved-google-review-link", Link)
        link.url = result.spreadsheet_url
        link.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return without consenting, replaying, or contacting a provider."""
        if event.button.id == "saved-google-review-close":
            self.app.pop_screen()
