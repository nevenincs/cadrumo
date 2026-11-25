"""The JSON document a projection serves, and the one result delivered in pages.

A projection reads an operation's settled result or its review; this module
names which, serializes the result once, and holds what later pages reuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from pydantic import BaseModel, JsonValue, TypeAdapter

from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationId, OperationStoredInvocation
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.projection_pages import EncodedProjectionDocument

if TYPE_CHECKING:
    from cadrumo.core.operations import OperationFrontendProjection

_PROJECTION_DOCUMENT = TypeAdapter(dict[str, JsonValue])
_PAGED_PROJECTION_DOCUMENT = TypeAdapter(dict[str, Any])


def projection_document(result: BaseModel, *, paged: bool) -> dict[str, JsonValue]:
    """Keep the full result shape and validate the paged document root once."""
    serialized = result.model_dump(mode="json", serialize_as_any=True)
    if paged:
        # Pydantic already serialized the full model; the page encoder checks
        # each value's JSON compatibility while producing canonical bytes.
        return cast("dict[str, JsonValue]", _PAGED_PROJECTION_DOCUMENT.validate_python(serialized))
    return _PROJECTION_DOCUMENT.validate_python(serialized)


def projection_target(
    request: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1,
) -> tuple[OperationId, AccessAction]:
    """Name the operation a projection reads and the disclosure it asks for."""
    if isinstance(request, OperationResultProjectionRequestV1):
        return request.operation_id, AccessAction.RESULT
    return request.reference.operation_id, AccessAction.REVIEW


@dataclass(frozen=True, slots=True)
class PagedDelivery:
    """The one result being delivered in pages, with what its later pages reuse.

    Its invocation and document are immutable once resolved. Reusing them spares
    no authority check: every page still takes the disclosure guard, and the
    settled result is still rechecked. Held for as long as the result snapshot.
    """

    operation_id: OperationId
    session_id: UUID
    frontend: OperationFrontendProjection
    invocation: OperationStoredInvocation
    result: BaseModel
    document: EncodedProjectionDocument
