"""Encrypted inventory-ledger resolver for the 2025 Modelo 100 projection."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import ClassVar, Protocol, get_args

from pydantic import ValidationError

from ...core.aggregation import BindingSourceKind
from ...core.modelo import Modelo
from ...domain.calculations._row_source_identity import RowSourceIdentity
from ...domain.calculations.registry.inventory_bindings import InventorySelector
from ...domain.calculations.registry.schema import DataBindingDefinition
from ...domain.contribuyente.inventory.records import (
    InventoryLedgerDocument,
    InventoryLedgerError,
    compute_inventory_anexo_d_projection,
)
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

    resolver_id: ClassVar[str] = "inventory"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = _OWNED_SOURCES

    def __init__(self, *, inventory_repository: InventoryLedgerRepositoryProtocol | None = None) -> None:
        self._inventory_repository = inventory_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        bindings = _inventory_bindings(context)
        if not bindings:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        binding_ids = tuple(sorted({binding.id for binding in bindings}))
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
        bindings_by_operation: dict[str, DataBindingDefinition] = {}
        for binding in bindings:
            assert isinstance(binding.selector, InventorySelector)
            operation = binding.selector.row_field
            if operation in bindings_by_operation:
                return self._template_refusal(binding_ids, "duplicate inventory operation row template")
            bindings_by_operation[operation] = binding
        if set(bindings_by_operation) != set(_CANONICAL_OPERATIONS) or len(bindings) != len(_CANONICAL_OPERATIONS):
            return self._template_refusal(binding_ids, "inventory row-template cohort must contain each operation once")
        if self._inventory_repository is None:
            return self._storage_refusal(binding_ids)
        try:
            document = self._inventory_repository.load()
        except InventoryLedgerError:
            return self._storage_refusal(binding_ids)
        ledgers = tuple(
            sorted(
                (item for item in document.ledgers if item.year == 2025),
                key=lambda item: item.actividad_id,
            ),
        )
        if not ledgers:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=binding_ids,
                diagnostics=(
                    _diagnostic(
                        reason="source_domain_not_ready",
                        state="missing_activity_ledgers",
                        message="no complete 2025 inventory activity ledger is available",
                    ),
                ),
            )
        row_values: dict[tuple[str, int], Decimal | str] = {}
        row_identities: dict[tuple[str, int], RowSourceIdentity] = {}
        diagnostics: list[CalculationSourceDiagnostic] = []
        try:
            for row_index, ledger in enumerate(ledgers, start=1):
                projection = compute_inventory_anexo_d_projection(ledger)
                for operation, binding in bindings_by_operation.items():
                    key = (binding.id, row_index)
                    row_values[key] = getattr(projection, _VALUE_ATTRIBUTE_BY_OPERATION[operation])
                    row_identities[key] = RowSourceIdentity(
                        source_kind=_SOURCE,
                        source_row_identity=projection.actividad_id,
                        fingerprint=projection.projection_fingerprint,
                    )
                if projection.closing_conflict is not None:
                    diagnostics.append(
                        _diagnostic(
                            reason="source_issue",
                            state="physical_closing_conflict",
                            message="one inventory activity retains a reviewed physical closing conflict",
                        ),
                    )
        except (InventoryLedgerError, ValidationError):
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=binding_ids,
                diagnostics=(
                    _diagnostic(
                        reason="unresolved_derived_binding",
                        state="incomplete_or_tampered_projection",
                        message="inventory activity projection is incomplete or inconsistent",
                    ),
                ),
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            row_binding_values=row_values,
            row_source_identities=row_identities,
            diagnostics=tuple(diagnostics),
        )

    def _template_refusal(
        self,
        binding_ids: tuple[str, ...],
        message: str,
    ) -> CalculationSourceResolution:
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=(
                _diagnostic(
                    reason="unresolved_derived_binding",
                    state="invalid_row_template_cohort",
                    message=message,
                ),
            ),
        )

    def _storage_refusal(self, binding_ids: tuple[str, ...]) -> CalculationSourceResolution:
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=(
                _diagnostic(
                    reason="storage_degraded",
                    state="repository_unreadable",
                    message="encrypted inventory storage could not be read",
                ),
            ),
        )


__all__ = ["InventoryLedgerRepositoryProtocol", "InventorySourceResolver"]
