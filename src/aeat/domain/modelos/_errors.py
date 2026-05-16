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


class CensusStaleRefusedError(ModeloError):
    """Raised when calculate / verify / file / build_draft / approve_draft / export_draft
    refuse because the operator applied a new census after the target entity was produced.

    Per the 2026-05-16 amendment to the modelo-036-037-foundation ADR,
    AEAT is the binding legal source of truth: any work unit,
    calculation revision, filing draft, or filing record that
    referenced census facts now superseded by an ``aeat config profile
    census apply`` must be refused until the operator re-runs the
    governing calculation against the fresh census. The fix is
    operator-driven: re-run ``aeat app modelo work calculate`` (or the
    relevant verb) against the affected work unit.
    """


__all__ = [
    "CensusStaleRefusedError",
    "Modelo036LifecycleError",
    "Modelo036PriorAltaRequiredError",
    "Modelo036TerminalStateError",
    "ModeloError",
    "ModeloExportError",
    "ModeloExportManifestError",
    "ModeloValidationError",
]
