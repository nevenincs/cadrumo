"""A refused work metadata read records the verdict its executor raised, for another process to read."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.metadata_read_operation import (
    MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
    ModeloWorkMetadataRequest,
    build_modelo_metadata_definition,
    build_modelo_metadata_registration,
)
from cadrumo.application.modelo.tests.work_operation_support import first_quarter_unit
from cadrumo.application.modelo.work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from cadrumo.application.operations.error_detail import OperationErrorDetailV1
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.work_unit import WorkUnitCatalogue

from .supervision_support import run_to_settlement
from .supervisor_test_support import operation_repositories, operation_supervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE = UUID("a0347100-3a01-4b0a-aeee-347102030499")


def test_contradictory_selector_refusal_keeps_its_verdict_in_the_recorded_detail(tmp_path: Path) -> None:
    """The receipt names only the registered code; the verdict reaches a frontend through the detail."""
    unit = first_quarter_unit(_PROFILE)

    class Repository:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    def ports() -> SimpleNamespace:
        return SimpleNamespace(work_unit_repository=Repository())

    factory = cast(ActiveWorkLifecyclePortsFactory, cast(object, ports))
    definition = build_modelo_metadata_definition(factory)
    registration = build_modelo_metadata_registration(definition, factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        bundled_indexed_authority().operation() as authority,
    ):
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = operation_supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_timeout=timedelta(minutes=1),
            authority_operation=authority,
        )

        async def settle() -> None:
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=ModeloWorkMetadataRequest(
                        profile_id=_PROFILE, work_unit_id=unit.work_unit_id, modelo="130", year=unit.filing_year
                    ),
                ),
                operation_id="4" * 64,
            )
            await run_to_settlement(supervisor, operation_id)
            settled = await supervisor.inspect(operation_id)
            assert settled.terminal_condition is OperationTerminalCondition.REFUSED
            receipt = settled.terminal_receipt
            assert receipt is not None
            assert receipt.error_detail_ref is not None
            detail = await operands.resolve(receipt.error_detail_ref, OperationErrorDetailV1)
            assert detail.error_code == receipt.refusal_ref
            assert detail.precondition_verdict() is not None

        asyncio.run(settle())
