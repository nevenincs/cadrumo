"""The sentence the pension contribution record operations serve for each of their refusals.

A frontend shows these sentences as served, so they sit under keys of their own
rather than reusing the command line's messages, which name command options.
Each sentence says why nothing was stored and the way out, the box an operator
may enter by hand among them. A sentence is worded from its key alone: it
carries no issuer, plan, amount, file name or path.
"""

from __future__ import annotations

from typing import Final

from ...core.external_constants import OutputLanguage
from ..operations.error_detail import operation_catalogue_refusal_words
from .contracts import PrevisionSocialRefusalReason

_SERVED_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "ejercicio_unsupported": "aggregation.prevision_social_contribution.served.ejercicio_unsupported",
    "identity_mismatch": "aggregation.prevision_social_contribution.served.identity_mismatch",
    "certificate_not_in_custody": "aggregation.prevision_social_contribution.served.certificate_not_in_custody",
    "unplaced_clave": "aggregation.prevision_social_contribution.served.unplaced_clave",
    "indirect_match": "aggregation.prevision_social_contribution.served.indirect_match",
    "design_not_bundled": "aggregation.prevision_social_contribution.served.design_not_bundled",
    "same_plan_split_unstated": "aggregation.prevision_social_contribution.served.same_plan_split_unstated",
    "beneficiary_out_of_scope": "aggregation.prevision_social_contribution.served.beneficiary_out_of_scope",
    "stale_revision": "aggregation.prevision_social_contribution.served.stale_revision",
    "certificate_fingerprint_required": (
        "aggregation.prevision_social_contribution.served.certificate_fingerprint_required"
    ),
    "certificate_file_unreadable": "aggregation.prevision_social_contribution.served.certificate_file_unreadable",
    "certificate_fingerprint_mismatch": (
        "aggregation.prevision_social_contribution.served.certificate_fingerprint_mismatch"
    ),
    "clave_pair_undefined": "aggregation.prevision_social_contribution.served.clave_pair_undefined",
    "not_found": "aggregation.prevision_social_contribution.served.not_found",
    "validation": "aggregation.prevision_social_contribution.served.validation",
}


def served_refusal_words(reason: PrevisionSocialRefusalReason, *, error_code: str) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, _SERVED_REFUSAL_LOCALE_KEYS[reason])


__all__ = ["served_refusal_words"]
