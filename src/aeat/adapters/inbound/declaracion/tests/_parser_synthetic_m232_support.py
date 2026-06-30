"""Shared Modelo 232 synthetic fixture expectations."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ._parser_boundary_support import (
    _MODELO_232_2016_SYNTHETIC_FIXTURE,
    _MODELO_232_2018_SYNTHETIC_FIXTURE,
    CasillaId,
    _casilla_id,
)

_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_DECL_TIPO_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.tipo-ejercicio")
_DECL_CNAE_CASILLA: CasillaId = _casilla_id("decl.cnae")
_M232_PROFILE_CASILLAS: frozenset[CasillaId] = frozenset(
    {
        _DECL_EJERCICIO_CASILLA,
        _DECL_TIPO_EJERCICIO_CASILLA,
        _DECL_CNAE_CASILLA,
    },
)
_M232_FIXTURE_PARAMS: tuple[tuple[Path, int, str, Decimal], ...] = (
    (_MODELO_232_2016_SYNTHETIC_FIXTURE, 2016, "2016-2017", Decimal("2016")),
    (_MODELO_232_2018_SYNTHETIC_FIXTURE, 2018, "2018-y-siguientes", Decimal("2018")),
)
