"""Shared constants for the parser boundary corpus split."""

from __future__ import annotations

from collections.abc import Mapping

from ._parser_boundary_support import CasillaId, Decimal, _casilla_id


def _expected_casilla_values(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return {_casilla_id(casilla_id): amount for casilla_id, amount in values.items()}


_M303_CASILLA_27: CasillaId = _casilla_id("27")
_M303_CASILLA_29: CasillaId = _casilla_id("29")
_M303_CASILLA_37: CasillaId = _casilla_id("37")
_M303_CASILLA_45: CasillaId = _casilla_id("45")
_M303_CASILLA_64: CasillaId = _casilla_id("64")
_M303_CASILLA_66: CasillaId = _casilla_id("66")
_M303_CASILLA_71: CasillaId = _casilla_id("71")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_ANTERIORES_CASILLA: CasillaId = _casilla_id("iva.compensacion-pendiente-periodos-anteriores")
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-aplicada-periodo")
_M303_COMPENSACION_POSTERIORES_CASILLA: CasillaId = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
_M349_NUMERO_OPERADORES_CASILLA: CasillaId = _casilla_id("decl.numero-operadores")
_M349_IMPORTE_OPERACIONES_CASILLA: CasillaId = _casilla_id("decl.importe-operaciones")
_M349_NUMERO_RECTIFICACIONES_CASILLA: CasillaId = _casilla_id("decl.numero-rectificaciones")
_M349_IMPORTE_RECTIFICACIONES_CASILLA: CasillaId = _casilla_id("decl.importe-rectificaciones")
_M840_TIPO_DECLARACION_CASILLA: CasillaId = _casilla_id("decl.tipo-declaracion")
_M840_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_M036_EVENT_KIND_CASILLA: CasillaId = _casilla_id("decl.event-kind")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = _casilla_id("03")
_M130_RESULTADO_CASILLA: CasillaId = _casilla_id("19")
