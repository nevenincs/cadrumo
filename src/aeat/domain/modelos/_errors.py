"""Domain errors for AEAT modelo codes."""

from __future__ import annotations

from ...core.errors import AeatError


class ModeloError(AeatError):
    """Base error for the modelos subpackage."""


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


__all__ = [
    "Modelo036LifecycleError",
    "Modelo036PriorAltaRequiredError",
    "Modelo036TerminalStateError",
    "ModeloError",
    "ModeloExportError",
    "ModeloExportManifestError",
    "ModeloValidationError",
]
