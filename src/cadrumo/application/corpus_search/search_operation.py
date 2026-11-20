"""Registered no-effect read of the bundled reference corpus.

`reference.corpus.search` answers one query from the corpus and terminology
handbook that ship with the product: ranked passages, or the verbatim evidence
of an exact citation under the publication pin the operation holds, with the
approved terminology concepts the query names. It reads no profile data and
contacts no network. Its result is orientation from bundled sources, not
verified current law.

The read is addressed to the signed-in profile only because every registered
operation is. It is ephemeral: the worker keeps it in memory and never
journals the query.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.external_constants import OutputLanguage
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
)
from ..operations.capabilities import EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .models import RetrievalResponse
from .reference_search import search_reference_corpus
from .terminology import TerminologyHit

REFERENCE_CORPUS_SEARCH_DEFINITION_ID: Final = "reference.corpus.search"

REFERENCE_CORPUS_QUERY_MAX_LENGTH: Final = 200
REFERENCE_CORPUS_LIMIT_DEFAULT: Final = 8
REFERENCE_CORPUS_LIMIT_MAX: Final = 25

type _Query = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REFERENCE_CORPUS_QUERY_MAX_LENGTH)
]


class ReferenceCorpusSearchRequest(CredentialFreeOperationRequest):
    """Search the bundled reference corpus for free text or one exact citation id."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    query: _Query
    output_language: OutputLanguage
    limit: Annotated[int, Field(ge=1, le=REFERENCE_CORPUS_LIMIT_MAX)] = REFERENCE_CORPUS_LIMIT_DEFAULT


class ReferenceCorpusSearchResult(BaseModel):
    """What the bundled sources answer, bound to the profile and publication it was read under."""

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    output_language: OutputLanguage
    authority_generation: ContentDigest
    retrieval: RetrievalResponse
    terminology: tuple[TerminologyHit, ...]


class ReferenceCorpusSearchExecutor:
    """Search the bundled corpus once, under the operation's own publication pin."""

    async def execute(
        self, request: OperationRequest[ReferenceCorpusSearchRequest], context: OperationExecutorContext
    ) -> str:
        """Store the answer as one no-effect result."""
        payload = request.payload
        if request.definition_id != REFERENCE_CORPUS_SEARCH_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(REFERENCE_CORPUS_SEARCH_DEFINITION_ID)
        operation = context.authority_operation

        def read() -> ReferenceCorpusSearchResult:
            found = search_reference_corpus(
                payload.query, limit=payload.limit, operation=operation, language=payload.output_language
            )
            return ReferenceCorpusSearchResult(
                profile_id=payload.profile_id,
                output_language=payload.output_language,
                authority_generation=operation.generation.logical_generation,
                retrieval=found.retrieval,
                terminology=found.terminology,
            )

        return await capture_read_result(context, read, task_name="reference-corpus-search")


def build_reference_corpus_search_definition() -> OperationDefinition:
    """Declare the no-effect, no-network, exact-profile corpus search."""
    return build_single_phase_definition(
        definition_id=REFERENCE_CORPUS_SEARCH_DEFINITION_ID,
        request_type=ReferenceCorpusSearchRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=ReferenceCorpusSearchResult,
        executor_type=ReferenceCorpusSearchExecutor,
        build=ReferenceCorpusSearchExecutor,
        capabilities=EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES,
    )


def resolve_reference_corpus_search_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit the signed-in profile's own period-independent read, with no tax-period scope."""
    require_access_request_profile_payload(
        request,
        definition_id=REFERENCE_CORPUS_SEARCH_DEFINITION_ID,
        payload_type=ReferenceCorpusSearchRequest,
        access_profile_id=context.profile_id,
    )
    return bind_replayed_period_independent_access(
        context,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        definition_id=REFERENCE_CORPUS_SEARCH_DEFINITION_ID,
    )


def build_reference_corpus_search_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the request and result schemas to the profile-bound read access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ReferenceCorpusSearchResult,
        access_resolver=resolve_reference_corpus_search_access,
    )


__all__ = [
    "REFERENCE_CORPUS_LIMIT_DEFAULT",
    "REFERENCE_CORPUS_LIMIT_MAX",
    "REFERENCE_CORPUS_QUERY_MAX_LENGTH",
    "REFERENCE_CORPUS_SEARCH_DEFINITION_ID",
    "ReferenceCorpusSearchExecutor",
    "ReferenceCorpusSearchRequest",
    "ReferenceCorpusSearchResult",
    "build_reference_corpus_search_definition",
    "build_reference_corpus_search_registration",
    "resolve_reference_corpus_search_access",
]
