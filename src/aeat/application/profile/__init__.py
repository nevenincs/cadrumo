"""Operator-facing profile services.

Houses the CLI-callable services that operate on the active profile:
census live-sync against the sede Mis Datos Censales endpoint, and future profile-cross-AEAT
operations. The lower-level profile schema/values/lifecycle layer
lives in :mod:`aeat.application.user_profile`; that module remains
the persistence + projection boundary while this module exposes the
operator workflows that compose it.
"""

from ._censo_errors import (
    CensoApplyConflictError,
    CensoFieldValidationError,
    CensoNotAvailableError,
    CensoSyncError,
)
from ._censo_sync import (
    CENSUS_SOURCE_TAG,
    CensoApplyResult,
    CensoComparisonStatus,
    CensoFieldComparison,
    CensoProfileComparison,
    CensoSyncService,
    CensoFactSource,
)

__all__ = [
    "CENSUS_SOURCE_TAG",
    "CensoApplyConflictError",
    "CensoApplyResult",
    "CensoComparisonStatus",
    "CensoFieldComparison",
    "CensoFieldValidationError",
    "CensoNotAvailableError",
    "CensoProfileComparison",
    "CensoSyncError",
    "CensoSyncService",
    "CensoFactSource",
]
