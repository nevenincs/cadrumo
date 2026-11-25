"""The Records review reads through the installed TUI's retained runtime session.

The Review area lists the queue ``ledger.review`` answers, and the Evidence
area lists the drafts ``ledger.evidence.review.list`` answers. Both doors share
one session pinned to the admitted profile, so composing them observes the
session once. Each door refuses a result its terminal receipt does not support:
another profile, a refusal where a success was reported, or any effect other
than none.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cadrumo.application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
)
from cadrumo.application.ledger.review_operation import (
    LEDGER_REVIEW_OPERATION_DEFINITION_ID,
    LedgerReviewProjection,
    LedgerReviewRequest,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession


def _read_settled(condition: OperationTerminalCondition, terminal: OperationPublicProjectionV1) -> bool:
    """A success with no refusal whose receipt reports that nothing was written."""
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is OperationEffect.NONE
    )


class RuntimeLedgerReviewTuiDoorV1:
    """Submit ``ledger.review`` for the exact profile and session the shared session pins."""

    def __init__(self, session: RuntimeProfileSession) -> None:
        """Bind the shared pinned session."""
        self._session = session

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def __call__(self, request: LedgerReviewRequest) -> LedgerReviewProjection:
        """Read the review queue, refusing a result its terminal receipt does not support."""

        def settle(
            result: LedgerReviewProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if (
                result.profile_id != request.profile_id
                or result.transaction_prefix != request.transaction_prefix
                or not _read_settled(condition, terminal)
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=LEDGER_REVIEW_OPERATION_DEFINITION_ID,
            result_type=LedgerReviewProjection,
            settle=settle,
            explain_failure=True,
        )


class RuntimeLedgerEvidenceReviewListTuiDoorV1:
    """Submit ``ledger.evidence.review.list`` for the exact profile and session the shared session pins."""

    def __init__(self, session: RuntimeProfileSession) -> None:
        """Bind the shared pinned session."""
        self._session = session

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def __call__(self, request: LedgerEvidenceReviewListRequest) -> LedgerEvidenceReviewListProjection:
        """Read the drafts waiting for review, refusing a result its terminal receipt does not support."""

        def settle(
            result: LedgerEvidenceReviewListProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if result.profile_id != request.profile_id or not _read_settled(condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceReviewListProjection,
            settle=settle,
            explain_failure=True,
        )


@dataclass(frozen=True, slots=True)
class RuntimeLedgerReviewDoorsV1:
    """The two review reads, admitted for one profile on one session."""

    review: RuntimeLedgerReviewTuiDoorV1
    evidence_review: RuntimeLedgerEvidenceReviewListTuiDoorV1


def compose_runtime_ledger_review_doors(client: FrontendClient, *, profile_label: str) -> RuntimeLedgerReviewDoorsV1:
    """Bind both review reads to one session pinned on the workbench's runtime client."""
    session = RuntimeProfileSession(client, profile_label=profile_label)
    return RuntimeLedgerReviewDoorsV1(
        review=RuntimeLedgerReviewTuiDoorV1(session),
        evidence_review=RuntimeLedgerEvidenceReviewListTuiDoorV1(session),
    )


__all__ = [
    "RuntimeLedgerEvidenceReviewListTuiDoorV1",
    "RuntimeLedgerReviewDoorsV1",
    "RuntimeLedgerReviewTuiDoorV1",
    "compose_runtime_ledger_review_doors",
]
