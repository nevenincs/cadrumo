"""Build synthetic identifiers using the actual pinned identifier-format contract."""

from __future__ import annotations

from datetime import date

from .....core.identity.documents import nif_check_letter as _nif_check_letter
from ..tax_id_format import runtime_tax_id_format


def runtime_nif_check_letter(number: int, *, effective_date: date | None = None) -> str:
    """Compute one check letter through the established bundled authority."""
    return _nif_check_letter(number, runtime_tax_id_format(effective_date=effective_date))
