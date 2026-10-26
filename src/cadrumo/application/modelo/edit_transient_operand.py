"""Register the canonical complete edit submission and exact co-committed effect proof."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import cast

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect
from ..operations.financial_operand_contract import (
    OperationFinancialOperandEffectReceiptV1,
    OperationFinancialOperandRefusalCode,
    OperationFinancialOperandRefusedError,
    OperationTransientFinancialOperandDeclarationV1,
    OperationTransientFinancialOperandRequirementV1,
    financial_operand_model_identity,
)
from .edit_models import ModeloEditBaselineV1, ModeloEditSubmissionV1
from .edit_receipt_ports import ModeloEditReceiptRepositoryFactory


def _baseline(operand: BaseModel) -> BaseModel:
    return cast(ModeloEditSubmissionV1, operand).baseline


def _reference(baseline: BaseModel) -> str:
    return cast(ModeloEditBaselineV1, baseline).baseline_id


def modelo_edit_financial_operand(
    receipt_repository_factory: ModeloEditReceiptRepositoryFactory | None,
) -> OperationTransientFinancialOperandDeclarationV1:
    """Bind exact application models, without a mirrored or restricted Decimal batch."""

    async def receipt(
        requirement: OperationTransientFinancialOperandRequirementV1,
    ) -> OperationFinancialOperandEffectReceiptV1 | None:
        if receipt_repository_factory is None:
            return None
        repository = receipt_repository_factory(bucket_id=require_active_bucket_id())
        committed = await await_cancellation_complete(
            asyncio.to_thread(
                repository.find_operation_receipt,
                operation_id=requirement.identity.operation_id,
                baseline_id=requirement.domain_baseline_ref,
            ),
            task_name="modelo-edit-exact-effect-receipt",
        )
        if committed is None:
            return None
        if committed.work_unit_id != requirement.identity.subject_ref:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_BASELINE)
        return OperationFinancialOperandEffectReceiptV1(
            identity=requirement.identity,
            handoff_id=requirement.handoff_id,
            domain_baseline_ref=requirement.domain_baseline_ref,
            effect=OperationEffect.UPDATED,
        )

    return OperationTransientFinancialOperandDeclarationV1(
        operand_type=ModeloEditSubmissionV1,
        operand_schema=financial_operand_model_identity(
            schema_id="modelo.edit.submission", schema_version=1, model_type=ModeloEditSubmissionV1
        ),
        baseline_type=ModeloEditBaselineV1,
        baseline_schema=financial_operand_model_identity(
            schema_id="modelo.edit.baseline", schema_version=1, model_type=ModeloEditBaselineV1
        ),
        baseline_accessor=_baseline,
        baseline_reference=_reference,
        lifetime=timedelta(minutes=5),
        effect_receipt_resolver=receipt,
    )
