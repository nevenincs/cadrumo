"""Domain-layer :class:`~cadrumo.core.errors.error_codes.ErrorCode` registry aggregator.

Combines the domain registrations, grouped by owning subpackage, into the tuple
consumed by :mod:`cadrumo.core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .domain_calculations import DECLARED_ERROR_CODES as DOMAIN_CALCULATIONS_CALCULATIONS_CODES
from .domain_filing import DECLARED_ERROR_CODES as DOMAIN_FILING_FILING_CODES
from .domain_ledger import DECLARED_ERROR_CODES as DOMAIN_LEDGER_LEDGER_CODES
from .domain_profile import DECLARED_ERROR_CODES as DOMAIN_PROFILE_PROFILE_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *DOMAIN_PROFILE_PROFILE_CODES,
    *DOMAIN_LEDGER_LEDGER_CODES,
    *DOMAIN_FILING_FILING_CODES,
    *DOMAIN_CALCULATIONS_CALCULATIONS_CODES,
)
