"""Domain-layer :class:`~cadrumo.core.errors.error_codes.ErrorCode` registry aggregator.

Combines the domain registrations, grouped by owning subpackage, into the tuple
consumed by :mod:`cadrumo.core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._domain_calculations import DECLARED_ERROR_CODES as _CALCULATIONS_CODES
from ._domain_filing import DECLARED_ERROR_CODES as _FILING_CODES
from ._domain_ledger import DECLARED_ERROR_CODES as _LEDGER_CODES
from ._domain_profile import DECLARED_ERROR_CODES as _PROFILE_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *_PROFILE_CODES,
    *_LEDGER_CODES,
    *_FILING_CODES,
    *_CALCULATIONS_CODES,
)
