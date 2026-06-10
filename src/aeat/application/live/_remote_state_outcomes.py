"""Outcome and redaction helpers for live IVA remote-state acquisition.

Use of :class:`SensitivityClass` for compliance.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from ...application.auth import AuthenticatedAeatSessionResult
from ...core.classification import SensitivityClass
from ...core.hashing import sha256_hex
from ...core.redaction import default_rules_for_class, redact
from ._errors import LiveIvaAcquisitionFailureMode, classify_live_iva_acquisition_failure
from ._remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaWalletCaptureReport,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)


def surface_outcome(
    surface: LiveIvaReadSurface,
    *,
    report: IvaCompensationHistoryCaptureReport | IvaWalletCaptureReport | None,
    error: BaseException | None,
    auth: LiveIvaAuthOutcome,
) -> LiveIvaReadOutcome:
    """Build and return a :class:`LiveIvaReadOutcome` for one live IVA read surface."""
    if auth.status is LiveIvaReadStatus.FAILED and auth.failure_type != "MissingAuthResult":
        return LiveIvaReadOutcome(
            surface=surface,
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=auth.outcome_mode,
            failure_mode=auth.failure_mode,
            failure_type=auth.failure_type,
        )
    if error is not None:
        failure_mode = classify_live_iva_acquisition_failure(error)
        return LiveIvaReadOutcome(
            surface=surface,
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=failure_mode,
            failure_mode=failure_mode,
            failure_type=error.__class__.__name__,
            failure_context=_redacted_failure_context(error),
        )
    if report is None:
        return LiveIvaReadOutcome(
            surface=surface,
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_type="MissingSurfaceReport",
        )
    failed_declaration_count = getattr(report, "failed_declaration_count", 0)
    if (
        surface is LiveIvaReadSurface.FILED_HISTORY
        and isinstance(failed_declaration_count, int)
        and failed_declaration_count
    ):
        return LiveIvaReadOutcome(
            surface=surface,
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED,
            failure_mode=LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED,
            failure_type="FiledHistoryPartialFailure",
            failure_context={
                "captured_count": getattr(report, "captured_count", None),
                "failed_declaration_count": failed_declaration_count,
                "failed_declarations": getattr(report, "failed_declarations", ()),
            },
            captured_count=getattr(report, "captured_count", None),
            calculation_observation_count=getattr(report, "calculation_observation_count", None),
        )
    return LiveIvaReadOutcome(
        surface=surface,
        status=LiveIvaReadStatus.SUCCEEDED,
        outcome_mode=LiveIvaAcquisitionFailureMode.AUTHENTICATED,
        captured_count=getattr(report, "captured_count", None),
        calculation_observation_count=getattr(report, "calculation_observation_count", None),
    )


def auth_outcome(
    *,
    auth_result: AuthenticatedAeatSessionResult | None,
    error: BaseException | None,
) -> LiveIvaAuthOutcome:
    """Build and return a :class:`LiveIvaAuthOutcome` for live IVA acquisition."""
    if error is not None:
        failure_mode = classify_live_iva_acquisition_failure(error)
        return LiveIvaAuthOutcome(
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=failure_mode,
            failure_mode=failure_mode,
            failure_type=error.__class__.__name__,
            diagnostic_ref=_auth_diagnostic_ref(error),
        )
    if auth_result is None:
        return LiveIvaAuthOutcome(
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_type="MissingAuthResult",
        )
    return LiveIvaAuthOutcome(
        status=LiveIvaReadStatus.SUCCEEDED,
        outcome_mode=LiveIvaAcquisitionFailureMode.AUTHENTICATED,
        provider_kind=auth_result.provider_kind.value,
        reused_persisted_session=auth_result.reused_persisted_session,
        fresh=auth_result.fresh,
    )


def bounded_context_text(value: object, *, max_length: int = 160) -> str:
    """Return normalized diagnostic text bounded for persisted context payloads."""
    text = " ".join(str(value).replace("\xa0", " ").split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _redacted_failure_context(error: BaseException) -> dict[str, object] | None:
    context = getattr(error, "context", None)
    if not isinstance(context, Mapping):
        return None
    redacted = _redacted_context_mapping(context)
    return redacted or None


def _redacted_context_mapping(context: object) -> dict[str, object]:
    if not isinstance(context, Mapping):
        return {}
    redacted: dict[str, object] = {}
    for raw_key, raw_value in context.items():
        key = str(raw_key)
        if not key or key.startswith("_"):
            continue
        value = _redacted_context_value(raw_value, key=key)
        if value is not None:
            redacted[key] = value
    return redacted


def _redacted_context_value(value: object, *, key: str) -> object | None:
    if _is_sensitive_failure_context_key(key):
        return _redacted_sensitive_context_value(value, key=key)
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        text = _redact_url_like_context_value(value, key=key)
        return text if text else None
    if isinstance(value, Mapping):
        return _redacted_context_mapping(value)
    if isinstance(value, tuple | list):
        items = tuple(
            item
            for item in (_redacted_sequence_context_value(entry, key=key) for entry in value[:8])
            if item is not None
        )
        return items
    return bounded_context_text(value)


_DIAGNOSTIC_CONTEXT_REDACTION_RULES = default_rules_for_class(SensitivityClass.DIAGNOSTIC)
_SENSITIVE_FAILURE_CONTEXT_EXACT_KEYS = frozenset(
    {
        "active_profile_id",
        "active_profile_ref",
        "authorization",
        "bucket_id",
        "certificate_nif",
        "credential",
        "diagnostic_id",
        "dni_nie",
        "identity_nif",
        "nif",
        "nie",
        "num_soporte",
        "object_key",
        "profile_id",
        "profile_ref",
        "secure_object_key",
        "storage_object_key",
        "tax_id",
    }
)
_SENSITIVE_FAILURE_CONTEXT_KEY_PARTS = frozenset(
    {
        "authorization",
        "bearer",
        "bucket",
        "certificate",
        "cookie",
        "credential",
        "dni",
        "nif",
        "nie",
        "object",
        "passphrase",
        "pkcs12",
        "profile",
        "secret",
        "soporte",
        "support",
        "token",
    }
)
_SAFE_FAILURE_CONTEXT_KEYS = frozenset(
    {
        "actual_type",
        "auth_mode",
        "captured_at",
        "cause_type",
        "description",
        "ejercicio",
        "expected",
        "failure_type",
        "modelo",
        "operation",
        "period",
        "phone_state",
        "reason",
        "stage",
        "target_period",
        "target_year",
        "timeout_ms",
    }
)


def _normalised_context_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _is_sensitive_failure_context_key(key: str) -> bool:
    normalised = _normalised_context_key(key)
    if not normalised or normalised in _SAFE_FAILURE_CONTEXT_KEYS:
        return False
    if normalised in _SENSITIVE_FAILURE_CONTEXT_EXACT_KEYS:
        return True
    parts = frozenset(part for part in normalised.split("_") if part)
    return any(
        part == sensitive or part.startswith(f"{sensitive}s")
        for part in parts
        for sensitive in _SENSITIVE_FAILURE_CONTEXT_KEY_PARTS
    )


def _redacted_sensitive_context_value(value: object, *, key: str) -> object | None:
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        text = _redact_diagnostic_context_text(value)
        return _evidence_ref(text) if text else None
    if isinstance(value, Mapping):
        redacted = _redacted_sensitive_context_mapping(value)
        return redacted or None
    if isinstance(value, tuple | list):
        items = tuple(
            item
            for item in (_redacted_sensitive_context_value(entry, key=key) for entry in value[:8])
            if item is not None
        )
        return items
    return _evidence_ref(bounded_context_text(value))


def _redacted_sensitive_context_mapping(context: object) -> dict[str, object]:
    if not isinstance(context, Mapping):
        return {}
    redacted: dict[str, object] = {}
    for raw_key, raw_value in context.items():
        key = str(raw_key)
        if not key or key.startswith("_"):
            continue
        value = _redacted_sensitive_context_value(raw_value, key=key)
        if value is not None:
            redacted[key] = value
    return redacted


def _redacted_sequence_context_value(value: object, *, key: str) -> object | None:
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        text = _redact_diagnostic_context_text(value)
        return _evidence_ref(text) if text else None
    return _redacted_context_value(value, key=key)


def _redact_url_like_context_value(value: str, *, key: str) -> str:
    text = _redact_diagnostic_context_text(value)
    if "url" not in key.casefold():
        return text
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if not parsed.scheme and not parsed.netloc:
        return parsed.path
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _redact_diagnostic_context_text(value: object) -> str:
    return bounded_context_text(redact(str(value), rules=_DIAGNOSTIC_CONTEXT_REDACTION_RULES))


def _auth_diagnostic_ref(error: BaseException) -> str | None:
    context = getattr(error, "context", None)
    if not isinstance(context, dict):
        return None
    diagnostic_id = context.get("diagnostic_id")
    if not isinstance(diagnostic_id, str) or not diagnostic_id.strip():
        return None
    return _evidence_ref(diagnostic_id)


def _evidence_ref(value: str) -> str:
    digest = sha256_hex(value.strip().encode("utf-8"))
    return f"sha256:{digest[:12]}"


__all__ = [
    "auth_outcome",
    "bounded_context_text",
    "surface_outcome",
]
