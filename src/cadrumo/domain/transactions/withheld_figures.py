"""Business figures a stored row holds although its classification refuses them, and their event trace."""

from __future__ import annotations

import weakref
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ...core.decimal.formatting import format_decimal
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ..buckets.event import BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH
from ..calculations.registry.facts.resolution import reading_dated_facts_below_support
from ..iva.schema import IvaCashAccountingTreatment, default_iva_cash_accounting_treatment
from .dates import transaction_operation_date
from .model_validation import figures_without_business, refusable_figures_of

if TYPE_CHECKING:
    from .models import Transaction


def withhold_figures_without_business(transaction: Transaction) -> Transaction:
    """Return ``transaction`` as a reader may see it: without business figures its classification refuses.

    A stored personal row written before the refusal existed can still carry a
    spending category, a taxable base or another business figure. Every reader
    sees those as absent, so no projection, calculation or export counts them,
    and the row's next write persists their absence. The stored bytes are not
    rewritten by reading. An unaffected row is returned as the same instance.

    The copy is not re-validated: the stored row already passed every other
    admission check, and absent figures are what any write of its
    classification would carry.
    """
    held = figures_held_without_business(transaction)
    if not held:
        return transaction
    absent: dict[str, object] = {name: None for name in held}
    if "cash_accounting_treatment" in held:
        absent["cash_accounting_treatment"] = _ordinary_treatment_on_row_date(transaction)
        absent["cash_accounting_payment_evidence"] = ()
    read = transaction.model_copy(update=absent)
    _remember_withheld_figures(read, held)
    return read


def figures_held_without_business(transaction: Transaction) -> Mapping[str, object]:
    """Return the business figures ``transaction`` holds although its classification refuses them.

    Empty for every row built or written since the refusal existed; a stored
    row decoded through :func:`~.models.validate_stored_transaction_json` can hold some.
    """
    figures = refusable_figures_of(transaction.business_classification, transaction)
    present = figures_without_business(transaction.business_classification, figures)
    held = {name: figures[name] for name in present}
    if figures and _keeps_cash_accounting_timing(transaction):
        # Criterio-de-caja timing settles a cuota the row's base and IVA carry; a row with
        # no business component has neither, so its timing goes with them.
        held["cash_accounting_treatment"] = transaction.cash_accounting_treatment
        held["cash_accounting_payment_evidence"] = transaction.cash_accounting_payment_evidence
    return MappingProxyType(held)


def _keeps_cash_accounting_timing(transaction: Transaction) -> bool:
    return bool(
        transaction.cash_accounting_payment_evidence
    ) or transaction.cash_accounting_treatment != _ordinary_treatment_on_row_date(transaction)


def _ordinary_treatment_on_row_date(transaction: Transaction) -> IvaCashAccountingTreatment:
    """Return the ordinary treatment in force on the row's date, as its own validation reads it."""
    with reading_dated_facts_below_support():
        return default_iva_cash_accounting_treatment(transaction_operation_date(transaction))


_WITHHELD_FIGURES: dict[int, Mapping[str, object]] = {}
"""The figures each read row had withheld, keyed by the identity of that read instance.

Identity, not content: only the instance a reader produced carries the fact
that its stored row held more, and an entry leaves with its instance. A write
that replaces the row asks :func:`withheld_figures` of the row it read, so its
own history can name what the write stops storing.
"""


def _remember_withheld_figures(read: Transaction, figures: Mapping[str, object]) -> None:
    key = id(read)
    weakref.finalize(read, _WITHHELD_FIGURES.pop, key, None)
    _WITHHELD_FIGURES[key] = MappingProxyType(dict(figures))


def withheld_figures(transaction: Transaction) -> Mapping[str, object]:
    """Return the business figures the stored row behind this read instance held and the read withheld.

    Empty for a row that held none, and for any instance a reader did not
    produce, such as a copy or a row built from a request.
    """
    return _WITHHELD_FIGURES.get(id(transaction), MappingProxyType({}))


WITHHELD_FIGURE_COUNT_KEY: Final[str] = "withheld_figure_count"
"""The event entry that marks an event as recording a row's withheld figures."""


def withheld_figures_event_entries(figures: Mapping[str, object]) -> dict[str, str]:
    """Return the bucket-event entries that record ``figures`` a write stops storing.

    Each prior value is kept under ``withheld_<field>``, with their count under
    ``withheld_figure_count``, so the event history still holds what the stored
    row said. A value longer than an event value may be is kept as its digest,
    under ``withheld_<field>_sha256``.
    """
    if not figures:
        return {}
    entries = {WITHHELD_FIGURE_COUNT_KEY: str(len(figures))}
    for name, value in sorted(figures.items()):
        text = _withheld_figure_text(value)
        if len(text) > BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH:
            entries[f"withheld_{name}_sha256"] = sha256_hex(text.encode(UTF_8_ENCODING))
        else:
            entries[f"withheld_{name}"] = text
    return entries


def _withheld_figure_text(value: object) -> str:
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return str(value)
