"""Manual Ledger classification through the retained installed TUI session."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.application.ledger.actions_common import display_decimal
from cadrumo.application.ledger.classify_correlation import classification_selected_fields_match
from cadrumo.application.ledger.classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyRequest,
)
from cadrumo.application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.entrypoints.tui.ledger.models import LedgerClassificationResultV1, LedgerClassificationSubmissionV1
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession


def _wire_value(value: object) -> object:
    if isinstance(value, Decimal):
        return display_decimal(value)
    if isinstance(value, str):
        return str(value)
    return value


def build_runtime_ledger_classification_patch(values: dict[str, object]) -> LedgerClassifyPatch:
    """Keep the explicit bounded inputs for authoritative validation in the worker."""
    if not values or not set(values) <= set(LedgerClassifyPatch.model_fields):
        raise TransactionValidationError(
            "classification requires fields supported by the registered command",
            translated_message="tui.ledger.refusal.submission_unavailable",
        )
    return LedgerClassifyPatch.model_validate({name: _wire_value(value) for name, value in values.items()})


def _patch_matches(result: LedgerClassifyOperationResult, request: LedgerClassifyRequest) -> bool:
    """Correlate the settled row and the fields the request selected."""
    transaction = result.transaction
    return (
        transaction is not None
        and transaction.transaction_id == request.transaction_id
        and classification_selected_fields_match(
            patch=request.patch, fields=request.patch_fields, m210=request.m210, result=result
        )
    )


def _settled_classification_matches(
    result: LedgerClassifyOperationResult,
    request: LedgerClassifyRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
    expected_effect: OperationEffect,
) -> bool:
    """Require the expected settled receipt and the selected resulting fields."""
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and result.outcome == "classified"
        and result.profile_id == request.profile_id
        and terminal.effect is expected_effect
        and terminal.refusal_ref is None
        and terminal.failure_error_code is None
        and terminal.diagnostic_ref is None
        and terminal.result_ref is not None
        and _patch_matches(result, request)
    )


class RuntimeLedgerClassificationTuiDoorV1:
    """Submit one canonical action and release only its settled transaction identity."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the originating profile and session for every submission."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> LedgerClassificationResultV1:
        """Preserve explicit patch selection and correlate the registered operation."""
        if submission.action.action_id != lookup_action("operator.ledger.classify").action_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        fields = tuple(sorted(submission.patch.model_fields_set))
        if not set(fields) <= set(LedgerClassifyPatch.model_fields):
            # Fields outside this registered command cannot be silently discarded.
            raise RefusalError(RefusalCode.UNAVAILABLE)
        request = LedgerClassifyRequest.model_validate(
            {
                "profile_id": self._session.profile_id,
                "transaction_id": submission.transaction_id,
                "patch": {name: _wire_value(getattr(submission.patch, name)) for name in fields},
                "patch_fields": fields,
            }
        )

        def settle(
            result: LedgerClassifyOperationResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            expected_effect = OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
            if not _settled_classification_matches(result, request, condition, terminal, expected_effect):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        await self._session.run_operation(
            request,
            definition_id=LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
            result_type=LedgerClassifyOperationResult,
            settle=settle,
            explain_failure=True,
        )
        return LedgerClassificationResultV1(transaction_id=submission.transaction_id)


__all__ = ["RuntimeLedgerClassificationTuiDoorV1", "build_runtime_ledger_classification_patch"]
