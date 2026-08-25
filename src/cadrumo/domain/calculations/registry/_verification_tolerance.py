"""Canonical registry tolerance projection for filing comparisons."""

from __future__ import annotations

from decimal import Decimal

from .errors import RegistryValidationError
from ._schema import RegistrySnapshot

__all__ = ["verification_tolerance_or_exact"]


def verification_tolerance_or_exact(snapshot: RegistrySnapshot) -> Decimal:
    """Return the snapshot's published comparison tolerance, or exact equality.

    The registry's verification policy owns a regulatory tolerance per revision.
    A revision without verification expectations has no published authority for a
    wider comparison, so its deliberate fallback is exact equality instead of an
    invented cent allowance.
    """
    try:
        return snapshot.verification_policy().tolerance
    except RegistryValidationError:
        return Decimal("0")
