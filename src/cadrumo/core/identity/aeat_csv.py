"""Canonical AEAT Código Seguro de Verificación identifier."""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, StringConstraints

from ..aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH, normalise_aeat_csv

__all__ = ["AeatCsv"]


AeatCsv = Annotated[
    str,
    BeforeValidator(normalise_aeat_csv),
    StringConstraints(
        min_length=AEAT_CSV_MIN_LENGTH,
        max_length=AEAT_CSV_MAX_LENGTH,
        pattern=rf"^[A-Z0-9]{{{AEAT_CSV_MIN_LENGTH},{AEAT_CSV_MAX_LENGTH}}}$",
    ),
]
"""AEAT's CSV, normalised before its uppercase alphanumeric constraints run."""
