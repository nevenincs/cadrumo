"""Shared registered-operation UI flow for saved calculation and ledger reviews."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Protocol

from textual.app import App

from ...application.export.publication_receipt import PublicationReceipt, PublicationState, ReadableExportAuthorization
from ...application.export.review_snapshot import ReviewSnapshot
from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...core.errors.error_codes import resolve_error_message
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language
from ...core.logging import get_logger
from ...core.operations import OperationEffect, OperationTerminalCondition
from ..review_publication_labels import GoogleReviewLabels
from ..review_publication_presentation import ReviewPublicationLabels
from .operations.controller_port import OperationControllerPort
from .operations.modal import OperationModal, OperationModalDetachedOutcomeV1, OperationModalSettledOutcomeV1
from .operations.refusal_explanation import public_refusal_explanation
from .review_publication import ReviewPublicationOfferScreen, ReviewPublicationResultScreen


class ReviewPublicationDoor(Protocol):
    """Session-bound UI requests supplied by the registered-operation composition."""

    async def load_offer(self) -> tuple[ReviewSnapshot, ReadableExportAuthorization]:
        """Resolve one immutable selection/disclosure through the captured exact-profile runtime session."""
        ...

    async def submit(
        self, snapshot: ReviewSnapshot, authorization: ReadableExportAuthorization
    ) -> OperationControllerPort:
        """Re-admit the exact shown selection/disclosure and submit its canonical registered request.

        Refuse changed source digests, publication identity, root or disclosure;
        never silently load newer values or broaden categories after confirmation.
        The flow starts and observes the returned immutable controller.
        """
        ...

    async def read_receipt(self, projection: OperationPublicProjectionV1) -> PublicationReceipt | None:
        """Validate the submitted operation/schema/subject and return its custodied receipt.

        Recheck the captured profile/session before request and after result
        disclosure. Do not reconstruct creation or publication custody from
        remote markers or a caller-supplied artifact identifier.
        """
        ...


class ReviewPublicationFlow[AppResultT]:
    """Open disclosure, progress and receipt screens without reading provider content."""

    def __init__(
        self,
        app: App[AppResultT],
        door: ReviewPublicationDoor,
        *,
        notice: Callable[[str], None],
        label: ReviewPublicationLabels | None = None,
    ) -> None:
        """Hold an exact selected-snapshot door and the host's ordinary notice surface."""
        self._app = app
        self._door = door
        self._notice = notice
        self._label = label if label is not None else GoogleReviewLabels(OutputLanguage(output_language()))
        self._busy = False
        self._unresolved = False
        self._controller: OperationControllerPort | None = None
        self._worker_group = f"google-review-{id(self)}"

    def open(self) -> None:
        """Load the selection once; duplicate gestures never submit parallel publications."""
        if self._unresolved:
            self._notice(self._label("google_review.notice.submission_unresolved"))
            return
        if self._busy:
            return
        self._busy = True
        self._app.run_worker(self._load_offer, group=f"{self._worker_group}-offer", exclusive=True)

    async def _load_offer(self) -> None:
        try:
            snapshot, authorization = await self._door.load_offer()
            screen = ReviewPublicationOfferScreen(snapshot, authorization, label=self._label)
        except CadrumoError as refusal:
            self._busy = False
            self._notice(resolve_error_message(refusal))
            return
        except Exception as failure:
            self._busy = False
            self._failed("prerequisite_unavailable", failure)
            return
        self._app.push_screen(screen, partial(self._offered, snapshot, authorization))

    def _offered(
        self, snapshot: ReviewSnapshot, authorization: ReadableExportAuthorization, confirmed: bool | None
    ) -> None:
        if not confirmed:
            self._busy = False
            return
        self._app.run_worker(
            partial(self._submit, snapshot, authorization),
            group=f"{self._worker_group}-operation",
            exclusive=True,
        )

    async def _submit(self, snapshot: ReviewSnapshot, authorization: ReadableExportAuthorization) -> None:
        try:
            self._controller = await self._door.submit(snapshot, authorization)
            acknowledged_id = await self._controller.start()
            if acknowledged_id != self._controller.operation_id:
                raise ValueError("start acknowledgement differs from the submitted operation")
        except CadrumoError as refusal:
            self._busy = False
            self._unresolved = True
            self._notice(
                f"{resolve_error_message(refusal)} {self._label('google_review.notice.submission_unresolved')}"
            )
            return
        except Exception as failure:
            # Admission may precede a lost acknowledgement. Keep the identity
            # and refuse another gesture until the runtime reconciles it.
            self._busy = False
            self._unresolved = True
            self._failed("submission_unresolved", failure)
            return
        self._app.push_screen(OperationModal(self._controller), partial(self._settled, snapshot, authorization))

    def _settled(self, snapshot: ReviewSnapshot, authorization: ReadableExportAuthorization, outcome: object) -> None:
        self._busy = False
        if isinstance(outcome, OperationModalDetachedOutcomeV1) or outcome is None:
            self._unresolved = True
            self._notice(self._label("google_review.notice.submission_unresolved"))
            return
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            self._unresolved = True
            self._notice(self._label("google_review.notice.receipt_unavailable"))
            return
        projection = outcome.view_model.projection
        if self._controller is None or projection.operation_id != self._controller.operation_id:
            self._unresolved = True
            self._notice(self._label("google_review.notice.receipt_unavailable"))
            return
        self._unresolved = projection.effect is OperationEffect.UNKNOWN
        self._busy = True
        self._app.run_worker(
            partial(self._read_receipt, snapshot, authorization, outcome),
            group=f"{self._worker_group}-receipt",
            exclusive=True,
        )

    async def _read_receipt(
        self,
        snapshot: ReviewSnapshot,
        authorization: ReadableExportAuthorization,
        outcome: OperationModalSettledOutcomeV1,
    ) -> None:
        try:
            projection = outcome.view_model.projection
            publication = await self._door.read_receipt(projection)
            if publication is None:
                self._unresolved = True
                explanation = outcome.error_explanation or public_refusal_explanation(outcome.view_model.receipt_ref)
                self._notice(explanation or self._label("google_review.notice.receipt_unavailable"))
                return
            if (
                publication.publication_id != authorization.publication_id
                or publication.root.artifact_id != authorization.root_folder_id
            ):
                raise ValueError("publication result differs from the disclosed offer")
            if publication.state is PublicationState.PUBLISHED and (
                projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
                or projection.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
            ):
                raise ValueError("published receipt lacks a successful supervised terminal")
            self._unresolved = self._unresolved or publication.state is not PublicationState.PUBLISHED
            self._app.push_screen(ReviewPublicationResultScreen(snapshot, publication, label=self._label))
        except CadrumoError as refusal:
            self._unresolved = True
            self._notice(resolve_error_message(refusal))
        except Exception as failure:
            self._unresolved = True
            self._failed("receipt_unavailable", failure)
        finally:
            self._busy = False

    def _failed(self, notice: str, failure: Exception) -> None:
        get_logger(__name__).error("Google review UI failed: %s", type(failure).__qualname__)
        self._notice(self._label(f"google_review.notice.{notice}"))
