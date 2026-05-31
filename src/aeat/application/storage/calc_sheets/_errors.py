"""Typed exception hierarchy for the calc-sheets application layer.

Every subclass inherits from :class:`aeat.core.errors.AeatError`; the
project error registry's ``__init_subclass__`` hook binds each subclass
to its declared :class:`aeat.core.errors.ErrorCode` row at import time.
"""

from __future__ import annotations

from ....core.errors import AeatError


class CalcSheetsEngineError(AeatError):
    """Raised when the sheet-export engine encounters an unresolvable state.

    Covers unsupported registry rounding codes and missing dated parameter
    values that prevent engine from producing a valid export plan.
    """


class CalcSheetsRecordError(AeatError):
    """Raised when a calc-sheets record operation fails validation.

    Covers column-index utility failures (out-of-range or malformed
    A1 column letters) that prevent SheetCellAddress construction.
    """


class CalcSheetsParityError(AeatError):
    """Raised when a parity-harness scenario references unknown casillas.

    Fired when a test scenario's casilla numbers cannot all be resolved
    in the registry snapshot, making the scenario unprovable.
    """


__all__ = [
    "CalcSheetsEngineError",
    "CalcSheetsParityError",
    "CalcSheetsRecordError",
]
