"""Review a suggested classification of the selected entry through the operation modal.

The suggestion is a proposal. The review operation pauses with it, the shared
operation modal shows it in the operator's words, and only Apply writes it;
Reject records the rejection and leaves the entry as it was. The screen reads
the settled outcome afterwards and says what, if anything, changed.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from typing import Final, Literal, cast, override

from pydantic import BaseModel, ValidationError
from textual.widget import Widget
from textual.widgets import Input, Select, Static

from ....application.ledger.llm_review_contracts import (
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    LedgerLlmSuggestionProjection,
)
from ....application.ledger.llm_review_results import LedgerLlmOperationResult
from ....application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..account import AccountSessionExpiredError
from ..operations.modal import OperationModal, OperationModalDetachedOutcomeV1, OperationModalSettledOutcomeV1
from ..operations.outcome import OperationOutcomeUnknownError
from ..operations.refusal_explanation import public_refusal_explanation
from .categorisation_common import (
    CategorisationScreen,
    action,
    action_row,
    blank_to_none,
    classification_label,
    field,
    heading,
    line,
)
from .categorisation_doors import LedgerSuggestionReviewDoorV1
from .controller import LedgerWorkspaceController
from .workspace_presentation import door_refusal_text

type ClassificationReviewMode = Literal["classification", "saturated", "auto_split"]

REVIEW_MODES: Final[dict[str, tuple[ClassificationReviewMode, LlmReviewInvocationOrigin]]] = {
    "classification": ("classification", LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY),
    "saturated": ("saturated", LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY),
    "auto_split": ("auto_split", LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT),
}
"""The classification review modes this tool offers, each with the origin the operation requires."""

_EVIDENCE_NO: Final = "no"
_EVIDENCE_YES: Final = "yes"


def _suggested_values(suggestion: LedgerLlmSuggestionProjection) -> Iterator[str]:
    if suggestion.classification is not None:
        yield tr(
            "tui.ledger.categorisation.review.suggested_classification",
            value=classification_label(suggestion.classification),
        )
    if suggestion.category is not None:
        yield tr("tui.ledger.categorisation.review.suggested_category", value=suggestion.category)
    if suggestion.confidence is not None:
        yield tr("tui.ledger.categorisation.review.suggested_confidence", value=suggestion.confidence)
    if suggestion.business_pct is not None:
        yield tr("tui.ledger.categorisation.review.suggested_business_pct", value=suggestion.business_pct)
    if suggestion.iva_category is not None:
        yield tr("tui.ledger.categorisation.review.suggested_iva_category", value=suggestion.iva_category)
    if suggestion.iva_rate is not None:
        yield tr("tui.ledger.categorisation.review.suggested_iva_rate", value=suggestion.iva_rate)
    if suggestion.taxable_base is not None:
        yield tr("tui.ledger.categorisation.review.suggested_taxable_base", value=suggestion.taxable_base)
    if suggestion.iva_amount is not None:
        yield tr("tui.ledger.categorisation.review.suggested_iva_amount", value=suggestion.iva_amount)
    if suggestion.parent_amount is not None:
        yield tr("tui.ledger.categorisation.review.suggested_parent_amount", value=suggestion.parent_amount)


def _suggestion_lines(suggestion: LedgerLlmSuggestionProjection) -> list[str]:
    lines = [tr("tui.ledger.categorisation.review.suggestion_heading"), *_suggested_values(suggestion)]
    for index, child in enumerate(suggestion.children, start=1):
        lines.append(
            tr(
                "tui.ledger.categorisation.review.suggested_child",
                index=index,
                amount=child.amount,
                description=child.description,
                category=child.category or "-",
            )
        )
    if suggestion.reason:
        lines.append(tr("tui.ledger.categorisation.review.suggested_reason", value=suggestion.reason))
    if suggestion.derivation_note:
        lines.append(tr("tui.ledger.categorisation.review.suggested_note", value=suggestion.derivation_note))
    if suggestion.evidence_advisory:
        lines.append(tr("tui.ledger.categorisation.review.suggested_note", value=suggestion.evidence_advisory))
    lines.append(tr("tui.ledger.categorisation.review.decide"))
    return lines


def suggestion_text(projection: BaseModel) -> str:
    """Word a review projection as a proposal the operator applies or rejects."""
    try:
        review = LedgerLlmReviewProjection.model_validate_json(projection.model_dump_json())
    except ValidationError:
        return projection.model_dump_json()
    return "\n".join(_suggestion_lines(review.suggestion))


def review_outcome_text(result: LedgerLlmOperationResult) -> str:
    """Say what a settled review changed."""
    if result.outcome == "classified" and result.classification is not None:
        transaction = result.classification.transaction
        classification = "-" if transaction is None else classification_label(transaction.business_classification)
        return tr("tui.ledger.categorisation.review.classified", classification=classification)
    if result.outcome == "split":
        return tr("tui.ledger.categorisation.review.split", count=len(result.child_transaction_ids))
    if result.outcome == "rejected":
        return tr("tui.ledger.categorisation.review.rejected")
    return tr("tui.ledger.categorisation.review.previewed")


class ReviewingCategorisationScreen(CategorisationScreen):
    """A tool that hands one review operation to the operation modal and reports its outcome."""

    def ask_for_review(self, door: LedgerSuggestionReviewDoorV1, request: LedgerLlmReviewRequest) -> None:
        """Submit one review off the event loop and let the modal take the decision."""
        if self.refuse_while_busy():
            return
        self.busy = True
        self.run_worker(self._open_review(door, request), exclusive=True, group="categorisation")

    async def _open_review(self, door: LedgerSuggestionReviewDoorV1, request: LedgerLlmReviewRequest) -> None:
        self.refuse("")
        self.show_outcome(None)
        self.status("tui.ledger.categorisation.review.asking")
        try:
            controller = await door.submit(request)
        except AccountSessionExpiredError as error:
            self.busy = False
            self.clear_private_view()
            self.refuse(door_refusal_text(error))
            self.query_one("#ledger-flow-status", Static).update(
                self.failed_write_status(error, "tui.ledger.categorisation.failed")
            )
            return
        except CadrumoError as error:
            self.busy = False
            self.refuse(door_refusal_text(error))
            # A review the runtime accepted but was not seen to start may be running: it is unknown, not refused.
            self.query_one("#ledger-flow-status", Static).update(
                self.failed_write_status(error, "tui.ledger.categorisation.failed")
            )
            return
        self.status("tui.ledger.categorisation.review.waiting")
        self.app.push_screen(
            OperationModal(controller, review_text=suggestion_text), partial(self._review_settled, door, request)
        )

    def _review_settled(
        self, door: LedgerSuggestionReviewDoorV1, request: LedgerLlmReviewRequest, outcome: object
    ) -> None:
        if isinstance(outcome, OperationModalDetachedOutcomeV1):
            self.busy = False
            self.status(None)
            self.show_outcome(lambda: tr("tui.ledger.categorisation.review.detached"))
            return
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            self.busy = False
            self.status(None)
            return
        view = outcome.view_model
        if view.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED:
            self.run_worker(self._read_review(door, request, view.projection), exclusive=True, group="categorisation")
            return
        self.busy = False
        explanation = outcome.error_explanation or (
            public_refusal_explanation(view.receipt_ref) if view.receipt_kind == "refusal" else None
        )
        if view.projection.effect is not OperationEffect.NONE:
            # The review settled without succeeding yet changed something, so its outcome is unknown, not refused.
            self.write_outcome_unknown = True
            self.status("tui.ledger.flow.outcome_unknown")
            unknown = door_refusal_text(
                OperationOutcomeUnknownError(operation_id=view.projection.operation_id, effect=view.projection.effect)
            )
            self.refuse(unknown if explanation is None else "\n".join((explanation, unknown)))
            return
        self.status("tui.ledger.categorisation.failed")
        self.refuse(tr("tui.ledger.categorisation.not_done") if explanation is None else explanation)

    async def _read_review(
        self,
        door: LedgerSuggestionReviewDoorV1,
        request: LedgerLlmReviewRequest,
        projection: OperationPublicProjectionV1,
    ) -> None:
        try:
            result = await door.read_result(request, projection)
        except AccountSessionExpiredError as error:
            self.clear_private_view()
            self.refuse(door_refusal_text(error))
            self.query_one("#ledger-flow-status", Static).update(
                self.failed_write_status(error, "tui.ledger.categorisation.failed")
            )
            return
        except CadrumoError as error:
            self.refuse(door_refusal_text(error))
            self.query_one("#ledger-flow-status", Static).update(
                self.failed_write_status(error, "tui.ledger.categorisation.failed")
            )
            return
        finally:
            self.busy = False
        self.show_outcome(lambda: review_outcome_text(result))
        if result.outcome in {"classified", "split"}:
            self.status("tui.ledger.categorisation.saved")
            self.refresh_then(self.after_refresh)
        else:
            self.status("tui.ledger.categorisation.not_done")


class LedgerSuggestionReviewScreen(ReviewingCategorisationScreen):
    """Ask for a suggested classification of the selected entry and decide on it in the modal."""

    ENTRY_SCOPED = True

    @override
    def banner(self) -> Static:
        return line("tui.ledger.categorisation.review.title", classes="cadrumo-banner")

    @override
    def prompt(self) -> Static:
        return line("tui.ledger.categorisation.review.prompt")

    def __init__(self, controller: LedgerWorkspaceController, *, door: LedgerSuggestionReviewDoorV1) -> None:
        """Keep the profile-bound classification review door."""
        super().__init__(controller, id="ledger-categorisation-review-screen")
        self.door = door

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.review.options_heading")
        yield Select[str](
            (
                (tr("tui.ledger.categorisation.review.mode.classification"), "classification"),
                (tr("tui.ledger.categorisation.review.mode.saturated"), "saturated"),
                (tr("tui.ledger.categorisation.review.mode.auto_split"), "auto_split"),
            ),
            value="classification",
            allow_blank=False,
            id="categorisation-review-mode",
        )
        yield Select[str](
            (
                (tr("tui.ledger.categorisation.review.evidence_no"), _EVIDENCE_NO),
                (tr("tui.ledger.categorisation.review.evidence_yes"), _EVIDENCE_YES),
            ),
            value=_EVIDENCE_NO,
            allow_blank=False,
            id="categorisation-review-evidence",
        )
        yield field("tui.ledger.categorisation.review.business_pct", id="categorisation-review-business-pct")
        yield field("tui.ledger.categorisation.review.reason", id="categorisation-review-reason")
        yield action_row(action("tui.ledger.categorisation.review.ask", id="categorisation-review-ask", primary=True))

    def build_request(self) -> LedgerLlmReviewRequest:
        """The review request the typed options describe, validated before anything is sent."""
        mode, origin = REVIEW_MODES[
            str(cast("Select[str]", self.query_one("#categorisation-review-mode", Select)).value)
        ]
        evidence = str(cast("Select[str]", self.query_one("#categorisation-review-evidence", Select)).value)
        return LedgerLlmReviewRequest(
            profile_id=self.door.profile_id,
            transaction_id=self.target,
            mode=mode,
            origin=origin,
            business_pct=blank_to_none(self.query_one("#categorisation-review-business-pct", Input).value),
            read_evidence=evidence == _EVIDENCE_YES,
            reason=self.query_one("#categorisation-review-reason", Input).value.strip(),
        )

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id != "categorisation-review-ask":
            return
        try:
            request = self.build_request()
        except (CadrumoError, ValueError) as error:
            self.refuse_error(error)
            return
        self.ask_for_review(self.door, request)


__all__ = [
    "REVIEW_MODES",
    "LedgerSuggestionReviewScreen",
    "ReviewingCategorisationScreen",
    "review_outcome_text",
    "suggestion_text",
]
