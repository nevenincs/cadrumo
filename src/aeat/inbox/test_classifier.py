"""Unit tests for the notification classifier.

Every rule is exercised against a fixture payload; the
``UNCLASSIFIED → (OTRO, HIGH)`` fallback is rigorously tested — see
[[2026-04-12-notifications-inbox-adr]] decision D3.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import AnyHttpUrl

from aeat.inbox import (
    NotificacionKind,
    NotificacionPriority,
    RawNotificacion,
    appeal_window_for,
    classify,
    compute_appeal_deadline,
)


def _raw(subject_es: str, notificacion_id: str = "AEAT-X") -> RawNotificacion:
    return RawNotificacion(
        notificacion_id=notificacion_id,
        subject={"es": subject_es, "en": subject_es, "hu": subject_es},
        body_excerpt={"es": "...", "en": "...", "hu": "..."},
        received_at=datetime(2026, 4, 1, tzinfo=UTC),
        effective_at=datetime(2026, 4, 1, tzinfo=UTC),
        source_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/notif/x"),
    )


# (subject_es, expected_kind, expected_priority)
_POSITIVE_CASES = [
    ("Requerimiento de información sobre IRPF 2025", NotificacionKind.REQUERIMIENTO, NotificacionPriority.CRITICAL),
    ("Requerimiento de subsanación", NotificacionKind.REQUERIMIENTO, NotificacionPriority.CRITICAL),
    ("Requerimiento genérico", NotificacionKind.REQUERIMIENTO, NotificacionPriority.CRITICAL),
    (
        "Propuesta de liquidación provisional IRPF",
        NotificacionKind.PROPUESTA_LIQUIDACION,
        NotificacionPriority.CRITICAL,
    ),
    (
        "Propuesta de regularización modelo 303",
        NotificacionKind.PROPUESTA_LIQUIDACION,
        NotificacionPriority.CRITICAL,
    ),
    ("Acuerdo de liquidación definitivo", NotificacionKind.ACUERDO_LIQUIDACION, NotificacionPriority.CRITICAL),
    ("Liquidación provisional IRPF 2024", NotificacionKind.ACUERDO_LIQUIDACION, NotificacionPriority.CRITICAL),
    ("Liquidación definitiva IVA", NotificacionKind.ACUERDO_LIQUIDACION, NotificacionPriority.CRITICAL),
    ("Diligencia de embargo de créditos", NotificacionKind.NOTIFICACION_EMBARGO, NotificacionPriority.CRITICAL),
    ("Notificación de embargo bancario", NotificacionKind.NOTIFICACION_EMBARGO, NotificacionPriority.CRITICAL),
    ("Acuse de recibo de escrito", NotificacionKind.ACUSE_RECIBO, NotificacionPriority.INFO),
    ("Justificante de recepción", NotificacionKind.ACUSE_RECIBO, NotificacionPriority.INFO),
    ("Comunicación general del servicio", NotificacionKind.COMUNICACION_GENERAL, NotificacionPriority.NORMAL),
    ("Información general para contribuyentes", NotificacionKind.COMUNICACION_GENERAL, NotificacionPriority.NORMAL),
]


@pytest.mark.unit
@pytest.mark.parametrize(("subject_es", "expected_kind", "expected_priority"), _POSITIVE_CASES)
def test_classifier_rules(
    subject_es: str,
    expected_kind: NotificacionKind,
    expected_priority: NotificacionPriority,
) -> None:
    kind, priority = classify(_raw(subject_es))
    assert kind is expected_kind
    assert priority is expected_priority


_UNCLASSIFIED_CASES = [
    "Aviso de novedad en tu área personal",
    "Procedimiento desconocido inventado 2030",
    "",
    "   ",
    "Other-subject-that-AEAT-may-invent-later",
    "Notificación sin prefijo reconocido",
    "NUEVO TIPO QUE NO EXISTE",
]


@pytest.mark.unit
@pytest.mark.parametrize("subject_es", _UNCLASSIFIED_CASES)
def test_unclassified_defaults_to_otro_high(subject_es: str) -> None:
    """ADR D3: anything we do not recognise is (OTRO, HIGH)."""
    kind, priority = classify(_raw(subject_es))
    assert kind is NotificacionKind.OTRO
    assert priority is NotificacionPriority.HIGH


@pytest.mark.unit
def test_classifier_covers_every_kind() -> None:
    """Every NotificacionKind must appear as the result of at least one rule or the fallback."""
    seen_kinds = {classify(_raw(subject))[0] for subject, _, _ in _POSITIVE_CASES}
    seen_kinds.add(classify(_raw("NUEVO TIPO"))[0])  # fallback -> OTRO
    assert seen_kinds == set(NotificacionKind)


@pytest.mark.unit
def test_classifier_is_accent_insensitive() -> None:
    """Accented and unaccented Spanish must match the same rule."""
    assert classify(_raw("Requerimiento de información"))[0] is NotificacionKind.REQUERIMIENTO
    assert classify(_raw("requerimiento de informacion"))[0] is NotificacionKind.REQUERIMIENTO


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kind", "expected_days"),
    [
        (NotificacionKind.REQUERIMIENTO, 10),
        (NotificacionKind.PROPUESTA_LIQUIDACION, 15),
        (NotificacionKind.ACUERDO_LIQUIDACION, 30),
        (NotificacionKind.NOTIFICACION_EMBARGO, 30),
    ],
)
def test_appeal_window_days(kind: NotificacionKind, expected_days: int) -> None:
    window = appeal_window_for(kind)
    assert window is not None
    assert window.days == expected_days


@pytest.mark.unit
@pytest.mark.parametrize(
    "kind",
    [NotificacionKind.ACUSE_RECIBO, NotificacionKind.COMUNICACION_GENERAL, NotificacionKind.OTRO],
)
def test_appeal_window_none(kind: NotificacionKind) -> None:
    assert appeal_window_for(kind) is None


@pytest.mark.unit
def test_compute_appeal_deadline_applies_window() -> None:
    effective_at = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    deadline = compute_appeal_deadline(effective_at, NotificacionKind.REQUERIMIENTO)
    assert deadline is not None
    assert deadline.isoformat() == "2026-04-11"


@pytest.mark.unit
def test_compute_appeal_deadline_none_for_informational() -> None:
    effective_at = datetime(2026, 4, 1, tzinfo=UTC)
    assert compute_appeal_deadline(effective_at, NotificacionKind.ACUSE_RECIBO) is None
