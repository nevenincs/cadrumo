"""List and rank the registered operations one admitted session may use, a page at a time."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import AccessDenialCode

from .operation_contract_cache import OperationContractCache
from .operation_search import rank_operations
from .protocol_contract import SEARCH_PAGE_DEFAULT, public_value, refusal_code
from .runtime_admission import require_exact_admitted_status

# An operation outside the session's frontend or scope is simply not offered.
_NOT_OFFERED = frozenset({AccessDenialCode.FRONTEND_DENIED.value, AccessDenialCode.OPERATION_DENIED.value})
# These refusals concern one operation, so the others are still worth listing.
_UNAVAILABLE_OPERATION = frozenset(
    {
        AccessDenialCode.OPERATION_UNAVAILABLE.value,
        AccessDenialCode.BACKEND_UNAVAILABLE.value,
        AccessDenialCode.PROVIDER_REQUIRED.value,
        AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED.value,
        AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED.value,
        AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value,
        AccessDenialCode.FRESH_PASSWORD_REQUIRED.value,
        AccessDenialCode.ADMINISTRATION_DENIED.value,
        AccessDenialCode.DISCLOSURE_DENIED.value,
        AccessDenialCode.PERIOD_DENIED.value,
        RuntimeRefusalCode.INVALID_FRAME.value,
    }
)


def search_operations(
    client: RuntimeFrontendClient,
    contracts: OperationContractCache,
    profile_id: UUID,
    args: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    """Return one page of the operations this exact session may describe.

    Without a query the page follows definition ID order and only the page's own
    contracts are read. With a query every contract in scope is needed to rank,
    so the ranked list is paged by position.
    """
    status = require_exact_admitted_status(client, profile_id=profile_id)
    family = args.get("family", "").strip()
    granted = sorted(status.effective_scope.operations)
    scope = [definition_id for definition_id in granted if _in_family(definition_id, family)]
    limit = args.get("limit", SEARCH_PAGE_DEFAULT)
    cursor = args.get("cursor")
    if args.get("query", "").strip():
        return _ranked_page(client, contracts, scope, args["query"], cursor, limit, deadline)
    return _listed_page(client, contracts, scope, cursor, limit, deadline)


def _in_family(definition_id: str, family: str) -> bool:
    return not family or definition_id == family or definition_id.startswith(f"{family}.")


def _listed_page(
    client: RuntimeFrontendClient,
    contracts: OperationContractCache,
    scope: list[str],
    cursor: str | None,
    limit: int,
    deadline: float,
) -> dict[str, Any]:
    if cursor is not None and cursor.isdecimal():
        raise ValueError("cursor does not belong to an unranked listing")
    pending = [definition_id for definition_id in scope if cursor is None or definition_id > cursor]
    rows: list[OperationPublicDefinitionDescriptionV1] = []
    unavailable: list[dict[str, str]] = []
    examined = 0
    for definition_id in pending:
        # A late page ends early and resumes from the cache instead of failing.
        if len(rows) >= limit or (examined and time.monotonic() >= deadline):
            break
        description = _described(client, contracts, definition_id, deadline, unavailable)
        examined += 1
        if description is not None:
            rows.append(description)
    page = _found(rows, unavailable)
    if examined < len(pending):
        page["next_cursor"] = pending[examined - 1]
    return page


def _ranked_page(
    client: RuntimeFrontendClient,
    contracts: OperationContractCache,
    scope: list[str],
    query: str,
    cursor: str | None,
    limit: int,
    deadline: float,
) -> dict[str, Any]:
    offset = _offset(cursor)
    permitted: list[OperationPublicDefinitionDescriptionV1] = []
    unavailable: list[dict[str, str]] = []
    for definition_id in scope:
        # Contracts already read stay cached, so a retry resumes where this stopped.
        if time.monotonic() >= deadline:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        description = _described(client, contracts, definition_id, deadline, unavailable)
        if description is not None:
            permitted.append(description)
    ranked = rank_operations(query, permitted)
    page = _found(ranked[offset : offset + limit], unavailable)
    if offset + limit < len(ranked):
        page["next_cursor"] = str(offset + limit)
    return page


def _offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if not (cursor.isascii() and cursor.isdecimal()):
        raise ValueError("cursor does not belong to a ranked search")
    return int(cursor)


def _described(
    client: RuntimeFrontendClient,
    contracts: OperationContractCache,
    definition_id: str,
    deadline: float,
    unavailable: list[dict[str, str]],
) -> OperationPublicDefinitionDescriptionV1 | None:
    try:
        return contracts.description(client, definition_id, deadline=deadline)
    except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
        code = refusal_code(error)
        if code in _NOT_OFFERED:
            return None
        if code in _UNAVAILABLE_OPERATION:
            unavailable.append({"definition_id": definition_id, "code": code})
            return None
        raise


def _found(
    descriptions: Sequence[OperationPublicDefinitionDescriptionV1], unavailable: list[dict[str, str]]
) -> dict[str, Any]:
    page: dict[str, Any] = {
        "outcome": "found",
        "operations": [public_value(description.contract) for description in descriptions],
    }
    if unavailable:
        page["unavailable"] = unavailable
    return page
