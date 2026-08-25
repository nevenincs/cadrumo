"""Typed exception hierarchy for the calc-sheets application layer.

Every subclass inherits from :class:`cadrumo.core.errors.CadrumoError`; the
project error registry's ``__init_subclass__`` hook binds each subclass
to its declared :class:`cadrumo.core.errors.ErrorCode` row at import time.
"""

from __future__ import annotations

from ....core.errors import CadrumoError, CoreValidationError


class CalcSheetsEngineError(CadrumoError):
    """Raised when the sheet-export engine encounters an unresolvable state.

    Covers unsupported registry rounding codes and missing dated parameter
    values that prevent engine from producing a valid export plan.
    """


class CalcSheetsRecordError(CoreValidationError):
    """Raised when a calc-sheets record operation fails validation.

    Covers column-index utility failures (out-of-range or malformed
    A1 column letters) that prevent SheetCellAddress construction.
    Inherits from :class:`~cadrumo.core.errors.CoreValidationError` so
    pydantic validators can surface it as structured validation failure
    without losing the project-wide :class:`CadrumoError` contract.
    """


class CalcSheetsParityError(CadrumoError):
    """Raised when a parity-harness scenario references unknown casillas.

    Fired when a test scenario's canonical casilla ids cannot all be resolved
    in the registry snapshot, making the scenario unprovable.
    """


__all__ = [
    "CalcSheetsEngineError",
    "CalcSheetsParityError",
    "CalcSheetsRecordError",
]
