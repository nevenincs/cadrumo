"""List and rank the registered operations an admitted session may use, a page at a time.

The session is shown the operations its scope and its surface keep, read from
the runtime. The person's own acts are never among them.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .operation_contract_cache import OperationContractCache
from .operation_search import rank_operations
from .protocol_contract import SEARCH_PAGE_DEFAULT, refusal_code
from .runtime_admission import McpAdmission, require_exact_admitted_status
from .surfaces import McpSurface

# An operation outside the connection's surface or the session's scope is simply not offered, and
# neither is a person's own act, which the runtime describes to no agent.
_NOT_OFFERED = frozenset(
    {
        AccessDenialCode.FRONTEND_DENIED.value,
        AccessDenialCode.OPERATION_DENIED.value,
        AccessDenialCode.PERSON_ACT_REQUIRED.value,
    }
)
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
        RefusalCode.INVALID_FRAME.value,
    }
)
# Reading one contract is one exchange with the runtime, and an exchange cut short
# by its deadline closes the connection and the session it holds. A search's own
# budget is therefore checked between reads, and each read is bounded by itself.
_CONTRACT_READ_SECONDS = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS


def search_operations(
    client: FrontendClient,
    contracts: OperationContractCache,
    profile_id: UUID,
    args: dict[str, Any],
    deadline: float,
    surface: McpSurface,
    *,
    admission: McpAdmission,
) -> dict[str, Any]:
    """Return one page of the operations this exact session may describe on its surface.

    Without a query the page follows definition ID order and only the page's own
    contracts are read. With a query every contract in scope is needed to rank,
    so the ranked list is paged by position. Leaving an operation out here only
    spares a call the runtime refuses; the runtime holds the connection to its
    surface.
    """
    status = require_exact_admitted_status(client, profile_id=profile_id, admission=admission)
    family = args.get("family", "").strip()
    # An act known to be the person's by its id is not even asked about; one known only by its
    # contract's secret is refused at its description and left out there.
    granted = sorted(
        item
        for item in status.effective_scope.operations
        if surface.admits(item) and not operation_is_persons_act(item, ephemeral_secret_required=False)
    )
    scope = [definition_id for definition_id in granted if _in_family(definition_id, family)]
    limit = args.get("limit", SEARCH_PAGE_DEFAULT)
    cursor = args.get("cursor")
    if args.get("query", "").strip():
        return _ranked_page(client, contracts, scope, args["query"], cursor, limit, deadline)
    return _listed_page(client, contracts, scope, cursor, limit, deadline)


def _in_family(definition_id: str, family: str) -> bool:
    return not family or definition_id == family or definition_id.startswith(f"{family}.")


def _listed_page(
    client: FrontendClient,
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
        description = _described(client, contracts, definition_id, unavailable)
        examined += 1
        if description is not None:
            rows.append(description)
    page = _found(rows, unavailable)
    if examined < len(pending):
        page["next_cursor"] = pending[examined - 1]
    return page


def _ranked_page(
    client: FrontendClient,
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
            raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
        description = _described(client, contracts, definition_id, unavailable)
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
    client: FrontendClient,
    contracts: OperationContractCache,
    definition_id: str,
    unavailable: list[dict[str, str]],
) -> OperationPublicDefinitionDescriptionV1 | None:
    try:
        return contracts.description(client, definition_id, deadline=time.monotonic() + _CONTRACT_READ_SECONDS)
    except (FrontendRefusedError, RefusalError) as error:
        code = refusal_code(error)
        if code in _NOT_OFFERED:
            return None
        if code in _UNAVAILABLE_OPERATION:
            unavailable.append({"definition_id": definition_id, "code": code})
            return None
        raise


def operation_summary(description: OperationPublicDefinitionDescriptionV1) -> dict[str, Any]:
    """Summarize one operation as a search row: what it is, and the facts that tell it from its neighbours.

    A row is small so that a page of them is cheap to read. The members that
    carry a contract's own value keep the contract's name for it. The whole
    contract and the request schema are what ``describe`` returns.
    """
    contract = description.contract
    row: dict[str, Any] = {"definition_id": contract.definition_id}
    purpose = _first_paragraph(description.request_json_schema.get("description"))
    if purpose:
        row["description"] = purpose
    row["subject_kind"] = contract.subject_reference.kind.value
    row["permitted_effects"] = sorted(effect.value for effect in contract.permitted_effects)
    row["interaction_kinds"] = sorted(kind.value for kind in contract.interaction_kinds)
    row["ephemeral_secret_required"] = contract.ephemeral_secret_required
    return row


def _first_paragraph(text: object) -> str:
    """Return the opening paragraph of a request's own description as one line, or nothing where it has none."""
    if not isinstance(text, str):
        return ""
    return " ".join(text.strip().split("\n\n", 1)[0].split())


def _found(
    descriptions: Sequence[OperationPublicDefinitionDescriptionV1], unavailable: list[dict[str, str]]
) -> dict[str, Any]:
    page: dict[str, Any] = {
        "outcome": "found",
        "operations": [operation_summary(description) for description in descriptions],
    }
    if unavailable:
        page["unavailable"] = unavailable
    return page
