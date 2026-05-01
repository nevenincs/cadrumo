"""Round-trip calculation verification for imported declaración drafts (#305 cluster E).

Turns an :class:`aeat.declaracion.DeclaracionFiling` + the project's
formula engine output into a Kent-readable verdict: ``verified`` /
``needs_review`` / ``unverifiable``. The module consumes
:func:`aeat.formulas.Engine.audit_against` and classifies each
discrepancy by cause (extraction unreliable / rounding / un-modelled
rule / correctness divergence) so Kent gets an actionable next step.

Public API:

    from aeat.application.verification import (
        DiscrepancyCause,
        ClassifiedDiscrepancy,
        VerificationStatus,
        VerificationVerdict,
        verify_declaracion,
    )
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
