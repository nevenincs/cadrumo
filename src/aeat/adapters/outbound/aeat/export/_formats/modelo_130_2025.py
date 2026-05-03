"""Define the fichero-BOE record spec for Modelo 130 ejercicio 2025.

Structural clone of :mod:`aeat.adapters.outbound.aeat.export._formats.modelo_130_2024`.
AEAT has not published a new Modelo 130 *Diseño de registros* for ejercicio
2025: Orden EHA/672/2007 (BOE-A-2007-6032) plus ``DR130e15v12.xls`` remain
canonical, and neither Orden HAC/819/2024 (IVA) nor Orden HAC/242/2025
(Modelo 100 rectificativa) touch the Modelo 130 layout.

The pipeline uses this module when exporting a 2025-period filing. The schema,
encoding, record length, and required headers are identical to the 2024
variant. The module exists for two reasons:

* Future-proofing — when AEAT publishes a Modelo 130-specific Orden, the
  delta lands here without churning 2024-period exports.
* Per-year filing-id stamping — the ``EJERCICIO`` value in the emitted
  payload is the key AEAT correlates against the submission calendar.

The 2025 schema mirrors the per-year-clone pattern used by the formulas
registry Modelo 130 definitions for the matching filing year.
"""

from __future__ import annotations

from .modelo_130_2024 import (
    ENCODING as ENCODING,
)
from .modelo_130_2024 import (
    RECORD_LENGTH as RECORD_LENGTH,
)
from .modelo_130_2024 import (
    RECORD_SPECS as RECORD_SPECS,
)
from .modelo_130_2024 import (
    REQUIRED_HEADER_FIELDS as REQUIRED_HEADER_FIELDS,
)

__all__ = [
    "ENCODING",
    "RECORD_LENGTH",
    "RECORD_SPECS",
    "REQUIRED_HEADER_FIELDS",
]
