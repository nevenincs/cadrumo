"""A registered export refused before it writes anything reports that nothing changed.

The export operation journals that records may have changed only when it
reaches an actual write: a secure-object commit, the signing key or the
exported file. A refusal of its preconditions, such as a revision that is not
verified, leaves the effect at none, so a surface does not tell the filer the
outcome is unknown when nothing was touched.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from cadrumo.adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.profile.review_package_signing import (
    build_review_package_signing_keypair_capability,
)
from cadrumo.adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import bound_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.calculation_operation import ModeloWorkCalculateExecutor
from cadrumo.application.modelo.calculation_request_fields import (
    ModeloCalculationInputFieldsV1,
    ModeloCalculationOverride,
)
from cadrumo.application.modelo.export_operation import ModeloExportExecutor
from cadrumo.application.modelo.operation_shared import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    resolve_active_workflow_profile,
)
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_export_contracts import ModeloExportRequest
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.core.operations import OperationEffect
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.adapter_composition_ports import build_modelo_export_ports
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_YEAR = filing_year_envelope().horizon
_CLOCK = datetime(_YEAR, 1, 2, 10, tzinfo=UTC)


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


def _calculated_revision(operation: PinnedAuthorityOperation) -> str:
    """Calculate a synthetic first-quarter Modelo 130, which stays an unverified draft."""
    period = Period.from_year_and_code(_YEAR, "1T")
    snapshot = operation.snapshot("130", filing_year=_YEAR, period=period.registry_token)
    unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation).work_lifecycle_ports,
        clock=_CLOCK,
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
            inputs=ModeloCalculationInputFieldsV1(
                binding_overrides=tuple(
                    ModeloCalculationOverride(key=key, value="0")
                    for key in (
                        "irpf.previous_year_economic_activity_net_income",
                        "modelo-130-resultados-negativos-anteriores",
                        "modelo-130-pagos-fraccionados-anteriores",
                    )
                )
            ),
        ),
    )
    context = _Context(operation)

    async def run() -> ModeloWorkCalculatePublicResultV3:
        reference = await executor.execute(request, cast(OperationExecutorContext, context))
        assert reference is not None
        return await context.operands.resolve(reference, ModeloWorkCalculatePublicResultV3)

    return asyncio.run(run()).calculation_revision_id


@pytest.mark.parametrize(
    "artefact",
    (ModeloExportArtefact.CALCULATION_REPORT_CSV, ModeloExportArtefact.FICHERO_BOE),
)
def test_an_export_refused_for_an_unverified_revision_reports_no_effect(
    artefact: ModeloExportArtefact,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    output = tmp_path / "out" / "export.bin"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        seed_modelo_ready_profile(bucket_id=_PROFILE_ID, at=_CLOCK)
        with bound_test_profile_record(_PROFILE_ID):
            revision_id = _calculated_revision(operation)
            output.parent.mkdir()
            executor = ModeloExportExecutor(
                profile_resolver=resolve_active_workflow_profile,
                export_ports_factory=build_modelo_export_ports,
                signing_keypair_capability_factory=build_review_package_signing_keypair_capability,
                calculation_summary_pdf_writer=write_calculation_summary_pdf,
            )
            context = _Context(operation)
            request = OperationRequest(
                definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
                subject_ref=revision_id,
                payload=ModeloExportRequest(
                    calculation_revision_id=revision_id,
                    output_path=str(output),
                    artefact=artefact,
                    actor="operator",
                ),
            )
            with pytest.raises(CalculationRevisionStateError):
                asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))

    assert context.events.effects == []
    assert list(output.parent.iterdir()) == []
