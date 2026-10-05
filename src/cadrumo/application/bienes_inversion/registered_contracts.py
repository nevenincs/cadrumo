"""Stable operation identifiers and refusal vocabulary for the capital-goods register."""

from __future__ import annotations

from typing import Literal

BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID = "ledger.bienes_inversion.list"

BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID = "ledger.bienes_inversion.declare"

BIENES_INVERSION_VALIDATION_REFUSAL_CODE = "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION"

BIENES_INVERSION_DUPLICATE_REFUSAL_CODE = BIENES_INVERSION_VALIDATION_REFUSAL_CODE

type BienesInversionOperationId = Literal["list", "declare"]

type BienesInversionRefusalReason = Literal["validation", "disposal_incomplete", "duplicate_identifier"]
