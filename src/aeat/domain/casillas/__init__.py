"""Curated AEAT casilla catalogues.

Owns the strict pydantic models, JSON read helpers, and the
verification flow for the curated casilla data committed under
``corpus/casillas/``. A casilla is one numbered field on an AEAT
modelo (e.g. ``modelo 303`` casilla ``01``) and the catalogue is the
typed, machine-readable view the rest of the system builds against.

Public surface:

* :class:`CasillaCatalogue`, :class:`CasillaRecord`,
  :class:`SelectOption`, :class:`LLMDraftProvenance`: the strict
  immutable pydantic models.
* :class:`CasillaDataType`, :class:`PeriodType`, :class:`ModeloCode`:
  the closed enumerations.
* :func:`load_casillas`, :func:`iter_casillas`, :func:`verify_casillas`,
  :data:`DEFAULT_CASILLAS_ROOT`: the catalogue read and verification helpers.
* :exc:`CasillaError` and its concrete subtypes
  (:exc:`CasillaParseError`, :exc:`VerifyError`,
  :exc:`MissingFieldError`, :exc:`UnreviewedRecordError`,
  :exc:`CrossReferenceError`).
"""

from __future__ import annotations

from .catalogue import DEFAULT_CASILLAS_ROOT, iter_casillas, load_casillas, verify_casillas
from .errors import (
    CasillaError,
    CasillaParseError,
    CrossReferenceError,
    MissingFieldError,
    UnreviewedRecordError,
    VerifyError,
)
from .models import (
    CasillaCatalogue,
    CasillaDataType,
    CasillaRecord,
    LLMDraftProvenance,
    ModeloCode,
    PeriodType,
    SelectOption,
)

__all__ = [
    "DEFAULT_CASILLAS_ROOT",
    "CasillaCatalogue",
    "CasillaDataType",
    "CasillaError",
    "CasillaParseError",
    "CasillaRecord",
    "CrossReferenceError",
    "LLMDraftProvenance",
    "MissingFieldError",
    "ModeloCode",
    "PeriodType",
    "SelectOption",
    "UnreviewedRecordError",
    "VerifyError",
    "iter_casillas",
    "load_casillas",
    "verify_casillas",
]
