"""Register modelo lifecycle operations using their canonical writers and public contracts.

Core types: :class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.models import (
    OperationTerminalReceipt,
)
from ..operations.registry import (
    OperationSchemaBindingV1,
)
from .workspace_models import ModeloWorkspaceRefreshTargetV1

if TYPE_CHECKING:
    from ...domain.deadlines.models import TaxpayerProfile


MODELO_WORK_RENAME_OPERATION_DEFINITION_ID = "modelo.work.rename"


MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID = "modelo.work.discard"


MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID = "modelo.work.calculate"


MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID = "modelo.work.verify"


MODELO_WORK_FILE_OPERATION_DEFINITION_ID = "modelo.work.file"


MODELO_EXPORT_OPERATION_DEFINITION_ID = "modelo.export"


MODELO_WORK_AMEND_OPERATION_DEFINITION_ID = "modelo.work.amend"


MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID = "modelo.edit.apply"


MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_SUFFIX = "workspace_refresh_target"


class _WorkUnitSubject(BaseModel):
    """Validate an operation subject reference as a real work-unit identifier."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId


def resolve_modelo_work_unit_refresh_target(
    terminal_receipt: OperationTerminalReceipt,
    /,
) -> ModeloWorkspaceRefreshTargetV1:
    """Derive the workspace read one settled Modelo work operation invalidates.

    Every definition below addresses one work unit, so the settled receipt's
    ``subject_ref`` is that unit's identifier. It is validated here rather
    than trusted: a subject that is not a well-formed
    :data:`~cadrumo.core.identity.hex_ids.WorkUnitId` raises, and the resolving
    service turns that into a typed refusal instead of handing a frontend a
    target it cannot read.
    """
    return ModeloWorkspaceRefreshTargetV1(
        work_unit_id=_WorkUnitSubject(work_unit_id=terminal_receipt.identity.subject_ref).work_unit_id,
    )


def modelo_workspace_refresh_target_binding(definition_id: str) -> OperationSchemaBindingV1:
    """Bind one enrolment's refresh-target schema to the shared target model."""
    return OperationSchemaBindingV1.bind(
        schema_id=f"{definition_id}.{MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_SUFFIX}",
        schema_version=1,
        model_type=ModeloWorkspaceRefreshTargetV1,
    )


type ModeloWorkVerifyProfileResolver = Callable[[PinnedAuthorityOperation], TaxpayerProfile]


def resolve_active_workflow_profile(operation: PinnedAuthorityOperation) -> TaxpayerProfile:
    """Resolve the active taxpayer profile when an operation actually runs.

    Injected as a strategy rather than a value: a definition composed into the
    production registry must not close over whichever profile happened to be
    active when the registry was built.
    """
    from ..wizard.status import load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    return load_active_taxpayer_profile(workflow_state_repository().load(), schema=operation.profile_schema())
