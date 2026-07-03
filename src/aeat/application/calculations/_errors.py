"""Typed exception hierarchy for the calculations application layer.

These exceptions are raised by previous-filing, binding-prefill, IVA
compensation, and encrypted observation-repository services at the application
boundary. Every class inherits from :class:`~aeat.core.errors.CoreError`;
validation failures use :class:`~aeat.core.errors.CoreValidationError` so CLI
and API callers receive registry-backed envelopes instead of generic
``ValueError`` or ``TypeError`` failures.

See Also:
    :mod:`aeat.application.calculations._binding_prefill`:
        Previous-filing binding readers that raise
        :exc:`BindingPrefillTypeError`.
    :mod:`aeat.application.calculations._iva_compensation_history`:
        Modelo 303 IVA compensation carry-forward readers that raise
        :exc:`IvaCompensationModeloError`.
    :mod:`aeat.application.calculations._observations_repository`:
        Encrypted observation storage that raises :exc:`ObservationKeyError`
        and :exc:`ObservationCasillaReferenceError`.
"""

from __future__ import annotations

from ...core.errors import CoreError, CoreValidationError


class IvaCompensationModeloError(CoreError):
    """Raised when a non-Modelo 303 observation is passed to IVA compensation history.

    The IVA compensation carry-forward pipeline is exclusively sourced from
    Modelo 303 filed observations. Passing any other modelo to
    :func:`~aeat.application.calculations._iva_compensation_history.iva_compensation_state_from_filed_observation`,
    :func:`~aeat.application.calculations._iva_compensation_history.iva_compensation_state_from_registry_observation`,
    or
    :func:`~aeat.application.calculations._iva_compensation_history.iva_compensation_annual_summary_from_filed_observation`
    violates the calculation boundary contract.
    """


class BindingPrefillTypeError(CoreValidationError):
    """Raised when a binding selector field carries an unexpected runtime type.

    Binding selectors flow through pydantic with a union value type, so static
    analysis loses the per-key shape. This error is raised by the selector
    narrowing helpers in :mod:`aeat.application.calculations._binding_prefill`.
    It protects
    :func:`~aeat.application.calculations._binding_prefill.resolve_bindings_from_local_store`
    from selector values that do not match the expected ``int | str`` or
    ``str | tuple[str, ...]`` shape.
    """


class ObservationKeyError(CoreValidationError):
    """Raised when an observation key component fails its repository contract.

    The repository key for a ``(modelo, filing_year, period)`` triple must
    satisfy
    :func:`~aeat.adapters.persistence.storage.safe_repository_id` for string
    components and fall within the supported year range ``[2000, 2099]`` for
    the integer year component. The key builders in
    :mod:`aeat.application.calculations._observations_repository` raise this
    error instead of a bare :class:`ValueError` so failures propagate through
    the typed error registry and produce structured envelopes.
    """


class ObservationCasillaReferenceError(CoreValidationError):
    """Raised when a persisted filing observation names undeclared casillas.

    :class:`~aeat.application.calculations.CalculationObservationRepository`
    is the encrypted calculation-history substrate for cross-period and
    cross-modelo reads. It must not persist a
    :class:`~aeat.domain.calculations.registry.RegistryModeloObservation` whose
    casilla keys are only syntactically valid ``CasillaId`` strings; every key
    must be declared by the resolved
    :class:`~aeat.domain.calculations.registry.RegistrySnapshot` for that
    modelo, year, and period via
    :func:`~aeat.domain.calculations.registry.undeclared_casilla_ids`.
    """
