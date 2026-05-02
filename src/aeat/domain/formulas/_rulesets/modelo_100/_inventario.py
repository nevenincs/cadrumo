"""Inventario valuation methods (LIS art. 17 / LIRPF art. 28 reference).

LIS art. 17 establishes the legal valuation methods for existencias
(inventory) used by actividades económicas IRPF en estimación directa
normal. Three methods are admissible:

- ``FIFO`` (first-in, first-out)
- ``PMP`` — precio medio ponderado (weighted average price)
- ``COSTE_MEDIO`` — coste medio (cost-average; functionally equivalent
  to PMP per the BOE consolidated text but distinguished here because
  the AEAT manual práctico lists them separately)

LIFO (last-in, first-out) is not admissible for tax purposes per LIS
art. 17.6 — the closed :class:`ValuationMethod` enum makes this
constraint structural rather than runtime-checked.

Source: Ley 27/2014 art. 17 consolidated text, BOE id
``BOE-A-2014-12328``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ValuationMethod(StrEnum):
    """Closed enumeration of LIS art. 17-admissible valuation methods.

    LIFO is intentionally absent — encoding it would violate LIS art.
    17.6. Any caller attempting to construct an :class:`InventoryRecord`
    for LIFO will hit a Pydantic validation failure at the field level.

    Attributes:
        FIFO: First-in, first-out.
        PMP: Precio medio ponderado (weighted-average price).
        COSTE_MEDIO: Coste medio (cost-average), distinguished from
            ``PMP`` for AEAT manual práctico fidelity.
    """

    FIFO = "fifo"
    PMP = "pmp"
    COSTE_MEDIO = "coste_medio"


class InventoryRecord(BaseModel):
    """Per-actividad inventory snapshot for an ejercicio.

    The variación de existencias (``final_value - initial_value``)
    feeds the rendimiento neto computation in Anexo D normal. The
    selected :attr:`method` is informational at this layer — the
    formula DSL operates on the resulting :class:`~decimal.Decimal`
    values supplied by the caller, not on the method itself; the
    closed :class:`ValuationMethod` enum exists to document and
    enforce the LIS art. 17 admissibility constraint at construction
    time.

    Attributes:
        method: Valuation method used for the period.
        initial_value: Value of existencias at the opening of the ejercicio.
        final_value: Value of existencias at the close of the ejercicio.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    method: ValuationMethod
    initial_value: Decimal
    final_value: Decimal


__all__ = [
    "InventoryRecord",
    "ValuationMethod",
]
