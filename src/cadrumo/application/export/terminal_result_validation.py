"""Shared terminal receipt checks for releasing completed review results."""

from __future__ import annotations

from ..operations.models import OperationTerminalReceipt


def terminal_receipt_has_result_only(receipt: OperationTerminalReceipt) -> bool:
    """Require one result and no refusal, error or diagnostic references."""
    return (
        receipt.result_ref is not None
        and receipt.refusal_ref is None
        and receipt.refusal_detail_ref is None
        and receipt.failure_error_code is None
        and receipt.diagnostic_ref is None
    )
