"""Operator-safe access to encrypted AEAT auth diagnostics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

# Imported from the defining `_clave_movil` module, not the `auth`
# package surface: `adapters.outbound.aeat.auth.__init__` imports
# `application.auth`, and `application.auth.__init__` imports this
# module — re-entering the package surface here closes a circular
# import. `_clave_movil` is a leaf module (no application-layer
# import), so importing the public-named constant from it directly
# breaks the cycle.
from ...adapters.outbound.aeat.auth._clave_movil import (
    CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
    CLAVE_MOVIL_OPERATOR_PHONE_STATES,
    _operator_phone_state_report_commands,
)
from ...adapters.persistence.storage import SensitivityClass
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
AUTH_DIAGNOSTIC_PHONE_STATES: tuple[str, ...] = CLAVE_MOVIL_OPERATOR_PHONE_STATES


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
    identity_kind: str = ""
    headless: bool | None = None
    active_profile_id: str = ""
    active_profile_label: str = ""
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
    operator_report_commands: tuple[str, ...] = ()
    profile_tax_id_fingerprint: str = ""
    clave_identity_fingerprint: str = ""
    dni_fecha_fingerprint: str = ""
    nie_soporte_fingerprint: str = ""
    certificate_path_fingerprint: str = ""


class AuthDiagnosticReportResult(BaseModel):
    """Result of recording an operator phone-state report for an auth diagnostic."""

    model_config = _STRICT_FROZEN

    diagnostic_id: str
    phone_state: str
    reported_at: datetime


def list_auth_diagnostics() -> AuthDiagnosticListReport:
    """List readable encrypted Cl@ve auth diagnostics without exposing page bodies."""

    rows = tuple(
        sorted(
            (
                _summary_from_payload(_payload(record.payload), include_private_context=False)
                for record in _diagnostic_records()
            ),
            key=lambda row: row.captured_at,
            reverse=True,
        )
    )
    return AuthDiagnosticListReport(row_count=len(rows), rows=rows)


def load_auth_diagnostic(diagnostic_id: str) -> AuthDiagnosticDetail | None:
    """Load one encrypted Cl@ve auth diagnostic by id, redacting sensitive bodies."""

    record = secure_object_repository_for_active_bucket().load(
        CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
        diagnostic_id,
        expected_class=SensitivityClass.SESSION,
        max_supported_version=1,
    )
    if record is None:
        return None
    payload = _payload(record.payload)
    summary = _summary_from_payload(payload)
    html = payload.get("html")
    excerpt = None
    if isinstance(html, str) and html.strip():
        excerpt = f"[redacted html captured: {len(html)} chars]"
    return AuthDiagnosticDetail(
        **summary.model_dump(),
        operator_report_commands=(
            _operator_phone_state_report_commands(summary.diagnostic_id) if summary.diagnostic_id else ()
        ),
        **_detail_fingerprints_from_payload(payload),
        html_excerpt=excerpt,
    )


def record_auth_diagnostic_phone_state(
    diagnostic_id: str,
    phone_state: str,
) -> AuthDiagnosticReportResult | None:
    """Attach the operator-observed Cl@ve app state to an encrypted diagnostic."""

    if phone_state not in AUTH_DIAGNOSTIC_PHONE_STATES:
        raise ValueError(phone_state)
    repository = secure_object_repository_for_active_bucket()
    record = repository.load(
        CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
        diagnostic_id,
        expected_class=SensitivityClass.SESSION,
        max_supported_version=1,
    )
    if record is None:
        return None
    payload = _payload(record.payload)
    reported_at = datetime.now(UTC)
    payload["operator_report"] = {
        "phone_state": phone_state,
        "reported_at": reported_at.isoformat(),
    }
    repository.save(
        namespace=CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
        object_key=diagnostic_id,
        classification=SensitivityClass.SESSION,
        schema_version=1,
        written_at=reported_at,
        payload=json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )
    return AuthDiagnosticReportResult(
        diagnostic_id=diagnostic_id,
        phone_state=phone_state,
        reported_at=reported_at,
    )


def _diagnostic_records():
    return secure_object_repository_for_active_bucket().list_records(
        CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
        expected_class=SensitivityClass.SESSION,
        max_supported_version=1,
    )


def _payload(raw: bytes) -> dict[str, object]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("auth diagnostic payload is not a JSON object")
    return {str(key): value for key, value in payload.items()}


def _json_object(value: object) -> dict[str, object]:
    """Narrow a JSON value to a string-keyed object, or an empty one."""

    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _summary_from_payload(
    payload: dict[str, object],
    *,
    include_private_context: bool = True,
) -> AuthDiagnosticSummary:
    captured_at = payload.get("captured_at")
    if not isinstance(captured_at, str):
        raise ValueError("auth diagnostic payload is missing captured_at")
    auth_attempt = _json_object(payload.get("auth_attempt"))
    operator_report = _json_object(payload.get("operator_report"))
    phone_state_reported_at = None
    raw_reported_at = operator_report.get("reported_at")
    if isinstance(raw_reported_at, str) and raw_reported_at:
        phone_state_reported_at = datetime.fromisoformat(raw_reported_at)
    raw_diagnostic_id = payload.get("diagnostic_id")
    raw_headless = auth_attempt.get("headless")
    summary = AuthDiagnosticSummary(
        diagnostic_id=raw_diagnostic_id if isinstance(raw_diagnostic_id, str) else None,
        reason=str(payload.get("reason") or ""),
        url=_redacted_url_summary(str(payload.get("url") or "")),
        captured_at=datetime.fromisoformat(captured_at),
        html_captured=isinstance(payload.get("html"), str) and bool(str(payload.get("html")).strip()),
        screenshot_captured=isinstance(payload.get("screenshot_png_base64"), str)
        and bool(str(payload.get("screenshot_png_base64")).strip()),
        auth_mode=str(auth_attempt.get("auth_mode") or ""),
        identity_kind=str(auth_attempt.get("identity_kind") or "") if include_private_context else "",
        headless=raw_headless if isinstance(raw_headless, bool) else None,
        active_profile_id=str(auth_attempt.get("active_profile_id") or "") if include_private_context else "",
        active_profile_label=str(auth_attempt.get("active_profile_label") or "") if include_private_context else "",
        active_profile_registered=(
            _optional_bool(auth_attempt.get("active_profile_registered")) if include_private_context else None
        ),
        profile_record_present=(
            _optional_bool(auth_attempt.get("profile_record_present")) if include_private_context else None
        ),
        profile_tax_id_present=(
            _optional_bool(auth_attempt.get("profile_tax_id_present")) if include_private_context else None
        ),
        identity_alignment=str(auth_attempt.get("identity_alignment") or "") if include_private_context else "",
        clave_identity_configured=(
            _optional_bool(auth_attempt.get("clave_identity_configured")) if include_private_context else None
        ),
        dni_fecha_configured=(
            _optional_bool(auth_attempt.get("dni_fecha_configured")) if include_private_context else None
        ),
        nie_soporte_configured=(
            _optional_bool(auth_attempt.get("nie_soporte_configured")) if include_private_context else None
        ),
        certificate_path_configured=(
            _optional_bool(auth_attempt.get("certificate_path_configured")) if include_private_context else None
        ),
        certificate_password_configured=(
            _optional_bool(auth_attempt.get("certificate_password_configured")) if include_private_context else None
        ),
        certificate_file_present=(
            _optional_bool(auth_attempt.get("certificate_file_present")) if include_private_context else None
        ),
        certificate_backend=str(auth_attempt.get("certificate_backend") or "") if include_private_context else "",
        phone_state=str(operator_report.get("phone_state") or payload.get("phone_state") or ""),
        phone_state_reported_at=phone_state_reported_at,
    )
    return summary


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _detail_fingerprints_from_payload(payload: dict[str, object]) -> dict[str, str]:
    raw_auth_attempt = payload.get("auth_attempt")
    if not isinstance(raw_auth_attempt, dict):
        return {}
    auth_attempt = _json_object(raw_auth_attempt)
    keys = (
        "profile_tax_id_fingerprint",
        "clave_identity_fingerprint",
        "dni_fecha_fingerprint",
        "nie_soporte_fingerprint",
        "certificate_path_fingerprint",
    )
    return {key: str(auth_attempt.get(key) or "") for key in keys}


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
