"""Application-layer :class:`~cadrumo.core.errors.error_codes.ErrorCode` registry aggregator.

Combines the application registrations, grouped by owning subpackage, into the
tuple consumed by :mod:`cadrumo.core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._application_ledger import DECLARED_ERROR_CODES as _LEDGER_CODES
from ._application_modelo import DECLARED_ERROR_CODES as _MODELO_CODES
from ._application_modelo_work import MODELO_WORK_ERROR_CODES
from ._application_operations import DECLARED_ERROR_CODES as _OPERATIONS_CODES
from ._application_profile import DECLARED_ERROR_CODES as _PROFILE_CODES
from ._application_profile_bundle import PROFILE_BUNDLE_ERROR_CODES
from ._application_profile_proof import PROFILE_PROOF_ERROR_CODES
from ._application_reads import DECLARED_ERROR_CODES as _READS_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *_MODELO_CODES,
    *MODELO_WORK_ERROR_CODES,
    *_LEDGER_CODES,
    *_PROFILE_CODES,
    *PROFILE_BUNDLE_ERROR_CODES,
    *PROFILE_PROOF_ERROR_CODES,
    *_OPERATIONS_CODES,
    *_READS_CODES,
)
