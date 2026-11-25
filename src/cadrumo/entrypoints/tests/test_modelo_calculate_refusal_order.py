"""A calculation refuses invalid supplied input before it judges an empty withholding window.

The empty-window pre-check reads the stored retenciones and refuses a period
that holds none. It runs only after the request's own inputs are validated, so
a filer who passed a malformed value is told about that value rather than being
asked to record a payment, and either refusal leaves nothing written.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import bound_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.errors import RetencionesWindowEmptyError
from cadrumo.application.modelo.calculate_input_validation import ModeloCalculateCasillaInputError
from cadrumo.application.modelo.calculation_operation import ModeloWorkCalculateExecutor
from cadrumo.application.modelo.calculation_request_fields import (
    ModeloCalculationInputFieldsV1,
    ModeloCalculationOverride,
)
from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.core.operations import OperationEffect
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "5c2e7a10-3b4d-4e5f-9a60-71b2c3d4e5f6"
_LEASE_MODELO = "115"


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        del phase_code

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield


class _Context:
    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.authority_operation = operation
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = operation_secure_reference_repository()


def _calculate_empty_lease_window(context: _Context, casilla_overrides: tuple[ModeloCalculationOverride, ...]) -> None:
    """Calculate a first-quarter Modelo 115 whose window holds no retención."""
    operation = context.authority_operation
    filing_year = operation.supported_filing_years().years[-1]
    period = Period.from_year_and_code(filing_year, "1T")
    clock = datetime(filing_year, 1, 2, 10, tzinfo=UTC)
    snapshot = operation.snapshot(_LEASE_MODELO, filing_year=filing_year, period=period.registry_token)
    unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo=_LEASE_MODELO,
        filing_year=filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation).work_lifecycle_ports,
        clock=clock,
        operation=operation,
    )
    store = AttachmentStore()
    executor = ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=build_calculation_action_ports,
        attachment_store_factory=lambda _bucket_id: store,
    )
    request = OperationRequest(
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref=unit.work_unit_id,
        payload=ModeloWorkCalculateRequest(
            work_unit_id=unit.work_unit_id,
            actor="operator",
            caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
            inputs=ModeloCalculationInputFieldsV1(casilla_overrides=casilla_overrides),
        ),
    )
    asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))


@pytest.fixture
def _ready_profile(tmp_path: Path, operation: PinnedAuthorityOperation) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        seed_modelo_ready_profile(
            bucket_id=_PROFILE_ID,
            at=datetime(operation.supported_filing_years().years[-1], 1, 1, tzinfo=UTC),
            # Paying rent subject to retención is what makes Modelo 115 apply.
            facts=(UserProfileFact(path="withholding.pays_rent_with_retencion", value="true"),),
        )
        with bound_test_profile_record(_PROFILE_ID):
            yield None


@pytest.mark.usefixtures("_ready_profile")
def test_an_undeclared_casilla_is_refused_before_the_empty_window(operation: PinnedAuthorityOperation) -> None:
    context = _Context(operation)
    with pytest.raises(ModeloCalculateCasillaInputError):
        _calculate_empty_lease_window(context, (ModeloCalculationOverride(key="99", value="1"),))
    assert context.events.effects == []


@pytest.mark.usefixtures("_ready_profile")
def test_a_valid_request_on_an_empty_window_is_refused_with_nothing_written(
    operation: PinnedAuthorityOperation,
) -> None:
    context = _Context(operation)
    with pytest.raises(RetencionesWindowEmptyError):
        _calculate_empty_lease_window(context, ())
    assert context.events.effects == []
