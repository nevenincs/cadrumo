"""Error hierarchy for the calculation-verification subpackage.

Defines :class:`VerificationError`, the base exception for unrecoverable
verification failures rooted at :class:`aeat.core.errors.AeatError`.
Ordinary discrepancies between printed and computed values are *not*
exceptions — they are encoded in
:class:`aeat.application.verification.VerificationVerdict`.
"""

from __future__ import annotations

from ...core.errors import AeatError


class VerificationError(AeatError):
    """Raised on catastrophic verification failures.

    Reserved for unrecoverable conditions (corrupt registry data, broken engine
    contract, missing core dependency). Discrepancies between the printed
    casilla values and the engine-derived values are not exceptions; they
    surface as
    :class:`aeat.application.verification.ClassifiedDiscrepancy` entries
    on the verdict.
    """
