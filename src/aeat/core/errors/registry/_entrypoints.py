"""Entrypoint-layer :class:`~aeat.core.errors.ErrorCode` registry declarations.

Rows map CLI boundary exception qualnames to stable
:class:`~aeat.core.errors.ErrorCategory` values and locale message keys.
"""

from .._registry import ErrorCategory, ErrorCode

_DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "aeat.entrypoints.cli._config._errors.ConfigBoundaryError",
        ErrorCode(
            code="ERROR_CONFIG_BOUNDARY",
            category=ErrorCategory.ERROR,
            message_key="errors.error.error_config_boundary",
            default_suggestion="aeat config repair --help",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli._errors.CliRefusedBoundaryError",
        ErrorCode(
            code="REFUSED_CLI_BOUNDARY",
            category=ErrorCategory.REFUSED,
            message_key="errors.refused.refused_cli_boundary",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli._errors.CliStoredDataValidationBoundaryError",
        ErrorCode(
            code="INTEGRITY_STORED_DATA_VALIDATION_BOUNDARY",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.storage.stored_data_validation_boundary",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli._log_levels.LogLevelResolutionError",
        ErrorCode(
            code="REFUSED_CLI_LOG_LEVEL_RESOLUTION",
            category=ErrorCategory.REFUSED,
            message_key="errors.refused.refused_cli_log_level_resolution",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
)
