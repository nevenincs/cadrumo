"""Encrypted inventory-ledger resolver for the 2025 Modelo 100 projection."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol, get_args

from ...adapters.persistence.profile.inventory import InventoryLedgerRepository
from ...core import BindingSourceKind, CalculationSourceLineageRole, Modelo
from ...domain.calculations.registry import (
    BindingId,
    DataBindingDefinition,
    InventorySelector,
)
from ...domain.contribuyente.inventory import (
    InventoryAnexoDResult,
    InventoryLedgerDocument,
    InventoryLedgerError,
    compute_inventory_anexo_d_projection,
)
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceDiagnosticReason,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

_SOURCE = BindingSourceKind.INVENTORY
_OWNED_SOURCES = (_SOURCE,)
_VALUE_ATTRIBUTE_BY_OPERATION: Mapping[str, str] = {
    "complete_acquisition_cost": "casilla_0181",
    "closing_minus_opening_positive": "casilla_0177",
    "opening_minus_closing_positive": "casilla_0182",
}
_OPERATION_ANNOTATION = InventorySelector.model_fields["operation"].annotation
_CANONICAL_OPERATIONS = get_args(getattr(_OPERATION_ANNOTATION, "__value__", _OPERATION_ANNOTATION))
if set(_VALUE_ATTRIBUTE_BY_OPERATION) != set(_CANONICAL_OPERATIONS):
    raise RuntimeError("inventory projection operation adapter is not exhaustive")


class InventoryLedgerRepositoryProtocol(Protocol):
    """Read boundary required by the inventory source resolver."""

    def load(self) -> InventoryLedgerDocument: ...


def _inventory_bindings(context: CalculationSourceContext) -> tuple[DataBindingDefinition, ...]:
    return tuple(binding for binding in context.revision.bindings if binding.source is _SOURCE)


def _diagnostic(
    *, reason: CalculationSourceDiagnosticReason, state: str, message: str
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=reason,
        source_kind=_SOURCE.value,
        resolver_id=InventorySourceResolver.resolver_id,
        message=f"inventory source {state}: {message}",
    )


def _source_ref(context: CalculationSourceContext, actividad_id: str) -> str:
    return f"inventory:{context.bucket_id}:{context.filing_year}:{actividad_id}"


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
        repository = self._inventory_repository or InventoryLedgerRepository()
        try:
            document = repository.load()
        except InventoryLedgerError:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=binding_ids,
                diagnostics=(
                    _diagnostic(
                        reason="storage_degraded",
                        state="repository_unreadable",
                        message="the encrypted inventory document could not be read",
                    ),
                ),
            )

        ledgers = {(ledger.actividad_id, ledger.year): ledger for ledger in document.ledgers}
        values: dict[BindingId, Decimal] = {}
        unresolved: list[BindingId] = []
        diagnostics: list[CalculationSourceDiagnostic] = []
        projections: dict[str, InventoryAnexoDResult] = {}
        bindings_by_activity: dict[str, list[DataBindingDefinition]] = {}
        for binding in bindings:
            selector = binding.selector
            if not isinstance(selector, InventorySelector):
                unresolved.append(binding.id)
                diagnostics.append(
                    _diagnostic(
                        reason="unresolved_derived_binding",
                        state="selector_unreadable",
                        message=f"binding {binding.id} does not carry the canonical inventory selector",
                    ),
                )
                continue
            bindings_by_activity.setdefault(selector.actividad_id, []).append(binding)

        for actividad_id, activity_bindings in sorted(bindings_by_activity.items()):
            ledger = ledgers.get((actividad_id, 2025))
            if ledger is None:
                unresolved.extend(binding.id for binding in activity_bindings)
                diagnostics.append(
                    _diagnostic(
                        reason="unresolved_binding",
                        state="ledger_absent",
                        message=(
                            f"no encrypted schema-v3 ledger exists for activity {actividad_id!r} "
                            "and filing year 2025"
                        ),
                    ),
                )
                continue
            try:
                projection = compute_inventory_anexo_d_projection(ledger)
            except InventoryLedgerError:
                unresolved.extend(binding.id for binding in activity_bindings)
                diagnostics.append(
                    _diagnostic(
                        reason="source_domain_not_ready",
                        state="projection_refused",
                        message=(
                            f"activity {actividad_id!r} filing year 2025 is incomplete, inconsistent, or tampered"
                        ),
                    ),
                )
                continue
            projections[actividad_id] = projection
            for binding in activity_bindings:
                selector = binding.selector
                assert isinstance(selector, InventorySelector)
                values[binding.id] = getattr(projection, _VALUE_ATTRIBUTE_BY_OPERATION[selector.operation])
            if projection.closing_conflict is not None:
                diagnostics.append(
                    _diagnostic(
                        reason="source_issue",
                        state="closing_conflict_retained",
                        message=(
                            f"activity {actividad_id!r} filing year 2025 retains a reviewed physical-closing conflict"
                        ),
                    ),
                )

        provenance = tuple(
            CalculationSourceProvenance(
                resolver_id=self.resolver_id,
                resolved_binding_source=_SOURCE,
                contributor_source_kind=_SOURCE.value,
                contributor_binding_source=_SOURCE,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=_source_ref(context, actividad_id),
                parent_source_ref=None,
                fingerprint=projection.projection_fingerprint,
            )
            for actividad_id, projection in sorted(projections.items())
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=values,
            unresolved_binding_ids=tuple(sorted(unresolved)),
            diagnostics=tuple(diagnostics),
            provenance=provenance,
        )


__all__ = ["InventoryLedgerRepositoryProtocol", "InventorySourceResolver"]
