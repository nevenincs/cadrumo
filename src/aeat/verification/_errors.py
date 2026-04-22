"""Error hierarchy for verification (#305 cluster E)."""

from __future__ import annotations

from ..errors import AeatError


class VerificationError(AeatError):
    """Raised on catastrophic verification failures (not ordinary discrepancies)."""
