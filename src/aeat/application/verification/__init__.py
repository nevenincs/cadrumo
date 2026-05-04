"""Registry-backed verification records for imported declaracion drafts."""

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
