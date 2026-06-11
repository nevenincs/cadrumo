"""Operator-safe access to encrypted AEAT auth diagnostics.

Diagnostic records are encrypted and retrieved through a
:class:`SecureObjectRepository` scoped to the active profile bucket.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from ...adapters.persistence.storage import CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import UTF_8_ENCODING, load_external_constants
from ...core.time import now
from ._errors import AuthDiagnosticPayloadError, AuthDiagnosticPhoneStateError

_DIAGNOSTIC_NAMESPACE = CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace
_DIAGNOSTIC_SENSITIVITY = CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity
_DIAGNOSTIC_SCHEMA_VERSION = CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version
AUTH_DIAGNOSTIC_PHONE_STATES: tuple[str, ...] = (
    "app_prompted_and_accepted",
    "app_prompted_not_accepted",
    "app_did_not_prompt",
    "operator_did_not_check",
)


class AuthDiagnosticSummary(BaseModel):
    """Redacted summary of one encrypted auth diagnostic artefact."""

    model_config = _STRICT_FROZEN

    diagnostic_id: str | None
    reason: str
    url: str
    captured_at: datetime
    html_captured: bool
    screenshot_captured: bool
    auth_mode: str = ""
    auth_route: str = ""
    identity_kind: str = ""
    headless: bool | None = None
    prefer_non_qr: bool | None = None
    timeout_ms: int | None = None
    route_label: str = ""
    active_profile_id: str = ""
    active_profile_ref: str = ""
    active_profile_label: str = ""
    active_profile_label_present: bool | None = None
    active_profile_registered: bool | None = None
    profile_record_present: bool | None = None
    profile_tax_id_present: bool | None = None
    identity_alignment: str = ""
    clave_identity_configured: bool | None = None
    dni_fecha_configured: bool | None = None
    nie_soporte_configured: bool | None = None
    certificate_path_configured: bool | None = None
    certificate_password_configured: bool | None = None
    certificate_file_present: bool | None = None
    certificate_backend: str = ""
    phone_state: str = ""
    phone_state_reported_at: datetime | None = None


class AuthDiagnosticListReport(BaseModel):
    """All readable encrypted auth diagnostics for the active profile."""

    model_config = _STRICT_FROZEN

    row_count: int
    rows: tuple[AuthDiagnosticSummary, ...]


class AuthDiagnosticDetail(AuthDiagnosticSummary):
    """Redacted detail for one encrypted auth diagnostic artefact."""

    html_excerpt: str | None = None
    profile_tax_id_fingerprint: str = ""
    clave_identity_fingerprint: str = ""
    dni_fecha_fingerprint: str = ""
    nie_soporte_fingerprint: str = ""
    certificate_path_fingerprint: str = ""
    operator_report_commands: tuple[str, ...] = ()


class AuthDiagnosticReportResult(BaseModel):
    """Result of recording an operator phone-state report for an auth diagnostic."""

    model_config = _STRICT_FROZEN

    diagnostic_id: str
    phone_state: str
    reported_at: datetime


class _DiagnosticPayload(BaseModel):
    """Typed envelope for a raw encrypted auth diagnostic JSON blob.

    Replaces the internal ``Mapping[str, object]`` boundary to give callers
    a stable typed contract instead of an untyped dict.  Fields are optional
    so validation does not reject payloads written by older schema versions.
    """

    model_config = ConfigDict(extra="allow")

    diagnostic_id: str | None = None
    reason: str = ""
    url: str = ""
    captured_at: str = ""
    html: str | None = None
    screenshot_png_base64: str | None = None
    auth_attempt: dict[str, object] = {}
    operator_report: dict[str, object] = {}
    phone_state: str = ""


def list_auth_diagnostics() -> AuthDiagnosticListReport:
    """List readable encrypted Cl@ve auth diagnostics without exposing page bodies.

    Returns an :class:`AuthDiagnosticListReport` sorted by capture time,
    most recent first.
    """
    rows = tuple(
        sorted(
            (_summary_from_payload(_payload(record.payload)) for record in _diagnostic_records()),
            key=lambda row: row.captured_at,
            reverse=True,
        ),
    )
    return AuthDiagnosticListReport(row_count=len(rows), rows=rows)


def load_auth_diagnostic(diagnostic_id: str) -> AuthDiagnosticDetail | None:
    """Load one encrypted Cl@ve auth diagnostic by id.

    Returns an :class:`AuthDiagnosticDetail`, redacting sensitive bodies.
    """
    record = _secure_objects().load(
        _DIAGNOSTIC_NAMESPACE,
        diagnostic_id,
        expected_class=_DIAGNOSTIC_SENSITIVITY,
        max_supported_version=_DIAGNOSTIC_SCHEMA_VERSION,
    )
    if record is None:
        return None
    payload = _payload(record.payload)
    summary = _summary_from_payload(payload)
    html = payload.html
    excerpt = None
    if html and html.strip():
        excerpt = f"[redacted html captured: {len(html)} chars]"
    return AuthDiagnosticDetail.model_validate(
        {
            **summary.model_dump(),
            **_detail_fingerprints_from_payload(payload),
            "html_excerpt": excerpt,
            "operator_report_commands": _operator_report_commands(summary.diagnostic_id or diagnostic_id),
        },
    )


def record_auth_diagnostic_phone_state(
    diagnostic_id: str,
    phone_state: str,
) -> AuthDiagnosticReportResult | None:
    """Attach the operator-observed Cl@ve app state to an encrypted diagnostic.

    Returns an :class:`AuthDiagnosticReportResult`, or ``None`` when the
    diagnostic is not found.
    """
    if phone_state not in AUTH_DIAGNOSTIC_PHONE_STATES:
        raise AuthDiagnosticPhoneStateError(phone_state, context={"phone_state": phone_state})
    objects = _secure_objects()
    record = objects.load(
        _DIAGNOSTIC_NAMESPACE,
        diagnostic_id,
        expected_class=_DIAGNOSTIC_SENSITIVITY,
        max_supported_version=_DIAGNOSTIC_SCHEMA_VERSION,
    )
    if record is None:
        return None
    payload = _payload(record.payload)
    reported_at = now()
    updated = payload.model_copy(
        update={
            "operator_report": {
                "phone_state": phone_state,
                "reported_at": reported_at.isoformat(),
            },
        },
    )
    objects.save(
        namespace=_DIAGNOSTIC_NAMESPACE,
        object_key=diagnostic_id,
        classification=_DIAGNOSTIC_SENSITIVITY,
        schema_version=_DIAGNOSTIC_SCHEMA_VERSION,
        written_at=reported_at,
        payload=json.dumps(
            updated.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        ).encode(UTF_8_ENCODING),
    )
    return AuthDiagnosticReportResult(
        diagnostic_id=diagnostic_id,
        phone_state=phone_state,
        reported_at=reported_at,
    )


def _diagnostic_records():
    return _secure_objects().list_records(
        _DIAGNOSTIC_NAMESPACE,
        expected_class=_DIAGNOSTIC_SENSITIVITY,
        max_supported_version=_DIAGNOSTIC_SCHEMA_VERSION,
    )


def _secure_objects() -> SecureObjectRepository:
    return secure_object_repository_for_active_bucket()


def _payload(raw: bytes) -> _DiagnosticPayload:
    """Deserialize an encrypted auth diagnostic blob into a typed payload envelope."""
    data = json.loads(raw.decode(UTF_8_ENCODING))
    if not isinstance(data, dict):
        raise AuthDiagnosticPayloadError("auth diagnostic payload is not a JSON object")
    return _DiagnosticPayload.model_validate(data)


def _summary_from_payload(payload: _DiagnosticPayload) -> AuthDiagnosticSummary:
    captured_at = payload.captured_at
    if not captured_at:
        raise AuthDiagnosticPayloadError("auth diagnostic payload is missing captured_at")
    auth_attempt = payload.auth_attempt
    operator_report = payload.operator_report
    phone_state_reported_at = None
    raw_reported_at = operator_report.get("reported_at")
    if isinstance(raw_reported_at, str) and raw_reported_at:
        phone_state_reported_at = datetime.fromisoformat(raw_reported_at)
    raw_headless = auth_attempt.get("headless")
    summary = AuthDiagnosticSummary(
        diagnostic_id=payload.diagnostic_id,
        reason=payload.reason,
        url=_redacted_url_summary(payload.url),
        captured_at=datetime.fromisoformat(captured_at),
        html_captured=bool(payload.html and payload.html.strip()),
        screenshot_captured=bool(payload.screenshot_png_base64 and payload.screenshot_png_base64.strip()),
        auth_mode=str(auth_attempt.get("auth_mode") or ""),
        auth_route=str(auth_attempt.get("auth_route") or ""),
        identity_kind=str(auth_attempt.get("identity_kind") or ""),
        headless=raw_headless if isinstance(raw_headless, bool) else None,
        prefer_non_qr=_optional_bool(auth_attempt.get("prefer_non_qr")),
        timeout_ms=_optional_int(auth_attempt.get("timeout_ms")),
        route_label=_diagnostic_route_label(payload.url),
        active_profile_id="",
        active_profile_ref=_redacted_ref(
            auth_attempt.get("active_profile_ref") or auth_attempt.get("active_profile_id"),
        ),
        active_profile_label="",
        active_profile_label_present=_optional_bool(auth_attempt.get("active_profile_label_present")),
        active_profile_registered=_optional_bool(auth_attempt.get("active_profile_registered")),
        profile_record_present=_optional_bool(auth_attempt.get("profile_record_present")),
        profile_tax_id_present=_optional_bool(auth_attempt.get("profile_tax_id_present")),
        identity_alignment=str(auth_attempt.get("identity_alignment") or ""),
        clave_identity_configured=_optional_bool(auth_attempt.get("clave_identity_configured")),
        dni_fecha_configured=_optional_bool(auth_attempt.get("dni_fecha_configured")),
        nie_soporte_configured=_optional_bool(auth_attempt.get("nie_soporte_configured")),
        certificate_path_configured=_optional_bool(auth_attempt.get("certificate_path_configured")),
        certificate_password_configured=_optional_bool(auth_attempt.get("certificate_password_configured")),
        certificate_file_present=_optional_bool(auth_attempt.get("certificate_file_present")),
        certificate_backend=str(auth_attempt.get("certificate_backend") or ""),
        phone_state=str(operator_report.get("phone_state") or payload.phone_state or ""),
        phone_state_reported_at=phone_state_reported_at,
    )
    return summary


def _redacted_ref(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("sha256:"):
        return text
    return f"sha256:{hashlib.sha256(text.encode(UTF_8_ENCODING)).hexdigest()}"


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _detail_fingerprints_from_payload(payload: _DiagnosticPayload) -> dict[str, str]:
    auth_attempt = payload.auth_attempt
    keys = (
        "profile_tax_id_fingerprint",
        "clave_identity_fingerprint",
        "dni_fecha_fingerprint",
        "nie_soporte_fingerprint",
        "certificate_path_fingerprint",
    )
    return {key: str(auth_attempt.get(key) or "") for key in keys}


def _operator_report_commands(diagnostic_id: str) -> tuple[str, ...]:
    return tuple(
        f"aeat config auth diagnostics report {diagnostic_id} --phone-state {phone_state}"
        for phone_state in AUTH_DIAGNOSTIC_PHONE_STATES
    )


def _redacted_url_summary(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "invalid-url"
    query_keys = ",".join(part.split("=", 1)[0] for part in parsed.query.split("&") if part)
    suffix = f"?keys={query_keys}" if query_keys else ""
    return f"{parsed.netloc}{parsed.path}{suffix}"


def _diagnostic_route_label(value: str) -> str:
    if not value:
        return ""
    try:
        path = urlsplit(value).path
    except ValueError:
        return "invalid_url"
    constants = load_external_constants().aeat
    clave = constants.clave_movil
    routes = (
        ("sede_auth_gate_4033", constants.sede_paths.auth_gate_4033),
        ("dialogo_representacion", clave.dialogo_representacion_path),
        ("clave_movil_qr_request", clave.obtener_clave_movil_qr_path),
        ("clave_movil_non_qr_request", clave.obtener_clave_movil_non_qr_path.split("?", 1)[0]),
        ("clave_movil_contrast", clave.autentica_dni_nie_contraste_path),
        ("clave_movil_cancel", clave.cancelar_clave_movil_path),
    )
    for label, route_path in routes:
        if route_path and path.casefold() == route_path.casefold():
            return label
    marker_routes = (
        ("selector_access", clave.selector_access_path_marker),
        ("dialogo_representacion", clave.dialogo_representacion_path_marker),
        ("clave_movil_qr_request", clave.obtener_clave_movil_qr_path_marker),
        ("clave_movil_request", clave.obtener_clave_movil_path_marker),
        ("clave_movil_cancel", clave.cancelar_clave_movil_path_marker),
    )
    folded_path = path.casefold()
    for label, marker in marker_routes:
        if marker.casefold() in folded_path:
            return label
    return "unknown"


__all__ = [
    "AUTH_DIAGNOSTIC_PHONE_STATES",
    "AuthDiagnosticDetail",
    "AuthDiagnosticListReport",
    "AuthDiagnosticReportResult",
    "AuthDiagnosticSummary",
    "list_auth_diagnostics",
    "load_auth_diagnostic",
    "record_auth_diagnostic_phone_state",
]
