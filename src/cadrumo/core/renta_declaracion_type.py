"""Canonical Renta filing-modality vocabulary."""

from enum import StrEnum


class RentaDeclaracionType(StrEnum):
    """Modelo 100 TIPOTRIBUTACION values."""

    INDIVIDUAL = "1"
    JOINT = "2"


__all__ = ["RentaDeclaracionType"]
