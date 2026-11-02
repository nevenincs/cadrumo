"""The operator-facing label of each suffered-withholding income class.

A label names the class in the official Renta vocabulary, in the configured
output language. The table is a literal mapping so the locale audit sees every
key reach the translator; adding a class without a label fails at import.
"""

from __future__ import annotations

from typing import Final

from .i18n.render import tr
from .retencion_soportada import RetencionSoportadaClase

__all__ = ["RETENCION_SOPORTADA_CLASE_LABEL_KEYS", "retencion_soportada_clase_label"]

RETENCION_SOPORTADA_CLASE_LABEL_KEYS: Final[dict[RetencionSoportadaClase, str]] = {
    RetencionSoportadaClase.TRABAJO: "aggregation.retencion_soportada.clase.trabajo",
    RetencionSoportadaClase.CAPITAL_MOBILIARIO: "aggregation.retencion_soportada.clase.capital_mobiliario",
    RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO: (
        "aggregation.retencion_soportada.clase.arrendamiento_inmueble_urbano"
    ),
    RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD: (
        "aggregation.retencion_soportada.clase.arrendamiento_inmueble_urbano_actividad"
    ),
    RetencionSoportadaClase.ACTIVIDAD_ECONOMICA: "aggregation.retencion_soportada.clase.actividad_economica",
    RetencionSoportadaClase.GANANCIA_PATRIMONIAL: "aggregation.retencion_soportada.clase.ganancia_patrimonial",
    RetencionSoportadaClase.ATRIBUCION_CAPITAL_MOBILIARIO: (
        "aggregation.retencion_soportada.clase.atribucion_capital_mobiliario"
    ),
    RetencionSoportadaClase.ATRIBUCION_CAPITAL_INMOBILIARIO: (
        "aggregation.retencion_soportada.clase.atribucion_capital_inmobiliario"
    ),
    RetencionSoportadaClase.ATRIBUCION_ACTIVIDAD_ECONOMICA: (
        "aggregation.retencion_soportada.clase.atribucion_actividad_economica"
    ),
    RetencionSoportadaClase.ATRIBUCION_GANANCIA_PATRIMONIAL: (
        "aggregation.retencion_soportada.clase.atribucion_ganancia_patrimonial"
    ),
    RetencionSoportadaClase.IMPUTACION_AIE_UTE: "aggregation.retencion_soportada.clase.imputacion_aie_ute",
    RetencionSoportadaClase.IMPUTACION_DERECHOS_IMAGEN: (
        "aggregation.retencion_soportada.clase.imputacion_derechos_imagen"
    ),
}
"""The locale key of each income class's label; every member has one."""

if frozenset(RETENCION_SOPORTADA_CLASE_LABEL_KEYS) != frozenset(RetencionSoportadaClase):
    raise ImportError("every suffered-withholding income class needs exactly one label key")


def retencion_soportada_clase_label(income_class: RetencionSoportadaClase) -> str:
    """Return the label of ``income_class`` in the configured output language."""
    return tr(RETENCION_SOPORTADA_CLASE_LABEL_KEYS[RetencionSoportadaClase(income_class)])
