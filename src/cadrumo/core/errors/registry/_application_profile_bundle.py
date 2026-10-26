"""Error-code rows for profile bundle export journalling."""

from ..error_codes import ErrorCategory, ErrorCode

PROFILE_BUNDLE_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "cadrumo.application.user_profile.bundle_export_operation.ProfileBundleExportJournalError",
        ErrorCode(
            code="ERROR_PROFILE_EXPORT_JOURNAL",
            category=ErrorCategory.ERROR,
            message_key="errors.error.error_config_boundary",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.application.user_profile.bundle_export_operation.ProfileBundleExportJournalNotFoundError",
        ErrorCode(
            code="ERROR_PROFILE_EXPORT_JOURNAL_NOT_FOUND",
            category=ErrorCategory.ERROR,
            message_key="errors.error.error_cadrumo_core_not_found",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.application.user_profile.bundle_export_operation.ProfileBundleExportJournalCorruptError",
        ErrorCode(
            code="ERROR_PROFILE_EXPORT_JOURNAL_CORRUPT",
            category=ErrorCategory.ERROR,
            message_key="errors.error.error_config_boundary",
            retryable=False,
            runbook_id=None,
        ),
    ),
)
