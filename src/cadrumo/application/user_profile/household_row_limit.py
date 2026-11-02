"""The most rows the declaration's own design lets one stored household group hold.

The profile stores a household as ``{object_path}.{n}.{leaf}`` facts, and the
Modelo 100 layout opens one repeating group over each such object, bounded by the
repeat limit the design itself declares. The limit is read from that layout, at the
last filing year the registry supports, so a writer holds no number of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition, FormRepeatingGroupBlock

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ids import BindingId

_HOUSEHOLD_MODELO: Final = "100"
_ANNUAL_PERIOD: Final = "0A"


def declared_household_row_limit(operation: PinnedAuthorityOperation, *, object_path: str) -> int | None:
    """Return the design's repeat limit for the group that reads ``object_path``, or ``None`` when it declares none."""
    revision = operation.revision_for_context(
        _HOUSEHOLD_MODELO, filing_year=operation.supported_filing_years().horizon, period=_ANNUAL_PERIOD
    )
    layout = operation.form_layout(_HOUSEHOLD_MODELO, revision.id)
    if layout is None:
        return None
    reading = {
        binding.id
        for binding in revision.bindings
        if isinstance(binding.provider, ProfileProvider)
        and binding.provider.rows is not None
        and binding.provider.rows.object_path == object_path
    }
    limits = _repeat_limits(layout, reading)
    return min(limits) if limits else None


def _repeat_limits(layout: FormLayoutDefinition, reading: set[BindingId]) -> list[int]:
    return [
        block.max_rows
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock) and block.binding_id in reading and block.max_rows is not None
    ]


__all__ = ["declared_household_row_limit"]
