"""Typed missing-input refusal from a Modelo calculation before publication."""

from __future__ import annotations

from typing import Self

from pydantic import TypeAdapter, ValidationError

from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import BindingId

_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_MISSING_BINDING_MESSAGES = frozenset(
    {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.date_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
    }
)


class ModeloWorkMissingInputError(RegistryValidationError):
    """A promptable binding refused an engine calculation before publication.

    Only the calculation action's engine-call boundary may raise this error.
    It says that no new calculation revision was published; earlier preparation
    may already have changed other state.
    """

    def __init__(self, source: RegistryValidationError, *, binding_id: BindingId) -> None:
        """Retain the original refusal and its renderer-facing metadata."""
        self.binding_id = binding_id
        super().__init__(
            str(source),
            context=source.context,
            translated_message=source.translated_message,
            registry_failure=source.registry_failure,
            precondition_verdict=source.terminal_precondition_verdict,
        )
        self.args = source.args
        self.__cause__ = source

    @classmethod
    def from_registry_error(cls, source: RegistryValidationError) -> Self | None:
        """Classify only supported engine tags with one canonical binding ID."""
        if isinstance(source, cls) or source.translated_message not in _MISSING_BINDING_MESSAGES:
            return None
        value = (source.context or {}).get("binding_id")
        try:
            binding_id = _BINDING_ID_ADAPTER.validate_python(value, strict=True)
        except ValidationError:
            return None
        return cls(source, binding_id=binding_id)
