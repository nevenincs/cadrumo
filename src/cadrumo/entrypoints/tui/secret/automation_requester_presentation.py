"""Safe outcome display and separate reviewer navigation for requester screens."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import App
from textual.widgets import Button, Static

from ....application.user_profile.automation_enrollment import EnrollmentStage
from ....core.i18n.render import tr
from . import automation_requester_contracts as _contracts

if TYPE_CHECKING:
    from .automation_requester import RuntimeAutomationRequesterScreen


_OUTCOME_LOCALE_KEYS = {
    "uncertain": "tui.automation_request.uncertain",
    "complete": "tui.automation_request.complete",
    "declined": "tui.automation_request.declined",
    "invalid": "tui.automation_request.invalid",
}


class RequesterPresentationMixin:
    """Render only safe result identity and independently bound reviewer access."""

    def _render_outcome(self: RuntimeAutomationRequesterScreen) -> None:
        if not self._live or not self.is_mounted:
            return
        outcome = self._outcome
        if outcome is None:
            return
        label = self._outcome_label(outcome)
        parts = [tr(_OUTCOME_LOCALE_KEYS[label])]
        if outcome.request_id is not None:
            parts.append(f"{tr('tui.automation_request.request_id')}: {outcome.request_id}")
        if outcome.review_digest is not None:
            parts.append(f"{tr('tui.automation_request.review_digest')}: {outcome.review_digest}")
        if outcome.credential_reference is not None:
            parts.append(f"{tr('tui.automation_request.reference')}: {outcome.credential_reference}")
        self.query_one("#automation-request-status", Static).update(" · ".join(parts))
        self.query_one("#automation-request-close", Button).disabled = False

    @staticmethod
    def _outcome_label(outcome: _contracts.AutomationRequestOutcome) -> str:
        if outcome.uncertain:
            return "uncertain"
        if outcome.stage is EnrollmentStage.COMPLETE:
            return "complete"
        if outcome.stage is EnrollmentStage.DECLINED:
            return "declined"
        return "invalid"

    def _open_review(self: RuntimeAutomationRequesterScreen) -> None:
        """Let the human inspect and decide separately while delivery remains owned."""
        from ..profile.automation_inventory import RuntimeAutomationInventoryScreen

        reviewer = self._reviewer_client
        if not self._live or self._submitted is None or reviewer is None or not self._reviewer_bound():
            return
        screen = RuntimeAutomationInventoryScreen(reviewer)

        def closed(lost: bool | None) -> None:
            if lost or screen.access_lost:
                self._reviewer_access_lost = True
            if self._live and self.is_mounted:
                self.query_one("#automation-request-review", Button).disabled = not self._reviewer_bound()

        cast("App[object]", self.app).push_screen(screen, closed)
