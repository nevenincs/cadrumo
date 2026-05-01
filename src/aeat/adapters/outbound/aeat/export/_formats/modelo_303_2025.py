"""Define the fichero-BOE envelope spec for Modelo 303 ejercicio 2025.

Structural clone of :mod:`aeat.adapters.outbound.aeat.export._formats.modelo_303_2024`.
Orden HAC/819/2024 (BOE-A-2024-16129) governs both 2024 and 2025 Modelo 303
filings; the LIVA arts. 90 / 91 régimen-general rates were not amended
between the two years. The 2025 formula ruleset at
:mod:`aeat.domain.formulas._rulesets.modelo_303_2025` mirrors the same
rationale.

Kent uses this module when exporting a 2025-period 303 filing. The schema,
encoding, envelope, and required-header set are identical to the 2024
variant. Keeping 2025 as its own module means a future Orden modifying 303
for 2026+ can publish a ``DR303e26`` fixture, be regenerated into its own
module, and leave 2024-period exports byte-identical.

A separate CLI registry entry also makes year-stamped filename routing
explicit: ``X1234567L20253T.303`` is Kent's Q3 2025 filing, not a
misdirected 2024 artefact.
"""

from __future__ import annotations

from .modelo_303_2024 import (
    ENCODING as ENCODING,
)
from .modelo_303_2024 import (
    ENVELOPE as ENVELOPE,
)
from .modelo_303_2024 import (
    REQUIRED_HEADER_FIELDS as REQUIRED_HEADER_FIELDS,
)

__all__ = [
    "ENCODING",
    "ENVELOPE",
    "REQUIRED_HEADER_FIELDS",
]
