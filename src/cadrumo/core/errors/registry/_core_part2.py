"""Ordered core :class:`~core.errors.ErrorCode` registry shard.

Rows map core exception qualnames to stable
:class:`~core.errors.ErrorCategory` values and locale message keys.
"""

from ..error_codes import ErrorCategory, ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "cadrumo.core.orden_anual_html.OrdenAnualHtmlParseError",
        ErrorCode(
            code="INTEGRITY_ORDEN_ANUAL_HTML_PARSE",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_orden_anual_html_parse",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.core.corpus_manifest.manifest._ManifestPayloadValidationError",
        ErrorCode(
            code="INTEGRITY_MANIFEST_PAYLOAD_VALIDATION",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_manifest_payload_validation",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.core.corpus_manifest.manifest._MalformedManifestPayloadError",
        ErrorCode(
            code="INTEGRITY_MALFORMED_MANIFEST_PAYLOAD",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_malformed_manifest_payload",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.core.corpus_manifest.manifest._UnsupportedManifestVersionError",
        ErrorCode(
            code="INTEGRITY_UNSUPPORTED_MANIFEST_VERSION",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_unsupported_manifest_version",
            retryable=False,
            runbook_id=None,
        ),
    ),
    (
        "cadrumo.core.corpus_manifest.manifest._TamperedManifestPayloadError",
        ErrorCode(
            code="INTEGRITY_TAMPERED_MANIFEST_PAYLOAD",
            category=ErrorCategory.INTEGRITY,
            message_key="errors.integrity.canonical_tampered_manifest_payload",
            retryable=False,
            runbook_id=None,
        ),
    ),
)
