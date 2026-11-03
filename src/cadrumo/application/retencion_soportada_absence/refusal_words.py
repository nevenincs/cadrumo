"""The sentence the suffered-withholding absence operations serve for each of their refusals.

A frontend shows these sentences as served, so they sit under keys of their own
rather than reusing the command line's messages. A sentence is worded from its
key alone: it carries no income class, note or amount.
"""

from __future__ import annotations

from typing import Final

from ...core.external_constants import OutputLanguage
from ..operations.error_detail import operation_catalogue_refusal_words
from .contracts import RetencionSoportadaAbsenceOperationRefusalReason

__all__ = ["served_absence_refusal_words"]

_SERVED_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "ejercicio_unsupported": "aggregation.retencion_soportada_absence.served.ejercicio_unsupported",
    "family_not_declared": "aggregation.retencion_soportada_absence.served.family_not_declared",
    "records_present": "aggregation.retencion_soportada_absence.served.records_present",
    "already_attested": "aggregation.retencion_soportada_absence.served.already_attested",
    "not_attested": "aggregation.retencion_soportada_absence.served.not_attested",
    "stale_revision": "aggregation.retencion_soportada_absence.served.stale_revision",
}


def served_absence_refusal_words(
    reason: RetencionSoportadaAbsenceOperationRefusalReason, *, error_code: str
) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, _SERVED_REFUSAL_LOCALE_KEYS[reason])
