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
