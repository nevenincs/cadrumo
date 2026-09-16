"""The collapsed technical-details group every Modelo workspace page ends with.

The pages lead with the operator's words. Producer attribution and raw
identifiers are still true and still wanted by whoever debugs a reading, so
they are kept -- folded away under one title, in one shape, on every page.
"""

from __future__ import annotations

from collections.abc import Iterable

from textual.widget import Widget

from .....core.i18n.render import tr
from ...components.widgets import ContentDataTable, DisclosureGroup
from .models import ModeloWorkspaceCapabilityRowV1, capability_label

type TechnicalDetailRowV1 = tuple[str, str, str]
"""One ``(row key, label, raw value)`` entry in a page's technical details."""


def mount_technical_details(body: Widget, rows: Iterable[TechnicalDetailRowV1], *, id: str) -> None:
    """Mount the collapsed group holding one page's raw identifiers at the end of ``body``."""
    table = ContentDataTable[str](id=id, cursor_type="row", zebra_stripes=True)
    body.mount(DisclosureGroup(table, title=tr("tui.modelo.technical_details"), collapsed=True))
    table.add_column(tr("tui.modelo.technical.column.field"), key="field")
    table.add_column(tr("tui.modelo.technical.column.value"), key="value")
    for key, label, value in rows:
        table.add_row(label, value, key=key)


def producer_row(row: ModeloWorkspaceCapabilityRowV1) -> TechnicalDetailRowV1:
    """Name the producer that answered one capability, under the capability's own name."""
    return (
        f"producer.{row.capability.value}",
        tr("tui.modelo.technical.producer_of", capability=capability_label(row.capability)),
        f"{row.producer_owner}.{row.producer}",
    )


__all__ = ["TechnicalDetailRowV1", "mount_technical_details", "producer_row"]
