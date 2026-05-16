"""Operator-facing profile services.

Houses the CLI-callable services that operate on the active profile:
census live-sync (W85.S2349), and future profile-cross-AEAT
operations. The lower-level profile schema/values/lifecycle layer
lives in :mod:`aeat.application.user_profile`; that module remains
the persistence + projection boundary while this module exposes the
operator workflows that compose it.
"""

from ._census_errors import (
    CensusApplyConflictError,
    CensusFieldValidationError,
    CensusNotAvailableError,
    CensusSyncError,
)
from ._census_sync import (
    CENSUS_SOURCE_TAG,
    CensusApplyResult,
    CensusComparisonStatus,
    CensusFactSource,
    CensusFieldComparison,
    CensusProfileComparison,
    CensusSyncService,
)

__all__ = [
    "CENSUS_SOURCE_TAG",
    "CensusApplyConflictError",
    "CensusApplyResult",
    "CensusComparisonStatus",
    "CensusFactSource",
    "CensusFieldComparison",
    "CensusFieldValidationError",
    "CensusNotAvailableError",
    "CensusProfileComparison",
    "CensusSyncError",
    "CensusSyncService",
]
