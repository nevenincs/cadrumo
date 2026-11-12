"""Domain errors for AEAT modelo records and calculations.

:class:`ModeloValidationError` is raised by :class:`ModeloCode` and
:class:`WorkUnit` invariant checks; :class:`PensionReduccionError` reports
invalid fiscal-reduction inputs, and :func:`raise_catalogue_integrity_error`
normalises repository integrity failures into typed :class:`ModeloError`
subclasses.
"""

from __future__ import annotations

from logging import Logger
from typing import ClassVar, NoReturn

from ...core.errors.hierarchy import CadrumoError, CoreValidationError, TerminalPreconditionErrorMixin


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


class ModeloValidationError(ModeloError):
    """Raised when a modelo code violates shape invariants."""


class ModeloOperatorLayerIntegrityError(ModeloValidationError):
    """Raised when a stored calculation operator layer contradicts the invariants its builder keeps.

    The layer is written by Cadrumo itself, so a record that breaks them was
    altered or damaged after it was stored; the operator has no entry that
    repairs it.
    """


class CalculationRevisionIntegrityError(ModeloValidationError):
    """Raised when a saved calculation revision contradicts itself.

    Every check behind it compares fields the application computed and stored
    together, never a value the operator typed, so a revision that fails one
    was altered, damaged or assembled wrongly; the operator has no entry that
    repairs it.
    """


class ModeloExportError(ModeloError):
    """Base error for modelo-revision export failures (manifest, archive build)."""


class ModeloExportManifestError(ModeloExportError):
    """Raised when a modelo export manifest cannot be built or validated."""


class ModeloExportPriorDomiciliationElectionRequiredError(ModeloExportError):
    """Raised when a Modelo 303 export names no prior-domiciliation action.

    The page-three marker is the operator's per-filing choice, so an export
    that carries none refuses before any byte is written instead of guessing
    one.
    """


class ModeloExportValueOverflowError(ModeloExportError):
    """Refused: a value is wider than its slot in the official record design.

    The file would only be writable by cutting the value, which would declare
    something else, so nothing is written. The value is put right where it was
    recorded.
    """

    # The text that did not fit is the filer's own content (a counterparty's
    # name); only the in-process envelope may show it, never a kept record.
    process_local_context_keys: ClassVar[frozenset[str]] = frozenset({"field_value"})


class ModeloExportRequiredRecordAbsentError(ModeloExportError):
    """Refused: the official design requires a record this return has nothing to state in.

    Without at least one occurrence of that record the design cannot be
    written, so nothing is written in this format.
    """


class ModeloExportDeclaredPartyNameError(TerminalPreconditionErrorMixin[object], ModeloExportError):
    """Refused: a party-name slot has no declared filing name the record design can take.

    The design fills the slot from the party's own name parts and allows no
    shortening, so the party's filing name is stated, or restated with a
    rendering for the slot's width, through the action the context names. The
    context never carries the name. The party's tax identifier and country
    travel only as process-local keys: no kept record, journal or log holds
    them, so the door's verdict leaves both arguments for the operator to state.
    """

    process_local_context_keys: ClassVar[frozenset[str]] = frozenset({"tax_identifier", "country_code"})


class ModeloExportProducerFactsRefusedError(ModeloExportError):
    """Refused: the facts the file states about the filer or the filing are incomplete.

    Identity, account and model facts the export needs to form its producer
    snapshot are missing or contradict each other. They are the filer's to
    supply, so this is a refusal rather than a failure to write.
    """


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
    "CalculationRevisionIntegrityError",
    "Modelo036LifecycleError",
    "Modelo036PriorAltaRequiredError",
    "Modelo036TerminalStateError",
    "ModeloError",
    "ModeloExportDeclaredPartyNameError",
    "ModeloExportError",
    "ModeloExportManifestError",
    "ModeloExportProducerFactsRefusedError",
    "ModeloExportRequiredRecordAbsentError",
    "ModeloExportValueOverflowError",
    "ModeloOperatorLayerIntegrityError",
    "ModeloValidationError",
    "raise_catalogue_integrity_error",
]
