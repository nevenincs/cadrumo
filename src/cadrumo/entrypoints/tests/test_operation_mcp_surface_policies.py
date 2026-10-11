"""Every operation the read-only local surface lists is admitted on it by its own resolved policy.

The surface refuses a submission whose policy holds the commit action, and a
connection on it holds none. The surface census beside this file judges that
rule with a synthetic policy, so it cannot see a listed read whose real access
resolver resolves the commit action: such a read would be advertised and then
refused at submission. Here each listed operation is put to its real resolver
through the production registry, with a request its own decoder accepts, and
the policy it resolves is held to carry no commit action and to be admitted on
the surface.

A request is first built from the operation's registered schema alone, exactly
as the census of recorded MCP decisions probes resolvers. An operation whose
resolver needs stored records, or whose request model checks rules a schema
does not carry, is resolved instead from the request its executor's conformance
scenario seeds into a real profile, as the subject-binding census does.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...application.operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    resolve_operation_access,
    with_commit_action,
)
from ...application.operations.mcp_surfaces import MCP_SURFACES, McpSurfaceName
from ...application.operations.models import OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.user_profile.access_contracts import AccessAction, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.errors.hierarchy import CadrumoError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .test_operation_mcp_admission import _PROBE_PROFILE, _probe_requests
from .test_operation_mcp_surfaces import (
    _ALLOWED,
    _CLIENT,
    _FRONTEND_DENIED,
    _registry,
    answer_for_resolved_access,
)
from .test_registered_executor_conformance import (
    _CloseWitness,
    _model_runtime_for,
    _runtime,
    _seeded_conformance_submission,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_READ_ONLY_LOCAL = McpSurfaceName.READ_ONLY_LOCAL
_NOT_RESOLVED = (ProfileAccessRefusedError, CadrumoError, ValueError, LookupError)


def _listed() -> tuple[str, ...]:
    operations = MCP_SURFACES[_READ_ONLY_LOCAL].operations
    assert operations
    return tuple(sorted(operations))


def _submission_context(
    registry: OperationRegistry, definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=_CLIENT,
        action=AccessAction.SUBMIT,
        frontend=_MCP,
        contract=registry.lookup_public_contract(definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )


def _resolve_submission(
    registry: OperationRegistry,
    request: OperationRequest[BaseModel],
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
) -> ResolvedOperationAccess | None:
    """Ask the operation's registered resolver about a fresh MCP submission; ``None`` when it does not resolve."""
    context = _submission_context(registry, request.definition_id, profile_id=profile_id, operation=operation)
    try:
        return resolve_operation_access(registry=registry, request=request, context=context)
    except _NOT_RESOLVED:
        return None


def _schema_resolutions(
    registry: OperationRegistry, definition_id: str, *, operation: PinnedAuthorityOperation
) -> list[ResolvedOperationAccess]:
    """Every access the resolver produces for a request built from the registered schema alone."""
    resolutions = (
        _resolve_submission(registry, request, profile_id=_PROBE_PROFILE, operation=operation)
        for request in _probe_requests(definition_id)
    )
    return [resolved for resolved in resolutions if resolved is not None]


def _assert_read_policy_is_admitted_on_the_surface(
    registry: OperationRegistry, definition_id: str, resolved: ResolvedOperationAccess
) -> None:
    where = f"{definition_id} resolves {sorted(action.value for action in resolved.policy.actions)}"
    assert resolved.request.action is AccessAction.SUBMIT, where
    assert AccessAction.COMMIT not in resolved.policy.actions, f"{where}: a listed read holds the commit action"
    assert not resolved.policy.requires_human, f"{where}: a listed read is reserved for a person"
    # The same access, without a surface, says whether anything else refuses it.
    assert answer_for_resolved_access(resolved, None, registry=registry) == _ALLOWED, where
    assert answer_for_resolved_access(resolved, _READ_ONLY_LOCAL, registry=registry) == _ALLOWED, where


def _assert_the_surface_would_catch_a_commit(
    registry: OperationRegistry, definition_id: str, resolved: ResolvedOperationAccess
) -> None:
    """A policy that did hold the commit action is refused on the surface, so the assertion above has teeth."""
    committing = with_commit_action(resolved)
    assert AccessAction.COMMIT in committing.policy.actions
    assert answer_for_resolved_access(committing, None, registry=registry) == _ALLOWED, definition_id
    refused = answer_for_resolved_access(committing, _READ_ONLY_LOCAL, registry=registry)
    assert refused == _FRONTEND_DENIED, definition_id


@pytest.mark.parametrize("definition_id", _listed())
def test_the_real_resolver_of_every_read_only_local_operation_holds_no_commit_and_is_admitted_on_the_surface(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """Each listed operation is judged on a request its own resolver resolves, whichever way one is built."""
    schema_registry = _registry()
    resolutions = _schema_resolutions(schema_registry, definition_id, operation=operation)
    for resolved in resolutions:
        _assert_read_policy_is_admitted_on_the_surface(schema_registry, definition_id, resolved)
    if resolutions:
        _assert_the_surface_would_catch_a_commit(schema_registry, definition_id, resolutions[0])
        return

    with (
        _model_runtime_for(definition_id),
        _runtime(tmp_path / definition_id, cleanup=_CloseWitness()) as (_driver, registry, profile_id),
    ):
        definition = registry.lookup(definition_id)
        submission = _seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        request = OperationRequest[BaseModel](
            definition_id=definition_id, subject_ref=submission.subject_ref, payload=submission.registered_payload
        )
        resolved = _resolve_submission(registry, request, profile_id=profile_id, operation=operation)
        assert resolved is not None, f"{definition_id} does not resolve the request its own scenario seeds"
        _assert_read_policy_is_admitted_on_the_surface(registry, definition_id, resolved)
        _assert_the_surface_would_catch_a_commit(registry, definition_id, resolved)
