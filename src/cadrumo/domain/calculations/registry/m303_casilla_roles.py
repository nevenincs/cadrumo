"""Modelo 303 casillas consumers locate by the semantic role each edition declares."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import RegistryValidationError

if TYPE_CHECKING:
    from ....core.casilla_id import CasillaId
    from .schema import ModeloRevision

__all__ = [
    "m303_importe_rectificacion_casilla",
    "m303_resultado_final_casilla",
]

_RESULTADO_FINAL_ROLE = "iva_resultado_final"
_IMPORTE_RECTIFICACION_ROLE = "iva_importe_rectificacion"


def _casilla_with_role(revision: ModeloRevision, role: str) -> CasillaId | None:
    matches = tuple(casilla.id for casilla in revision.casillas if casilla.semantic_role == role)
    if len(matches) > 1:
        raise RegistryValidationError(f"revision {revision.id!r} declares role {role!r} on {sorted(matches)!r}")
    return matches[0] if matches else None


def m303_resultado_final_casilla(revision: ModeloRevision) -> CasillaId:
    """Return the box carrying the final result of the liquidation.

    Raises:
        RegistryValidationError: When the revision does not declare the role.
    """
    casilla_id = _casilla_with_role(revision, _RESULTADO_FINAL_ROLE)
    if casilla_id is None:
        raise RegistryValidationError(f"revision {revision.id!r} does not declare role {_RESULTADO_FINAL_ROLE!r}")
    return casilla_id


def m303_importe_rectificacion_casilla(revision: ModeloRevision) -> CasillaId | None:
    """Return the box stating the rectified amount, or ``None`` on an edition without one."""
    return _casilla_with_role(revision, _IMPORTE_RECTIFICACION_ROLE)
