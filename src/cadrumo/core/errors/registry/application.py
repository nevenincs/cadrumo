"""Application-layer :class:`~cadrumo.core.errors.error_codes.ErrorCode` registry aggregator.

Combines the application registrations, grouped by owning subpackage, into the
tuple consumed by :mod:`cadrumo.core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .application_ledger import DECLARED_ERROR_CODES as APPLICATION_LEDGER_LEDGER_CODES
from .application_modelo import DECLARED_ERROR_CODES as APPLICATION_MODELO_MODELO_CODES
from .application_modelo_export_review import (
    DECLARED_ERROR_CODES as APPLICATION_MODELO_EXPORT_REVIEW_MODELO_EXPORT_REVIEW_CODES,
)
from .application_modelo_lifecycle import DECLARED_ERROR_CODES as APPLICATION_MODELO_LIFECYCLE_MODELO_LIFECYCLE_CODES
from .application_modelo_work import MODELO_WORK_ERROR_CODES
from .application_operations import DECLARED_ERROR_CODES as APPLICATION_OPERATIONS_OPERATIONS_CODES
from .application_profile import DECLARED_ERROR_CODES as APPLICATION_PROFILE_PROFILE_CODES
from .application_profile_bundle import PROFILE_BUNDLE_ERROR_CODES
from .application_profile_proof import PROFILE_PROOF_ERROR_CODES
from .application_reads import DECLARED_ERROR_CODES as APPLICATION_READS_READS_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *APPLICATION_MODELO_MODELO_CODES,
    *APPLICATION_MODELO_EXPORT_REVIEW_MODELO_EXPORT_REVIEW_CODES,
    *APPLICATION_MODELO_LIFECYCLE_MODELO_LIFECYCLE_CODES,
    *MODELO_WORK_ERROR_CODES,
    *APPLICATION_LEDGER_LEDGER_CODES,
    *APPLICATION_PROFILE_PROFILE_CODES,
    *PROFILE_BUNDLE_ERROR_CODES,
    *PROFILE_PROOF_ERROR_CODES,
    *APPLICATION_OPERATIONS_OPERATIONS_CODES,
    *APPLICATION_READS_READS_CODES,
)
