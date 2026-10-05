"""Focused row visibility and creation notices for the filing portfolio."""

from __future__ import annotations

from rich.text import Text
from textual.geometry import Region

from ....application.modelo.declaration_targets import DeclarationTarget
from ....core.i18n.render import tr
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import natural_address
from .models import ModeloWorkCreateResultV1


def reveal_portfolio_row(table: ContentDataTable[Text | str], page: ContentScroll) -> None:
    """Reveal the same highlighted row within its outer content scroll."""
    index = table.cursor_row
    rows = table.ordered_rows
    header = table.header_height if table.show_header else 0
    top = table.virtual_region.y + header + sum(row.height for row in rows[:index])
    page.scroll_to_region(
        Region(table.virtual_region.x, top, table.size.width, rows[index].height),
        animate=False,
        x_axis=False,
    )


def creation_notice(result: ModeloWorkCreateResultV1, target: DeclarationTarget, advisories: tuple[str, ...]) -> str:
    """Keep persisted creation status and all brought-forward obligations visible."""
    return "\n".join(
        (
            tr(
                "tui.declarations.work_create.reused" if result.reused else "tui.declarations.work_create.created",
                address=natural_address(target.modelo, target.period.filing_year, target.period),
            ),
            *advisories,
        )
    )
