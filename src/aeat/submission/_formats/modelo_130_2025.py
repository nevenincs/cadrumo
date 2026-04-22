"""Fichero-BOE record spec for Modelo 130 ejercicio 2025.

Wave 80b (EPIC #201 / EPIC #305). Structural clone of
:mod:`modelo_130_2024` — AEAT has not published a new Modelo 130
*Diseño de registros* for ejercicio 2025. Orden EHA/672/2007
(BOE-A-2007-6032) + DR130e15v12.xls remain canonical; neither
Orden HAC/819/2024 (IVA) nor Orden HAC/242/2025 (Modelo 100
rectificativa) touch the Modelo 130 layout.

Kent uses this module when exporting a 2025-period filing. The
schema, encoding, record length, and required headers are
identical to the 2024 variant. This module exists for two
reasons:

1. Future-proofing: if AEAT publishes a Modelo 130-specific
   Orden for 2026, the delta lands here without churning 2024-
   period exports.
2. Per-year filing-id stamping: the ``EJERCICIO`` value in the
   emitted payload is the key AEAT correlates against the
   submission calendar.

See :doc:`aeat-fichero-boe-export-adr` §Long-term for the
per-year-clone pattern (mirrors the formulas-ruleset
`modelo_130_2024.py`/`modelo_130_2025.py` convention where the
2025 ruleset imports from 2024).
"""

from __future__ import annotations

from .modelo_130_2024 import (
    _RECORD_SPECS as _RECORD_SPECS,
)
from .modelo_130_2024 import (
    ENCODING as ENCODING,
)
from .modelo_130_2024 import (
    RECORD_LENGTH as RECORD_LENGTH,
)
from .modelo_130_2024 import (
    REQUIRED_HEADER_FIELDS as REQUIRED_HEADER_FIELDS,
)

__all__ = [
    "ENCODING",
    "RECORD_LENGTH",
    "REQUIRED_HEADER_FIELDS",
    "_RECORD_SPECS",
]
