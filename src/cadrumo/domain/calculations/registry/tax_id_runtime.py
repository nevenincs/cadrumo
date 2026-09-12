"""Authority-aware runtime operations for Spanish tax identifiers."""

from __future__ import annotations

from datetime import date

from ....core.identity.documents import IdentityDocument
from ....core.identity.documents import nif_check_letter as _nif_check_letter
from ....core.identity.documents import validate_identity as _validate_identity
from ....core.identity.tax_id import validate_spanish_tax_id as _validate_spanish_tax_id
from .tax_id_format import runtime_tax_id_format


def validate_runtime_spanish_tax_id(value: str, *, effective_date: date | None = None) -> str:
    """Validate one identifier through the established bundled authority."""
    return _validate_spanish_tax_id(value, runtime_tax_id_format(effective_date=effective_date))


def validate_runtime_identity(candidate: object, *, effective_date: date | None = None) -> IdentityDocument:
    """Classify one identifier through the established bundled authority."""
    return _validate_identity(candidate, runtime_tax_id_format(effective_date=effective_date))


def runtime_nif_check_letter(number: int, *, effective_date: date | None = None) -> str:
    """Compute one check letter through the established bundled authority."""
    return _nif_check_letter(number, runtime_tax_id_format(effective_date=effective_date))


__all__ = ["runtime_nif_check_letter", "validate_runtime_identity", "validate_runtime_spanish_tax_id"]
