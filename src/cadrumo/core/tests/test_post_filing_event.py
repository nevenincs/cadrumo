"""Tests for the AEAT post-filing event taxonomy and its classifier.

Expected classifications are derived from the standard AEAT trámite
concepto vocabulary published on the sede electrónica (the demand,
comprobación, liquidación, sancionador, and recaudación categories), not
from re-running the classifier's own substring table.
"""

from __future__ import annotations

import pytest

from ..post_filing_event import (
    ACTIONABLE_POST_FILING_EVENT_KINDS,
    PostFilingEventKind,
    classify_post_filing_event_kind,
    post_filing_event_is_actionable,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_classifier_maps_concepto_to_expected_category() -> None:
    for concepto, tipo, expected in (
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
    ):
        assert classify_post_filing_event_kind(concepto=concepto, tipo=tipo) is expected, concepto


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


def test_tipo_fallback_when_concepto_is_uninformative() -> None:
    for tipo, expected in (
        ("notificacion", PostFilingEventKind.NOTIFICACION),
        ("comunicacion", PostFilingEventKind.COMUNICACION),
        ("pendiente", PostFilingEventKind.PENDIENTE),
    ):
        assert classify_post_filing_event_kind(concepto="", tipo=tipo) is expected, tipo


def test_unknown_concepto_and_tipo_resolve_to_other() -> None:
    assert classify_post_filing_event_kind(concepto="", tipo="unknown") is PostFilingEventKind.OTHER
    assert classify_post_filing_event_kind(concepto=None, tipo=None) is PostFilingEventKind.OTHER


def test_actionable_taxonomy_flags_only_operator_response_categories() -> None:
    # The actionable set is exactly the demand / liquidación / sancionador /
    # recaudación categories that require an operator response or signal
    # enforcement — not the informational notificación / comunicación / acuse.
    expected_actionable = frozenset(
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

    assert expected_actionable == ACTIONABLE_POST_FILING_EVENT_KINDS
    for kind in PostFilingEventKind:
        assert post_filing_event_is_actionable(kind) is (kind in expected_actionable), kind


def test_enum_values_are_stable_stored_tokens() -> None:
    # The StrEnum values are the persisted/serialised tokens; pin them so a
    # rename cannot silently drift a stored payload.
    assert PostFilingEventKind.REQUERIMIENTO.value == "requerimiento"
    assert PostFilingEventKind.DILIGENCIA_EMBARGO.value == "diligencia_embargo"
    assert PostFilingEventKind.DECLARACION_PRESENTADA.value == "declaracion_presentada"
