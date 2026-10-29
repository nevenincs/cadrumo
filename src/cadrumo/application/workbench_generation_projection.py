"""Strict versioned public projection of the complete workbench generation.

Only incompatible canonical nodes are mirrored; compatible children retain their
existing typed models. Projection and restoration validate the original models.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from cadrumo.application.aeat_sync.workspace import (
    AeatSyncWorkspaceProjectionV1,
)
from cadrumo.application.ledger.workspace import (
    LedgerWorkspaceProjectionV1,
)
from cadrumo.application.modelo.declaration_summary import DeclarationSummary
from cadrumo.application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
)
from cadrumo.application.modelo.declarations_workspace_contracts import (
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceLifecycleRefV1,
    DeclarationsWorkspaceProjectionV1,
)
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceProjectionV1,
)
from cadrumo.application.search.installed_workbench import (
    InstalledWorkbenchSearchSnapshotV1,
)
from cadrumo.application.search.workbench import WorkbenchDestinationAdmission

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import validate_utc_aware
from ..core.type_guards import is_object_mapping, is_object_tuple
from .operations.public_mirror import (
    excluded_canonical_fields,
    project_public_mirror,
    restore_public_mirror,
)
from .workbench_generation import (
    assemble_workbench_generation_search,
)
from .workbench_generation_contracts import (
    WorkbenchGenerationProjectionResultV1,
    WorkbenchGenerationV1,
)
from .workbench_generation_modelo_contracts import (
    PublicModeloWorkReview,
    PublicModeloWorkspaceResolvedTargetV1,
)
from .workbench_generation_public_contracts import (
    PublicDeclarationsWorkspaceProjectionV1,
    PublicLedgerWorkspaceProjectionV1,
    PublicSearchGenerationStateV1,
    PublicWorkbenchGenerationV1,
)


class WorkbenchGenerationOperationProjection(BaseModel):
    """Public exact-profile envelope around one complete generation version."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    generation: PublicWorkbenchGenerationV1

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_utc_instants(self) -> Self:
        """Retain the canonical UTC-only boundary after primitive projection."""

        def inspect(value: object) -> None:
            if isinstance(value, datetime):
                validate_utc_aware(value)
            elif isinstance(value, BaseModel):
                for field_name in type(value).model_fields:
                    inspect(getattr(value, field_name))
            elif is_object_tuple(value):
                for item in value:
                    inspect(item)

        inspect(self.generation)
        _require_profile_binding(self.profile_id, self.generation)
        return self


WorkbenchGenerationOperationProjection.model_rebuild()


_REVIEWED_EXCLUDED_FIELDS: frozenset[tuple[type[BaseModel], str]] = frozenset(
    {
        (DeclarationsWorkspaceProjectionV1, "bucket_id"),
        (DeclarationsWorkspaceDeclarationRefV1, "work_unit_id"),
        (DeclarationsWorkspaceCalculationRevisionRefV1, "calculation_revision_id"),
        (DeclarationsWorkspaceCalculationRevisionRefV1, "work_unit_id"),
        (DeclarationsWorkspaceFilingRefV1, "filing_record_id"),
        (DeclarationsWorkspaceFilingRefV1, "work_unit_id"),
        (DeclarationsWorkspaceFilingRefV1, "calculation_revision_id"),
        (DeclarationsWorkspaceFilingRefV1, "amends_filing_record_id"),
        (DeclarationsWorkspaceLifecycleRefV1, "fact_id"),
        (DeclarationsWorkspaceLifecycleRefV1, "work_unit_id"),
        (DeclarationSummary, "technical_reason"),
        (DeclarationsCalendarEntryRefV1, "aeat_reference_id"),
        (DeclarationsCalendarEntryRefV1, "recovery_action"),
    }
)


def _require_reviewed_exclusions() -> None:
    """Reject any new omitted canonical field before projecting owner data."""
    # Search documents and identity bases never enter the public result.
    discovered = excluded_canonical_fields(
        WorkbenchGenerationV1, opaque=frozenset({InstalledWorkbenchSearchSnapshotV1})
    )
    if discovered != _REVIEWED_EXCLUDED_FIELDS:
        raise ValueError("workbench public excluded-field inventory changed")


_PROFILE_BOUND_PUBLIC_MODELS: frozenset[type[BaseModel]] = frozenset(
    {
        PublicDeclarationsWorkspaceProjectionV1,
        PublicLedgerWorkspaceProjectionV1,
        PublicModeloWorkspaceResolvedTargetV1,
        PublicModeloWorkReview,
    }
)


def _inspect_profile_binding_model(value: BaseModel, expected: str) -> None:
    model = type(value)
    if "bucket_id" in model.model_fields:
        if model not in _PROFILE_BOUND_PUBLIC_MODELS:
            raise ValueError("workbench bucket-bearing model needs review")
        bucket_id = value.__dict__["bucket_id"]
        if bucket_id is not None and bucket_id != expected:
            raise ValueError("workbench projection profile mismatch")
    for field_name in model.model_fields:
        _inspect_profile_binding_value(getattr(value, field_name), expected)


def _inspect_profile_binding_value(value: object, expected: str) -> None:
    if isinstance(value, BaseModel):
        _inspect_profile_binding_model(value, expected)
        return
    if is_object_mapping(value):
        for item in value.values():
            _inspect_profile_binding_value(item, expected)
        return
    if is_object_tuple(value):
        for item in value:
            _inspect_profile_binding_value(item, expected)
        return
    if is_dataclass(value):
        for field in fields(value):
            _inspect_profile_binding_value(getattr(value, field.name), expected)


def _require_profile_binding(profile_id: UUID, generation: PublicWorkbenchGenerationV1) -> None:
    """Check each explicit bucket coordinate against the admitted envelope."""
    _inspect_profile_binding_value(generation, str(profile_id))


_OMITTED: dict[type[BaseModel], frozenset[str]] = {PublicSearchGenerationStateV1: frozenset({"projection"})}
"""Public search carries state only; its private identity is rebuilt in the reader process."""
_WITHHELD: frozenset[tuple[type[object], str]] = frozenset({(WorkbenchGenerationV1, "search")})


def _require_restored_type[T](value: object, expected: type[T]) -> T:
    if not isinstance(value, expected):
        raise TypeError("workbench restored field changed type")
    return value


def _rebuild_search(canonical: type[object], restored: dict[str, object], public: BaseModel) -> None:
    """Rebuild search identity from the restored sibling projections, then check its public state."""
    if canonical is not WorkbenchGenerationV1:
        return
    if not isinstance(public, PublicWorkbenchGenerationV1):
        raise TypeError("workbench public generation changed")
    search = assemble_workbench_generation_search(
        ledger=_require_restored_type(
            restored["ledger"], WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1]
        ),
        declarations=_require_restored_type(
            restored["declarations"], WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1]
        ),
        aeat_sync=_require_restored_type(
            restored["aeat_sync"], WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1]
        ),
        modelo=_require_restored_type(
            restored["modelo"], WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]]
        ),
        ledger_admission=_require_restored_type(restored["ledger_admission"], WorkbenchDestinationAdmission),
        declarations_admission=_require_restored_type(
            restored["declarations_admission"], WorkbenchDestinationAdmission
        ),
        aeat_sync_admission=_require_restored_type(restored["aeat_sync_admission"], WorkbenchDestinationAdmission),
    )
    safe_search = public.search
    if (
        search.availability != safe_search.availability
        or search.observed_at != safe_search.observed_at
        or search.refusal != safe_search.refusal
    ):
        raise ValueError("workbench search state changed")
    restored["search"] = search


def _project(generation: WorkbenchGenerationV1) -> object:
    return project_public_mirror(generation, WorkbenchGenerationV1, PublicWorkbenchGenerationV1, omitted=_OMITTED)


def _restore(public: PublicWorkbenchGenerationV1) -> object:
    return restore_public_mirror(
        public, WorkbenchGenerationV1, PublicWorkbenchGenerationV1, withheld=_WITHHELD, complete=_rebuild_search
    )


def project_workbench_generation(
    profile_id: UUID, generation: WorkbenchGenerationV1
) -> WorkbenchGenerationOperationProjection:
    """Project the complete typed generation without retaining private search identity."""
    _require_reviewed_exclusions()
    public_generation = _project(generation)
    if not isinstance(public_generation, PublicWorkbenchGenerationV1):
        raise TypeError("workbench public projection failed")
    projection = WorkbenchGenerationOperationProjection(profile_id=profile_id, generation=public_generation)
    restored = _restore(public_generation)
    if not isinstance(restored, WorkbenchGenerationV1):
        raise TypeError("workbench canonical round-trip failed")
    if _project(restored) != public_generation:
        raise ValueError("workbench public projection changed canonical meaning")
    return projection


def restore_workbench_generation(projection: WorkbenchGenerationOperationProjection) -> WorkbenchGenerationV1:
    """Rebuild the canonical generation and local process-keyed search identities."""
    _require_reviewed_exclusions()
    _require_profile_binding(projection.profile_id, projection.generation)
    restored = _restore(projection.generation)
    if not isinstance(restored, WorkbenchGenerationV1):
        raise TypeError("workbench canonical restoration failed")
    if _project(restored) != projection.generation:
        raise ValueError("workbench public projection changed canonical meaning")
    return restored
