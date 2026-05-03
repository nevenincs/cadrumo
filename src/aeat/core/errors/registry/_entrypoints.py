"""Error code registry for aeat.entrypoints."""

from aeat.core.errors._registry import ErrorCategory, ErrorCode

_DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "aeat.entrypoints.cli._errors.CliValidationBoundaryError",
        ErrorCode(
            code="INTEGRITY_CLI_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion del comando fallo.",
            default_message_en="The command input failed validation.",
            default_message_hu="A parancs bemenetenek ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli._errors.CliUnexpectedBoundaryError",
        ErrorCode(
            code="INTERNAL_CLI_UNEXPECTED_EXCEPTION",
            category=ErrorCategory.INTERNAL,
            default_message_es="El comando fallo por un error interno inesperado.",
            default_message_en="The command failed due to an unexpected internal error.",
            default_message_hu="A parancs varatlan belso hiba miatt meghiusult.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli._errors.CliRefusedBoundaryError",
        ErrorCode(
            code="REFUSED_CLI_BOUNDARY",
            category=ErrorCategory.REFUSED,
            default_message_es="El comando rechazo la solicitud actual.",
            default_message_en="The command refused the current request.",
            default_message_hu="A parancs elutasitotta az aktualis kerest.",
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
            default_message_es="La configuracion del nivel de log no es valida.",
            default_message_en="The requested CLI log-level configuration is invalid.",
            default_message_hu="A kert naplozasi szint beallitas ervenytelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli._tty.NonTtyRefusedError",
        ErrorCode(
            code="REFUSED_CLI_TTY_REQUIRED",
            category=ErrorCategory.REFUSED,
            default_message_es="El comando requiere una terminal interactiva.",
            default_message_en="The command requires an interactive terminal.",
            default_message_hu="A parancs interaktiv terminalt igenyel.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli.auth._registry.NoConfiguredProviderError",
        ErrorCode(
            code="AUTH_CLI_AUTH_REGISTRY_NO_CONFIGURED_PROVIDER",
            category=ErrorCategory.AUTH,
            default_message_es="No hay ningun proveedor de autenticacion configurado.",
            default_message_en="No auth provider is configured and no default was specified.",
            default_message_hu="Nincs beallitott hitelesitesi szolgaltato.",
            default_suggestion="aeat setup auth configure",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli.auth._registry.ProviderUnavailableError",
        ErrorCode(
            code="AUTH_CLI_AUTH_REGISTRY_PROVIDER_UNAVAILABLE",
            category=ErrorCategory.AUTH,
            default_message_es="El proveedor solicitado no esta disponible.",
            default_message_en="The requested provider is not available.",
            default_message_hu="A kert szolgaltato nem erheto el.",
            default_suggestion="aeat setup auth providers",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli.auth._registry.UnknownProviderError",
        ErrorCode(
            code="AUTH_CLI_AUTH_REGISTRY_UNKNOWN_PROVIDER",
            category=ErrorCategory.AUTH,
            default_message_es="Proveedor desconocido.",
            default_message_en="The requested provider kind is not registered.",
            default_message_hu="Ismeretlen szolgaltato.",
            default_suggestion="aeat setup auth providers",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli.auth._session.CorruptAuthSessionError",
        ErrorCode(
            code="INTEGRITY_CLI_AUTH_SESSION_CORRUPT_AUTH_SESSION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La sesi\xf3n almacenada de AEAT est\xe1 corrupta.",
            default_message_en="The persisted AEAT session is corrupt.",
            default_message_hu="A t\xe1rolt AEAT munkamenet s\xe9r\xfclt.",
            default_suggestion="aeat setup auth login",
            retryable=False,
            runbook_id=None,
        ),
    ),
)
