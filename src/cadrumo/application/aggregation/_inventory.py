"""Encrypted inventory-ledger resolver for the 2025 Modelo 100 projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, get_args

from ...core import BindingSourceKind, Modelo
from ...domain.calculations.registry import (
    DataBindingDefinition,
    InventorySelector,
)
from ...domain.contribuyente.inventory import InventoryLedgerDocument
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceDiagnosticReason,
    CalculationSourceResolution,
)

_SOURCE = BindingSourceKind.INVENTORY
_OWNED_SOURCES = (_SOURCE,)
_VALUE_ATTRIBUTE_BY_OPERATION: Mapping[str, str] = {
    "complete_acquisition_cost": "casilla_0181",
    "closing_minus_opening_positive": "casilla_0177",
    "opening_minus_closing_positive": "casilla_0182",
}
_OPERATION_ANNOTATION = InventorySelector.model_fields["row_field"].annotation
_CANONICAL_OPERATIONS = get_args(getattr(_OPERATION_ANNOTATION, "__value__", _OPERATION_ANNOTATION))
if set(_VALUE_ATTRIBUTE_BY_OPERATION) != set(_CANONICAL_OPERATIONS):
    raise RuntimeError("inventory projection operation adapter is not exhaustive")


class InventoryLedgerRepositoryProtocol(Protocol):
    """Read boundary required by the inventory source resolver."""

    def load(self) -> InventoryLedgerDocument: ...


def _inventory_bindings(context: CalculationSourceContext) -> tuple[DataBindingDefinition, ...]:
    return tuple(binding for binding in context.revision.bindings if binding.source is _SOURCE)


def _diagnostic(
    *, reason: CalculationSourceDiagnosticReason, state: str, message: str, remedy: str | None = None
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=reason,
        source_kind=_SOURCE.value,
        resolver_id=InventorySourceResolver.resolver_id,
        message=f"inventory source {state}: {message}",
        remedy=remedy,
    )


class InventorySourceResolver:
    """Resolve inventory bindings from one encrypted schema-v3 ledger document.

    This adapter selects an exact activity/year ledger and delegates every
    monetary and authority decision to the sealed inventory projection. It does
    not aggregate across activities, allocate values, enroll itself in the mesh,
    or provide a manual fallback.
    """

    resolver_id = "inventory"
    owned_sources = _OWNED_SOURCES

    def __init__(self, *, inventory_repository: InventoryLedgerRepositoryProtocol | None = None) -> None:
        self._inventory_repository = inventory_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        bindings = _inventory_bindings(context)
        if not bindings:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        binding_ids = tuple(sorted(binding.id for binding in bindings))
        if context.modelo != Modelo.M100 or context.filing_year != 2025 or context.period.filing_year != 2025:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=binding_ids,
                diagnostics=(
                    _diagnostic(
                        reason="unhandled_binding_source",
                        state="unsupported_coordinate",
                        message="only Modelo 100 filing year 2025 inventory bindings are supported",
                    ),
                ),
            )
        if any(not isinstance(binding.selector, InventorySelector) for binding in bindings):
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=binding_ids,
                diagnostics=(
                    _diagnostic(
                        reason="unresolved_derived_binding",
                        state="selector_unreadable",
                        message="one or more bindings do not carry the canonical inventory row template",
                    ),
                ),
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=(
                _diagnostic(
                    reason="source_domain_not_ready",
                    state="row_template_not_expanded",
                    message="runtime inventory activity-row expansion is not enrolled",
                    remedy="complete the canonical inventory row-expansion integration before calculation",
                ),
            ),
        )


__all__ = ["InventoryLedgerRepositoryProtocol", "InventorySourceResolver"]
