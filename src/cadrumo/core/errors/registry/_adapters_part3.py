"""Ordered adapter :class:`~core.errors.ErrorCode` registry shard.

Rows map adapter exception qualnames to stable
:class:`~core.errors.ErrorCategory` values and canonical message keys.
"""

from ..error_codes import ErrorCategory, ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "cadrumo.adapters.persistence.profile.relation_binding_join.RelationBindingJoinError",
        ErrorCode(
            code="INTEGRITY_RELATION_BINDING_JOIN",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_relation_binding_join",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.adapters.persistence.storage.custody.kdf_supervision._CalibrationDeadlineElapsedError",
        ErrorCode(
            code="INTERNAL_CALIBRATION_DEADLINE_ELAPSED",
            category=ErrorCategory.INTERNAL,
            message_key="errors.internal.canonical_calibration_deadline_elapsed",
            retryable=False,
            runbook_id=None,
        ),
    ),
)
