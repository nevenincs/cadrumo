"""Domain exceptions for the calculations application layer."""

from __future__ import annotations

from ...core.errors import CoreError, CoreValidationError


class IvaCompensationModeloError(CoreError):
    """Raised when a non-Modelo 303 observation is passed to IVA compensation history.

    The IVA compensation carry-forward pipeline is exclusively sourced from
    Modelo 303 filed observations. Passing any other modelo violates the
    calculation boundary contract.
    """


class BindingPrefillTypeError(CoreValidationError):
    """Raised when a binding selector field carries an unexpected runtime type.

    Binding selectors flow through pydantic with a union value type, so static
    analysis loses the per-key shape. This error is raised by the selector
    narrowing helpers in :mod:`aeat.application.calculations._binding_prefill`
    when a field value does not match the expected ``int | str`` or
    ``str | tuple[str, ...]`` shape.
    """


class ObservationKeyError(CoreValidationError):
    """Raised when an observation key component fails its repository contract.

    The repository key for a ``(modelo, filing_year, period)`` triple must
    satisfy the :func:`safe_repository_id` contract for string components and
    fall within the supported year range ``[2000, 2099]`` for the integer
    year component. Any violation of those constraints raises this error
    instead of a bare :class:`ValueError` so the failure propagates through
    the typed error registry and produces a structured envelope.
    """


class ObservationCasillaReferenceError(CoreValidationError):
    """Raised when a persisted filing observation names undeclared casillas.

    `CalculationObservationRepository` is the encrypted calculation-history
    substrate for cross-period and cross-modelo reads. It must not persist a
    `RegistryModeloObservation` whose casilla keys are only syntactically valid
    :class:`CasillaId` strings; every key must be declared by the resolved
    registry snapshot for that modelo, year, and period.
    """
