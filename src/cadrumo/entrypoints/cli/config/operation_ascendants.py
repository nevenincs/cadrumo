"""Exact-profile ascendant reads and atomic replacement over the bound profile connection."""

from __future__ import annotations

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import ProfileViewCollection

from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....application.user_profile.ascendant_rows import ProfileAscendantRow, ascendant_rows_from_facts
from ....application.user_profile.profile_operation_contracts import (
    ProfileAscendantsOperationProjection,
    ProfileAscendantsOperationRequest,
)
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....core.errors.hierarchy import CadrumoError
from .profile_mutation import execute_profile_mutation


def decode_ascendants(client: FrontendClient, collection: ProfileViewCollection) -> tuple[ProfileAscendantRow, ...]:
    """Read the stored ascendant rows out of one complete facts stream."""
    if collection.profile_id != client.profile_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    items = collection.items(ProfileViewPageKind.FACTS)
    facts = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
    if len(facts) != len(items):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return ascendant_rows_from_facts(facts)


def replace_ascendants(
    client: FrontendClient,
    *,
    baseline: ProfileViewCollection,
    ascendants: tuple[ProfileAscendantRow, ...],
    deadline: float,
) -> tuple[ProfileAscendantRow, ...]:
    """Publish once and expose only the verified committed revision's ascendants.

    A readback or decoding refusal after settlement retains its operation ID;
    it cannot be mistaken for a write that never happened.
    """
    if baseline.profile_id != client.profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    completed, current = execute_profile_mutation(
        client,
        ProfileAscendantsOperationRequest(
            profile_id=client.profile_id,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
            ascendants=ascendants,
        ),
        deadline=deadline,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ProfileAscendantsOperationProjection):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        rows = decode_ascendants(client, current)
        if projection.total != len(rows):
            raise RefusalError(RefusalCode.INVALID_FRAME)
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


__all__ = ["decode_ascendants", "replace_ascendants"]
