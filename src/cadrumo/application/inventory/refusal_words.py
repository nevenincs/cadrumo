"""The sentence the inventory operations serve for each of their refusals.

The sentence is the one the inventory service's catalogue writes for the typed
reason, filled from the facts the refusal carries, so a frontend shows it as
served and words no reason of its own.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.external_constants import OutputLanguage
from ...domain.contribuyente.inventory.corrections import inventory_refusal_key
from ..operations.error_detail import operation_catalogue_refusal_words
from .registered_requests import InventoryRefusalCode, InventoryRefusalReason


def served_refusal_words(
    reason: InventoryRefusalReason, *, error_code: InventoryRefusalCode, facts: Mapping[str, str]
) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, inventory_refusal_key(reason), facts)


__all__ = ["served_refusal_words"]
