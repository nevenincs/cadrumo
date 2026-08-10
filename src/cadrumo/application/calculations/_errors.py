"""Typed exception hierarchy for the calculations application layer.

These exceptions are raised by previous-filing, binding-prefill, IVA
compensation, and encrypted observation-repository services at the application
boundary. Every class inherits from :class:`~core.errors.CoreError`;
validation failures use :class:`~core.errors.CoreValidationError` so CLI
and API callers receive registry-backed envelopes instead of generic
``ValueError`` or ``TypeError`` failures.

See Also:
    :mod:`application.calculations._binding_prefill`:
        Previous-filing binding readers that raise
        :exc:`BindingPrefillTypeError`.
    :mod:`application.calculations._iva_compensation_history`:
        Modelo 303 IVA compensation carry-forward readers that raise
        :exc:`IvaCompensationModeloError`.
    :mod:`application.calculations._observations_repository`:
        Encrypted observation storage that raises :exc:`ObservationKeyError`
        and :exc:`ObservationCasillaReferenceError`.
"""

from __future__ import annotations

from ...core.errors import CoreError, CoreValidationError


class IvaCompensationModeloError(CoreError):
    """Raised when a non-Modelo 303 observation is passed to IVA compensation history.

    The IVA compensation carry-forward pipeline is exclusively sourced from
    Modelo 303 filed observations. Passing any other modelo to
    :func:`~application.calculations._iva_compensation_history.iva_compensation_state_from_observation_envelope`,
    or
    :func:`~application.calculations._iva_compensation_history.iva_compensation_annual_summary_from_filed_observation`
    violates the calculation boundary contract.
    """


class BindingPrefillTypeError(CoreValidationError):
    """Raised when a binding selector field carries an unexpected runtime type.

    Binding selectors flow through pydantic with a union value type, so static
    analysis loses the per-key shape. This error is raised by the selector
    narrowing helpers in :mod:`application.calculations._binding_prefill`.
    It protects
    :func:`~application.calculations._binding_prefill.resolve_bindings_from_local_store`
    from selector values that do not match the expected ``int | str`` or
    ``str | tuple[str, ...]`` shape.
    """


class ObservationKeyError(CoreValidationError):
    """Raised when an observation key component fails its repository contract.

    The repository key for a ``(modelo, filing_year, period)`` triple must
    satisfy
    :func:`~adapters.persistence.storage.safe_repository_id` for string
    components and fall within the supported year range ``[2000, 2099]`` for
    the integer year component. The key builders in
    :mod:`application.calculations._observations_repository` raise this
    error instead of a bare :class:`ValueError` so failures propagate through
    the typed error registry and produce structured envelopes.
    """


class ObservationEvidenceDisplacementError(CoreValidationError):
    """Raised when a non-official write would displace official AEAT evidence.

    A ``(modelo, filing_year, period)`` slot holding evidence observed from AEAT
    -- a captured justificante, a live Sede capture, a CSV register row -- is the
    only record of what the authority holds. Writing a locally-sourced
    observation into that slot replaces it, and the displaced evidence cannot be
    recovered through any path this repository exposes.

    Both non-official provenances are refused, for different reasons that the
    refusal message distinguishes. An operator-manual figure displacing captured
    evidence is a downgrade with no compensating gain. A local filing
    recalculation displacing it is the same downgrade wearing a plausible
    justification: if the recalculation is correct the operator must re-file with
    AEAT and re-pull, so the local figure is not the authority either way.

    The operator verb can override deliberately; the local filing flow cannot,
    because there is no situation in which it should silently win.
    """


class ObservationCasillaReferenceError(CoreValidationError):
    """Raised when a persisted filing observation names undeclared casillas.

    :class:`~application.calculations.CalculationObservationRepository`
    is the encrypted calculation-history substrate for cross-period and
    cross-modelo reads. It must not persist a
    :class:`~domain.calculations.registry.RegistryModeloObservation` whose
    casilla keys are only syntactically valid ``CasillaId`` strings; every key
    must be declared by the resolved
    :class:`~domain.calculations.registry.RegistrySnapshot` for that
    modelo, year, and period via
    :func:`~domain.calculations.registry.undeclared_casilla_ids`.
    """
