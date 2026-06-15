"""Shared selector normalization and field-validator helpers for registry bindings."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition

__all__ = [
    "intracommunity_clave_validator",
    "invariant_diagnostics",
    "selector_against_model",
    "selector_as_dict",
    "unique_tuple",
    "uppercase_alpha_code",
    "validate_rectification_fields",
]


def selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    """Return a plain selector mapping without injected source metadata."""
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return selector.model_dump(exclude={"source"}, exclude_none=True)
    return {key: value for key, value in selector.items() if key != "source"}


def selector_against_model(
    binding: DataBindingDefinition,
    selector_model: type[BaseModel],
) -> list[str]:
    """Validate ``binding.selector`` against ``selector_model``, accumulating diagnostics.

    Projects the selector through :func:`selector_as_dict` (the same normalised
    mapping the resolve-time helpers see, so the build gate is never stricter
    than runtime), validates against the strict pydantic model, and returns the
    underlying field message verbatim in a diagnostic naming the binding id, its
    source, and the violated model. The underlying pydantic error is preserved
    rather than flattened to a generic "malformed selector", matching the shape
    the counterpart/withholding build-time lift already emits.

    Returns an empty list when the selector validates.
    """
    try:
        selector_model.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates {selector_model.__name__}: {exc}",
        ]
    return []


def invariant_diagnostics(
    binding: DataBindingDefinition,
    label: str,
    check: Callable[[DataBindingDefinition], object],
) -> list[str]:
    """Run a raise-style op/fact invariant ``check`` and collect its diagnostic.

    The detail-record, previous-filing, counterpart, withholding, invoice, and
    ledger families enforce their op/fact cross-invariants by raising
    :class:`RegistryValidationError`. This adapter runs the raising ``check`` and
    converts the raised message into one accumulating diagnostic string naming
    the binding id, its source, and the ``label`` family, preserving the
    underlying field message. Returns an empty list when the invariant holds.
    """
    try:
        check(binding)
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) {label} invariants violated: {exc}"]
    return []


def uppercase_alpha_code(field_label: str) -> Callable[[type, str], str]:
    """Build a field validator that rejects a non-uppercase-alphabetic code.

    Shared by the binding observation models whose ISO country / member-state /
    currency codes must be uppercase alphabetic; ``field_label`` names the field
    in the raised :class:`RegistryValidationError`.
    """

    def _validate(cls: type, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError(f"{field_label} must be uppercase alphabetic")
        return value

    return _validate


_AEAT_OPERATION_CLAVES: frozenset[str] = frozenset({"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"})


def intracommunity_clave_validator() -> Callable[[type, str | None], str | None]:
    """Build the shared ``intracommunity_clave`` field validator.

    Both :class:`InvoiceObservation` and :class:`CounterpartAggregationObservation`
    carried a byte-identical ``intracommunity_clave`` field validator: a clave is
    optional, must be uppercase, and must be one of the closed AEAT clave de
    operación set. The single factory replaces both copies.
    """

    def _validate(cls: type, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.upper():
            raise RegistryValidationError("intracommunity_clave must be uppercase")
        if value not in _AEAT_OPERATION_CLAVES:
            raise RegistryValidationError(f"intracommunity_clave {value!r} is not an AEAT clave de operacion")
        return value

    return _validate


class _RectifiableObservation(Protocol):
    is_rectification: bool
    rectified_year: int | None
    rectified_period: str | None
    rectified_base_previous: Decimal | None


def validate_rectification_fields(observation: _RectifiableObservation) -> None:
    """Enforce the rectification-field coupling shared by the invoice families.

    A rectification observation must declare ``rectified_year``,
    ``rectified_period`` and ``rectified_base_previous``; a non-rectification
    observation must declare none of them. :class:`InvoiceObservation` and
    :class:`CounterpartAggregationObservation` carried a byte-identical
    ``_validate_rectification`` model validator; this one shared check replaces
    both, raising :class:`RegistryValidationError` on a violation.
    """
    if observation.is_rectification:
        if observation.rectified_year is None or observation.rectified_period is None:
            raise RegistryValidationError(
                "rectification observation must declare rectified_year and rectified_period",
            )
        if observation.rectified_base_previous is None:
            raise RegistryValidationError("rectification observation must declare rectified_base_previous")
        return
    if observation.rectified_year is not None or observation.rectified_period is not None:
        raise RegistryValidationError("non-rectification observation must not declare rectified_year/period")
    if observation.rectified_base_previous is not None:
        raise RegistryValidationError("non-rectification observation must not declare rectified_base_previous")


def unique_tuple(label: str) -> Callable[[type, tuple[str, ...]], tuple[str, ...]]:
    """Build a field validator that rejects duplicate entries in a tuple field.

    Shared by the binding requirement models; ``label`` names the offending
    tuple in the raised :class:`RegistryValidationError` (``"<label> entries
    must be unique"``).
    """

    def _validate(cls: type, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(f"{label} entries must be unique")
        return value

    return _validate
