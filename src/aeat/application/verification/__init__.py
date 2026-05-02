"""Round-trip calculation verification for imported declaración drafts.

Turns an :class:`aeat.adapters.inbound.declaracion.DeclaracionFiling` plus
the project's formula engine output into an operator-readable verdict:
``verified``, ``needs_review``, or ``unverifiable``. The module consumes
:meth:`aeat.domain.formulas.Engine.audit_against` and classifies each
discrepancy by cause — extraction unreliable, rounding, unmodelled rule,
or correctness divergence — so the operator gets an actionable next step.

Examples:
    >>> from aeat.application.verification import verify_declaracion
    >>> verdict = verify_declaracion(filing, ruleset=ruleset)
    >>> verdict.status
    <VerificationStatus.VERIFIED: 'VERIFIED'>
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
