"""Shared Modelo 232 synthetic fixture expectations."""

from __future__ import annotations

from pathlib import Path

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import _MODELO_232_2016_SYNTHETIC_FIXTURE, _MODELO_232_2018_SYNTHETIC_FIXTURE, CasillaId

_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio", surface="declaracion_parser_boundary.casilla"
)
_DECL_TIPO_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.tipo-ejercicio", surface="declaracion_parser_boundary.casilla"
)
_DECL_CNAE_CASILLA: CasillaId = validated_casilla_id("decl.cnae", surface="declaracion_parser_boundary.casilla")
_M232_PROFILE_CASILLAS: frozenset[CasillaId] = frozenset(
    {
        _DECL_EJERCICIO_CASILLA,
        _DECL_TIPO_EJERCICIO_CASILLA,
        _DECL_CNAE_CASILLA,
    },
)
_M232_FIXTURE_PARAMS: tuple[tuple[Path, int, str, str], ...] = (
    (_MODELO_232_2016_SYNTHETIC_FIXTURE, 2016, "2016-2017", "2016"),
    (_MODELO_232_2018_SYNTHETIC_FIXTURE, 2018, "2018-y-siguientes", "2018"),
)
