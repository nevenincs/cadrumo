"""Encrypted inventory-ledger resolver for typed inventory binding projections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar, Protocol, get_args

from pydantic import ValidationError

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.binding_temporal import SameTargetContext
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.inventory_bindings import InventoryProvider
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.row_source_identity import RowSourceIdentity
from ...domain.contribuyente.inventory.records import (
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
)
from ...domain.contribuyente.inventory.valuation import compute_inventory_anexo_d_projection
from .source_mesh import (
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
_OPERATION_ANNOTATION = InventoryProvider.model_fields["row_field"].annotation
_CANONICAL_OPERATIONS = get_args(getattr(_OPERATION_ANNOTATION, "__value__", _OPERATION_ANNOTATION))
if set(_VALUE_ATTRIBUTE_BY_OPERATION) != set(_CANONICAL_OPERATIONS):
    raise RuntimeError("inventory projection operation adapter is not exhaustive")


class InventoryLedgerRepositoryProtocol(Protocol):
    """Read boundary required by the inventory source resolver."""

    def load(self) -> InventoryLedgerDocument: ...


def _inventory_bindings(context: CalculationSourceContext) -> tuple[BindingDefinition, ...]:
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


@dataclass(frozen=True, slots=True)
class _InventoryBindingTemplate:
    """Validated inventory row templates carried into ledger projection."""

    by_operation: Mapping[str, BindingDefinition]


def _resolve_inventory_binding_template(
    bindings: tuple[BindingDefinition, ...],
    *,
    binding_ids: tuple[str, ...],
    filing_year: int,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> _InventoryBindingTemplate | CalculationSourceResolution:
    """Validate selector shape, filing coordinate, and the complete operation cohort."""
    typed_bindings = [
        (binding, binding.provider) for binding in bindings if isinstance(binding.provider, InventoryProvider)
    ]
    if len(typed_bindings) != len(bindings):
        return CalculationSourceResolution(
            resolver_id=resolver_id,
            owned_sources=owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=(
                _diagnostic(
                    reason="unresolved_derived_binding",
                    state="selector_unreadable",
                    message="one or more bindings do not carry the canonical inventory row template",
                ),
            ),
        )

    # The declaration carries no authored year: it states timeless intent and the
    # filing context supplies the coordinate. The year guard is therefore a guard
    # on the temporal selector -- an inventory row template must rest on the
    # target's own filing coordinate rather than shifting off it.
    if any(not isinstance(selector.temporal, SameTargetContext) for _binding, selector in typed_bindings):
        return _template_refusal_resolution(
            binding_ids,
            "inventory binding must rest on the selected filing coordinate",
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )

    bindings_by_operation: dict[str, BindingDefinition] = {}
    for binding, selector in typed_bindings:
        operation = selector.row_field
        if operation in bindings_by_operation:
            return _template_refusal_resolution(
                binding_ids,
                "duplicate inventory operation row template",
                resolver_id=resolver_id,
                owned_sources=owned_sources,
            )
        bindings_by_operation[operation] = binding
    if set(bindings_by_operation) != set(_CANONICAL_OPERATIONS) or len(bindings) != len(_CANONICAL_OPERATIONS):
        return _template_refusal_resolution(
            binding_ids,
            "inventory row-template cohort must contain each operation once",
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )
    return _InventoryBindingTemplate(by_operation=bindings_by_operation)


def _load_inventory_ledgers(
    repository: InventoryLedgerRepositoryProtocol,
    *,
    binding_ids: tuple[str, ...],
    filing_year: int,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> tuple[InventoryLedger, ...] | CalculationSourceResolution:
    """Read and select the deterministic filing-year activity ledger cohort."""
    try:
        document = repository.load()
    except InventoryLedgerError:
        return _storage_refusal_resolution(
            binding_ids,
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )
    ledgers = tuple(
        sorted(
            (item for item in document.ledgers if item.year == filing_year),
            key=lambda item: item.actividad_id,
        ),
    )
    if not ledgers:
        return CalculationSourceResolution(
            resolver_id=resolver_id,
            owned_sources=owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=(
                _diagnostic(
                    reason="source_domain_not_ready",
                    state="missing_activity_ledgers",
                    message=f"no complete {filing_year} inventory activity ledger is available",
                ),
            ),
        )
    return ledgers


def _row_provenance(content_fingerprint: str) -> CalculationSourceProvenance:
    """Name the activity record one row value rests on, addressed by its content.

    The terminal fact behind an inventory row value is one sealed activity
    projection, so the node is primary and carries the detail-record origin the
    provider registration admits. The reference addresses that record by its
    content digest rather than by ``actividad_id``: provenance is serialised
    into calculation persistence and operator-facing explanation, where the
    taxpayer's own activity identifier is not disclosable, and the digest names
    exactly one record without disclosing it.
    """
    return CalculationSourceProvenance(
        resolver_id=InventorySourceResolver.resolver_id,
        resolved_binding_source=_SOURCE,
        contributor_source_kind=_SOURCE.value,
        contributor_binding_source=_SOURCE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=f"inventory_activity:{content_fingerprint}",
        parent_source_ref=None,
        terminal_origin=TerminalOriginClass.DETAIL_RECORD,
        fingerprint=content_fingerprint,
    )


def _resolve_inventory_rows(
    ledgers: tuple[InventoryLedger, ...],
    *,
    binding_ids: tuple[str, ...],
    bindings_by_operation: Mapping[str, BindingDefinition],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Project each activity into row values, identities, and physical evidence diagnostics."""
    row_values: dict[tuple[str, int], Decimal | str] = {}
    row_identities: dict[tuple[str, int], RowSourceIdentity] = {}
    provenance: list[CalculationSourceProvenance] = []
    diagnostics: list[CalculationSourceDiagnostic] = []
    try:
        for row_index, ledger in enumerate(ledgers, start=1):
            projection = compute_inventory_anexo_d_projection(ledger)
            content_fingerprint = content_hash_hex(projection.model_dump(mode="json"))
            for operation, binding in bindings_by_operation.items():
                key = (binding.id, row_index)
                row_values[key] = getattr(projection, _VALUE_ATTRIBUTE_BY_OPERATION[operation])
                row_identities[key] = RowSourceIdentity(
                    source_kind=_SOURCE,
                    source_row_identity=projection.actividad_id,
                    fingerprint=projection.projection_fingerprint,
                )
            # One node per activity record, not per produced value: the three
            # operation values of an activity rest on that one sealed
            # projection, and the envelope admits a primary source reference
            # once, because a second copy would state two terminal facts where
            # the taxpayer has one.
            provenance.append(_row_provenance(content_fingerprint))
            if projection.closing_conflict is not None:
                diagnostics.append(
                    _diagnostic(
                        reason="source_issue",
                        state="physical_closing_conflict",
                        message="one inventory activity retains a reviewed physical closing conflict",
                    ),
                )
    except (InventoryLedgerError, ValidationError):
        return _projection_refusal_resolution(
            binding_ids,
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        row_binding_values=row_values,
        row_source_identities=row_identities,
        provenance=tuple(provenance),
        diagnostics=tuple(diagnostics),
    )


def _template_refusal_resolution(
    binding_ids: tuple[str, ...],
    message: str,
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Build the fail-closed result for an invalid inventory row-template cohort."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(
            _diagnostic(
                reason="unresolved_derived_binding",
                state="invalid_row_template_cohort",
                message=message,
            ),
        ),
    )


def _storage_refusal_resolution(
    binding_ids: tuple[str, ...],
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Build the fail-closed result for unreadable encrypted inventory storage."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(
            _diagnostic(
                reason="storage_degraded",
                state="repository_unreadable",
                message="encrypted inventory storage could not be read",
            ),
        ),
    )


def _projection_refusal_resolution(
    binding_ids: tuple[str, ...],
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Build the fail-closed result for incomplete or tampered activity projections."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(
            _diagnostic(
                reason="unresolved_derived_binding",
                state="incomplete_or_tampered_projection",
                message="inventory activity projection is incomplete or inconsistent",
            ),
        ),
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
        template = _resolve_inventory_binding_template(
            bindings,
            binding_ids=binding_ids,
            filing_year=context.filing_year,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )
        if isinstance(template, CalculationSourceResolution):
            return template
        if self._inventory_repository is None:
            return self._storage_refusal(binding_ids)
        ledgers = _load_inventory_ledgers(
            self._inventory_repository,
            binding_ids=binding_ids,
            filing_year=context.filing_year,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )
        if isinstance(ledgers, CalculationSourceResolution):
            return ledgers
        return _resolve_inventory_rows(
            ledgers,
            binding_ids=binding_ids,
            bindings_by_operation=template.by_operation,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )

    def _template_refusal(
        self,
        binding_ids: tuple[str, ...],
        message: str,
    ) -> CalculationSourceResolution:
        return _template_refusal_resolution(
            binding_ids,
            message,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )

    def _storage_refusal(self, binding_ids: tuple[str, ...]) -> CalculationSourceResolution:
        return _storage_refusal_resolution(
            binding_ids,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )


__all__ = ["InventoryLedgerRepositoryProtocol", "InventorySourceResolver"]
