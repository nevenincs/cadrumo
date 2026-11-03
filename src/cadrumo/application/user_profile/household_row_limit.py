"""The most rows the declaration's own design lets one stored household group hold.

The profile stores a household as ``{object_path}.{n}.{leaf}`` facts. The registry
names the declaration and layout group that own the repeat limit of each such object.
The limit is read from that group at the last filing year the registry supports, so a
writer holds no number of its own, names no modelo and scans no other declaration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.profile_row_limits import repeating_group, row_limit_owners
from ...domain.calculations.registry.temporal import select_revision_metadata

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_ANNUAL_PERIOD: Final = "0A"


def declared_household_row_limit(operation: PinnedAuthorityOperation, *, object_path: str) -> int | None:
    """Return the design's repeat limit for ``object_path``, or ``None`` for an object the registry does not name.

    A named owner whose layout declares no such limit breaks the registry's own contract and refuses,
    since no row count could then be offered safely.
    """
    owner = row_limit_owners(authority=operation).get(object_path)
    if owner is None:
        return None
    revision = select_revision_metadata(
        operation.modelo_directory(owner.form),
        filing_year=operation.supported_filing_years().horizon,
        period=_ANNUAL_PERIOD,
    )
    layout = operation.form_layout(owner.form, revision.id)
    group = None if layout is None else repeating_group(layout, owner.group_id)
    if group is None or group.max_rows is None:
        raise RegistryValidationError(f"the owner of the {object_path!r} row limit declares no repeat limit for it")
    return group.max_rows


__all__ = ["declared_household_row_limit"]
