"""Ordered domain :class:`~core.errors.error_codes.ErrorCode` registry shard.

Rows map authority-registry and previous-filing domain exception qualnames to
stable :class:`~core.errors.error_codes.ErrorCategory` values and canonical message keys.
"""

from ..error_codes import ErrorCategory, ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "cadrumo.domain.calculations.registry.authority_artifact.AuthorityComponentCodecError",
        ErrorCode(
            code="INTEGRITY_AUTHORITY_COMPONENT_CODEC",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_authority_component_codec",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.domain.calculations.registry.authority_cache.AuthorityCacheCycleError",
        ErrorCode(
            code="INTERNAL_AUTHORITY_CACHE_CYCLE",
            category=ErrorCategory.INTERNAL,
            message_key="errors.internal.canonical_authority_cache_cycle",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.domain.calculations.registry.authority_store.AuthorityStoreError",
        ErrorCode(
            code="INTEGRITY_AUTHORITY_STORE",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_authority_store",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.domain.calculations.registry.authority_store.AuthorityStoreCutoverError",
        ErrorCode(
            code="INTEGRITY_AUTHORITY_STORE_CUTOVER",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_authority_store_cutover",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.domain.calculations.registry.authority_store.AuthorityStoreCorruptionError",
        ErrorCode(
            code="INTEGRITY_AUTHORITY_STORE_CORRUPTION",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_authority_store_corruption",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.domain.calculations.registry.authority_store.AuthorityStoreFormatError",
        ErrorCode(
            code="INTEGRITY_AUTHORITY_STORE_FORMAT",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_authority_store_format",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.domain.calculations.registry.bindings_previous_filing._PreviousFilingObservationAbsentError",
        ErrorCode(
            code="REFUSED_PREVIOUS_FILING_OBSERVATION_ABSENT",
            category=ErrorCategory.REFUSED,
            message_key="errors.refused.canonical_previous_filing_observation_absent",
            retryable=False,
            runbook_id=None,
        ),
    ),
)
