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
from .action_errors import ModeloOperationSubjectNotWorkUnitError
from .projection_next_steps import open_work_step
from .workspace_models import ModeloWorkspaceRefreshTargetV1

if TYPE_CHECKING:
    from ...domain.deadlines.models import TaxpayerProfile
    from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol


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


def require_owning_work_unit_subject(
    subject_ref: str,
    *,
    owning_work_unit_id: str | None,
    named_record: tuple[str, str],
    active_bucket_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
) -> None:
    """Refuse a request whose subject is not the work unit owning the record its payload names.

    The contract's subject is that stored work unit, and the receipt is held to
    it, so a request submitted under any other subject -- the record id itself,
    say -- would run and then never project. It is refused before anything is
    written, with a door to the declaration that owns the record.
    ``owning_work_unit_id`` is ``None`` when the record is not visible to this
    profile. That record, or a work unit this profile cannot see, is left to the
    service, which refuses it with its own typed error.
    ``named_record`` is the payload field name and id the refusal reports.
    """
    if owning_work_unit_id is None or owning_work_unit_id == subject_ref:
        return
    unit = work_unit_repository.load().work_units.get(owning_work_unit_id)
    if unit is None or unit.bucket_id != active_bucket_id:
        return
    raise ModeloOperationSubjectNotWorkUnitError(
        translated_message="errors.refused.refused_modelo_operation_subject_not_work_unit",
        context={named_record[0]: named_record[1], "work_unit_id": unit.work_unit_id},
        next_step=open_work_step(unit),
    )
