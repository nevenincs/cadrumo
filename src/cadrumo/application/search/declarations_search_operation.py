"""Recorded, exact-profile search over a profile's declarations and works for the desktop palette.

``modelo.declarations.search`` reads the same declarations list every frontend
shows and looks a query up in the words that list says for each row: the
modelo's number and title, the period in the filer's language and the state.
It returns ranked hits, each with the words the window shows and the address
that opens it. Local work ranks before a declaration that is only due or held
by the AEAT. It writes nothing and settles with no effect.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..modelo.declarations_calendar import DeclarationsCalendarProjectionV1
from ..modelo.declarations_list import declaration_list_rows
from ..modelo.declarations_list_operation import DeclarationListReaderFactory
from ..modelo.declarations_list_projection import ModeloDeclarationListRowV1, worded_list_row
from ..modelo.declarations_workspace_contracts import DeclarationsWorkspaceProjectionV1
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
from .installed_workbench import (
    declaration_list_documents,
    searchable_declaration_rows,
)
from .workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
    WorkbenchModeloAddress,
    WorkbenchSearchRequest,
    WorkbenchSearchService,
)

MODELO_DECLARATIONS_SEARCH_OPERATION_DEFINITION_ID = "modelo.declarations.search"

_DESTINATION = "workbench.declarations"
_MAX_HITS = 100


class ModeloDeclarationsSearchHitKind(StrEnum):
    """Whether a hit is local work, or a declaration that is only due or held by the AEAT."""

    WORK = "work"
    DECLARATION = "declaration"


class ModeloDeclarationsSearchRequest(CredentialFreeOperationRequest):
    """The exact profile, the language the hits are said in, and what to look for."""

    profile_id: UUID
    output_language: OutputLanguage
    query: str
    limit: Annotated[int, Field(gt=0, le=_MAX_HITS)] = 20

    @field_validator("query")
    @classmethod
    @pydantic_validation_boundary
    def _query_has_searchable_words(cls, value: str) -> str:
        return WorkbenchSearchRequest(query=value).query


class ModeloDeclarationsSearchHitV1(BaseModel):
    """One match, said in the filer's language, with the address that opens it."""

    model_config = STRICT_FROZEN_CONFIG

    #: Zero-based position in the ranking.
    rank: NonNegativeInt
    score: float = Field(gt=0.0, allow_inf_nan=False)
    kind: ModeloDeclarationsSearchHitKind
    #: The declarations list row this hit is, which a form read or a start addresses.
    row_key: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=16)
    modelo_number: str
    #: The modelo's number and title: the words the hit is shown under.
    title_words: str
    filing_year: int
    period_code: str
    period_words: str | None = None
    state_words: str
    #: The local work a form read opens; ``None`` for a declaration with no local work.
    work_unit_id: str | None = None
    opens_local_work: bool = False


class ModeloDeclarationsSearchResultV1(BaseModel):
    """Ranked hits for one query, work before a declaration that has none."""

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    output_language: OutputLanguage
    hits: tuple[ModeloDeclarationsSearchHitV1, ...] = Field(default=(), max_length=_MAX_HITS)
    #: How many rows matched, which may exceed the hits returned.
    total_matches: NonNegativeInt = 0


def _hit(
    rank: int, score: float, row: ModeloDeclarationListRowV1, year: int, period_code: str
) -> ModeloDeclarationsSearchHitV1:
    return ModeloDeclarationsSearchHitV1(
        rank=rank,
        score=score,
        kind=(
            ModeloDeclarationsSearchHitKind.WORK
            if row.work_unit_id is not None
            else ModeloDeclarationsSearchHitKind.DECLARATION
        ),
        row_key=row.key,
        modelo=row.modelo,
        modelo_number=row.modelo_number,
        title_words=row.modelo_title,
        filing_year=year,
        period_code=period_code,
        period_words=row.period_words,
        state_words=row.state_words,
        work_unit_id=row.work_unit_id,
        opens_local_work=row.opens_local_work,
    )


def project_declarations_search(
    payload: ModeloDeclarationsSearchRequest,
    workspace: DeclarationsWorkspaceProjectionV1,
    calendar: DeclarationsCalendarProjectionV1,
) -> ModeloDeclarationsSearchResultV1:
    """Look the query up in one profile's worded declarations, ranked, in the language asked for."""
    language = payload.output_language
    worded = tuple(
        worded_list_row(row, language, workspace.filings) for row in declaration_list_rows(workspace, calendar)
    )
    rows = searchable_declaration_rows(worded)
    admission = WorkbenchDestinationAdmission(
        destination=_DESTINATION, state=WorkbenchDestinationAdmissionState.AVAILABLE
    )
    service = WorkbenchSearchService(declaration_list_documents(rows, admission))
    response = service.search(WorkbenchSearchRequest(query=payload.query, limit=payload.limit))
    hits: list[ModeloDeclarationsSearchHitV1] = []
    for result in response.results:
        address = result.address
        if not isinstance(address, WorkbenchModeloAddress):  # pragma: no cover - documents carry this address
            continue
        year, code = int(address.filing_year), str(address.period.code)
        row = rows[(str(address.modelo), year, code)]
        hits.append(_hit(result.rank, result.score, row, year, code))
    return ModeloDeclarationsSearchResultV1(
        result_version=1,
        profile_id=payload.profile_id,
        output_language=language,
        hits=tuple(hits),
        total_matches=response.total_matches,
    )


class ModeloDeclarationsSearchExecutor:
    """Capture the declarations under the pinned authority inside profile custody and search them."""

    def __init__(self, reader_factory: DeclarationListReaderFactory) -> None:
        """Retain the composition-owned exact-profile capture."""
        self._reader_factory = reader_factory

    async def execute(
        self, request: OperationRequest[ModeloDeclarationsSearchRequest], context: OperationExecutorContext
    ) -> str:
        """Store one encrypted result without writing domain state."""
        payload = request.payload
        if request.definition_id != MODELO_DECLARATIONS_SEARCH_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_DECLARATIONS_SEARCH_OPERATION_DEFINITION_ID)
        operation = context.authority_operation

        def read() -> ModeloDeclarationsSearchResultV1:
            with validating_governed_facts(operation):
                inputs = self._reader_factory(str(payload.profile_id), operation)()
                if inputs.workspace is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                return project_declarations_search(payload, inputs.workspace, inputs.calendar)

        return await capture_read_result(context, read, task_name="modelo-declarations-search")


def build_modelo_declarations_search_definition(reader_factory: DeclarationListReaderFactory) -> OperationDefinition:
    """Declare one credential-free request with an encrypted result."""
    return build_single_phase_definition(
        definition_id=MODELO_DECLARATIONS_SEARCH_OPERATION_DEFINITION_ID,
        request_type=ModeloDeclarationsSearchRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=ModeloDeclarationsSearchResultV1,
        executor_type=ModeloDeclarationsSearchExecutor,
        build=lambda: ModeloDeclarationsSearchExecutor(reader_factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def build_modelo_declarations_search_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require unrestricted whole-profile consent: a search can name every period's declarations."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        require_access_request_profile_payload(
            request,
            definition_id=definition.definition_id,
            payload_type=ModeloDeclarationsSearchRequest,
            access_profile_id=context.profile_id,
        )
        return bind_replayed_period_independent_access(
            context, LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS, definition_id=request.definition_id
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloDeclarationsSearchResultV1,
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_DECLARATIONS_SEARCH_OPERATION_DEFINITION_ID",
    "ModeloDeclarationsSearchExecutor",
    "ModeloDeclarationsSearchHitKind",
    "ModeloDeclarationsSearchHitV1",
    "ModeloDeclarationsSearchRequest",
    "ModeloDeclarationsSearchResultV1",
    "build_modelo_declarations_search_definition",
    "build_modelo_declarations_search_registration",
    "project_declarations_search",
]
