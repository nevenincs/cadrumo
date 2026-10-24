"""Recorded, exact-profile read of the declarations list, every row said in the filer's language.

``modelo.declarations.list`` joins the profile's local declarations with the
legal calendar inside the profile worker and returns the rows every frontend
lists, each with its state, group, next step and the AEAT's facts kept apart
from its own. It writes nothing and settles with no effect.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..operations.access_resolution import (
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .declarations_list import DeclarationListInputs, ModeloDeclarationListRowV1, worded_declaration_list

MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID = "modelo.declarations.list"

type DeclarationListReaderFactory = Callable[[str, PinnedAuthorityOperation], Callable[[], DeclarationListInputs]]
"""Bind the list's capture to one profile and the pinned authority of the read."""


class ModeloDeclarationsListRequest(CredentialFreeOperationRequest):
    """The exact profile and the language its rows are said in."""

    profile_id: UUID
    output_language: OutputLanguage


class ModeloDeclarationsListProjectionV1(BaseModel):
    """Every row of one profile's declarations list, in the order every frontend lists them."""

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    output_language: OutputLanguage
    rows: tuple[ModeloDeclarationListRowV1, ...]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _each_row_once(self) -> Self:
        if len({row.key for row in self.rows}) != len(self.rows):
            raise ValueError("the declarations list repeats a row")
        return self


class ModeloDeclarationsListExecutor:
    """Capture the list under the pinned authority inside profile custody."""

    def __init__(self, reader_factory: DeclarationListReaderFactory) -> None:
        """Retain the composition-owned exact-profile capture."""
        self._reader_factory = reader_factory

    async def execute(
        self, request: OperationRequest[ModeloDeclarationsListRequest], context: OperationExecutorContext
    ) -> str:
        """Store one encrypted list without writing domain state."""
        payload = request.payload
        if request.definition_id != MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID)
        operation = context.authority_operation

        def read() -> ModeloDeclarationsListProjectionV1:
            with validating_governed_facts(operation):
                inputs = self._reader_factory(str(payload.profile_id), operation)()
                if inputs.workspace is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                rows = worded_declaration_list(inputs.workspace, inputs.calendar, payload.output_language)
            return ModeloDeclarationsListProjectionV1(
                result_version=1, profile_id=payload.profile_id, output_language=payload.output_language, rows=rows
            )

        return await capture_read_result(context, read, task_name="modelo-declarations-list")


def build_modelo_declarations_list_definition(reader_factory: DeclarationListReaderFactory) -> OperationDefinition:
    """Declare one credential-free request with an encrypted result."""
    return build_single_phase_definition(
        definition_id=MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID,
        request_type=ModeloDeclarationsListRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=ModeloDeclarationsListProjectionV1,
        executor_type=ModeloDeclarationsListExecutor,
        build=lambda: ModeloDeclarationsListExecutor(reader_factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def build_modelo_declarations_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require unrestricted whole-profile consent: the list names every period's declarations."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        require_access_request_profile_payload(
            request,
            definition_id=definition.definition_id,
            payload_type=ModeloDeclarationsListRequest,
            access_profile_id=context.profile_id,
        )
        return bind_replayed_period_independent_access(
            context, LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS, definition_id=request.definition_id
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloDeclarationsListProjectionV1,
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID",
    "DeclarationListReaderFactory",
    "ModeloDeclarationsListExecutor",
    "ModeloDeclarationsListProjectionV1",
    "ModeloDeclarationsListRequest",
    "build_modelo_declarations_list_definition",
    "build_modelo_declarations_list_registration",
]
