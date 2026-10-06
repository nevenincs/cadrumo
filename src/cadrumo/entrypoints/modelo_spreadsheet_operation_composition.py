"""Bind canonical spreadsheet algorithms to one immutable profile worker.

Core types: :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from ..application.calculations.relation_prefill import resolve_relations_from_local_store
from ..application.modelo.modelo_spreadsheet_operation_contracts import (
    ModeloSpreadsheetOperationPorts,
)
from ..application.storage.calc_sheets.engine import (
    RelationResolver,
    build_export_plan,
)
from ..application.storage.calc_sheets.records import OperatorInputs, RelationValues, SheetExportPlan
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.schema import RegistrySnapshot

if TYPE_CHECKING:
    pass


def build_modelo_spreadsheet_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ModeloSpreadsheetOperationPorts:
    """Compose lazy ports; never discover providers or credentials at registry build."""

    def require_profile() -> None:
        if require_active_bucket_id() != str(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    require_profile()

    def bound_relation_resolver(snapshot: RegistrySnapshot) -> RelationValues:
        from ..adapters.persistence.profile.calculation_observations import CalculationObservationRepository
        from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

        require_profile()
        repository = CalculationObservationRepository(objects=secure_object_repository_for_bucket(str(profile_id)))
        return resolve_relations_from_local_store(snapshot, operation=operation, repository=repository)

    def bound_plan_builder(
        snapshot: RegistrySnapshot,
        *,
        operator_inputs: OperatorInputs,
        relation_values: RelationValues | None = None,
        relation_resolver: RelationResolver | None = None,
    ) -> SheetExportPlan:
        require_profile()
        return build_export_plan(
            snapshot,
            operator_inputs=operator_inputs,
            relation_values=relation_values,
            relation_resolver=bound_relation_resolver if relation_resolver is not None else None,
        )

    def materialize(plan: SheetExportPlan) -> bytes:
        from ..adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan

        require_profile()
        return materialize_export_plan(plan)

    return ModeloSpreadsheetOperationPorts(
        profile_id=profile_id,
        operation=operation,
        materialize=materialize,
        plan_builder=bound_plan_builder,
    )


__all__ = ["build_modelo_spreadsheet_operation_ports"]
