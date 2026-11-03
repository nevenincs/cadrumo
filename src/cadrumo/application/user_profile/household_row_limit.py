"""The most rows the declaration's own design lets one stored household group hold.

The profile stores a household as ``{object_path}.{n}.{leaf}`` facts. A declaration
that reads such an object through a repeating profile binding opens one repeating
group over it, bounded by the repeat limit the design itself declares. The limit is
read from the layout of every declaration whose bindings read the object, at the
last filing year the registry supports, so a writer holds no number of its own and
names no modelo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...domain.calculations.registry.errors import NoRevisionForPeriodError
from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition, FormRepeatingGroupBlock

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ids import BindingId

_ANNUAL_PERIOD: Final = "0A"


def declared_household_row_limit(operation: PinnedAuthorityOperation, *, object_path: str) -> int | None:
    """Return the design's repeat limit for the group that reads ``object_path``, or ``None`` when it declares none.

    A declaration with no annual revision at the last supported year does not read the household.
    When several declarations read the object, the smallest limit holds, so no row is offered that one cannot carry.
    """
    horizon = operation.supported_filing_years().horizon
    limits: list[int] = []
    for modelo_id in operation.modelo_ids():
        try:
            revision = operation.revision_for_context(modelo_id, filing_year=horizon, period=_ANNUAL_PERIOD)
        except NoRevisionForPeriodError:
            continue
        reading = {
            binding.id
            for binding in revision.bindings
            if isinstance(binding.provider, ProfileProvider)
            and binding.provider.rows is not None
            and binding.provider.rows.object_path == object_path
        }
        if not reading:
            continue
        layout = operation.form_layout(modelo_id, revision.id)
        if layout is not None:
            limits.extend(_repeat_limits(layout, reading))
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
