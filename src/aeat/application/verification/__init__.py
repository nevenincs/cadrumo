"""Registry-backed verification of imported declaración drafts.

Compares an imported declaración draft against the registry's expectations
and classifies each discrepancy, so an operator can see where a parsed
filing diverges from what the registry predicts. Pure value logic over
typed inputs.

Major declarations:

* :func:`verify_declaracion` — run the verification and return a
  :class:`VerificationVerdict`.
* :class:`VerificationStatus` and :class:`ClassifiedDiscrepancy` with
  :class:`DiscrepancyCause` — the verdict status and the per-field
  discrepancy classification.
* :class:`VerificationError` — the failure raised on malformed input.
"""

from __future__ import annotations

from ._errors import VerificationError
from ._schema import (
    ClassifiedDiscrepancy,
    DiscrepancyCause,
    VerificationStatus,
    VerificationVerdict,
)
from ._verify import verify_declaracion

__all__ = [
    "ClassifiedDiscrepancy",
    "DiscrepancyCause",
    "VerificationError",
    "VerificationStatus",
    "VerificationVerdict",
    "verify_declaracion",
]
