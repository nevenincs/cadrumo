"""The view link of the one record an operation's settled result names.

A result that names exactly one record a view can select, such as the
transaction ``ledger.add`` created or the invoice ``ledger.invoice.add``
created, is answered with the link that opens that record, spelled by the
client contract's one link formatter. The agent copies the link instead of
composing one. Results that name several records, or none a view selects,
carry no link.

Results are named by their registered result schema id, which every result
read carries, so an inline completion and a later ``result`` call answer
the same link.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from cadrumo_client.contracts.navigation import view_link

_SELECT: Final = "select"


@dataclass(frozen=True, slots=True)
class RecordView:
    """Where one result names its record, and the view that selects it."""

    view_id: str
    path: tuple[str, ...]
    """The keys from the result projection down to the record's id."""


_MOVEMENT: Final = "ledger/movements"
_INVOICE: Final = "ledger/invoices"

RECORD_VIEWS: Final[Mapping[str, RecordView]] = MappingProxyType(
    {
        "ledger.add.result": RecordView(_MOVEMENT, ("transaction", "transaction_id")),
        "ledger.update.result": RecordView(_MOVEMENT, ("transaction", "transaction_id")),
        "ledger.classify.single.result": RecordView(_MOVEMENT, ("transaction", "transaction_id")),
        "ledger.invoice.add.result": RecordView(_INVOICE, ("invoice", "invoice_id")),
        "ledger.invoice.update.result": RecordView(_INVOICE, ("invoice", "invoice_id")),
        "ledger.invoice.wizard.result": RecordView(_INVOICE, ("result", "invoice", "invoice_id")),
        "ledger.evidence.confirm.result": RecordView(_INVOICE, ("confirmation", "invoice", "invoice_id")),
    }
)
"""Per registered result schema id, the one record its projection names and the view that selects it."""


def record_link(result_schema_id: str, document: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the view link of the record a successful result names, or ``None`` when it names none.

    A result that did not succeed, or whose projection does not carry an id
    of the view's value kind at the declared place, has no link.
    """
    record = RECORD_VIEWS.get(result_schema_id)
    if record is None or document.get("outcome") != "success":
        return None
    value: Any = document.get("projection")
    for key in record.path:
        value = value.get(key) if isinstance(value, Mapping) else None
    if not isinstance(value, str):
        return None
    params = {_SELECT: value}
    try:
        link = view_link(record.view_id, params)
    except ValueError:
        return None
    return {"view": record.view_id, "params": params, "link": link}
