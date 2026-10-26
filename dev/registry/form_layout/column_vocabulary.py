"""The shared grid column vocabulary.

A grid column whose legal meaning recurs across modelos -- base imponible, tipo,
cuota, the three columns of a withholding summary -- carries one shared
catalogue key rather than one key per modelo, so it is translated once. The
vocabulary maps the design's own column wording, folded for comparison, onto
that key. A column the vocabulary does not recognise keeps a per-modelo key.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

__all__ = ["SHARED_COLUMN_HEADING_KEY_PREFIX", "SHARED_COLUMN_KEYS", "shared_column_key"]

SHARED_COLUMN_HEADING_KEY_PREFIX: Final[str] = "modelo.form.column"

_WORDING: Final[Mapping[str, str]] = MappingProxyType(
    {
        "base imponible": "base_imponible",
        "base": "base_imponible",
        "bases imponibles": "base_imponible",
        "tipo": "tipo",
        "tipo pct": "tipo",
        "tipo de gravamen": "tipo",
        "porcentaje": "tipo",
        "cuota": "cuota",
        "cuotas": "cuota",
        "cuota soportada": "cuota_soportada",
        "cuotas soportadas": "cuota_soportada",
        "cuota deducible": "cuota_deducible",
        "cuotas deducibles": "cuota_deducible",
        "no de perceptores": "numero_perceptores",
        "numero de perceptores": "numero_perceptores",
        "no perceptores": "numero_perceptores",
        "importe de las percepciones": "importe_percepciones",
        "importe percepciones": "importe_percepciones",
        "importe de las retenciones": "importe_retenciones",
        "importe retenciones": "importe_retenciones",
        "retenciones": "importe_retenciones",
        "valor percepciones en especie": "valor_percepciones_especie",
        "valor de las percepciones en especie": "valor_percepciones_especie",
        "importe de los ingresos a cuenta": "ingresos_a_cuenta",
        "importe ingresos a cuenta": "ingresos_a_cuenta",
        "ingresos a cuenta": "ingresos_a_cuenta",
        "aumentos": "aumentos",
        "disminuciones": "disminuciones",
        "pendiente de aplicacion al principio del periodo": "pendiente_inicio",
        "pendiente de aplicacion a principio del periodo": "pendiente_inicio",
        "pendiente de aplicacion en periodos futuros": "pendiente_futuro",
        "pendiente de aplicacion en periodos impositivos futuros": "pendiente_futuro",
        "aplicado en esta liquidacion": "aplicado",
        "aplicado en la liquidacion": "aplicado",
        "aplicada en esta liquidacion": "aplicado",
        "deduccion pendiente": "pendiente_inicio",
        "aplicado": "aplicado",
        "no de declarados": "numero_declarados",
        "numero de declarados": "numero_declarados",
        "importe total": "importe_total",
        "importe de las operaciones": "importe_operaciones",
        "importe de operaciones": "importe_operaciones",
        "importe de operaciones con derecho a deduccion": "importe_operaciones_derecho_deduccion",
        "codigo cnae": "codigo_cnae",
        "tipo de prorrata": "tipo_prorrata",
        "pct de prorrata": "porcentaje_prorrata",
        "base impon": "base_imponible",
        "cuota deduc": "cuota_deducible",
        "total": "total",
        "deduccion pendiente generada": "pendiente_generada",
        "pendiente aplicacion a principio del periodo generada en el periodo": "pendiente_generada",
        "importe generado pendiente principio periodo": "pendiente_generada",
        "pendiente aplicacion en periodos futuros": "pendiente_futuro",
        "pendiente aplic en periodos futuros": "pendiente_futuro",
        "importe aplicado": "aplicado",
        "base deduccion": "base_deduccion",
        "base de la deduccion": "base_deduccion",
        "importe de la deduccion": "importe_deduccion",
        "permanentes": "diferencias_permanentes",
        "temporarias con origen en el ejercicio": "diferencias_temporarias_ejercicio",
        "temporarias con origen en ejercicios anteriores": "diferencias_temporarias_anteriores",
        "estado": "territorio_estado",
        "araba alava": "territorio_araba_alava",
        "gipuzkoa": "territorio_gipuzkoa",
        "bizkaia": "territorio_bizkaia",
        "navarra": "territorio_navarra",
    }
)

#: Every shared column key, which the catalogue must translate in each locale.
SHARED_COLUMN_KEYS: Final[frozenset[str]] = frozenset(_WORDING.values())


def _fold(text: str) -> str:
    spelled = text.replace("º", "o").replace("ª", "a").replace("%", " pct ").replace("nº", "no")
    folded = unicodedata.normalize("NFKD", spelled).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", folded).split())


def shared_column_key(column_text: str) -> str | None:
    """Return the shared key for a design column wording, or ``None`` when it is not shared."""
    return _WORDING.get(_fold(column_text))
