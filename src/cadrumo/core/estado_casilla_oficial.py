"""Closed classification for a casilla's official filing representation."""

from __future__ import annotations

from enum import StrEnum


class EstadoCasillaOficial(StrEnum):
    """How a registry casilla is represented by an official export surface."""

    ADDRESSED = "addressed"
    """An official layout addresses the casilla identity directly."""

    REPRESENTED_VIA_BINDING = "represented_via_binding"
    """A binding-derived official field represents the casilla indirectly."""

    UNDEFINED = "undefined"
    """The revision declares no official layout answer for the casilla."""


__all__ = ["EstadoCasillaOficial"]
