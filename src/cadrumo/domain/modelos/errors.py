"""Domain errors for AEAT modelo records and calculations.

:class:`ModeloValidationError` is raised by :class:`ModeloCode` and
:class:`WorkUnit` invariant checks; :class:`PensionReduccionError` reports
invalid fiscal-reduction inputs, and :func:`raise_catalogue_integrity_error`
normalises repository integrity failures into typed :class:`ModeloError`
subclasses.
"""

from __future__ import annotations

from logging import Logger
from typing import NoReturn

from ...core.errors.hierarchy import CadrumoError, CoreValidationError


class ModeloError(CadrumoError):
    """Base error for the modelos subpackage."""


class PensionReduccionError(CoreValidationError):
    """Raised when a pension reducción computation pre-condition is violated.

    Covers the numeric guard checks for both the DT 12ª plan-de-pensiones capital
    rescate reducción and the Ley 44/2015 SAL/SLL reserva especial dotacion
    computation. Raises instead of a bare :class:`ValueError` so the failure
    reaches the typed error registry with a stable error code and a structured
    context envelope.
    """


class ModeloValidationError(ModeloError, ValueError):
    """Raised when a modelo code violates shape invariants."""


class ModeloExportError(ModeloError):
    """Base error for modelo-revision export failures (manifest, archive build)."""


class ModeloExportManifestError(ModeloExportError):
    """Raised when a modelo export manifest cannot be built or validated."""


class Modelo036LifecycleError(ModeloError):
    """Base error for the Modelo 036 lifecycle (alta / modificacion / baja)."""


class Modelo036PriorAltaRequiredError(Modelo036LifecycleError):
    """Raised when modificacion or baja is requested without a prior alta."""


class Modelo036TerminalStateError(Modelo036LifecycleError):
    """Raised when an operation is requested on a 036 record already in a terminal (baja) state."""


def raise_catalogue_integrity_error(
    exc: Exception,
    *,
    error_cls: type[ModeloError],
    label: str,
    translated_message: str,
    logger: Logger,
) -> NoReturn:
    """Log and re-raise a secure-object catalogue integrity failure as ``error_cls``.

    The modelo catalogue repositories share one recovery path when a stored
    envelope fails its classification / schema-version guard: log the
    ``"<label> catalogue integrity error"`` at error level and raise the
    repository's typed ``ModeloError`` subclass carrying the
    ``secure_object_integrity`` reason and the originating exception's type in
    its context, chained from ``exc``.
    """
    message = f"{label} catalogue integrity error"
    logger.error(message, exc_info=True)
    raise error_cls(
        message,
        translated_message=translated_message,
        context={"reason": "secure_object_integrity", "cause_type": type(exc).__name__},
    ) from exc


__all__ = [
    "Modelo036LifecycleError",
    "Modelo036PriorAltaRequiredError",
    "Modelo036TerminalStateError",
    "ModeloError",
    "ModeloExportError",
    "ModeloExportManifestError",
    "ModeloValidationError",
    "raise_catalogue_integrity_error",
]
