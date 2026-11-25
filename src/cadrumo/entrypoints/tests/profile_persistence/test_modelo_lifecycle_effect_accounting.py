"""A Modelo verification or filing says records may have changed only once a write begins.

Verify and file each run their gates before anything is saved. A refusal from
one of those gates, or an outcome that saves nothing, settles with no effect;
only a write that is about to begin journals that records may have changed.

Real behaviour throughout: an isolated encrypted profile, the bundled
authority, the production executors and their production repository bundles.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import pytest

from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....application.modelo.action_errors import CalculationRevisionStateError
from ....application.modelo.operation_definitions import ModeloWorkFileExecutor, ModeloWorkVerifyExecutor
from ....application.modelo.operation_shared import resolve_active_workflow_profile
from ....application.modelo.work_filing_contracts import ModeloWorkFileApproval, ModeloWorkFileRequest
from ....application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
from ....application.operations.models import OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.errors.hierarchy import CadrumoError
from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...adapter_composition_work_ports import build_filing_action_ports, build_verification_repository_bundle
from ..modelo_operator_work_storage import seeded_operator_work
from ..operation_contract_support import unavailable, unavailable_operator_scope_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

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


def _verify(operation: PinnedAuthorityOperation, calculation_revision_id: str) -> tuple[_Context, CadrumoError]:
    executor = ModeloWorkVerifyExecutor(
        certificate_secret_backend_factory=unavailable,
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=unavailable_operator_scope_ports(),
        verification_repository_bundle_factory=build_verification_repository_bundle,
    )
    context = _Context(operation)
    request = OperationRequest(
        definition_id="modelo.work.verify",
        subject_ref=calculation_revision_id,
        payload=ModeloWorkVerifyRequest(calculation_revision_id=calculation_revision_id, actor="operator"),
    )
    with pytest.raises(CadrumoError) as refused:
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    return context, refused.value


def _file(
    operation: PinnedAuthorityOperation, work_unit_id: str, calculation_revision_id: str
) -> tuple[_Context, CadrumoError]:
    executor = ModeloWorkFileExecutor(
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=unavailable_operator_scope_ports(),
        filing_action_ports_factory=build_filing_action_ports,
        certificate_secret_backend_factory=unavailable,
    )
    context = _Context(operation)
    request = OperationRequest(
        definition_id="modelo.work.file",
        subject_ref=work_unit_id,
        payload=ModeloWorkFileRequest(
            approval=ModeloWorkFileApproval(
                calculation_revision_id=calculation_revision_id,
                verification_report_id="0" * 64,
            ),
            actor="operator",
        ),
    )
    with pytest.raises(CadrumoError) as refused:
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    return context, refused.value


def test_a_verification_its_gates_refuse_settles_with_no_effect(tmp_path: Path) -> None:
    """A declaration whose calculation is still blocked is refused at verification before any report is saved."""
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        context, refused = _verify(work.operation, head.calculation_revision_id)

    assert get_registered_error_code(refused).category is ErrorCategory.REFUSED, refused
    assert context.events.effects == []


def test_a_filing_its_preconditions_refuse_settles_with_no_effect(tmp_path: Path) -> None:
    """An approval naming no verification of the revision is refused before any filing record is saved."""
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        context, refused = _file(work.operation, work.work_unit_id, head.calculation_revision_id)

    assert isinstance(refused, CalculationRevisionStateError), refused
    assert refused.precondition_failure is not None
    assert refused.precondition_failure.scenario_id == "modelo.work.file.calculation_revision.unverified"
    assert context.events.effects == []
