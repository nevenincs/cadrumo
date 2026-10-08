"""Volatile operator input conversion before amount-free operation admission.

The native input encoding is held only in bounded memory buffers. The worker
validates it into the canonical domain batch once; that model is neither
serialized into an operation request nor hashed as an admission operand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.hashing import reject_duplicate_json_members, reject_json_constant
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.financial_operand_contract import (
    OperationFinancialOperandRefusalCode,
    OperationFinancialOperandRefusedError,
)
from .edit_apply_contracts import ModeloEditApplySubmissionV1
from .edit_models import ModeloEditSubmissionV1
from .edit_operation_requests import ModeloEditApplyOperationRequestV2, ModeloEditPreflightRequestV2


class ModeloEditOperatorInputV2(BaseModel):
    """Exact bounded human input encoding for all four canonical intent families."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    input_version: Literal[2] = 2
    submission: ModeloEditApplySubmissionV1 = Field(repr=False)


@dataclass(slots=True)
class PreparedModeloEditOperand:
    """Call-scoped transfer of the safe request and private complete batch."""

    request: ModeloEditApplyOperationRequestV2 | ModeloEditPreflightRequestV2
    operand: ModeloEditSubmissionV1 | None = field(repr=False)

    def release(self) -> None:
        """Drop the intake scope's reference after transfer or refusal."""
        self.operand = None


def prepare_modelo_edit_operand(
    *, definition_id: str, profile_id: UUID, subject_ref: str, input_json: str
) -> PreparedModeloEditOperand:
    """Validate human input before creating any operation, provenance or content digest."""
    encoded: ModeloEditOperatorInputV2 | None = None
    operand: ModeloEditSubmissionV1 | None = None
    try:
        if definition_id not in {"modelo.edit.apply", "modelo.edit.preflight"}:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_MODEL)
        # Verify JSON membership and finiteness before Pydantic hydrates input.
        # No re-encoding or content fingerprint is produced from financial values.
        checked = json.loads(
            input_json, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        del checked
        encoded = ModeloEditOperatorInputV2.model_validate_json(input_json)
        operand = encoded.submission.to_submission()
        baseline = operand.baseline
        if baseline.bucket_id != str(profile_id) or baseline.work_unit_id != subject_ref:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_BASELINE)
        request_type = (
            ModeloEditApplyOperationRequestV2 if definition_id == "modelo.edit.apply" else ModeloEditPreflightRequestV2
        )
        return PreparedModeloEditOperand(
            request=request_type(
                profile_id=profile_id, work_unit_id=baseline.work_unit_id, financial_baseline_ref=baseline.baseline_id
            ),
            operand=operand,
        )
    finally:
        input_json = ""
        encoded = None
        operand = None
