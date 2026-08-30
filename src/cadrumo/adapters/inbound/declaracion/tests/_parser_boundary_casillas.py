"""Shared casilla constants for parser boundary tests."""

from __future__ import annotations

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import CasillaId

_M303_CASILLA_27: CasillaId = validated_casilla_id("27", surface="declaracion_parser_boundary.casilla")
_M303_CASILLA_29: CasillaId = validated_casilla_id("29", surface="declaracion_parser_boundary.casilla")
_M303_CASILLA_37: CasillaId = validated_casilla_id("37", surface="declaracion_parser_boundary.casilla")
_M303_CASILLA_45: CasillaId = validated_casilla_id("45", surface="declaracion_parser_boundary.casilla")
_M303_CASILLA_64: CasillaId = validated_casilla_id("64", surface="declaracion_parser_boundary.casilla")
_M303_CASILLA_66: CasillaId = validated_casilla_id("66", surface="declaracion_parser_boundary.casilla")
_M303_CASILLA_71: CasillaId = validated_casilla_id("71", surface="declaracion_parser_boundary.casilla")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.resultado-regimen-general", surface="declaracion_parser_boundary.casilla"
)
_M303_COMPENSACION_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores", surface="declaracion_parser_boundary.casilla"
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-aplicada-periodo", surface="declaracion_parser_boundary.casilla"
)
_M303_COMPENSACION_POSTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-posteriores", surface="declaracion_parser_boundary.casilla"
)
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id(
    "iva.resultado", surface="declaracion_parser_boundary.casilla"
)
_M349_NUMERO_OPERADORES_CASILLA: CasillaId = validated_casilla_id(
    "decl.numero-operadores", surface="declaracion_parser_boundary.casilla"
)
_M349_IMPORTE_OPERACIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.importe-operaciones", surface="declaracion_parser_boundary.casilla"
)
_M349_NUMERO_RECTIFICACIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.numero-rectificaciones", surface="declaracion_parser_boundary.casilla"
)
_M349_IMPORTE_RECTIFICACIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.importe-rectificaciones", surface="declaracion_parser_boundary.casilla"
)
_M840_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id(
    "decl.tipo-declaracion", surface="declaracion_parser_boundary.casilla"
)
_M840_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio", surface="declaracion_parser_boundary.casilla"
)
_M036_EVENT_KIND_CASILLA: CasillaId = validated_casilla_id(
    "decl.event-kind", surface="declaracion_parser_boundary.casilla"
)
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="declaracion_parser_boundary.casilla")
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19", surface="declaracion_parser_boundary.casilla")
