"""Shared selector normalization and field-validator helpers for registry bindings."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition

__all__ = [
    "BindingExportDataType",
    "BindingExportSelector",
    "BindingFixedExportSelector",
    "BindingRowExportSelector",
    "binding_export_selector",
    "intracommunity_clave_validator",
    "invariant_diagnostics",
    "selector_against_model",
    "selector_as_dict",
    "unique_tuple",
    "uppercase_alpha_code",
    "validate_rectification_fields",
]


BindingExportDataType = Literal["text", "integer", "decimal", "money", "date", "boolean"]


class BindingFixedExportSelector(BaseModel):
    """Typed fixed-width export projection carried by a binding selector."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record: str = Field(min_length=1, max_length=64)
    offset: int = Field(ge=1)
    length: int = Field(ge=1)
    data_type: BindingExportDataType
    field: str | None = Field(default=None, min_length=1, max_length=128)


class BindingRowExportSelector(BaseModel):
    """Typed row-field export projection carried by a binding selector."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record: str = Field(min_length=1, max_length=64)
    row_field: str = Field(min_length=1, max_length=128)


BindingExportSelector = BindingFixedExportSelector | BindingRowExportSelector


class _BindingExportProjection(BaseModel):
    """Projection model for export-specific keys embedded in source-family selectors."""

    model_config = ConfigDict(strict=True, frozen=True, extra="ignore")

    record: str | None = Field(default=None, min_length=1, max_length=64)
    row_field: str | None = Field(default=None, min_length=1, max_length=128)
    offset: int | None = Field(default=None, ge=1)
    length: int | None = Field(default=None, ge=1)
    data_type: BindingExportDataType | None = None
    field: str | None = Field(default=None, min_length=1, max_length=128)

    def export_selector(self, *, binding_id: str) -> BindingExportSelector | None:
        """Return the typed export selector, or ``None`` for non-export selectors."""
        if self.record is None:
            if self.offset is not None or self.length is not None:
                raise RegistryValidationError(
                    f"binding {binding_id!r} export selector projection must declare record with offset or length",
                )
            return None

        fixed_values = (self.offset, self.length, self.data_type)
        fixed_count = sum(value is not None for value in fixed_values)
        if fixed_count == len(fixed_values):
            if self.row_field is not None:
                raise RegistryValidationError(
                    f"binding {binding_id!r} export selector projection cannot declare row_field "
                    "with offset/length/data_type",
                )
            assert self.offset is not None
            assert self.length is not None
            assert self.data_type is not None
            return BindingFixedExportSelector(
                record=self.record,
                offset=self.offset,
                length=self.length,
                data_type=self.data_type,
                field=self.field,
            )
        if fixed_count:
            missing = [
                key
                for key, value in (
                    ("offset", self.offset),
                    ("length", self.length),
                    ("data_type", self.data_type),
                )
                if value is None
            ]
            raise RegistryValidationError(
                f"binding {binding_id!r} export selector projection is missing fixed-field keys {missing!r}",
            )
        if self.row_field is not None:
            return BindingRowExportSelector(record=self.record, row_field=self.row_field)
        raise RegistryValidationError(
            f"binding {binding_id!r} export selector projection must declare row_field or offset/length/data_type",
        )


def selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    """Return a plain selector mapping without injected source metadata."""
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return selector.model_dump(exclude={"source"}, exclude_none=True)
    return {key: value for key, value in selector.items() if key != "source"}


def binding_export_selector(binding: DataBindingDefinition) -> BindingExportSelector | None:
    """Return the typed export projection embedded in ``binding.selector``.

    Binding source-family selectors remain authoritative for business facts.
    Export record resolution only needs the official record-coordinate
    projection; this helper parses that projection once into a typed fixed-field
    or row-field selector instead of letting callers probe the raw selector map.
    """
    try:
        projection = _BindingExportProjection.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed export selector projection: {exc}",
        ) from exc
    return projection.export_selector(binding_id=binding.id)


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
    selector = selector_as_dict(binding)
    try:
        selector_model.model_validate(selector)
    except ValueError as exc:
        hint = _canonical_selector_key_hint(selector, selector_model)
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates {selector_model.__name__}: "
            f"{exc}{hint}",
        ]
    return []


def _canonical_selector_key_hint(selector: Mapping[str, object], selector_model: type[BaseModel]) -> str:
    if "source_casillas" in selector and "source_casilla_ids" in selector_model.model_fields:
        return "; use source_casilla_ids, not source_casillas"
    if "source_output" in selector and "source_casilla_id" in selector_model.model_fields:
        return "; use source_casilla_id, not source_output"
    if "target_casilla" in selector and "target_casilla_id" in selector_model.model_fields:
        return "; use target_casilla_id, not target_casilla"
    return ""


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
