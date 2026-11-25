"""Exact-profile household baseline: the stored facts and what the profile says about each group."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import remaining_budget
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.user_profile.family_rows import ProfileFamilyGroupState, ProfileViewFamilyGroupItem
from ....application.user_profile.view_operation import ProfileViewPageKind

if TYPE_CHECKING:
    from cadrumo_client.transport.frontend_client import FrontendClient
    from cadrumo_client.transport.frontend_client_contracts import ProfileViewCollection

_NONE_FLAG = "--none"
_BASELINE_PAGES = (ProfileViewPageKind.FACTS, ProfileViewPageKind.FAMILY_ROWS)


def read_household_baseline(client: FrontendClient, *, deadline: float) -> ProfileViewCollection:
    """Capture the facts and the served household groups of one exact revision, with its CAS pair."""
    try:
        return client.read_profile_view(_BASELINE_PAGES, timeout=remaining_budget(deadline))
    except FrontendRefusedError as error:
        raise CliRefusedBoundaryError(error.reason, context=error.context) from error


def household_group(collection: ProfileViewCollection, *, group_key: str) -> ProfileViewFamilyGroupItem:
    """Return the group the backend serves for ``group_key``: rows, none declared, incomplete or unknown."""
    for item in collection.items(ProfileViewPageKind.FAMILY_ROWS):
        if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == group_key:
            return item
    raise RefusalError(RefusalCode.INVALID_FRAME)


def require_rows_or_none(*, flag: str, supplied: int, none: bool) -> None:
    """Refuse a request that neither names a row nor states none, or that does both."""
    if none and supplied:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.household.none_conflicts_with_rows",
            context={"flag": flag, "none": _NONE_FLAG},
        )
    if not none and not supplied:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.household.rows_or_none_required",
            context={"flag": flag, "none": _NONE_FLAG},
        )


def require_group_open_to_none(group: ProfileViewFamilyGroupItem) -> None:
    """Refuse to state that a household has none while the profile stores rows or states a count.

    A stored person is removed by naming them; a stated count that outruns the rows is an
    incomplete answer the operator resolves explicitly. Only an unanswered group, or one that
    already states none, can be answered with none.
    """
    if group.state not in (ProfileFamilyGroupState.UNKNOWN, ProfileFamilyGroupState.NONE_DECLARED):
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.household.none_with_stored_rows",
            context={
                "state": group.state.value,
                "rows": str(group.row_count),
                "stated_count": group.stated_count or "-",
            },
        )


__all__ = ["household_group", "read_household_baseline", "require_group_open_to_none", "require_rows_or_none"]
