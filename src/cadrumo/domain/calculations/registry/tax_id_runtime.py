"""Authority-aware runtime operations for Spanish tax identifiers."""

from __future__ import annotations

from datetime import date

from ....core.identity.documents import IdentityDocument, validate_identity
from ....core.identity.tax_id import validate_spanish_tax_id
from .tax_id_format import runtime_tax_id_format


def validate_runtime_spanish_tax_id(value: str, *, effective_date: date | None = None) -> str:
    """Validate one identifier through the established bundled authority."""
    return validate_spanish_tax_id(value, runtime_tax_id_format(effective_date=effective_date))


def validate_runtime_identity(candidate: object, *, effective_date: date | None = None) -> IdentityDocument:
    """Classify one identifier through the established bundled authority."""
    return validate_identity(candidate, runtime_tax_id_format(effective_date=effective_date))


__all__ = ["validate_runtime_identity", "validate_runtime_spanish_tax_id"]
