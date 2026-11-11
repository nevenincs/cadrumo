"""Shared mechanics of the property and lease doors under ``config profile``.

Both records are repeatable profile sections, so a door reads the complete facts
view once, judges the row it is about to write against the rest of the profile,
and submits one registered row operation bound to the exact revision and content
digest it read. A profile that moved in between refuses the write.

A door only parses: the registered row operation admits the row and stores its
canonical form, the same for the generic row command and for these doors, and the
door reports the row the settled view states.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ....application.user_profile.profile_operation_contracts import (
    ProfileRepeatableRowChangeOperationProjection,
    ProfileRepeatableRowMutationOperationProjection,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
    ProfileRepeatableRowValue,
)
from ....application.user_profile.section_rows import validate_profile_repeatable_row_fields
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....domain.contribuyente.inmueble_facts import rows_from_facts
from ....domain.user_profile.errors import UserProfileValidationError
from ..state_projection_support import authority_operation
from .profile_mutation import execute_profile_mutation, mutation_deadline, read_mutation_baseline
from .profile_row_commands import parse_values
from .profile_support import require_active_profile_pointer

if TYPE_CHECKING:
    import typer

    from cadrumo_client.transport.frontend_client import FrontendClient
    from cadrumo_client.transport.frontend_client_contracts import ProfileViewCollection

    from ....application.workflow.profile_bucket_models import ProfileBucketPointer
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation

_ROW_NOT_FOUND_LOCALE_KEY = "application.user_profile.errors.row_not_found"


@dataclass(frozen=True, slots=True)
class RentalDoorState:
    """The exact profile revision a door read, with the connection that will write against it."""

    pointer: ProfileBucketPointer
    client: FrontendClient
    deadline: float
    baseline: ProfileViewCollection
    path_values: dict[str, str]
    authority: PinnedAuthorityOperation


def facts_of(collection: ProfileViewCollection) -> dict[str, str]:
    """Return the facts of one complete view as ``path -> value``."""
    items = collection.items(ProfileViewPageKind.FACTS)
    facts = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
    if len(facts) != len(items):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return facts


def open_rental_door(ctx: typer.Context) -> RentalDoorState:
    """Bind the active profile, read its complete facts and pin the command's authority."""
    pointer = require_active_profile_pointer()
    authority = authority_operation(ctx)
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    deadline = mutation_deadline()
    baseline = read_mutation_baseline(client, deadline=deadline)
    if baseline.profile_id != client.profile_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return RentalDoorState(pointer, client, deadline, baseline, facts_of(baseline), authority)


def checked_values(
    state: RentalDoorState, section: str, tokens: list[str] | None, clears: tuple[str, ...] = ()
) -> dict[str, str]:
    """Parse ``LEAF=VALUE`` tokens and refuse a leaf the section does not declare."""
    values = parse_values(tokens or [])
    validate_profile_repeatable_row_fields(
        state.authority.profile_decode_context().schema.section(section), values=values, clear_fields=clears
    )
    return values


def stored_rows(state: RentalDoorState, section: str) -> dict[int, dict[str, str]]:
    """Return the rows the profile states for ``section``, keyed by row position."""
    return rows_from_facts(section, state.path_values)


def require_row(section: str, row: int, rows: dict[int, dict[str, str]]) -> dict[str, str]:
    """Return the stated facts of ``row`` or refuse naming the section."""
    if row not in rows:
        raise UserProfileValidationError(
            translated_message=_ROW_NOT_FOUND_LOCALE_KEY, context={"section": section, "row": str(row)}
        )
    return rows[row]


def count_after(section: str, current: ProfileViewCollection) -> int:
    """Count the rows a settled view states for ``section``."""
    return len(rows_from_facts(section, facts_of(current)))


def settled_row(section: str, row: int, current: ProfileViewCollection) -> dict[str, str]:
    """Return the facts the settled view states for row: the stored form the operation admitted."""
    return require_row(section, row, rows_from_facts(section, facts_of(current)))


def submit_add(state: RentalDoorState, section: str, stored: dict[str, str]) -> tuple[int, ProfileViewCollection]:
    """Add one row; return its stable position and the settled view."""
    completed, current = execute_profile_mutation(
        state.client,
        ProfileRepeatableRowMutationOperationRequest(
            profile_id=state.client.profile_id,
            expected_revision=state.baseline.record_revision,
            expected_content_digest=state.baseline.content_digest,
            section_key=section,
            values=tuple(ProfileRepeatableRowValue(field_key=leaf, value=value) for leaf, value in stored.items()),
        ),
        deadline=state.deadline,
    )
    outcome = completed.projection
    if not isinstance(outcome, ProfileRepeatableRowMutationOperationProjection):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return outcome.row_index, current


def submit_edit(
    state: RentalDoorState, section: str, row: int, before: dict[str, str], after: dict[str, str]
) -> tuple[bool, ProfileViewCollection]:
    """Replace the leaves that differ and clear the leaves the new row no longer states."""
    changed = {leaf: value for leaf, value in after.items() if before.get(leaf) != value}
    cleared = tuple(leaf for leaf in before if leaf not in after)
    if not changed and not cleared:
        return False, state.baseline
    completed, current = execute_profile_mutation(
        state.client,
        ProfileRepeatableRowUpdateOperationRequest(
            profile_id=state.client.profile_id,
            expected_revision=state.baseline.record_revision,
            expected_content_digest=state.baseline.content_digest,
            section_key=section,
            row_key=str(row),
            values=tuple(ProfileRepeatableRowValue(field_key=leaf, value=value) for leaf, value in changed.items()),
            clear_fields=cleared,
        ),
        deadline=state.deadline,
    )
    outcome = completed.projection
    if not isinstance(outcome, ProfileRepeatableRowChangeOperationProjection):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return outcome.changed, current


def submit_remove(state: RentalDoorState, section: str, row: int) -> ProfileViewCollection:
    """Remove one row by position and return the settled view."""
    _completed, current = execute_profile_mutation(
        state.client,
        ProfileRepeatableRowRemoveOperationRequest(
            profile_id=state.client.profile_id,
            expected_revision=state.baseline.record_revision,
            expected_content_digest=state.baseline.content_digest,
            section_key=section,
            row_key=str(row),
        ),
        deadline=state.deadline,
    )
    return current


def merged_row(before: dict[str, str], values: dict[str, str], clears: tuple[str, ...]) -> dict[str, str]:
    """Apply an edit's replacements and clears to the stated facts of a row."""
    merged = {**before, **values}
    for leaf in clears:
        merged.pop(leaf, None)
    return merged


def distinct_clears(clear: list[str] | None) -> tuple[str, ...]:
    """Refuse a leaf cleared twice before anything is read."""
    clears = tuple(clear or ())
    if len(set(clears)) != len(clears):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.add_row.duplicate_field")
    return clears


__all__ = [
    "RentalDoorState",
    "checked_values",
    "count_after",
    "distinct_clears",
    "facts_of",
    "merged_row",
    "open_rental_door",
    "require_row",
    "settled_row",
    "stored_rows",
    "submit_add",
    "submit_edit",
    "submit_remove",
]
