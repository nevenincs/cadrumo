"""Registered modelo work-lifecycle operations composed from existing writers.

Each definition here supervises a lifecycle writer that already exists; none
of them re-implements lifecycle policy. ``rename_work_unit`` already decides
what a rename means - that a discarded unit is immutable, that the
content-addressed id survives, that the catalogue and its lifecycle event
co-commit - and this module's only job is to run that decision under a
recorded operation identity.

That separation is the point. An enrolment that re-derived the rules would
give the supervised path different behaviour from the direct one, and the
lifecycle refusal an operator sees would depend on which door they came
through.

See Also:
    :func:`~cadrumo.application.modelo._work_lifecycle.rename_work_unit`
        The single writer this operation supervises.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ._work_lifecycle import rename_work_unit

if TYPE_CHECKING:
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext

MODELO_WORK_RENAME_OPERATION_DEFINITION_ID = "modelo.work.rename"

_WORK_UNIT_ID = Annotated[str, Field(min_length=1, max_length=128)]
_WORK_UNIT_NAME = Annotated[str, Field(min_length=1, max_length=200)]


class ModeloWorkRenameRequest(CredentialFreeOperationRequest):
    """The addressed unit and the display name to give it.

    Credential-free by construction: a rename names a unit and a label, so the
    request carries nothing that would be unsafe to journal.
    """

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: _WORK_UNIT_ID
    new_name: _WORK_UNIT_NAME


class ModeloWorkRenamePublicResultV1(BaseModel):
    """The settled rename, as a caller outside this package may see it.

    A distinct projection rather than the WorkUnit itself: the stored record
    carries lifecycle state a result consumer has no business depending on.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    work_unit_id: _WORK_UNIT_ID
    name: _WORK_UNIT_NAME
    bucket_id: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkRenameExecutor:
    """Run the existing rename writer under one recorded operation identity."""

    def __init__(self, *, actor: str) -> None:
        """Bind the actor whose rename event this operation will emit."""
        self._actor = actor

    async def execute(
        self,
        request: OperationRequest[ModeloWorkRenameRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the single writer and return the renamed unit's id.

        The writer owns the atomic write set - the work-unit catalogue and the
        bucket lifecycle event co-commit inside it - so nothing here opens a
        second write path around them.
        """
        del context
        renamed = rename_work_unit(
            request.payload.work_unit_id,
            request.payload.new_name,
            actor=self._actor,
        )
        return renamed.work_unit_id


def build_modelo_work_rename_definition(*, actor: str) -> OperationDefinition:
    """Bind the rename writer to its registered operation contract."""

    def build() -> ModeloWorkRenameExecutor:
        return ModeloWorkRenameExecutor(actor=actor)

    return OperationDefinition(
        definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRenameRequest,
        result_type=ModeloWorkRenamePublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkRenameRequest,
            executor_type=ModeloWorkRenameExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.rename",),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_rename_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the rename definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.rename.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.rename.result",
            schema_version=1,
            model_type=ModeloWorkRenamePublicResultV1,
        ),
    )


__all__ = [
    "MODELO_WORK_RENAME_OPERATION_DEFINITION_ID",
    "ModeloWorkRenameExecutor",
    "ModeloWorkRenamePublicResultV1",
    "ModeloWorkRenameRequest",
    "build_modelo_work_rename_definition",
    "build_modelo_work_rename_registration",
]
