"""A Modelo 130 box the filer typed over an unanswered prior-quarter carry calculates and publishes.

Box 05 carries the pagos fraccionados of the earlier quarters of the same
ejercicio from the Modelo 130 returns filed for them. With none held, the
binding that feeds box 05 stays unanswered. A filer who types box 05 answers it:
the published calculation carries the typed figure in box 05 and names no
unanswered binding for that box, because a box with a value is not a gap.

The production calculate definition runs under a real supervisor, and its
public result is read back the way another process reads it. Real encrypted
store, real published authority, real calculation engine. No doubles.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.tests.supervision_support import run_to_settlement
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
from cadrumo.adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculation_operation import (
    build_modelo_work_calculate_definition,
    build_modelo_work_calculate_registration,
)
from cadrumo.application.modelo.calculation_request_fields import (
    ModeloCalculationInputFieldsV1,
    ModeloCalculationOverride,
)
from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.period import Period
from cadrumo.core.time.clock import today_madrid
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import published_supported_filing_years
from cadrumo.entrypoints.tests.dependency_operation_gating_support import supervisor_with_projections
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET = "44444444-4444-4444-8444-444444440130"
_MODELO = "130"
# A quarter after the first, so the prior-quarter carry into box 05 has quarters to read.
_PERIOD = "3T"
_CARRY_BOX = "05"
_ANSWERED_BINDINGS = (
    ModeloCalculationOverride(key="irpf.previous_year_economic_activity_net_income", value="13000"),
    ModeloCalculationOverride(key="modelo-130-resultados-negativos-anteriores", value="0"),
)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _filing_year() -> int:
    """The latest supported filing year that has begun, read from the registry envelope."""
    supported = published_supported_filing_years()
    assert supported is not None
    return max(year for year in supported.years if year <= today_madrid().year)


def _calculate(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    *,
    casilla_overrides: tuple[ModeloCalculationOverride, ...],
) -> ModeloWorkCalculatePublicResultV3:
    """Create the Modelo 130 work unit, settle one calculation, and read its public result back."""
    year = _filing_year()
    seed_modelo_ready_profile(bucket_id=_BUCKET, at=datetime.now(UTC), tax_id=SEEDED_SOURCE_TAX_ID)
    work_units = WorkUnitCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    calculations = CalculationRevisionCatalogueRepository(objects=secure_objects)
    events = BucketEventHistoryRepository(objects=secure_objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo=_MODELO,
        filing_year=year,
        period=Period.from_year_and_code(year, _PERIOD),
        revision_id=operation.snapshot(_MODELO, filing_year=year, period=_PERIOD).revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=work_units, bucket_event_repository=events),
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET,
        work_unit_repository=work_units,
        calculation_repository=calculations,
        bucket_event_repository=events,
    ) as ports:
        definition = build_modelo_work_calculate_definition(
            calculation_action_ports_factory=lambda **_composition: ports,
            attachment_store_factory=lambda _bucket_id: AttachmentStore(objects=secure_objects),
        )
        registration = build_modelo_work_calculate_registration(definition)
        supervisor, projections = supervisor_with_projections(
            tmp_path=tmp_path,
            profile_objects=secure_objects,
            authority_operation=operation,
            registry=OperationRegistry(definitions=(definition,), public_registrations=(registration,)),
        )
        request = OperationRequest[BaseModel](
            definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            subject_ref=work_unit.work_unit_id,
            payload=ModeloWorkCalculateRequest(
                work_unit_id=work_unit.work_unit_id,
                actor="operator-A",
                caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
                inputs=ModeloCalculationInputFieldsV1(
                    casilla_overrides=casilla_overrides, binding_overrides=_ANSWERED_BINDINGS
                ),
            ),
        )

        async def settle() -> object:
            operation_id = await supervisor.submit(request, operation_id="4" * 64)
            terminal = await run_to_settlement(supervisor, operation_id)
            receipt = terminal.terminal_receipt
            assert receipt is not None
            assert receipt.condition is OperationTerminalCondition.SUCCEEDED, receipt
            assert registration.contract.result_schema is not None
            return await projections.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=registration.contract.definition_contract_digest,
                    result_schema=registration.contract.result_schema,
                ),
                ModeloWorkCalculatePublicResultV3,
            )

        resolved = asyncio.run(settle())
    assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
    published = resolved.projection
    assert isinstance(published, ModeloWorkCalculatePublicResultV3)
    return published


def _box_values(published: ModeloWorkCalculatePublicResultV3) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for fact in published.calculation.casilla_values:
        assert isinstance(fact.value, PublicDecimal)
        values[fact.key] = Decimal(fact.value.decimal)
    return values


def test_a_typed_carry_box_publishes_the_typed_figure_and_names_no_gap_for_it(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    published = _calculate(
        secure_objects,
        tmp_path,
        operation,
        casilla_overrides=(ModeloCalculationOverride(key=_CARRY_BOX, value="150.00"),),
    )

    assert _box_values(published)[_CARRY_BOX] == Decimal("150.00")
    assert _CARRY_BOX not in {row.casilla_id for row in published.unresolved_bindings}
    assert _CARRY_BOX not in {row.casilla_id for row in published.unresolved_casillas}
