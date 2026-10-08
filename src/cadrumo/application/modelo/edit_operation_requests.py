"""Version-two amount-free operation requests for exact transient edit batches."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from ...core.identity.hex_ids import WorkUnitId
from ..operations.financial_operand_contract import CredentialFreeFinancialOperationRequest


class ModeloEditApplyOperationRequestV2(CredentialFreeFinancialOperationRequest):
    """Safe apply admission coordinates; every intent stays in runtime custody."""

    request_version: Literal[2] = 2
    profile_id: UUID
    work_unit_id: WorkUnitId


class ModeloEditPreflightRequestV2(CredentialFreeFinancialOperationRequest):
    """Safe preflight admission coordinates with the same whole-batch custody."""

    request_version: Literal[2] = 2
    profile_id: UUID
    work_unit_id: WorkUnitId
