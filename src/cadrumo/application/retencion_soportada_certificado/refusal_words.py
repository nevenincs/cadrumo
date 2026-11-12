"""The sentence the suffered-withholding record operation serves for each of its refusals.

A frontend shows these sentences as served, so they sit under keys of their own
rather than reusing the command line's messages, which name command options. A
sentence is worded from its key alone: it carries no payer, amount, file name or
path.
"""

from __future__ import annotations

from typing import Final

from ...core.external_constants import OutputLanguage
from ..operations.error_detail import operation_catalogue_refusal_words
from .contracts import RetencionSoportadaCertificadoRefusalReason

_SERVED_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "own_tax_id": "aggregation.retencion_soportada.served.own_tax_id",
    "ejercicio_unsupported": "aggregation.retencion_soportada.served.ejercicio_unsupported",
    "family_not_declared": "aggregation.retencion_soportada.served.family_not_declared",
    "identity_mismatch": "aggregation.retencion_soportada.served.identity_mismatch",
    "stale_revision": "aggregation.retencion_soportada.served.stale_revision",
    "repercutido_exceeds_ingreso_a_cuenta": "aggregation.retencion_soportada.served.repercutido_exceeds_ingreso",
    "certificate_fingerprint_required": "aggregation.retencion_soportada.served.certificate_needs_fingerprint",
    "certificate_not_in_custody": "aggregation.retencion_soportada.served.certificate_not_in_custody",
    "certificate_file_unreadable": "aggregation.retencion_soportada.served.certificate_file_unreadable",
    "certificate_fingerprint_mismatch": "aggregation.retencion_soportada.served.certificate_fingerprint_mismatch",
    "taxpayer_tax_id_unknown": "aggregation.retencion_soportada.served.taxpayer_tax_id_unknown",
    "not_found": "aggregation.retencion_soportada.served.not_found",
    "validation": "aggregation.retencion_soportada.served.validation",
    "trabajo_certificate_figure_missing": "aggregation.retencion_soportada.served.trabajo_certificate_figure_missing",
}


def served_refusal_words(
    reason: RetencionSoportadaCertificadoRefusalReason, *, error_code: str
) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, _SERVED_REFUSAL_LOCALE_KEYS[reason])


__all__ = ["served_refusal_words"]
