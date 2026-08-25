"""Shared support for Modelo 349 registry tests."""

from __future__ import annotations

from functools import lru_cache

from .....core import CasillaId, validated_casilla_id
from .....tests.aeat_literal_fixtures import aeat_host
from .....tests.registry_tree import bundled_registry_tree
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues

_WWW6_HOST = aeat_host("www6")

# Field positions taken from Orden HAC/174/2020 Anexo (DR_Anexo_349.pdf
# pages 9-22), the layout authority cited by Modelo 349's registry revision.
# Tipo 1 = registro de declarante (500 bytes); Tipo 2 = registro de operador
# intracomunitario / rectificaciones (500 bytes).


_DECL_NUMERO_OPERADORES_CASILLA: CasillaId = validated_casilla_id(
    "decl.numero-operadores", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_DECL_IMPORTE_OPERACIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.importe-operaciones", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_DECL_NUMERO_RECTIFICACIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.numero-rectificaciones", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_DECL_IMPORTE_RECTIFICACIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.importe-rectificaciones", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_OP_CODIGO_PAIS_CASILLA: CasillaId = validated_casilla_id(
    "op.codigo-pais", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_OP_NIF_COMUNITARIO_CASILLA: CasillaId = validated_casilla_id(
    "op.nif-comunitario", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_OP_APELLIDOS_RAZON_SOCIAL_CASILLA: CasillaId = validated_casilla_id(
    "op.apellidos-razon-social", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_OP_CLAVE_OPERACION_CASILLA: CasillaId = validated_casilla_id(
    "op.clave-operacion", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_OP_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "op.base-imponible", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_RECT_EJERCICIO_RECTIFICADO_CASILLA: CasillaId = validated_casilla_id(
    "rect.ejercicio-rectificado", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_RECT_PERIODO_RECTIFICADO_CASILLA: CasillaId = validated_casilla_id(
    "rect.periodo-rectificado", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_RECT_BASE_RECTIFICADA_CASILLA: CasillaId = validated_casilla_id(
    "rect.base-rectificada", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_RECT_BASE_ANTERIOR_CASILLA: CasillaId = validated_casilla_id(
    "rect.base-anterior", surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS"
)
_DECLARANT_SUMMARY_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_NUMERO_OPERADORES_CASILLA,
    _DECL_IMPORTE_OPERACIONES_CASILLA,
    _DECL_NUMERO_RECTIFICACIONES_CASILLA,
    _DECL_IMPORTE_RECTIFICACIONES_CASILLA,
)
_M349_SUBSTANTIVE_BINDING_LEGAL_REFS = frozenset(
    {
        "rd-1624-1992:art-79",
        "rd-1624-1992:art-80",
        "ley-37-1992:art-9-bis",
        "ley-37-1992:art-13",
        "ley-37-1992:art-15",
        "ley-37-1992:art-25",
        "ley-37-1992:art-26",
        "ley-37-1992:art-27",
        "ley-37-1992:art-69",
        "ley-37-1992:art-70",
        "ley-37-1992:art-80",
        "ley-37-1992:art-84",
        "ley-37-1992:art-86",
    },
)

_OFFICIAL_FIELD_POSITIONS: dict[CasillaId, tuple[int, int]] = {
    _DECL_NUMERO_OPERADORES_CASILLA: (138, 146),
    _DECL_IMPORTE_OPERACIONES_CASILLA: (147, 161),
    _DECL_NUMERO_RECTIFICACIONES_CASILLA: (162, 170),
    _DECL_IMPORTE_RECTIFICACIONES_CASILLA: (171, 185),
    _OP_CODIGO_PAIS_CASILLA: (76, 77),
    _OP_NIF_COMUNITARIO_CASILLA: (78, 92),
    _OP_APELLIDOS_RAZON_SOCIAL_CASILLA: (93, 132),
    _OP_CLAVE_OPERACION_CASILLA: (133, 133),
    _OP_BASE_IMPONIBLE_CASILLA: (134, 146),
    _RECT_EJERCICIO_RECTIFICADO_CASILLA: (147, 150),
    _RECT_PERIODO_RECTIFICADO_CASILLA: (151, 152),
    _RECT_BASE_RECTIFICADA_CASILLA: (153, 165),
    _RECT_BASE_ANTERIOR_CASILLA: (166, 178),
}
_OFFICIAL_FIELD_WIDTHS: dict[CasillaId, int] = {
    casilla_id: end - start + 1 for casilla_id, (start, end) in _OFFICIAL_FIELD_POSITIONS.items()
}
_M349_GB_XI_SOURCE_REF = "aeat-modelo-349-instructions"
_M349_GB_XI_ORDINARY_BINDINGS = (
    "iva-349-operador-row-codigo-pais",
    "iva-349-operador-row-codigo-pais-adquisicion",
)
_M349_GB_XI_RECTIFICATION_BINDINGS = (
    "iva-349-rectificacion-row-codigo-pais",
    "iva-349-rectificacion-row-codigo-pais-adquisicion",
)
_M349_GB_XI_ORDINARY_REQUIRED_TEXT = (
    "exclusivamente para los bienes (no para servicios)",
    "NIVA que comenzará por XI",
    "Para los períodos 1M y 1T de 2021, el modelo 349 admitirá los prefijos GB y XI",
    "Para los periodos 2M a 12M y 2T a 4T de 2021 sólo se admitirá el prefijo XI",
)
_M349_GB_XI_RECTIFICATION_REQUIRED_TEXT = (
    "Para las rectificaciones de operaciones anteriores a 2021, sólo se admitirá el prefijo GB",
    "Para las rectificaciones de operaciones del 1M o 1T de 2021",
    "Para las rectificaciones de operaciones de 2M a 12M y 2T a 4T de 2021, sólo se admitirá el prefijo XI",
)
_M349_CADENCE_LEGAL_REF = "rd-1624-1992:art-81"
_M349_CADENCE_REQUIRED_TEXT = (
    "Lugar, forma y plazos de presentacion de la declaracion recapitulativa",
    "por cada mes natural durante los veinte primeros dias naturales",
    "en cada uno de los cuatro trimestres naturales anteriores",
    "50.000 euros",
    "durante los veinte primeros dias naturales del mes inmediato siguiente al correspondiente periodo trimestral",
)


@lru_cache(maxsize=1)
def _load_modelo_349() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "349")
    return modelo, catalogues


def _modelo_349_revision() -> ModeloRevision:
    modelo, _ = _load_modelo_349()
    return modelo.revisions["2020-y-siguientes"]


def _fixed_width_record(length: int, fields: dict[tuple[int, int], str]) -> str:
    record = [" "] * length
    for (start, end), value in fields.items():
        if len(value) != end - start + 1:
            raise AssertionError(f"field {start}-{end} has length {len(value)}")
        record[start - 1 : end] = value
    return "".join(record)
