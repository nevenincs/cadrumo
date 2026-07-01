"""Tests for the AEAT post-filing event taxonomy and its classifier.

Expected classifications are derived from the standard AEAT trámite
concepto vocabulary published on the sede electrónica (the demand,
comprobación, liquidación, sancionador, and recaudación categories), not
from re-running the classifier's own substring table.
"""

from __future__ import annotations

import pytest

from aeat.core import (
    ACTIONABLE_POST_FILING_EVENT_KINDS,
    PostFilingEventKind,
    classify_post_filing_event_kind,
    post_filing_event_is_actionable,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("concepto", "tipo", "expected"),
    [
        # Recaudación enforcement — highest severity, wins over co-mentions.
        ("Diligencia de embargo de cuentas y depósitos", "notificacion", PostFilingEventKind.DILIGENCIA_EMBARGO),
        ("Providencia de apremio con recargo del 20%", "notificacion", PostFilingEventKind.PROVIDENCIA_APREMIO),
        # Sancionador.
        (
            "Acuerdo de inicio de procedimiento sancionador",
            "notificacion",
            PostFilingEventKind.ACUERDO_SANCION,
        ),
        # Liquidación chain: propuesta before the confirmed liquidación.
        (
            "Propuesta de liquidación provisional IRPF 2023",
            "notificacion",
            PostFilingEventKind.PROPUESTA_LIQUIDACION,
        ),
        ("Acuerdo de liquidación provisional", "notificacion", PostFilingEventKind.LIQUIDACION),
        # Demand and comprobación.
        ("Requerimiento de documentación relativa al IVA", "notificacion", PostFilingEventKind.REQUERIMIENTO),
        (
            "Inicio de procedimiento de verificación de datos",
            "notificacion",
            PostFilingEventKind.COMPROBACION,
        ),
        ("Comunicación de inicio de comprobación limitada", "notificacion", PostFilingEventKind.COMPROBACION),
        # Refund / resolution / receipt.
        ("Acuerdo de devolución de ingresos indebidos", "comunicacion", PostFilingEventKind.DEVOLUCION),
        ("Resolución del recurso de reposición", "notificacion", PostFilingEventKind.RESOLUCION),
        ("Acuse de recibo de la notificación", "comunicacion", PostFilingEventKind.ACUSE_RECIBO),
    ],
)
def test_classifier_maps_concepto_to_expected_category(
    concepto: str,
    tipo: str,
    expected: PostFilingEventKind,
) -> None:
    assert classify_post_filing_event_kind(concepto=concepto, tipo=tipo) is expected


def test_classifier_is_accent_and_case_insensitive() -> None:
    # A concepto AEAT prints without accents (or upper-cased) must classify the
    # same as the accented, mixed-case form.
    assert (
        classify_post_filing_event_kind(concepto="REQUERIMIENTO DE INFORMACION", tipo=None)
        is PostFilingEventKind.REQUERIMIENTO
    )
    assert (
        classify_post_filing_event_kind(concepto="propuesta de liquidacion", tipo=None)
        is PostFilingEventKind.PROPUESTA_LIQUIDACION
    )


def test_severity_priority_prefers_enforcement_over_liquidacion() -> None:
    # A recaudación diligencia that also names a prior liquidación classifies as
    # the embargo (the more severe, more specific enforcement act).
    kind = classify_post_filing_event_kind(
        concepto="Diligencia de embargo derivada de liquidación provisional",
        tipo="notificacion",
    )
    assert kind is PostFilingEventKind.DILIGENCIA_EMBARGO


@pytest.mark.parametrize(
    ("tipo", "expected"),
    [
        ("notificacion", PostFilingEventKind.NOTIFICACION),
        ("comunicacion", PostFilingEventKind.COMUNICACION),
        ("pendiente", PostFilingEventKind.PENDIENTE),
    ],
)
def test_tipo_fallback_when_concepto_is_uninformative(
    tipo: str,
    expected: PostFilingEventKind,
) -> None:
    assert classify_post_filing_event_kind(concepto="", tipo=tipo) is expected


def test_unknown_concepto_and_tipo_resolve_to_other() -> None:
    assert classify_post_filing_event_kind(concepto="", tipo="unknown") is PostFilingEventKind.OTHER
    assert classify_post_filing_event_kind(concepto=None, tipo=None) is PostFilingEventKind.OTHER


def test_actionable_set_covers_demand_and_enforcement_categories() -> None:
    # The actionable set is exactly the demand / liquidación / sancionador /
    # recaudación categories that require an operator response or signal
    # enforcement — not the informational notificación / comunicación / acuse.
    assert (
        frozenset(
            {
                PostFilingEventKind.REQUERIMIENTO,
                PostFilingEventKind.COMPROBACION,
                PostFilingEventKind.PROPUESTA_LIQUIDACION,
                PostFilingEventKind.LIQUIDACION,
                PostFilingEventKind.ACUERDO_SANCION,
                PostFilingEventKind.PROVIDENCIA_APREMIO,
                PostFilingEventKind.DILIGENCIA_EMBARGO,
            },
        )
        == ACTIONABLE_POST_FILING_EVENT_KINDS
    )


@pytest.mark.parametrize(
    "kind",
    [
        PostFilingEventKind.REQUERIMIENTO,
        PostFilingEventKind.PROPUESTA_LIQUIDACION,
        PostFilingEventKind.DILIGENCIA_EMBARGO,
        PostFilingEventKind.PROVIDENCIA_APREMIO,
    ],
)
def test_actionable_kinds_are_flagged(kind: PostFilingEventKind) -> None:
    assert post_filing_event_is_actionable(kind) is True


@pytest.mark.parametrize(
    "kind",
    [
        PostFilingEventKind.DECLARACION_PRESENTADA,
        PostFilingEventKind.NOTIFICACION,
        PostFilingEventKind.COMUNICACION,
        PostFilingEventKind.ACUSE_RECIBO,
        PostFilingEventKind.PENDIENTE,
        PostFilingEventKind.OTHER,
    ],
)
def test_non_actionable_kinds_are_not_flagged(kind: PostFilingEventKind) -> None:
    assert post_filing_event_is_actionable(kind) is False


def test_enum_values_are_stable_stored_tokens() -> None:
    # The StrEnum values are the persisted/serialised tokens; pin them so a
    # rename cannot silently drift a stored payload.
    assert PostFilingEventKind.REQUERIMIENTO.value == "requerimiento"
    assert PostFilingEventKind.DILIGENCIA_EMBARGO.value == "diligencia_embargo"
    assert PostFilingEventKind.DECLARACION_PRESENTADA.value == "declaracion_presentada"
