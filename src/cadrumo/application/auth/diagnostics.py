"""Operator-safe access to encrypted AEAT auth diagnostics.

Diagnostic records are support evidence for failed Cl@ve/browser auth flows.
They may include raw HTML, screenshot bytes, route metadata, and identity
alignment hints, so they are stored only as encrypted objects through a
:class:`adapters.persistence.storage.SecureObjectRepository` scoped to
the active profile bucket.

Public functions return redacted summaries, bounded body placeholders, and
hash fingerprints instead of raw page bodies or taxpayer identifiers.
When AEAT exposes an authenticated post-Cl@ve landing, that browser transition
is recorded as the authoritative phone-state observation. Operator reports are
offered only when the browser state cannot determine what happened on the app.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.persistence.storage import (
    CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE,
    SecureObjectRepository,
    secure_object_repository_for_active_bucket,
)
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.errors.hierarchy import CoreValidationError
from ...core.external_constants import UTF_8_ENCODING, load_external_constants
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.time import now, validate_utc_aware
from ..operator_actions import PreconditionVerdict, no_action_precondition_verdict
from .errors import AuthDiagnosticPayloadError, AuthDiagnosticPhoneStateError

_DIAGNOSTIC_NAMESPACE = CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace
_DIAGNOSTIC_SENSITIVITY = CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity
_DIAGNOSTIC_SCHEMA_VERSION = CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version

#: Registered locale key for every structural rejection of a persisted diagnostic
#: payload. The refusals differ by the ``validation_rule`` fact on the error
#: context, not by an authored sentence, so each renders in the operator's own
#: locale while the failing check stays machine-readable.
_PAYLOAD_MESSAGE_KEY = "errors.refused.refused_auth_diagnostic_payload"


class AuthDiagnosticPhoneState(StrEnum):
    """Closed vocabulary of observed Cl@ve Móvil app states."""

    APP_PROMPTED_AND_ACCEPTED = "app_prompted_and_accepted"
    APP_PROMPTED_NOT_ACCEPTED = "app_prompted_not_accepted"
    APP_DID_NOT_PROMPT = "app_did_not_prompt"
    OPERATOR_DID_NOT_CHECK = "operator_did_not_check"


class AuthDiagnosticPhoneStateSource(StrEnum):
    """Closed authority that established a diagnostic phone state."""

    AEAT_AUTHENTICATED_LANDING = "aeat_authenticated_landing"
    OPERATOR_REPORT = "operator_report"


AUTH_DIAGNOSTIC_PHONE_STATES: tuple[str, ...] = tuple(state.value for state in AuthDiagnosticPhoneState)


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
    #: The operator-observed Cl@ve app state, or ``None`` when the operator has
    #: not reported one yet. Typed from the closed vocabulary rather than left
    #: as free text: the taxonomy used to be enforced only on the mutation
    #: verb, so a persisted row could list a state the mutation API refuses.
    phone_state: AuthDiagnosticPhoneState | None = None
    phone_state_source: AuthDiagnosticPhoneStateSource | None = None
    phone_state_observed_at: datetime | None = None
    phone_state_reported_at: datetime | None = None

    @model_validator(mode="after")
    def _instants_are_utc(self) -> AuthDiagnosticSummary:
        """Hold every projected instant to the canonical UTC contract."""
        validate_utc_aware(self.captured_at)
        if self.phone_state_observed_at is not None:
            validate_utc_aware(self.phone_state_observed_at)
        if self.phone_state_reported_at is not None:
            validate_utc_aware(self.phone_state_reported_at)
        return self


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
    operator_report_verdict: PreconditionVerdict | None = None


class AuthDiagnosticReportResult(BaseModel):
    """Result of recording an operator phone-state report for an auth diagnostic."""

    model_config = _STRICT_FROZEN

    diagnostic_id: str = Field(min_length=1)
    phone_state: AuthDiagnosticPhoneState
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
    phone_state_source: str = ""
    phone_state_observed_at: str = ""


@dataclass(frozen=True)
class _DiagnosticPhoneStateProjection:
    state: AuthDiagnosticPhoneState | None
    source: AuthDiagnosticPhoneStateSource | None
    observed_at: datetime | None
    reported_at: datetime | None


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

    Returns an :class:`AuthDiagnosticDetail` with redacted body placeholders
    and hashed identity/configuration fingerprints. Raw HTML and screenshot
    bytes remain encrypted in storage and are not returned by this facade.
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
            "operator_report_verdict": (
                no_action_precondition_verdict(
                    condition_id="auth.diagnostics.phone_state_recorded",
                    facts={"diagnostic_available": True, "phone_state_observed": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                )
                if summary.phone_state is None
                else None
            ),
        },
    )


def record_auth_diagnostic_phone_state(
    diagnostic_id: str,
    phone_state: str,
) -> AuthDiagnosticReportResult | None:
    """Attach the operator-observed Cl@ve app state to an encrypted diagnostic.

    The update writes the selected closed phone-state token back into the same
    encrypted diagnostic payload. It does not create a plaintext report file.

    Returns an :class:`AuthDiagnosticReportResult`, or ``None`` when the
    diagnostic is not found.
    """
    try:
        AuthDiagnosticPhoneState(phone_state)
    except ValueError as exc:
        raise AuthDiagnosticPhoneStateError(
            translated_message="errors.refused.refused_auth_diagnostic_phone_state",
            context={"phone_state": phone_state},
        ) from exc
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
        payload=canonical_json_bytes(updated.model_dump(mode="json")),
    )
    return AuthDiagnosticReportResult(
        diagnostic_id=diagnostic_id,
        phone_state=AuthDiagnosticPhoneState(phone_state),
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
        raise AuthDiagnosticPayloadError(
            translated_message=_PAYLOAD_MESSAGE_KEY,
            context={"validation_rule": "json_root_object", "json_root_type": type(data).__name__},
        )
    return _DiagnosticPayload.model_validate(data)


def _validated_utc_instant(raw: str, *, field: str) -> datetime:
    """Parse a persisted ISO instant and hold it to the canonical UTC contract.

    These instants were parsed with a bare :meth:`datetime.fromisoformat`, so a
    row written without an offset, or with a local one, was returned as a naive
    or non-UTC value while :func:`~core.time.validate_utc_aware` — the contract
    every other persisted instant in this codebase carries — rejects both. A
    diagnostic listing sorted by capture time then ordered naive and aware rows
    against each other, which is not a comparison the two shapes support.

    Raises:
        AuthDiagnosticPayloadError: When ``raw`` is not an ISO instant, or is
            not UTC-aware.
    """
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AuthDiagnosticPayloadError(
            translated_message=_PAYLOAD_MESSAGE_KEY,
            context={"validation_rule": "iso_8601_instant", "field": field},
        ) from exc
    try:
        return validate_utc_aware(parsed)
    except CoreValidationError as exc:
        raise AuthDiagnosticPayloadError(
            translated_message=_PAYLOAD_MESSAGE_KEY,
            context={"validation_rule": "utc_aware_instant", "field": field},
        ) from exc


def _validated_phone_state(raw: object) -> AuthDiagnosticPhoneState | None:
    """Resolve a persisted phone state through the one closed vocabulary.

    The taxonomy was enforced only on the mutation verb: the read path pushed
    whatever the row held through ``str()``, so a payload carrying an
    unrecognised state was listed verbatim while the mutation API refused the
    same value. ``None`` is the documented absence — a diagnostic captured
    before the operator reported anything simply has no state yet.

    Raises:
        AuthDiagnosticPayloadError: When a populated value is outside the
            closed vocabulary.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return AuthDiagnosticPhoneState(text)
    except ValueError as exc:
        raise AuthDiagnosticPayloadError(
            translated_message=_PAYLOAD_MESSAGE_KEY,
            context={
                "validation_rule": "closed_phone_state_vocabulary",
                "phone_state": text,
                "accepted_phone_states": ", ".join(AUTH_DIAGNOSTIC_PHONE_STATES),
            },
        ) from exc


def _phone_state_projection(payload: _DiagnosticPayload) -> _DiagnosticPhoneStateProjection:
    browser_phone_state = _validated_phone_state(payload.phone_state)
    operator_report = payload.operator_report
    phone_state_reported_at = None
    raw_reported_at = operator_report.get("reported_at")
    if isinstance(raw_reported_at, str) and raw_reported_at:
        phone_state_reported_at = _validated_utc_instant(raw_reported_at, field="operator_report.reported_at")
    if browser_phone_state is not None:
        if payload.phone_state_source != AuthDiagnosticPhoneStateSource.AEAT_AUTHENTICATED_LANDING:
            raise AuthDiagnosticPayloadError(
                translated_message=_PAYLOAD_MESSAGE_KEY,
                context={
                    "validation_rule": "browser_proven_state_requires_landing_source",
                    "phone_state_source": payload.phone_state_source,
                },
            )
        if not payload.phone_state_observed_at:
            raise AuthDiagnosticPayloadError(
                translated_message=_PAYLOAD_MESSAGE_KEY,
                context={"validation_rule": "browser_proven_state_requires_observation_instant"},
            )
        return _DiagnosticPhoneStateProjection(
            state=browser_phone_state,
            source=AuthDiagnosticPhoneStateSource.AEAT_AUTHENTICATED_LANDING,
            observed_at=_validated_utc_instant(
                payload.phone_state_observed_at,
                field="phone_state_observed_at",
            ),
            reported_at=None,
        )
    return _DiagnosticPhoneStateProjection(
        state=_validated_phone_state(operator_report.get("phone_state")),
        source=(AuthDiagnosticPhoneStateSource.OPERATOR_REPORT if operator_report.get("phone_state") else None),
        observed_at=phone_state_reported_at,
        reported_at=phone_state_reported_at,
    )


def _summary_from_payload(payload: _DiagnosticPayload) -> AuthDiagnosticSummary:
    captured_at = payload.captured_at
    if not captured_at:
        raise AuthDiagnosticPayloadError(
            translated_message=_PAYLOAD_MESSAGE_KEY,
            context={"validation_rule": "captured_at_present"},
        )
    auth_attempt = payload.auth_attempt
    phone_state = _phone_state_projection(payload)
    raw_headless = auth_attempt.get("headless")
    summary = AuthDiagnosticSummary(
        diagnostic_id=payload.diagnostic_id,
        reason=payload.reason,
        url=_redacted_url_summary(payload.url),
        captured_at=_validated_utc_instant(captured_at, field="captured_at"),
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
        phone_state=phone_state.state,
        phone_state_source=phone_state.source,
        phone_state_observed_at=phone_state.observed_at,
        phone_state_reported_at=phone_state.reported_at,
    )
    return summary


def _redacted_ref(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("sha256:"):
        return text
    return f"sha256:{sha256_hex(text.encode(UTF_8_ENCODING))}"


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
    "AuthDiagnosticPhoneState",
    "AuthDiagnosticPhoneStateSource",
    "AuthDiagnosticReportResult",
    "AuthDiagnosticSummary",
    "list_auth_diagnostics",
    "load_auth_diagnostic",
    "record_auth_diagnostic_phone_state",
]
