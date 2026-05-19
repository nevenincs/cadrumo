"""Operator-safe access to encrypted AEAT auth diagnostics."""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.aeat.auth._clave_movil import _DIAGNOSTIC_NAMESPACE
from ...adapters.persistence.storage import SensitivityClass
from ...adapters.persistence.storage.sql import SecureObjectRepository

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AuthDiagnosticSummary(BaseModel):
    """Redacted summary of one encrypted auth diagnostic artefact."""

    model_config = _STRICT_FROZEN

    diagnostic_id: str | None
    reason: str
    url: str
    captured_at: datetime
    html_captured: bool
    screenshot_captured: bool


class AuthDiagnosticListReport(BaseModel):
    """All readable encrypted auth diagnostics for the active profile."""

    model_config = _STRICT_FROZEN

    row_count: int
    rows: tuple[AuthDiagnosticSummary, ...]


class AuthDiagnosticDetail(AuthDiagnosticSummary):
    """Redacted detail for one encrypted auth diagnostic artefact."""

    html_excerpt: str | None = None


def list_auth_diagnostics() -> AuthDiagnosticListReport:
    """List readable encrypted Cl@ve auth diagnostics without exposing page bodies."""

    rows = tuple(
        sorted(
            (_summary_from_payload(_payload(record.payload)) for record in _diagnostic_records()),
            key=lambda row: row.captured_at,
            reverse=True,
        )
    )
    return AuthDiagnosticListReport(row_count=len(rows), rows=rows)


def load_auth_diagnostic(diagnostic_id: str) -> AuthDiagnosticDetail | None:
    """Load one encrypted Cl@ve auth diagnostic by id, redacting sensitive bodies."""

    record = SecureObjectRepository().load(
        _DIAGNOSTIC_NAMESPACE,
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
    return AuthDiagnosticDetail(**summary.model_dump(), html_excerpt=excerpt)


def _diagnostic_records():
    return SecureObjectRepository().list_records(
        _DIAGNOSTIC_NAMESPACE,
        expected_class=SensitivityClass.SESSION,
        max_supported_version=1,
    )


def _payload(raw: bytes) -> dict[str, object]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("auth diagnostic payload is not a JSON object")
    return payload


def _summary_from_payload(payload: dict[str, object]) -> AuthDiagnosticSummary:
    captured_at = payload.get("captured_at")
    if not isinstance(captured_at, str):
        raise ValueError("auth diagnostic payload is missing captured_at")
    return AuthDiagnosticSummary(
        diagnostic_id=payload.get("diagnostic_id") if isinstance(payload.get("diagnostic_id"), str) else None,
        reason=str(payload.get("reason") or ""),
        url=str(payload.get("url") or ""),
        captured_at=datetime.fromisoformat(captured_at),
        html_captured=isinstance(payload.get("html"), str) and bool(str(payload.get("html")).strip()),
        screenshot_captured=isinstance(payload.get("screenshot_png_base64"), str)
        and bool(str(payload.get("screenshot_png_base64")).strip()),
    )


__all__ = [
    "AuthDiagnosticDetail",
    "AuthDiagnosticListReport",
    "AuthDiagnosticSummary",
    "list_auth_diagnostics",
    "load_auth_diagnostic",
]
