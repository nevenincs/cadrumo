"""Structured error-code registry and rendering helpers.

This module centralises AEAT's stable CLI error taxonomy. Error classes
bind to predeclared :class:`ErrorCode` rows so the public contract stays
explicit and reviewable.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

_SECRET_FIELD_PATTERN = re.compile(
    r"(credential|token|secret|pkcs12|passphrase|cert_password|cookie|bearer)",
    re.IGNORECASE,
)


class ErrorCategory(StrEnum):
    """Closed catalogue of stable CLI error categories."""

    ERROR = "ERROR"
    REFUSED = "REFUSED"
    AUTH = "AUTH"
    INTEGRITY = "INTEGRITY"
    FAIL = "FAIL"
    INTERNAL = "INTERNAL"
    LOCKED = "LOCKED"
    DEPRECATED = "[deprecated]"
    MOVED = "[moved]"


class ErrorCode(BaseModel):
    """Stable metadata attached to an :class:`aeat.core.errors.AeatError` type."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        validate_assignment=True,
        extra="forbid",
    )

    code: str
    category: ErrorCategory
    default_message_es: str
    default_message_en: str
    default_message_hu: str
    default_suggestion: str | None
    retryable: bool
    runbook_id: str | None


class ErrorEnvelope(BaseModel):
    """Machine-readable error payload emitted on stderr."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        validate_assignment=True,
        extra="forbid",
    )

    schema_version: str = "1"
    code: str
    category: str
    message: str
    suggestion: str | None
    retryable: bool
    runbook_id: str | None
    context: dict[str, str] | None
    trace_id: str | None


_ERROR_REGISTRY_MUTABLE: dict[str, ErrorCode] = {}
_CLASS_CODE_REGISTRY: dict[type[BaseException], ErrorCode] = {}


def register(code: ErrorCode) -> ErrorCode:
    """Register ``code`` in the global catalogue.

    Args:
        code: The error-code record to add.

    Returns:
        The same ``code`` object for fluent use at declaration sites.

    Raises:
        ValueError: If a duplicate code identifier is encountered.
    """

    existing = _ERROR_REGISTRY_MUTABLE.get(code.code)
    if existing is not None and existing != code:
        raise ValueError(f"duplicate ErrorCode registration for {code.code!r}")
    _ERROR_REGISTRY_MUTABLE[code.code] = code
    return code


_DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "aeat.domain.justificante._errors.PdfFilingImportError",
        ErrorCode(
            code="ERROR_PDF_IMPORT_PDF_FILING_IMPORT",
            category=ErrorCategory.ERROR,
            default_message_es="Error de pdf presentacion importacion.",
            default_message_en="Base class for every PDF-import parsing error.",
            default_message_hu="Pdf beadas importalas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.pdf._scrub.ScrubError",
        ErrorCode(
            code="ERROR_PDF_IMPORT_SCRUB",
            category=ErrorCategory.ERROR,
            default_message_es="Error de limpieza.",
            default_message_en="Raised when scrubbing cannot produce a safe output.",
            default_message_hu="Tisztitas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth._authenticator._PersistedSessionInvalidError",
        ErrorCode(
            code="AUTH_AUTH_AUTHENTICATOR_PERSISTED_SESSION_INVALID",
            category=ErrorCategory.AUTH,
            default_message_es="La sesion persistida de AEAT no es valida.",
            default_message_en="Raised when a persisted AEAT browser session cannot be trusted.",
            default_message_hu="A tarolt AEAT munkamenet nem megbizhato.",
            default_suggestion=None,
            retryable=True,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth._clave_movil.ClaveMovilApprovalTimeoutError",
        ErrorCode(
            code="AUTH_AUTH_CLAVE_MOVIL_CLAVE_MOVIL_APPROVAL_TIMEOUT",
            category=ErrorCategory.AUTH,
            default_message_es="La aprobacion de Clave Movil agoto el tiempo de espera.",
            default_message_en="Raised when Kent does not approve the Cl@ve push within the time window.",
            default_message_hu="Clave movil jovahagyas idotullepessel vegzodott.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth._clave_movil.ClaveMovilConfigurationError",
        ErrorCode(
            code="AUTH_AUTH_CLAVE_MOVIL_CLAVE_MOVIL_CONFIGURATION",
            category=ErrorCategory.AUTH,
            default_message_es="Clave movil no esta configurado correctamente.",
            default_message_en="Raised when required Cl@ve M\xf3vil settings are missing or malformed.",
            default_message_hu="Clave movil nincs megfeleloen beallitva.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.AeatLiveReadNotEnabledError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_AEAT_LIVE_READ_NOT_ENABLED",
            category=ErrorCategory.AUTH,
            default_message_es="La lectura en vivo de AEAT no esta habilitada.",
            default_message_en="Raised when live-read access is required but the gate is shut.",
            default_message_hu="Az AEAT elo olvasasi mod nincs engedelyezve.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.AeatLoginAssertionError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_AEAT_LOGIN_ASSERTION",
            category=ErrorCategory.AUTH,
            default_message_es="No se pudo completar la verificacion posterior al inicio de sesion de AEAT.",
            default_message_en="Raised when a post-auth verification attempt cannot be produced.",
            default_message_hu="Az AEAT bejelentkezes utani ellenorzes nem keszult el.",
            default_suggestion="aeat auth login",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.AeatSessionExpiredError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_AEAT_SESSION_EXPIRED",
            category=ErrorCategory.AUTH,
            default_message_es="La sesi\xf3n autenticada de AEAT ha caducado.",
            default_message_en="The authenticated AEAT session expired.",
            default_message_hu="Az AEAT hiteles\xedtett munkamenet lej\xe1rt.",
            default_suggestion="aeat auth login",
            retryable=True,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.CertificateError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE",
            category=ErrorCategory.AUTH,
            default_message_es="Error de certificado.",
            default_message_en="Base class for every certificate-auth domain error.",
            default_message_hu="Tanusitvany hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.CertificateExpiredError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_EXPIRED",
            category=ErrorCategory.AUTH,
            default_message_es="Certificado caducado.",
            default_message_en="The loaded certificate is already expired.",
            default_message_hu="Tanusitvany lejart.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.CertificateHandshakeError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_HANDSHAKE",
            category=ErrorCategory.AUTH,
            default_message_es="Error de certificado handshake.",
            default_message_en="Raised when handshake input is structurally invalid.",
            default_message_hu="Tanusitvany kezfogas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.CertificateLoadError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_LOAD",
            category=ErrorCategory.AUTH,
            default_message_es="No se pudo cargar certificado.",
            default_message_en="Raised when PKCS#12 bytes cannot be parsed at all.",
            default_message_hu="Tanusitvany betoltese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.CertificateNifParseError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_NIF_PARSE",
            category=ErrorCategory.AUTH,
            default_message_es="No se pudo analizar certificado nif.",
            default_message_en="Raised when no NIF / NIE can be parsed from a certificate subject.",
            default_message_hu="Tanusitvany nif feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.CertificatePasswordError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_PASSWORD",
            category=ErrorCategory.AUTH,
            default_message_es="Error de contrasena del certificado.",
            default_message_en="Raised when the passphrase env var is missing/empty or wrong.",
            default_message_hu="Tanusitvany jelszo hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.auth.certificate.CertificatePreExpiryError",
        ErrorCode(
            code="AUTH_AUTH_CERTIFICATE_PRE_EXPIRY",
            category=ErrorCategory.AUTH,
            default_message_es="Error de certificado pre expiry.",
            default_message_en="Raised when a certificate is within the pre-expiry danger window.",
            default_message_hu="Tanusitvany elo expiry hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.borrador._errors.ArtefactNotRecognisedError",
        ErrorCode(
            code="ERROR_BORRADOR_ARTEFACT_NOT_RECOGNISED",
            category=ErrorCategory.ERROR,
            default_message_es="El artefacto del PDF no coincide con un formato conocido.",
            default_message_en="Raised when the PDF does not match any known Modelo 100 artefact shape.",
            default_message_hu="A PDF artefaktuma nem egyezik ismert formatummal.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.borrador._errors.BorradorParseError",
        ErrorCode(
            code="FAIL_BORRADOR_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo analizar borrador.",
            default_message_en="The Modelo 100 PDF could not be parsed into a draft filing.",
            default_message_hu="Tervezet feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.browser.session.BrowserError",
        ErrorCode(
            code="FAIL_BROWSER_SESSION_BROWSER",
            category=ErrorCategory.FAIL,
            default_message_es="Error de navegador.",
            default_message_en="Base class for browser-related errors.",
            default_message_hu="Bongeszo hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.casillas.errors.CasillaError",
        ErrorCode(
            code="ERROR_CASILLAS_CASILLA",
            category=ErrorCategory.ERROR,
            default_message_es="Error de casilla.",
            default_message_en="Base class for casilla-related errors.",
            default_message_hu="Casilla hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.casillas.errors.CasillaParseError",
        ErrorCode(
            code="FAIL_CASILLAS_CASILLA_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo analizar casilla.",
            default_message_en="Raised when a casilla catalogue file cannot be parsed or validated.",
            default_message_hu="Casilla feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.casillas.errors.CrossReferenceError",
        ErrorCode(
            code="ERROR_CASILLAS_CROSS_REFERENCE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de cruce referencia.",
            default_message_en="Raised when a record references another casilla that does not exist.",
            default_message_hu="Kereszt hivatkozas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.casillas.errors.MissingFieldError",
        ErrorCode(
            code="ERROR_CASILLAS_MISSING_FIELD",
            category=ErrorCategory.ERROR,
            default_message_es="Error de faltante campo.",
            default_message_en="Raised when a record is missing a required logical field.",
            default_message_hu="Hianyzik mezo hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.casillas.errors.UnreviewedRecordError",
        ErrorCode(
            code="ERROR_CASILLAS_UNREVIEWED_RECORD",
            category=ErrorCategory.ERROR,
            default_message_es="Error de sin revisar registro.",
            default_message_en="Raised when a canonical record lacks required review metadata.",
            default_message_hu="Ellenorizetlen rekord hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.casillas.errors.VerifyError",
        ErrorCode(
            code="ERROR_CASILLAS_VERIFY",
            category=ErrorCategory.ERROR,
            default_message_es="Error de verificar.",
            default_message_en="Base class for structured verification failures.",
            default_message_hu="Ellenoriz hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
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
        "aeat.core.json_contract.OutputSchemaError",
        ErrorCode(
            code="INTEGRITY_CLI_OUTPUT_SCHEMA",
            category=ErrorCategory.INTEGRITY,
            default_message_es="El registro de esquemas JSON del CLI no es valido.",
            default_message_en="The CLI JSON schema registry is invalid.",
            default_message_hu="A CLI JSON sema regisztere ervenytelen.",
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
            default_suggestion="aeat auth init",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.entrypoints.cli.auth._registry.ProviderNotImplementedError",
        ErrorCode(
            code="AUTH_CLI_AUTH_REGISTRY_PROVIDER_NOT_IMPLEMENTED",
            category=ErrorCategory.AUTH,
            default_message_es="El proveedor solicitado aun no tiene implementacion disponible.",
            default_message_en="The provider kind is known but no implementation has shipped yet.",
            default_message_hu="A kert szolgaltatohoz meg nincs megvalositas.",
            default_suggestion="aeat auth list-providers",
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
            default_suggestion="aeat auth list-providers",
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
            default_suggestion="aeat auth login",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.deadlines._errors.DeadlineError",
        ErrorCode(
            code="ERROR_DEADLINES_DEADLINE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de plazo.",
            default_message_en="Base class for deadline-related errors.",
            default_message_hu="Hatarido hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.deadlines._errors.ProfileError",
        ErrorCode(
            code="ERROR_DEADLINES_PROFILE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de perfil.",
            default_message_en="The autonomo profile could not be loaded or validated.",
            default_message_hu="Profil hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.deadlines._errors.ScheduleComputationError",
        ErrorCode(
            code="ERROR_DEADLINES_SCHEDULE_COMPUTATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de planificacion calculo.",
            default_message_en="The deadline schedule could not be computed.",
            default_message_hu="Utemezes szamitas hiba.",
            default_suggestion="aeat deadlines explain 303 --period 2024Q1",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.declaracion._errors.DeclaracionParseError",
        ErrorCode(
            code="FAIL_DECLARACION_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo analizar declaracion.",
            default_message_en="The PDF could not be parsed into a declaration filing.",
            default_message_hu="Bevallas feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.declaracion._errors.NoExtractorRegisteredError",
        ErrorCode(
            code="ERROR_DECLARACION_NO_EXTRACTOR_REGISTERED",
            category=ErrorCategory.ERROR,
            default_message_es="No hay un extractor registrado para la plantilla detectada.",
            default_message_en="Raised when no concrete extractor exists for the detected template.",
            default_message_hu="A felismert sablonhoz nincs regisztralt kinyero.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.declaracion._errors.TemplateNotDetectedError",
        ErrorCode(
            code="ERROR_DECLARACION_TEMPLATE_NOT_DETECTED",
            category=ErrorCategory.ERROR,
            default_message_es="No se pudo detectar la plantilla del PDF.",
            default_message_en="The declaration template could not be identified from the PDF.",
            default_message_hu="A bevallasi sablon nem volt felismerheto a PDF-bol.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.AeatObservabilityError",
        ErrorCode(
            code="ERROR_AEAT_OBSERVABILITY",
            category=ErrorCategory.ERROR,
            default_message_es="Error de aeat observabilidad.",
            default_message_en="Base class for observability-layer errors (#99).",
            default_message_hu="Aeat megfigyelhetoseg hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.AmbiguousPeriodError",
        ErrorCode(
            code="ERROR_AMBIGUOUS_PERIOD",
            category=ErrorCategory.ERROR,
            default_message_es="Error de ambiguo periodo.",
            default_message_en="Raised when a period matches more than one ruleset span.",
            default_message_hu="Ketertelmu idoszak hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.AuditDiscrepancyError",
        ErrorCode(
            code="INTEGRITY_AUDIT_DISCREPANCY",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de auditoria discrepancia.",
            default_message_en="The audit report contains discrepancies.",
            default_message_hu="Audit elteres hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.CasillaNotDefinedError",
        ErrorCode(
            code="ERROR_CASILLA_NOT_DEFINED",
            category=ErrorCategory.ERROR,
            default_message_es="La casilla referenciada no esta definida en el conjunto de reglas.",
            default_message_en="Raised when a formula references a casilla that the ruleset does not declare.",
            default_message_hu="A hivatkozott casilla nincs meghatarozva.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.DeprecatedAliasError",
        ErrorCode(
            code="DEPRECATED_DEPRECATED_ALIAS",
            category=ErrorCategory.DEPRECATED,
            default_message_es="Se utiliz\xf3 un alias obsoleto de la CLI.",
            default_message_en="A deprecated CLI alias was used.",
            default_message_hu="Egy elavult CLI alias haszn\xe1lata t\xf6rt\xe9nt.",
            default_suggestion="aeat --help",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.EvaluationError",
        ErrorCode(
            code="ERROR_EVALUATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de evaluacion.",
            default_message_en="Raised when a formula evaluation produces an arithmetic domain error.",
            default_message_hu="Ertekeles hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.FilingFixtureError",
        ErrorCode(
            code="INTEGRITY_FILING_FIXTURE",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de presentacion fixture.",
            default_message_en="Raised when a synthetic filing-history fixture cannot be loaded.",
            default_message_hu="Beadas fixeles hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.FixtureProvisioningError",
        ErrorCode(
            code="ERROR_FIXTURE_PROVISIONING",
            category=ErrorCategory.ERROR,
            default_message_es="Error de fixture aprovisionamiento.",
            default_message_en="Raised when Google Workspace test-fixture provisioning fails.",
            default_message_hu="Fixeles letrehozas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.FormulaCycleError",
        ErrorCode(
            code="INTEGRITY_FORMULA_CYCLE",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de formula cycle.",
            default_message_en="Raised when a ruleset DAG contains a cycle between computed casillas.",
            default_message_hu="Formula cycle hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.FormulasError",
        ErrorCode(
            code="ERROR_FORMULAS",
            category=ErrorCategory.ERROR,
            default_message_es="Error de formulas.",
            default_message_en="Base class for formula-engine errors.",
            default_message_hu="Formulas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.McpLaunchError",
        ErrorCode(
            code="FAIL_MCP_LAUNCH",
            category=ErrorCategory.FAIL,
            default_message_es="Error de mcp launch.",
            default_message_en="Raised when a repo-managed MCP process cannot be launched safely.",
            default_message_hu="Mcp launch hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.MissingRulesetError",
        ErrorCode(
            code="ERROR_MISSING_RULESET",
            category=ErrorCategory.ERROR,
            default_message_es="Error de faltante conjunto de reglas.",
            default_message_en="Raised when no ruleset covers the requested modelo/period pair.",
            default_message_hu="Hianyzik szabalykeszlet hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.MovedAliasError",
        ErrorCode(
            code="MOVED_MOVED_ALIAS",
            category=ErrorCategory.MOVED,
            default_message_es="Se utiliz\xf3 un alias movido de la CLI.",
            default_message_en="A moved CLI alias was used.",
            default_message_hu="\xc1thelyezett CLI alias haszn\xe1lata t\xf6rt\xe9nt.",
            default_suggestion="aeat --help",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.RulesetValidationError",
        ErrorCode(
            code="INTEGRITY_RULESET_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion de conjunto de reglas fallo.",
            default_message_en="Raised when a ruleset fails structural validation at load time.",
            default_message_hu="Szabalykeszlet ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.SiteHealthError",
        ErrorCode(
            code="FAIL_SITE_HEALTH",
            category=ErrorCategory.FAIL,
            default_message_es="Error de estado del sitio de AEAT.",
            default_message_en="Raised when AEAT site-health detection classifies a non-OK state.",
            default_message_hu="Az AEAT oldalallapota hibas.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.errors.WorkspaceLockedError",
        ErrorCode(
            code="LOCKED_WORKSPACE_LOCKED",
            category=ErrorCategory.LOCKED,
            default_message_es="El espacio de trabajo est\xe1 bloqueado por otra operaci\xf3n.",
            default_message_en="The workspace is locked by another operation.",
            default_message_hu="A munkater\xfcletet egy m\xe1sik m\u0171velet z\xe1rolja.",
            default_suggestion="aeat workflow list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.filing._errors.FilingAmendmentError",
        ErrorCode(
            code="ERROR_FILING_AMENDMENT",
            category=ErrorCategory.ERROR,
            default_message_es="Error de presentacion rectificacion.",
            default_message_en="Base class for every amendment-related filing error.",
            default_message_hu="Beadas helyesbites hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.filing._errors.FilingAmendmentValidationError",
        ErrorCode(
            code="INTEGRITY_FILING_AMENDMENT_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion de presentacion rectificacion fallo.",
            default_message_en="Raised when an amendment violates legal or shape invariants.",
            default_message_hu="Beadas helyesbites ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.filing._errors.FilingBuilderError",
        ErrorCode(
            code="ERROR_FILING_BUILDER",
            category=ErrorCategory.ERROR,
            default_message_es="Error de presentacion builder.",
            default_message_en="Raised when builder selection or execution fails.",
            default_message_hu="Beadas builder hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.filing._errors.FilingComputationError",
        ErrorCode(
            code="ERROR_FILING_COMPUTATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de presentacion calculo.",
            default_message_en="Raised when a builder cannot evaluate a formula casilla.",
            default_message_hu="Beadas szamitas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.filing._errors.FilingDraftError",
        ErrorCode(
            code="ERROR_FILING_DRAFT",
            category=ErrorCategory.ERROR,
            default_message_es="Error del borrador de presentacion.",
            default_message_en="Base class for filing-draft errors.",
            default_message_hu="Beadasi tervezet hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.filing._errors.FilingImportError",
        ErrorCode(
            code="FAIL_FILING_IMPORT",
            category=ErrorCategory.FAIL,
            default_message_es="Error de presentacion importacion.",
            default_message_en="Raised when importing a filing from a justificante PDF fails.",
            default_message_hu="Beadas importalas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.filing._errors.FilingValidationError",
        ErrorCode(
            code="INTEGRITY_FILING_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion de presentacion fallo.",
            default_message_en="Raised when validation surfaces a blocking finding.",
            default_message_hu="Beadas ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.attachments._errors.AttachmentError",
        ErrorCode(
            code="ERROR_FINANCIAL_ATTACHMENTS_ATTACHMENT",
            category=ErrorCategory.ERROR,
            default_message_es="Error de adjunto.",
            default_message_en="Base error for every attachment-service failure.",
            default_message_hu="Melleklet hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.attachments._errors.AttachmentNotFoundError",
        ErrorCode(
            code="ERROR_FINANCIAL_ATTACHMENTS_ATTACHMENT_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro adjunto.",
            default_message_en="Raised when a manifest or blob lookup targets a missing attachment.",
            default_message_hu="Melleklet nem talalhato.",
            default_suggestion="aeat attachments list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.attachments._errors.AttachmentPersistenceError",
        ErrorCode(
            code="FAIL_FINANCIAL_ATTACHMENTS_ATTACHMENT_PERSISTENCE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo persistir adjunto.",
            default_message_en="The attachment store could not read or write attachment bytes or manifests.",
            default_message_hu="Melleklet mentese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.attachments._errors.AttachmentValidationError",
        ErrorCode(
            code="INTEGRITY_FINANCIAL_ATTACHMENTS_ATTACHMENT_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion de adjunto fallo.",
            default_message_en="Raised when an attachment payload fails domain validation.",
            default_message_hu="Melleklet ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.invoices._errors.InvoiceCatalogueError",
        ErrorCode(
            code="ERROR_FINANCIAL_INVOICES_INVOICE_CATALOGUE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de factura catalogo.",
            default_message_en="Raised when an invoice catalogue is invalid or inconsistent.",
            default_message_hu="Szamla katalogus hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.invoices._errors.InvoiceError",
        ErrorCode(
            code="ERROR_FINANCIAL_INVOICES_INVOICE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de factura.",
            default_message_en="Base error for every invoice-catalogue failure.",
            default_message_hu="Szamla hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.invoices._errors.InvoiceLinkError",
        ErrorCode(
            code="ERROR_FINANCIAL_INVOICES_INVOICE_LINK",
            category=ErrorCategory.ERROR,
            default_message_es="Error de factura enlace.",
            default_message_en="Raised when a bidirectional invoice/transaction link cannot proceed.",
            default_message_hu="Szamla kapcsolat hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.invoices._errors.InvoiceLinkInconsistencyError",
        ErrorCode(
            code="ERROR_FINANCIAL_INVOICES_INVOICE_LINK_INCONSISTENCY",
            category=ErrorCategory.ERROR,
            default_message_es="Error de factura enlace inconsistencia.",
            default_message_en="Raised when a bidirectional link leaves the two catalogues out of sync.",
            default_message_hu="Szamla kapcsolat kovetkezetlenseg hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.invoices._errors.InvoiceNotFoundError",
        ErrorCode(
            code="ERROR_FINANCIAL_INVOICES_INVOICE_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro factura.",
            default_message_en="Raised when a catalogue lookup targets a missing invoice.",
            default_message_hu="Szamla nem talalhato.",
            default_suggestion="aeat financial invoices list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.invoices._errors.InvoicePersistenceError",
        ErrorCode(
            code="FAIL_FINANCIAL_INVOICES_INVOICE_PERSISTENCE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo persistir factura.",
            default_message_en="Raised when invoice catalogue persistence cannot be completed.",
            default_message_hu="Szamla mentese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.financial.providers._base.FinancialProviderError",
        ErrorCode(
            code="ERROR_FINANCIAL_PROVIDERS_BASE_FINANCIAL_PROVIDER",
            category=ErrorCategory.ERROR,
            default_message_es="Error de financiero proveedor.",
            default_message_en="Base error raised by financial-ingest providers.",
            default_message_hu="Penzugyi szolgaltato hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.financial.providers._base.InvalidFinancialSourceError",
        ErrorCode(
            code="ERROR_FINANCIAL_PROVIDERS_BASE_INVALID_FINANCIAL_SOURCE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de invalid financiero origen.",
            default_message_en="Raised when a source document is unreadable or structurally invalid.",
            default_message_hu="Invalid penzugyi forras hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.financial.providers._base.UnsupportedFinancialSourceError",
        ErrorCode(
            code="ERROR_FINANCIAL_PROVIDERS_BASE_UNSUPPORTED_FINANCIAL_SOURCE",
            category=ErrorCategory.ERROR,
            default_message_es="No hay un proveedor compatible para el origen financiero indicado.",
            default_message_en="Raised when no provider can interpret a source document.",
            default_message_hu="A megadott penzugyi forrashoz nincs tamogatott szolgaltato.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.transactions._errors.TransactionCatalogueError",
        ErrorCode(
            code="ERROR_FINANCIAL_TRANSACTIONS_TRANSACTION_CATALOGUE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de transaccion catalogo.",
            default_message_en="Raised when a transaction catalogue is invalid or inconsistent.",
            default_message_hu="Tranzakcio katalogus hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.transactions._errors.TransactionError",
        ErrorCode(
            code="ERROR_FINANCIAL_TRANSACTIONS_TRANSACTION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de transaccion.",
            default_message_en="Base error for every transaction-catalogue failure.",
            default_message_hu="Tranzakcio hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.transactions._errors.TransactionNotFoundError",
        ErrorCode(
            code="ERROR_FINANCIAL_TRANSACTIONS_TRANSACTION_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro transaccion.",
            default_message_en="Raised when a catalogue lookup targets a missing transaction.",
            default_message_hu="Tranzakcio nem talalhato.",
            default_suggestion="aeat financial txs list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.transactions._errors.TransactionPersistenceError",
        ErrorCode(
            code="FAIL_FINANCIAL_TRANSACTIONS_TRANSACTION_PERSISTENCE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo persistir transaccion.",
            default_message_en="Raised when catalogue persistence cannot be completed.",
            default_message_hu="Tranzakcio mentese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.aggregation._errors.AggregationError",
        ErrorCode(
            code="ERROR_FINANCIAL_AGGREGATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de agregacion financiera.",
            default_message_en="Base class for financial T6 aggregation failures.",
            default_message_hu="Penzugyi osszesitesi hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.aggregation._errors.AggregationPeriodError",
        ErrorCode(
            code="ERROR_FINANCIAL_AGGREGATION_PERIOD",
            category=ErrorCategory.ERROR,
            default_message_es="El periodo de agregacion no es valido.",
            default_message_en="The aggregation period is invalid or ambiguous.",
            default_message_hu="Az osszesitesi idoszak ervenytelen vagy ketertelmu.",
            default_suggestion="aeat financial aggregate --modelo 130 --period 2025-Q1",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.aggregation._errors.AggregationUnsupportedModeloError",
        ErrorCode(
            code="REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO",
            category=ErrorCategory.REFUSED,
            default_message_es="Este modelo aun no tiene agregacion financiera.",
            default_message_en="This modelo does not yet have financial aggregation support.",
            default_message_hu="Ehhez a nyomtatvanyhoz meg nincs penzugyi osszesites.",
            default_suggestion="aeat financial aggregate --modelo 130 --period 2025-Q1",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.aggregation._errors.AggregationMissingClassificationError",
        ErrorCode(
            code="REFUSED_FINANCIAL_AGGREGATION_MISSING_CLASSIFICATION",
            category=ErrorCategory.REFUSED,
            default_message_es="Faltan clasificaciones de transacciones.",
            default_message_en="One or more transactions still need classification.",
            default_message_hu="Egy vagy tobb tranzakcio meg besorolasra var.",
            default_suggestion="aeat financial txs list --state NOT_YET_PROCESSED",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.aggregation._errors.AggregationCategoryCoverageError",
        ErrorCode(
            code="REFUSED_FINANCIAL_AGGREGATION_CATEGORY_COVERAGE",
            category=ErrorCategory.REFUSED,
            default_message_es="Una transaccion no tiene cobertura de categoria fiscal.",
            default_message_en="A transaction has no fiscal category coverage.",
            default_message_hu="Egy tranzakciohoz nincs adozasi kategoria-lefedettseg.",
            default_suggestion="aeat financial txs list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.aggregation._errors.AggregationCasillaMappingError",
        ErrorCode(
            code="REFUSED_FINANCIAL_AGGREGATION_CASILLA_MAPPING",
            category=ErrorCategory.REFUSED,
            default_message_es="No hay mapeo de casilla util para la agregacion.",
            default_message_en="No usable casilla mapping exists for the aggregation.",
            default_message_hu="Nincs hasznalhato casilla-lekepezes az osszesiteshez.",
            default_suggestion="aeat categories list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.usage_ratios._errors.UsageRatioError",
        ErrorCode(
            code="ERROR_FINANCIAL_USAGE_RATIOS_USAGE_RATIO",
            category=ErrorCategory.ERROR,
            default_message_es="Error de uso ratio.",
            default_message_en="Base error for every usage-ratio profile failure.",
            default_message_hu="Hasznalat arany hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.usage_ratios._errors.UsageRatioPersistenceError",
        ErrorCode(
            code="FAIL_FINANCIAL_USAGE_RATIOS_USAGE_RATIO_PERSISTENCE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo persistir uso ratio.",
            default_message_en="The usage-ratio profile could not be read or written.",
            default_message_hu="Hasznalat arany mentese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.vat.errors.VatCatalogueError",
        ErrorCode(
            code="ERROR_FINANCIAL_VAT_CATALOGUE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de iva catalogo.",
            default_message_en="Raised when a VAT catalogue cannot be loaded or is malformed.",
            default_message_hu="Afa katalogus hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.vat.errors.VatCategoryNotFoundError",
        ErrorCode(
            code="ERROR_FINANCIAL_VAT_CATEGORY_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro la categoria de IVA solicitada.",
            default_message_en="The requested VAT category could not be found in the catalogue.",
            default_message_hu="A kert afa kategoria nem talalhato.",
            default_suggestion="aeat vat categories list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.vat.errors.VatClassificationError",
        ErrorCode(
            code="ERROR_FINANCIAL_VAT_CLASSIFICATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de iva clasificacion.",
            default_message_en="The VAT classifier could not produce a deterministic match.",
            default_message_hu="Afa besorolas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.vat.errors.VatError",
        ErrorCode(
            code="ERROR_FINANCIAL_VAT",
            category=ErrorCategory.ERROR,
            default_message_es="Error de iva.",
            default_message_en="Base class for VAT-related errors.",
            default_message_hu="Afa hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.vat.errors.VatRateNotFoundError",
        ErrorCode(
            code="ERROR_FINANCIAL_VAT_RATE_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro iva tipo.",
            default_message_en="The requested VAT rate could not be resolved.",
            default_message_hu="Afa kulcs nem talalhato.",
            default_suggestion="aeat vat rates list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.vat.errors.VatRateOverlapError",
        ErrorCode(
            code="ERROR_FINANCIAL_VAT_RATE_OVERLAP",
            category=ErrorCategory.ERROR,
            default_message_es="Error de iva tipo solapamiento.",
            default_message_en="Two VAT rate records overlap in an active time window.",
            default_message_hu="Afa kulcs atfedes hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.i18n.TranslationError",
        ErrorCode(
            code="ERROR_I18N_TRANSLATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de traduccion.",
            default_message_en="Raised when a required translation is missing or invalid.",
            default_message_hu="Forditas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.justificante._errors.JustificanteCsvNotFoundError",
        ErrorCode(
            code="ERROR_JUSTIFICANTE_CSV_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro justificante csv.",
            default_message_en="Raised when a PDF does not contain a C\xf3digo Seguro de Verificaci\xf3n.",
            default_message_hu="Igazolas csv nem talalhato.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.justificante._errors.JustificanteError",
        ErrorCode(
            code="ERROR_JUSTIFICANTE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de justificante.",
            default_message_en="Base class for every justificante-related failure.",
            default_message_hu="Igazolas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.justificante._errors.JustificanteParseError",
        ErrorCode(
            code="FAIL_JUSTIFICANTE_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo analizar justificante.",
            default_message_en="The PDF could not be parsed into a justificante record.",
            default_message_hu="Igazolas feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.justificante._errors.JustificanteVerificationError",
        ErrorCode(
            code="INTEGRITY_JUSTIFICANTE_VERIFICATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La verificacion de justificante fallo.",
            default_message_en="Raised when the live CSV verification round-trip fails.",
            default_message_hu="Igazolas ellenorzese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.llm._errors.LLMCacheError",
        ErrorCode(
            code="FAIL_LLM_L_M_CACHE",
            category=ErrorCategory.FAIL,
            default_message_es="Error de cache del cliente LLM.",
            default_message_en="Raised when a cache entry cannot be read, written, or parsed.",
            default_message_hu="Az LLM gyorsitotar hibas.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.llm._errors.LLMConfigError",
        ErrorCode(
            code="FAIL_LLM_L_M_CONFIG",
            category=ErrorCategory.FAIL,
            default_message_es="Error de configuracion del cliente LLM.",
            default_message_en="Raised when the LLM client configuration is invalid or incomplete.",
            default_message_hu="Az LLM kliens beallitasa hibas vagy hianyos.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.llm._errors.LLMError",
        ErrorCode(
            code="FAIL_LLM_L_M",
            category=ErrorCategory.FAIL,
            default_message_es="Error del subsistema LLM.",
            default_message_en="Base exception for LLM package failures.",
            default_message_hu="LLM alrendszerhiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.llm._errors.LLMProviderError",
        ErrorCode(
            code="FAIL_LLM_L_M_PROVIDER",
            category=ErrorCategory.FAIL,
            default_message_es="Error del proveedor LLM.",
            default_message_en="Raised when a provider returns an unrecoverable error.",
            default_message_hu="Az LLM szolgaltato helyrehozhatatlan hibaval valaszolt.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.llm._errors.LLMRateLimitError",
        ErrorCode(
            code="FAIL_LLM_L_M_RATE_LIMIT",
            category=ErrorCategory.FAIL,
            default_message_es="El proveedor LLM rechazo la solicitud por limite de uso.",
            default_message_en="Raised when a provider rejects a request because of rate limits.",
            default_message_hu="Az LLM szolgaltato sebessegkorlat miatt utasitotta el a kerest.",
            default_suggestion=None,
            retryable=True,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.manuals.errors.ManifestError",
        ErrorCode(
            code="INTEGRITY_MANUALS_MANIFEST",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de manifiesto.",
            default_message_en="The manuals manifest could not be parsed.",
            default_message_hu="Manifestum hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.manuals.errors.ManualError",
        ErrorCode(
            code="ERROR_MANUALS_MANUAL",
            category=ErrorCategory.ERROR,
            default_message_es="Error de manual.",
            default_message_en="Base class for manual-corpus errors.",
            default_message_hu="Kezikonyv hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.manuals.errors.ManualNotFoundError",
        ErrorCode(
            code="ERROR_MANUALS_MANUAL_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro manual.",
            default_message_en="Raised when a requested manual/year/part is missing on disk.",
            default_message_hu="Kezikonyv nem talalhato.",
            default_suggestion="aeat manual fetch",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.manuals.errors.ManualParseError",
        ErrorCode(
            code="FAIL_MANUALS_MANUAL_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo analizar manual.",
            default_message_en="Raised when a committed manual record fails schema validation.",
            default_message_hu="Kezikonyv feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.manuals.errors.ManualReviewRequiredError",
        ErrorCode(
            code="ERROR_MANUALS_MANUAL_REVIEW_REQUIRED",
            category=ErrorCategory.ERROR,
            default_message_es="Error de manual revision requerido.",
            default_message_en="Raised when a persisted record lacks reviewer metadata.",
            default_message_hu="Kezikonyv ellenorzes szukseges hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.manuals.errors.RuleExtractionError",
        ErrorCode(
            code="ERROR_MANUALS_RULE_EXTRACTION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de regla extraction.",
            default_message_en="The rule-extraction step is not available yet in this CLI phase.",
            default_message_hu="Szabaly extraction hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.modelos._errors.ModeloRegistryError",
        ErrorCode(
            code="ERROR_MODELS_MODELO_REGISTRY",
            category=ErrorCategory.ERROR,
            default_message_es="Error de modelo registro.",
            default_message_en="Base class for modelo-registry errors.",
            default_message_hu="Modelo jegyzek hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.modelos._errors.RegistryIntegrityError",
        ErrorCode(
            code="INTEGRITY_MODELS_REGISTRY_INTEGRITY",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de registro integridad.",
            default_message_en="Raised at import time when the registry fails a structural check.",
            default_message_hu="Jegyzek integritas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.modelos._errors.UnknownModeloError",
        ErrorCode(
            code="ERROR_MODELS_UNKNOWN_MODELO",
            category=ErrorCategory.ERROR,
            default_message_es="Modelo desconocido.",
            default_message_en="The requested modelo is unknown.",
            default_message_hu="Ismeretlen modelo.",
            default_suggestion="aeat modelos list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.normatives.errors.NormativeError",
        ErrorCode(
            code="ERROR_NORMATIVES_NORMATIVE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de normativa.",
            default_message_en="Base class for normative lookup errors.",
            default_message_hu="Jogszabaly hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.normatives.errors.NormativeNotFoundError",
        ErrorCode(
            code="ERROR_NORMATIVES_NORMATIVE_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro normativa.",
            default_message_en="Raised when a requested normative or article is missing.",
            default_message_hu="Jogszabaly nem talalhato.",
            default_suggestion="aeat normatives list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.normatives.errors.NormativeParseError",
        ErrorCode(
            code="FAIL_NORMATIVES_NORMATIVE_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo analizar normativa.",
            default_message_en="Raised when a committed normative JSON fails schema validation.",
            default_message_hu="Jogszabaly feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.observability._errors.AeatCorpusDriftError",
        ErrorCode(
            code="INTEGRITY_OBSERVABILITY_AEAT_CORPUS_DRIFT",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de aeat corpus drift.",
            default_message_en="The normative corpus fingerprint no longer matches the replay metadata.",
            default_message_hu="Aeat korpusz drift hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.observability._errors.RunContextMissingError",
        ErrorCode(
            code="INTERNAL_OBSERVABILITY_RUN_CONTEXT_MISSING",
            category=ErrorCategory.INTERNAL,
            default_message_es="Error de ejecucion contexto faltante.",
            default_message_en="Raised when an observability call is made outside an active run context.",
            default_message_hu="Futas kontextus hianyzik hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.observability._errors.RunTraceValidationError",
        ErrorCode(
            code="INTEGRITY_OBSERVABILITY_RUN_TRACE_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion de ejecucion traza fallo.",
            default_message_en="The persisted run trace artifacts failed validation.",
            default_message_hu="Futas nyomvonal ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.portals._errors.PortalIntegrityError",
        ErrorCode(
            code="INTEGRITY_PORTALS_PORTAL_INTEGRITY",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de portal integridad.",
            default_message_en="Raised at import time when the registry fails a structural check.",
            default_message_hu="Portal integritas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.portals._errors.PortalRegistryError",
        ErrorCode(
            code="ERROR_PORTALS_PORTAL_REGISTRY",
            category=ErrorCategory.ERROR,
            default_message_es="Error de portal registro.",
            default_message_en="Base class for portal-registry errors.",
            default_message_hu="Portal jegyzek hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.portals._errors.UnknownPortalError",
        ErrorCode(
            code="ERROR_PORTALS_UNKNOWN_PORTAL",
            category=ErrorCategory.ERROR,
            default_message_es="Portal desconocido.",
            default_message_en="The requested portal is unknown.",
            default_message_hu="Ismeretlen portal.",
            default_suggestion="aeat portals list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile.errors.AssetRecordError",
        ErrorCode(
            code="ERROR_PROFILE_ASSET_RECORD",
            category=ErrorCategory.ERROR,
            default_message_es="El registro de activo no es valido.",
            default_message_en="The asset record is invalid.",
            default_message_hu="Az eszkozrekord ervenytelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile.errors.AmortizationLedgerError",
        ErrorCode(
            code="ERROR_PROFILE_AMORTIZATION_LEDGER",
            category=ErrorCategory.ERROR,
            default_message_es="El libro de amortizacion no es valido.",
            default_message_en="The amortization ledger is invalid.",
            default_message_hu="Az amortizacios naplo ervenytelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile.errors.InventoryLedgerError",
        ErrorCode(
            code="ERROR_PROFILE_INVENTORY_LEDGER",
            category=ErrorCategory.ERROR,
            default_message_es="El libro de inventario no es valido.",
            default_message_en="The inventory ledger is invalid.",
            default_message_hu="A keszletnaplo ervenytelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile.errors.LIFOForbiddenError",
        ErrorCode(
            code="REFUSED_PROFILE_INVENTORY_LIFO",
            category=ErrorCategory.REFUSED,
            default_message_es="LIFO no esta admitido para este libro fiscal.",
            default_message_en="LIFO is not admitted for this tax ledger.",
            default_message_hu="A LIFO nem engedelyezett ebben az adonaploban.",
            default_suggestion="aeat data ledgers inventory create --help",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile.errors.BasisCapExceededError",
        ErrorCode(
            code="INTEGRITY_PROFILE_AMORTIZATION_BASIS_CAP",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La amortizacion acumulada supera la base de coste.",
            default_message_en="Cumulative amortization exceeds the cost basis.",
            default_message_hu="A halmozott amortizacio meghaladja a bekerulesi erteket.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.review._errors.ReviewError",
        ErrorCode(
            code="ERROR_REVIEW",
            category=ErrorCategory.ERROR,
            default_message_es="Error de revision.",
            default_message_en="Base class for review-related errors.",
            default_message_hu="Ellenorzes hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.review._errors.ReviewKindReservedError",
        ErrorCode(
            code="REFUSED_REVIEW_KIND_RESERVED",
            category=ErrorCategory.REFUSED,
            default_message_es="El tipo de revisi\xf3n solicitado est\xe1 reservado.",
            default_message_en="The requested review kind is reserved.",
            default_message_hu="A k\xe9rt ellen\u0151rz\xe9si t\xedpus fenntartott.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.review._errors.ReviewSourceLoadError",
        ErrorCode(
            code="FAIL_REVIEW_SOURCE_LOAD",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo cargar revision origen.",
            default_message_en="Raised when a source disk file is present but cannot be parsed.",
            default_message_hu="Ellenorzes forras betoltese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.schema._errors.SchemaCacheError",
        ErrorCode(
            code="FAIL_SCHEMA_CACHE",
            category=ErrorCategory.FAIL,
            default_message_es="Error de cache del esquema.",
            default_message_en="Raised when on-disk schema persistence fails.",
            default_message_hu="A sema gyorsitotar hibas.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.schema._errors.SchemaError",
        ErrorCode(
            code="ERROR_SCHEMA",
            category=ErrorCategory.ERROR,
            default_message_es="Error de esquema.",
            default_message_en="Base class for schema-processing errors.",
            default_message_hu="Sema hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.schema._errors.SchemaEvaluationError",
        ErrorCode(
            code="ERROR_SCHEMA_EVALUATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de esquema evaluacion.",
            default_message_en="The schema formula AST could not be evaluated.",
            default_message_hu="Sema ertekeles hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.schema._errors.SchemaExtractionError",
        ErrorCode(
            code="ERROR_SCHEMA_EXTRACTION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de extraccion de esquema.",
            default_message_en="The schema extractor could not parse its source.",
            default_message_hu="A sema kinyerese sikertelen.",
            default_suggestion="aeat schema refresh",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.schema._errors.SchemaValidationError",
        ErrorCode(
            code="INTEGRITY_SCHEMA_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion de esquema fallo.",
            default_message_en="A cached modelo JSON document failed validation.",
            default_message_hu="Sema ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.sede._errors.ExpedienteNotFoundError",
        ErrorCode(
            code="ERROR_SEDE_EXPEDIENTE_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="No se encontro expediente.",
            default_message_en="Raised when no expediente matches the requested filter.",
            default_message_hu="Ugy nem talalhato.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.sede._errors.JustificanteFetchError",
        ErrorCode(
            code="FAIL_SEDE_JUSTIFICANTE_FETCH",
            category=ErrorCategory.FAIL,
            default_message_es="Error de justificante descarga.",
            default_message_en="Raised when the CSV-keyed PDF download fails or is malformed.",
            default_message_hu="Igazolas letoltes hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.sede._errors.SedeError",
        ErrorCode(
            code="ERROR_SEDE",
            category=ErrorCategory.ERROR,
            default_message_es="Error de sede.",
            default_message_en="Base class for post-auth AEAT sede errors.",
            default_message_hu="Sede hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.sede._errors.SedeNavigationError",
        ErrorCode(
            code="ERROR_SEDE_NAVIGATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de sede navegacion.",
            default_message_en="Raised when a navigation step fails (goto, click, wait).",
            default_message_hu="Sede navigacio hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.outbound.aeat.sede._errors.SedeParseError",
        ErrorCode(
            code="FAIL_SEDE_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo analizar sede.",
            default_message_en="Raised when the captured HTML cannot be parsed to a record.",
            default_message_hu="Sede feldolgozasa sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile._errors.TaxResidenceProfileError",
        ErrorCode(
            code="ERROR_PROFILE_TAX_RESIDENCE",
            category=ErrorCategory.ERROR,
            default_message_es="Error del perfil de residencia fiscal.",
            default_message_en="Tax-residence profile error.",
            default_message_hu="Adoilletosegi profil hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile._errors.ProfileNotConfiguredError",
        ErrorCode(
            code="REFUSED_PROFILE_NOT_CONFIGURED",
            category=ErrorCategory.REFUSED,
            default_message_es="No hay perfil de residencia fiscal configurado para RENTA.",
            default_message_en="No tax-residence profile is configured for RENTA.",
            default_message_hu="Nincs beallitva RENTA adoilletosegi profil.",
            default_suggestion="aeat profile set tax-region <ccaa>",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.profile._errors.ForalRegimeError",
        ErrorCode(
            code="REFUSED_PROFILE_FORAL_REGIME",
            category=ErrorCategory.REFUSED,
            default_message_es="El regimen foral solicitado se gestiona en #424.",
            default_message_en="The requested foral regime is handled in #424.",
            default_message_hu="A kert foralis rendszert a #424 kezeli.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.sanitizer._errors.AlreadySanitizedError",
        ErrorCode(
            code="REFUSED_SANITIZER_ALREADY_SANITIZED",
            category=ErrorCategory.REFUSED,
            default_message_es="El PDF ya esta sanitizado.",
            default_message_en=(
                "Raised when the source SHA already lives in SANITIZED_SHAS; bypass with --allow-already-sanitized."
            ),
            default_message_hu="A PDF mar sanitizalt.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.sanitizer._errors.SanitizationError",
        ErrorCode(
            code="ERROR_SANITIZER",
            category=ErrorCategory.ERROR,
            default_message_es="Error del sanitizador.",
            default_message_en="Base class for the AEAT PDF sanitiser failures.",
            default_message_hu="Sanitizalo hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.sanitizer._errors.SanitizerSourceParseError",
        ErrorCode(
            code="FAIL_SANITIZER_SOURCE_PARSE",
            category=ErrorCategory.FAIL,
            default_message_es="No se pudo abrir el PDF de origen.",
            default_message_en="Raised when pikepdf cannot open the source PDF (corrupt or password-protected).",
            default_message_hu="Forras PDF megnyitas sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.sanitizer._errors.SignaturePresentError",
        ErrorCode(
            code="REFUSED_SANITIZER_SIGNATURE_PRESENT",
            category=ErrorCategory.REFUSED,
            default_message_es="El PDF tiene una firma digital y no se puede sanitizar.",
            default_message_en=(
                "Raised when the source PDF carries a digital signature; sanitisation would invalidate it."
            ),
            default_message_hu="A PDF digitalis alairast tartalmaz.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.inbound.sanitizer._errors.UnknownSurfaceError",
        ErrorCode(
            code="ERROR_SANITIZER_UNKNOWN_SURFACE",
            category=ErrorCategory.ERROR,
            default_message_es="Superficie del sanitizador desconocida.",
            default_message_en=(
                "Raised when a TokenMap entry references a surface category the pipeline does not handle."
            ),
            default_message_hu="Ismeretlen sanitizalo felulet.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.setup._errors.SetupAbortedError",
        ErrorCode(
            code="REFUSED_SETUP_ABORTED",
            category=ErrorCategory.REFUSED,
            default_message_es="La configuracion fue cancelada por el usuario.",
            default_message_en="Raised when the user explicitly aborts the wizard.",
            default_message_hu="A beallitasi varazslo megszakadt.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.setup._errors.SetupAnswersError",
        ErrorCode(
            code="ERROR_SETUP_ANSWERS",
            category=ErrorCategory.ERROR,
            default_message_es="Error de configuracion respuestas.",
            default_message_en="The setup answers payload could not be loaded or validated.",
            default_message_hu="Beallitas valaszok hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.setup._errors.SetupError",
        ErrorCode(
            code="ERROR_SETUP",
            category=ErrorCategory.ERROR,
            default_message_es="Error de configuracion.",
            default_message_en="Base class for every setup-wizard error.",
            default_message_hu="Beallitas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.setup._errors.SetupVerifyError",
        ErrorCode(
            code="ERROR_SETUP_VERIFY",
            category=ErrorCategory.ERROR,
            default_message_es="Error de configuracion verificar.",
            default_message_en="Raised when the verify step finds an ERROR-severity problem.",
            default_message_hu="Beallitas ellenoriz hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.identity._documents.IdentityError",
        ErrorCode(
            code="INTEGRITY_IDENTITY_DOCUMENT",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Documento de identidad no valido.",
            default_message_en="The candidate string is not a valid NIF, NIE, or CIF.",
            default_message_hu="Ervenytelen azonosito okmany.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.BlobIntegrityError",
        ErrorCode(
            code="INTEGRITY_STORAGE_BLOB",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Integridad del blob comprometida.",
            default_message_en="A blob's on-disk SHA-256 disagrees with its manifest.",
            default_message_hu="Blob integritasa serult.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.BlobNotFoundError",
        ErrorCode(
            code="FAIL_STORAGE_BLOB_NOT_FOUND",
            category=ErrorCategory.FAIL,
            default_message_es="Blob no encontrado.",
            default_message_en="No blob exists at the requested reference.",
            default_message_hu="A blob nem talalhato.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.ClassificationError",
        ErrorCode(
            code="INTEGRITY_STORAGE_CLASSIFICATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Clase de sensibilidad incompatible con el repositorio.",
            default_message_en="The declared sensitivity class is incompatible with this repository.",
            default_message_hu="Erzekenysegi osztaly nem kompatibilis.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.DecryptionError",
        ErrorCode(
            code="INTEGRITY_STORAGE_DECRYPTION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error al descifrar el registro almacenado.",
            default_message_en="AEAD decryption failed (tag mismatch or malformed ciphertext).",
            default_message_hu="A tarolt rekord visszafejtese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.EncryptionError",
        ErrorCode(
            code="INTEGRITY_STORAGE_ENCRYPTION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error de cifrado de almacenamiento.",
            default_message_en="Base class for AEAD encryption / decryption failures.",
            default_message_hu="Titkositasi hiba a tarolasban.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.EnvelopeVersionError",
        ErrorCode(
            code="INTEGRITY_STORAGE_ENVELOPE_VERSION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Version de envoltura incompatible.",
            default_message_en="The on-disk envelope schema version is incompatible with this consumer.",
            default_message_hu="A boriték verzioja nem kompatibilis.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.KeyDerivationError",
        ErrorCode(
            code="INTEGRITY_STORAGE_KEY_DERIVATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Error al derivar la clave de cifrado.",
            default_message_en="Key derivation (HKDF or scrypt) failed.",
            default_message_hu="A kulcsszarmaztatas sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.locks.LockAcquisitionError",
        ErrorCode(
            code="LOCKED_STORAGE_LOCK_ACQUISITION",
            category=ErrorCategory.LOCKED,
            default_message_es="No se pudo adquirir el bloqueo de archivo exclusivo.",
            default_message_en="Failed to acquire the exclusive file lock within the configured timeout.",
            default_message_hu="A fajl zarolas nem sikerult.",
            default_suggestion=None,
            retryable=True,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.KeyringUnavailableError",
        ErrorCode(
            code="AUTH_STORAGE_KEYRING_UNAVAILABLE",
            category=ErrorCategory.AUTH,
            default_message_es="El llavero del sistema operativo no esta disponible.",
            default_message_en="The OS keychain backend is unusable; no master key could be retrieved.",
            default_message_hu="Az operacios rendszer kulcskezeloje nem elerheto.",
            default_suggestion="aeat doctor",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.MasterKeyUnavailableError",
        ErrorCode(
            code="AUTH_STORAGE_MASTER_KEY_UNAVAILABLE",
            category=ErrorCategory.AUTH,
            default_message_es="No se puede acceder a la clave maestra de almacenamiento.",
            default_message_en="No master key could be acquired from the configured backend.",
            default_message_hu="Nem sikerult mester kulcsot beszerezni.",
            default_suggestion="aeat doctor",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.MasterKeyKdfVersionError",
        ErrorCode(
            code="AUTH_STORAGE_MASTER_KEY_KDF_VERSION",
            category=ErrorCategory.AUTH,
            default_message_es=(
                "El archivo master.kdf usa una version de KDF que esta build no admite; ejecute la migracion."
            ),
            default_message_en=("master.kdf declares a KDF version this build cannot consume; run the migration tool."),
            default_message_hu=("A master.kdf egy nem tamogatott KDF-verziot deklaral; futtassa a migracios eszkozt."),
            default_suggestion="aeat security migrate-master-key-kdf",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.MasterKeyKeychainLockedError",
        ErrorCode(
            code="AUTH_STORAGE_MASTER_KEY_KEYCHAIN_LOCKED",
            category=ErrorCategory.AUTH,
            default_message_es=("El llavero del sistema esta bloqueado; desbloquee el llavero y reintente."),
            default_message_en=("OS keychain is locked; unlock it (Touch ID / Hello / desktop-wallet) and retry."),
            default_message_hu=("Az operacios rendszer kulcstartoja zarolva; oldja fel es probalja ujra."),
            # No CLI command can unlock the OS keychain on the operator's
            # behalf; the runbook hint lives in the message itself.
            default_suggestion=None,
            retryable=True,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.MasterKeyPassphraseMismatchError",
        ErrorCode(
            code="AUTH_STORAGE_MASTER_KEY_PASSPHRASE_MISMATCH",
            category=ErrorCategory.AUTH,
            default_message_es=("La frase de paso no desbloqueo la clave maestra; verifique e intente de nuevo."),
            default_message_en=("Passphrase did not unlock the master key; verify and retry."),
            default_message_hu=("A jelszo nem oldotta fel a mester kulcsot; ellenorizze es probalja ujra."),
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.MasterKeyMaterialMissingError",
        ErrorCode(
            code="AUTH_STORAGE_MASTER_KEY_MATERIAL_MISSING",
            category=ErrorCategory.AUTH,
            default_message_es=("No existe material de clave maestra; ejecute la provision."),
            default_message_en=("No master-key material exists; run the security-provisioning command."),
            default_message_hu=("Nincs mester kulcs anyag; futtassa a biztonsagi provisioning parancsot."),
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.UnsecuredModeRefusedError",
        ErrorCode(
            code="REFUSED_STORAGE_UNSECURED_MODE",
            category=ErrorCategory.REFUSED,
            default_message_es=(
                "Modo no cifrado rechazado: requiere AEAT_ALLOW_UNENCRYPTED=1 y es incompatible con un NIF real."
            ),
            default_message_en=(
                "Unsecured mode refused: requires AEAT_ALLOW_UNENCRYPTED=1 and is incompatible with a real NIF."
            ),
            default_message_hu=(
                "Nem biztonsagos mod elutasitva: AEAT_ALLOW_UNENCRYPTED=1 szukseges es nem hasznalhato valodi NIF-fel."
            ),
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.MigrationError",
        ErrorCode(
            code="FAIL_STORAGE_MIGRATION",
            category=ErrorCategory.FAIL,
            default_message_es="Error de migracion.",
            default_message_en="Raised when an Alembic migration operation fails.",
            default_message_hu="Migracio hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.NonceCollisionError",
        ErrorCode(
            code="INTEGRITY_STORAGE_NONCE_COLLISION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Colision de nonce detectada.",
            default_message_en="Defensive AEAD nonce-uniqueness invariant violation.",
            default_message_hu="Nonce utkozes eszlelve.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.PathContainmentError",
        ErrorCode(
            code="INTEGRITY_STORAGE_PATH_CONTAINMENT",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La ruta computada se sale de su raiz configurada.",
            default_message_en="A computed path escapes its configured root directory.",
            default_message_hu="A szamitott utvonal kilep a konfiguralt gyokerbol.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.PersistenceError",
        ErrorCode(
            code="FAIL_STORAGE_PERSISTENCE",
            category=ErrorCategory.FAIL,
            default_message_es="Error de persistencia segura.",
            default_message_en="Base class for the secure-persistence-foundation error tree.",
            default_message_hu="Biztonsagos tarolasi hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.RepositoryError",
        ErrorCode(
            code="FAIL_STORAGE_REPOSITORY",
            category=ErrorCategory.FAIL,
            default_message_es="Error de repositorio.",
            default_message_en="A repository operation failed due to lookup, integrity, or persistence errors.",
            default_message_hu="Tarolo hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.RetentionPolicyError",
        ErrorCode(
            code="INTEGRITY_STORAGE_RETENTION_POLICY",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Politica de retencion violada por el registro.",
            default_message_en="A persisted record's retention metadata violates its classification policy.",
            default_message_hu="A megorzesi szabalyzat sertese.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.CorpusManifestError",
        ErrorCode(
            code="INTEGRITY_STORAGE_CORPUS_MANIFEST",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Manifiesto de corpus invalido o estructuralmente roto.",
            default_message_en="A corpus manifest is structurally invalid or its version is unsupported.",
            default_message_hu="A korpusz manifeszt strukturalisan ervenytelen.",
            default_suggestion="aeat security verify-corpus --regenerate",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.CorpusManifestTamperError",
        ErrorCode(
            code="INTEGRITY_STORAGE_CORPUS_MANIFEST_TAMPER",
            category=ErrorCategory.INTEGRITY,
            default_message_es="Digesto autodeclarado del manifiesto no coincide con el cuerpo.",
            default_message_en=(
                "A corpus manifest's recorded sha256 does not match its body; the manifest may have been tampered with."
            ),
            default_message_hu="A manifeszt onaltal jelolt SHA-256 nem egyezik a tartalommal.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.CorpusManifestDriftError",
        ErrorCode(
            code="INTEGRITY_STORAGE_CORPUS_MANIFEST_DRIFT",
            category=ErrorCategory.INTEGRITY,
            default_message_es="El corpus en disco no coincide con el manifiesto.",
            default_message_en="The on-disk corpus diverges from its manifest (added / removed / changed files).",
            default_message_hu="A lemezen levo korpusz elter a manifeszttol.",
            default_suggestion="aeat security verify-corpus --regenerate",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.SecretAlreadyExistsError",
        ErrorCode(
            code="REFUSED_STORAGE_SECRET_ALREADY_EXISTS",
            category=ErrorCategory.REFUSED,
            default_message_es="Ya existe un secreto con esa clave.",
            default_message_en="A secret already exists for the given key; pass overwrite=True to replace it.",
            default_message_hu="Mar letezik a titkos kulcs.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.SecretNotFoundError",
        ErrorCode(
            code="FAIL_STORAGE_SECRET_NOT_FOUND",
            category=ErrorCategory.FAIL,
            default_message_es="Secreto no encontrado.",
            default_message_en="No secret exists at the requested key.",
            default_message_hu="A titkos kulcs nem talalhato.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.SecretStoreError",
        ErrorCode(
            code="FAIL_STORAGE_SECRET_STORE",
            category=ErrorCategory.FAIL,
            default_message_es="Error del almacen de secretos.",
            default_message_en="Base class for secret-store I/O failures.",
            default_message_hu="Titokkezelo hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.adapters.persistence.storage.errors.StorageError",
        ErrorCode(
            code="FAIL_STORAGE",
            category=ErrorCategory.FAIL,
            default_message_es="Error de almacenamiento.",
            default_message_en="Base class for storage-related errors.",
            default_message_hu="Tarolas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.access_gate._errors.SubmissionError",
        ErrorCode(
            code="ERROR_ACCESS_GATE_SUBMISSION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de política de envío.",
            default_message_en="Base class for access-gate submission policy errors.",
            default_message_hu="Hozzáférési kapu beküldési hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.access_gate._errors.SubmissionPreflightError",
        ErrorCode(
            code="ERROR_ACCESS_GATE_SUBMISSION_PREFLIGHT",
            category=ErrorCategory.ERROR,
            default_message_es="La política previa de envío rechazó la operación.",
            default_message_en="Raised when access-gate preflight rejects a submission operation.",
            default_message_hu="A hozzáférési kapu előzetes ellenőrzése elutasította a beküldést.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.access_gate._errors.LiveSubmitForbiddenError",
        ErrorCode(
            code="LOCKED_ACCESS_GATE_LIVE_SUBMIT_FORBIDDEN",
            category=ErrorCategory.LOCKED,
            default_message_es="El envío en vivo a AEAT está permanentemente prohibido.",
            default_message_en="Live AEAT submission is permanently forbidden by the access gate.",
            default_message_hu="Az élő AEAT beküldést a hozzáférési kapu véglegesen tiltja.",
            default_suggestion="aeat submission export",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.core.access_gate._errors.AeatLiveReadNotEnabledError",
        ErrorCode(
            code="REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED",
            category=ErrorCategory.REFUSED,
            default_message_es="La lectura en vivo de AEAT no está habilitada.",
            default_message_en="Live AEAT read access is not enabled.",
            default_message_hu="Az élő AEAT olvasás nincs engedélyezve.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.submission._errors.SubmissionError",
        ErrorCode(
            code="ERROR_DOMAIN_SUBMISSION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de envío de dominio.",
            default_message_en="Base class for domain submission errors.",
            default_message_hu="Domain beküldési hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.submission._errors.SubmissionPreflightError",
        ErrorCode(
            code="ERROR_DOMAIN_SUBMISSION_PREFLIGHT",
            category=ErrorCategory.ERROR,
            default_message_es="La validación previa del envío de dominio rechazó el borrador.",
            default_message_en="Raised when domain submission preflight rejects a draft.",
            default_message_hu="A domain beküldés előzetes ellenőrzése elutasította a tervezetet.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.submission._errors.LiveSubmitForbiddenError",
        ErrorCode(
            code="LOCKED_DOMAIN_LIVE_SUBMIT_FORBIDDEN",
            category=ErrorCategory.LOCKED,
            default_message_es="El envío en vivo a AEAT está permanentemente prohibido.",
            default_message_en="Live AEAT submission is permanently forbidden in the domain submission engine.",
            default_message_hu="Az élő AEAT beküldés véglegesen tiltott a domain beküldési motorban.",
            default_suggestion="aeat submission export",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.sync._errors.DivergenceClassificationError",
        ErrorCode(
            code="ERROR_SYNC_DIVERGENCE_CLASSIFICATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de divergencia clasificacion.",
            default_message_en="Raised when the classifier cannot decide the shape of a divergence.",
            default_message_hu="Elteres besorolas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.sync._errors.DivergenceRepositoryError",
        ErrorCode(
            code="ERROR_SYNC_DIVERGENCE_REPOSITORY",
            category=ErrorCategory.ERROR,
            default_message_es="Error de divergencia repositorio.",
            default_message_en="Raised when the divergence repository cannot persist or load a record.",
            default_message_hu="Elteres tarolo hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.sync._errors.HealingError",
        ErrorCode(
            code="ERROR_SYNC_HEALING",
            category=ErrorCategory.ERROR,
            default_message_es="Error de reparacion.",
            default_message_en="Raised when a healing strategy cannot apply a divergence record.",
            default_message_hu="Helyreallitas hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.sync._errors.SyncError",
        ErrorCode(
            code="ERROR_SYNC",
            category=ErrorCategory.ERROR,
            default_message_es="Error de sincronizacion.",
            default_message_en="Base class for sync-related errors.",
            default_message_hu="Szinkron hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.sync._errors.WireValidationError",
        ErrorCode(
            code="INTEGRITY_SYNC_WIRE_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validacion de wire fallo.",
            default_message_en="Raised when a live AEAT payload fails strict pydantic validation.",
            default_message_hu="Wire ervenyesitese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.sync._errors.SyncError",
        ErrorCode(
            code="ERROR_DOMAIN_SYNC",
            category=ErrorCategory.ERROR,
            default_message_es="Error de sincronización de dominio.",
            default_message_en="Base class for domain sync errors.",
            default_message_hu="Domain szinkron hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.sync._errors.WireValidationError",
        ErrorCode(
            code="INTEGRITY_DOMAIN_SYNC_WIRE_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La validación wire de dominio falló.",
            default_message_en="Raised when a domain sync payload fails strict validation.",
            default_message_hu="A domain sync wire érvényesítése sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.sync._errors.DivergenceClassificationError",
        ErrorCode(
            code="ERROR_DOMAIN_SYNC_DIVERGENCE_CLASSIFICATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error de clasificación de divergencia de dominio.",
            default_message_en="Raised when the domain sync classifier cannot classify a divergence.",
            default_message_hu="Domain sync eltérés besorolási hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.sync._errors.HealingError",
        ErrorCode(
            code="ERROR_DOMAIN_SYNC_HEALING",
            category=ErrorCategory.ERROR,
            default_message_es="Error al reparar una divergencia de dominio.",
            default_message_en="Raised when a domain sync healing strategy cannot apply.",
            default_message_hu="Domain sync javítási hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.sync._errors.DivergenceRepositoryError",
        ErrorCode(
            code="ERROR_DOMAIN_SYNC_DIVERGENCE_REPOSITORY",
            category=ErrorCategory.ERROR,
            default_message_es="Error del repositorio de divergencias de dominio.",
            default_message_en="Raised when the domain sync divergence repository cannot persist or load.",
            default_message_hu="Domain sync eltérés tár hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.verification._errors.VerificationError",
        ErrorCode(
            code="INTEGRITY_VERIFICATION",
            category=ErrorCategory.INTEGRITY,
            default_message_es="La verificacion de verificacion fallo.",
            default_message_en="Raised on catastrophic verification failures (not ordinary discrepancies).",
            default_message_hu="Ellenorzes ellenorzese sikertelen.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.workflow._errors.WorkflowAbortedError",
        ErrorCode(
            code="REFUSED_WORKFLOW_ABORTED",
            category=ErrorCategory.REFUSED,
            default_message_es="El flujo de trabajo fue abortado por el solicitante.",
            default_message_en="Raised only when a caller explicitly opts in to exception-on-abort.",
            default_message_hu="A munkafolyamatot a hivo megszakitotta.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.workflow._errors.WorkflowComponentError",
        ErrorCode(
            code="ERROR_WORKFLOW_COMPONENT",
            category=ErrorCategory.ERROR,
            default_message_es="Error de flujo de trabajo componente.",
            default_message_en="Raised when a cross-module component raises an unexpected exception.",
            default_message_hu="Munkafolyamat komponens hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.application.workflow._errors.WorkflowError",
        ErrorCode(
            code="ERROR_WORKFLOW",
            category=ErrorCategory.ERROR,
            default_message_es="Error de flujo de trabajo.",
            default_message_en="Base class for workflow errors.",
            default_message_hu="Munkafolyamat hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.rental._errors.RentalRegisterError",
        ErrorCode(
            code="ERROR_RENTAL_REGISTER",
            category=ErrorCategory.ERROR,
            default_message_es="Error del registro de alquileres.",
            default_message_en="Base class for rental-register errors (#454).",
            default_message_hu="Bérleti nyilvántartás hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.rental._errors.FincaNotFoundError",
        ErrorCode(
            code="ERROR_RENTAL_FINCA_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="Finca no encontrada en el registro.",
            default_message_en="Raised when a referenced finca id is not present in the rental register.",
            default_message_hu="A bérleti ingatlan nem található a nyilvántartásban.",
            default_suggestion="aeat rental finca list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.rental._errors.ContractNotFoundError",
        ErrorCode(
            code="ERROR_RENTAL_CONTRACT_NOT_FOUND",
            category=ErrorCategory.ERROR,
            default_message_es="Contrato no encontrado en el registro.",
            default_message_en="Raised when a referenced rental contract id is not present in the register.",
            default_message_hu="A bérleti szerződés nem található a nyilvántartásban.",
            default_suggestion="aeat rental contract list",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.rental._errors.TierResolutionError",
        ErrorCode(
            code="ERROR_RENTAL_TIER_RESOLUTION",
            category=ErrorCategory.ERROR,
            default_message_es="No se puede resolver el tramo de reducción art. 23.2.",
            default_message_en=(
                "Raised when contract metadata is inconsistent and the LIRPF art. 23.2 tier cannot be resolved."
            ),
            default_message_hu="A 23.2 cikk csökkentési szint nem oldható fel.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.rental._errors.AmortizationLedgerCapExceededError",
        ErrorCode(
            code="ERROR_RENTAL_AMORTIZATION_CAP_EXCEEDED",
            category=ErrorCategory.ERROR,
            default_message_es=("El acumulado de amortización supera el coste de adquisición de la construcción."),
            default_message_en=(
                "Raised in strict mode when cumulative amortización would exceed the per-finca "
                "construction-cost basis cap."
            ),
            default_message_hu="A halmozott amortizáció meghaladja az építmény bekerülési értékét.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "aeat.domain.rental._errors.AnexoCAggregationError",
        ErrorCode(
            code="ERROR_RENTAL_ANEXO_C_AGGREGATION",
            category=ErrorCategory.ERROR,
            default_message_es="Error al agregar el Anexo C desde el registro de alquileres.",
            default_message_en="Raised when the rental register cannot produce a coherent Anexo C aggregate set.",
            default_message_hu="Anexo C aggregálási hiba.",
            default_suggestion=None,
            retryable=False,
            runbook_id=None,
        ),
    ),
)

_DECLARED_CODE_BY_QUALNAME: Mapping[str, ErrorCode] = MappingProxyType(
    {qualname: register(code) for qualname, code in _DECLARED_ERROR_CODES}
)
ERROR_REGISTRY: Mapping[str, ErrorCode] = MappingProxyType(_ERROR_REGISTRY_MUTABLE)


def bind_error_code(error_type: type[BaseException]) -> ErrorCode:
    """Bind a stable :class:`ErrorCode` to ``error_type``.

    Args:
        error_type: Error class being declared.

    Returns:
        The registered :class:`ErrorCode` for ``error_type``.

    Raises:
        ValueError: If ``error_type`` has no declared registry entry.
    """

    bound = _CLASS_CODE_REGISTRY.get(error_type)
    if bound is not None:
        return bound
    qualname = _qualname(error_type)
    code = _DECLARED_CODE_BY_QUALNAME.get(qualname)
    if code is None:
        raise ValueError(f"AeatError subclass {qualname} is missing a declared ErrorCode registry entry")
    _CLASS_CODE_REGISTRY[error_type] = code
    type.__setattr__(error_type, "code", code)
    return code


def get_registered_error_code(error: BaseException | type[BaseException]) -> ErrorCode:
    """Return the registered :class:`ErrorCode` for ``error``."""

    error_type = error if isinstance(error, type) else type(error)
    code = _CLASS_CODE_REGISTRY.get(error_type)
    if code is None:
        code = bind_error_code(error_type)
    return code


def resolve_output_language() -> str:
    """Resolve the configured output language, defaulting to ``es``."""

    try:
        from ..config import load_settings
        from ..i18n import Language

        value = load_settings().aeat_output_language
        return Language(value).value
    except Exception:
        return "es"


def scrub_error_context(context: Mapping[str, object] | None) -> dict[str, str] | None:
    """Redact secret-looking keys from ``context`` and stringify the values."""

    if not context:
        return None
    scrubbed: dict[str, str] = {}
    for key, value in sorted(context.items()):
        if _SECRET_FIELD_PATTERN.search(key):
            scrubbed[key] = "<redacted>"
        else:
            scrubbed[key] = _stringify_context_value(value)
    return scrubbed or None


def build_error_envelope(
    error: BaseException,
    *,
    context: Mapping[str, object] | None = None,
    trace_id: str | None = None,
) -> ErrorEnvelope:
    """Build the deterministic JSON stderr envelope for ``error``."""

    code = get_registered_error_code(error)
    merged_context = _merge_error_context(error, context)
    return ErrorEnvelope(
        code=code.code,
        category=code.category.value,
        message=resolve_error_message(error, code),
        suggestion=get_error_suggestion(error, code),
        retryable=code.retryable,
        runbook_id=code.runbook_id,
        context=scrub_error_context(merged_context),
        trace_id=trace_id,
    )


def render_error_text(
    error: BaseException,
    *,
    context: Mapping[str, object] | None = None,
) -> str:
    """Render the human-readable stderr payload for ``error``."""

    code = get_registered_error_code(error)
    prefix = code.category.value
    message = resolve_error_message(error, code)
    first_line = f"{prefix} {message}" if prefix.startswith("[") else f"{prefix}: {message}"
    suggestion = get_error_suggestion(error, code)
    lines = [first_line]
    if suggestion is not None:
        lines.append(f"  -> Run `{suggestion}`")
    scrubbed_context = scrub_error_context(_merge_error_context(error, context))
    if scrubbed_context:
        for key, value in scrubbed_context.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines) + "\n"


def render_error_json(
    error: BaseException,
    *,
    context: Mapping[str, object] | None = None,
    trace_id: str | None = None,
) -> str:
    """Serialize ``error`` to a deterministic single-line JSON document."""

    envelope = build_error_envelope(error, context=context, trace_id=trace_id)
    payload = {"error": envelope.model_dump(mode="json")}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def get_error_exit_code(category: ErrorCategory) -> int:
    """Return the placeholder process exit code for ``category``."""

    return {
        ErrorCategory.ERROR: 1,
        ErrorCategory.REFUSED: 2,
        ErrorCategory.AUTH: 3,
        ErrorCategory.INTEGRITY: 4,
        ErrorCategory.FAIL: 5,
        ErrorCategory.INTERNAL: 6,
        ErrorCategory.LOCKED: 7,
        ErrorCategory.DEPRECATED: 4,
        ErrorCategory.MOVED: 4,
    }[category]


def resolve_error_message(error: BaseException, code: ErrorCode | None = None) -> str:
    """Resolve the user-facing message for ``error``."""

    resolved_code = code or get_registered_error_code(error)
    translated_message = getattr(error, "translated_message", None)
    if isinstance(translated_message, Mapping):
        try:
            from ..i18n import Language, TranslationError, get_translation
        except ImportError:
            translated_message = None
        else:
            try:
                return get_translation(translated_message, Language(resolve_output_language()))
            except (TranslationError, TypeError, ValueError):
                translated_message = None
    if error.args and isinstance(error.args[0], str) and error.args[0]:
        return error.args[0]
    language = resolve_output_language()
    if language == "en":
        return resolved_code.default_message_en
    if language == "hu":
        return resolved_code.default_message_hu
    return resolved_code.default_message_es


def get_error_suggestion(error: BaseException, code: ErrorCode | None = None) -> str | None:
    """Resolve the copy-paste recovery command for ``error``."""

    resolved_code = code or get_registered_error_code(error)
    suggestion = getattr(error, "suggestion", None)
    if isinstance(suggestion, str) and suggestion:
        return suggestion
    return resolved_code.default_suggestion


def _qualname(error_type: type[BaseException]) -> str:
    return f"{error_type.__module__}.{error_type.__name__}"


def _merge_error_context(
    error: BaseException,
    context: Mapping[str, object] | None,
) -> dict[str, object] | None:
    merged: dict[str, object] = {}
    error_context = getattr(error, "context", None)
    if isinstance(error_context, Mapping):
        merged.update(error_context)
    for key, value in vars(error).items():
        if key.startswith("_") or key in {"code", "context", "translated_message", "suggestion"}:
            continue
        merged[key] = value
    if context:
        merged.update(context)
    return merged or None


def _stringify_context_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return str(value)


__all__ = [
    "ERROR_REGISTRY",
    "ErrorCategory",
    "ErrorCode",
    "ErrorEnvelope",
    "bind_error_code",
    "build_error_envelope",
    "get_error_exit_code",
    "get_registered_error_code",
    "register",
    "render_error_json",
    "render_error_text",
    "resolve_error_message",
    "resolve_output_language",
    "scrub_error_context",
]
