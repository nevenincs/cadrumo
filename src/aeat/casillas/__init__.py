"""Curated AEAT casilla catalogues.

This subpackage owns the strict pydantic models, JSON persistence helpers, and
verification flow for curated casilla data stored under `corpus/casillas/`.
"""

from __future__ import annotations

from .catalogue import DEFAULT_CASILLAS_ROOT, iter_casillas, load_casillas, save_casillas, verify_casillas
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
    "save_casillas",
    "verify_casillas",
]
