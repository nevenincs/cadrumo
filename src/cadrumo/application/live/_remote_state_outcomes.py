"""Outcome and redaction helpers for live IVA remote-state acquisition.

Failure contexts are redacted with the :class:`SensitivityClass` diagnostic
policy before they are copied into live IVA read outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...application.auth.sessions import AuthenticatedAeatSessionResult
from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
from ...core.classification import SensitivityClass
from ...core.hashing import sha256_hex
from ...core.redaction import (
    ALWAYS_REDACT_KEY_TERMS,
    default_rules_for_class,
    normalise_redaction_key,
    redact,
)
from ._errors import LiveIvaAcquisitionFailureMode, classify_live_iva_acquisition_failure
from ._remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaWalletCaptureReport,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)


def _string_object_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


def _object_sequence(value: object) -> tuple[object, ...] | None:
    if not isinstance(value, tuple | list):
        return None
    return OBJECT_TUPLE_ADAPTER.validate_python(value)


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
    typed_context = _string_object_mapping(context)
    if typed_context is None:
        return None
    redacted = _redacted_context_mapping(typed_context)
    return redacted or None


def _redacted_context_mapping(context: object) -> dict[str, object]:
    typed_context = _string_object_mapping(context)
    if typed_context is None:
        return {}
    redacted: dict[str, object] = {}
    for key, raw_value in typed_context.items():
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
    mapping = _string_object_mapping(value)
    if mapping is not None:
        return _redacted_context_mapping(mapping)
    sequence = _object_sequence(value)
    if sequence is not None:
        items = tuple(
            item
            for item in (_redacted_sequence_context_value(entry, key=key) for entry in sequence[:8])
            if item is not None
        )
        return items
    return bounded_context_text(value)


_DIAGNOSTIC_CONTEXT_REDACTION_RULES = default_rules_for_class(SensitivityClass.DIAGNOSTIC)
_SENSITIVE_FAILURE_CONTEXT_EXACT_KEYS = ALWAYS_REDACT_KEY_TERMS | frozenset(
    {
        "active_profile_id",
        "active_profile_ref",
        "bucket_id",
        "certificate_nif",
        "diagnostic_id",
        "dni_nie",
        "identity_nif",
        "num_soporte",
        "object_key",
        "profile_id",
        "profile_ref",
        "secure_object_key",
        "storage_object_key",
    },
)
_SENSITIVE_FAILURE_CONTEXT_KEY_PARTS = ALWAYS_REDACT_KEY_TERMS | frozenset(
    {
        "bucket",
        "dni",
        "object",
        "profile",
        "soporte",
        "support",
    },
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
    },
)


def _is_sensitive_failure_context_key(key: str) -> bool:
    normalised = normalise_redaction_key(key)
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
        return evidence_ref(text) if text else None
    mapping = _string_object_mapping(value)
    if mapping is not None:
        redacted = _redacted_sensitive_context_mapping(mapping)
        return redacted or None
    sequence = _object_sequence(value)
    if sequence is not None:
        items = tuple(
            item
            for item in (_redacted_sensitive_context_value(entry, key=key) for entry in sequence[:8])
            if item is not None
        )
        return items
    return evidence_ref(bounded_context_text(value))


def _redacted_sensitive_context_mapping(context: object) -> dict[str, object]:
    typed_context = _string_object_mapping(context)
    if typed_context is None:
        return {}
    redacted: dict[str, object] = {}
    for key, raw_value in typed_context.items():
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
        return evidence_ref(text) if text else None
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
    typed_context = _string_object_mapping(context)
    if typed_context is None:
        return None
    diagnostic_id = typed_context.get("diagnostic_id")
    if not isinstance(diagnostic_id, str) or not diagnostic_id.strip():
        return None
    return evidence_ref(diagnostic_id)


def evidence_ref(value: str) -> str:
    """Return the stable, non-reversing reference this package prints for a value.

    A diagnostic that has to name a sensitive value names this instead. The
    truncation width is the reason the helper is shared rather than
    reimplemented: one reference is only comparable to another if every
    producer truncates identically, and a second copy is one edit away from
    silently disagreeing about that width.
    """
    digest = sha256_hex(value.strip().encode("utf-8"))
    return f"sha256:{digest[:12]}"


__all__ = [
    "auth_outcome",
    "bounded_context_text",
    "evidence_ref",
    "surface_outcome",
]
