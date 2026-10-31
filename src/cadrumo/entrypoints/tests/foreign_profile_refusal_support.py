"""Run an operation while another profile is active and require a refusal with no effect."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from pydantic import BaseModel

from ...core.config import override_settings
from ...core.operations import OperationEffect, OperationTerminalCondition
from . import registered_executor_case_support as conformance


def assert_refused_for_foreign_active_profile(
    driver: conformance._ExecutionDriver,
    *,
    definition_id: str,
    subject_ref: str,
    payload: BaseModel,
) -> None:
    """Submit with a different profile active and require a terminal refusal that recorded no effect."""
    with override_settings(cadrumo_active_profile=str(uuid4())):
        refused_submission, refused_observation = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
        )
    refused_snapshot = asyncio.run(
        driver.services.submission.supervisor.inspect(refused_submission.receipt.operation_id)
    )
    refused_receipt = refused_snapshot.terminal_receipt
    assert refused_receipt is not None
    assert refused_receipt.identity.subject_ref == subject_ref
    assert refused_receipt.condition is OperationTerminalCondition.REFUSED
    assert refused_receipt.effect is OperationEffect.NONE
    assert refused_receipt.result_ref is None
    assert refused_observation.projection.terminal_condition is OperationTerminalCondition.REFUSED
