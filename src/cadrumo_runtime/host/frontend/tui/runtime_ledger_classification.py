"""Manual Ledger classification through the retained installed TUI session."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.application.ledger.actions_common import display_decimal
from cadrumo.application.ledger.classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyRequest,
)
from cadrumo.application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.transactions.enums import BusinessClassification
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
    """Correlate the selected fields with the canonical writer's normalization."""
    transaction = result.transaction
    if transaction is None or transaction.transaction_id != request.transaction_id:
        return False
    business = transaction.business_classification in {
        BusinessClassification.BUSINESS.value,
        BusinessClassification.MIXED.value,
    }
    expected_share = request.patch.business_pct if transaction.business_classification == "MIXED" else None
    if transaction.business_pct != expected_share:
        return False
    for field in request.patch_fields:
        expected = getattr(request.patch, field)
        if field in {"deduction_fact_kind", "investment_asset_id"}:
            actual = getattr(result, field)
        else:
            actual = getattr(transaction, field)
        if field == "category_id":
            expected = (expected.strip() or None) if expected is not None and business else None
        elif field in {"taxable_base", "iva_rate", "iva_amount", "irpf_category"} and not business:
            expected = None
        elif field == "notes":
            expected = expected or ""
        if actual != expected:
            return False
    return True


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
            if (
                condition is not OperationTerminalCondition.SUCCEEDED
                or result.outcome != "classified"
                or result.profile_id != request.profile_id
                or terminal.effect is not expected_effect
                or terminal.refusal_ref is not None
                or terminal.failure_error_code is not None
                or terminal.diagnostic_ref is not None
                or terminal.result_ref is None
                or not _patch_matches(result, request)
            ):
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
