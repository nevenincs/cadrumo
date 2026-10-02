"""Exact-profile descendant reads and atomic runtime family replacement."""

from __future__ import annotations

from ....adapters.local_runtime.frontend_client import ProfileViewCollection, RuntimeFrontendClient
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....application.user_profile.descendant_rows import encode_descendant_rows
from ....application.user_profile.operations import (
    ProfileDescendantsOperationProjection,
    ProfileDescendantsOperationRequest,
)
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....core.errors.hierarchy import CadrumoError
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_list_from_facts
from ..errors import CliRefusedBoundaryError
from ._runtime_profile_mutation import execute_profile_mutation, read_mutation_baseline


def _decode(
    client: RuntimeFrontendClient, collection: ProfileViewCollection, operation: PinnedAuthorityOperation
) -> tuple[DescendantInfo, ...]:
    if collection.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    items = collection.items(ProfileViewPageKind.FACTS)
    facts = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
    if len(facts) != len(items):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return descendant_list_from_facts(facts, authority=operation)


def read_runtime_descendants(
    client: RuntimeFrontendClient, *, operation: PinnedAuthorityOperation, deadline: float
) -> tuple[ProfileViewCollection, tuple[DescendantInfo, ...]]:
    """Read one complete authorized revision and its canonical family rows."""
    baseline = read_mutation_baseline(client, deadline=deadline)
    return baseline, _decode(client, baseline, operation)


def replace_runtime_descendants(
    client: RuntimeFrontendClient,
    *,
    baseline: ProfileViewCollection,
    descendants: tuple[DescendantInfo, ...],
    operation: PinnedAuthorityOperation,
    deadline: float,
) -> tuple[DescendantInfo, ...]:
    """Publish once and expose only the verified committed revision's family.

    A readback or decoding refusal after settlement retains its operation ID;
    it cannot be mistaken for a write that never happened.
    """
    if baseline.profile_id != client.profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    completed, current = execute_profile_mutation(
        client,
        ProfileDescendantsOperationRequest(
            profile_id=client.profile_id,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
            descendants=encode_descendant_rows(descendants, authority=operation),
        ),
        deadline=deadline,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ProfileDescendantsOperationProjection):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        rows = _decode(client, current, operation)
        if projection.total != len(rows):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    except (CadrumoError, ValueError, TypeError) as error:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.mutation.committed_view_unavailable",
            context={
                "operation_id": str(completed.operation_id),
                "commit_state": "succeeded",
                "record_revision": completed.projection.record_revision,
                "read_state": "unavailable",
            },
        ) from error
    return rows
