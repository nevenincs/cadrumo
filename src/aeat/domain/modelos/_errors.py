"""Domain errors for AEAT modelo codes."""

from __future__ import annotations

from ...core.errors import AeatError, CoreValidationError


class ModeloError(AeatError):
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


class CensoStaleRefusedError(ModeloError):
    """Raised when an operation is refused because the censo was updated after the target was produced.

    Applies to calculate, verify, file, build_draft, approve_draft, and export_draft.
    AEAT is the binding legal source of truth: any work unit, calculation revision,
    filing draft, or filing record that referenced censo facts now superseded by a
    ``aeat config profile censo apply`` must be refused until the operator re-runs
    the governing calculation against the fresh censo. The fix is operator-driven:
    re-run ``aeat app modelo work calculate`` (or the relevant verb) against the
    affected work unit.
    """


__all__ = [
    "CensoStaleRefusedError",
    "Modelo036LifecycleError",
    "Modelo036PriorAltaRequiredError",
    "Modelo036TerminalStateError",
    "ModeloError",
    "ModeloExportError",
    "ModeloExportManifestError",
    "ModeloValidationError",
]
