"""The sentence the Modelo 232 related-party operations serve for each of their refusals.

A frontend shows these sentences as served, so they sit under keys of their own
rather than reusing the command line's messages. A sentence is worded from its
key alone: it carries no counterparty, amount or note.
"""

from __future__ import annotations

from typing import Final

from ...core.external_constants import OutputLanguage
from ..operations.error_detail import operation_catalogue_refusal_words
from .contracts import Modelo232RelatedPartyOperationRefusalReason

__all__ = ["served_m232_related_party_refusal_words"]

_SERVED_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "ejercicio_unsupported": "aggregation.modelo_232_related_party.served.ejercicio_unsupported",
    "code_unknown": "aggregation.modelo_232_related_party.served.code_unknown",
    "already_stated": "aggregation.modelo_232_related_party.served.already_stated",
    "not_stated": "aggregation.modelo_232_related_party.served.not_stated",
    "none_stated": "aggregation.modelo_232_related_party.served.none_stated",
    "operations_present": "aggregation.modelo_232_related_party.served.operations_present",
    "specific_operation_required": "aggregation.modelo_232_related_party.served.specific_operation_required",
    "stale_revision": "aggregation.modelo_232_related_party.served.stale_revision",
    "validation": "aggregation.modelo_232_related_party.served.validation",
}


def served_m232_related_party_refusal_words(
    reason: Modelo232RelatedPartyOperationRefusalReason, *, error_code: str
) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, _SERVED_REFUSAL_LOCALE_KEYS[reason])
