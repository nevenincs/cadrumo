"""Resolve the prorrata activity-row bindings from the profile's prorrata register.

Modelo 390 apartado 12 prints one row per activity: CNAE code, volume of
operations, volume with the right to deduct, kind of prorrata and its
definitive percentage. The register owns those rows. This resolver reads the
row each binding names and hands its fact to the calculation unchanged: codes
on the text channel, amounts and the percentage on the decimal channel.

Where the register records no prorrata for the ejercicio, every row is outside
the filing and its boxes stay absent rather than zero. Where it records one, a
row the register leaves empty is likewise absent, and an incomplete row set is
reported as a gap, never filled.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.prorrata_register_activity_bindings import (
    ProrrataActivityField,
    ProrrataRegisterActivityProvider,
)
from ...domain.prorrata_register.register import ProrrataActivityRow, ProrrataRegister
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import source_context_operation

if TYPE_CHECKING:
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol

__all__ = ["ProrrataRegisterActivitySourceResolver"]

_SOURCE: Final = BindingSourceKind.PRORRATA_REGISTER_ACTIVITY


def _row_fact(row: ProrrataActivityRow, field: ProrrataActivityField) -> str | Decimal:
    match field:
        case ProrrataActivityField.CNAE:
            return row.cnae_code
        case ProrrataActivityField.OPERACIONES_TOTAL:
            return row.operaciones_total
        case ProrrataActivityField.OPERACIONES_CON_DERECHO:
            return row.operaciones_con_derecho
        case ProrrataActivityField.TIPO:
            return row.prorrata_type.value
        case ProrrataActivityField.PORCENTAJE:
            return row.percentage


def _provenance(row: ProrrataActivityRow) -> CalculationSourceProvenance:
    fingerprint = content_hash_hex(row.model_dump(mode="json"))
    return CalculationSourceProvenance(
        resolver_id=ProrrataRegisterActivitySourceResolver.resolver_id,
        resolved_binding_source=_SOURCE,
        contributor_source_kind=_SOURCE.value,
        contributor_binding_source=_SOURCE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=f"prorrata_activity_row:{fingerprint}",
        parent_source_ref=None,
        terminal_origin=TerminalOriginClass.DETAIL_RECORD,
        fingerprint=fingerprint,
    )


class ProrrataRegisterActivitySourceResolver:
    """Resolve each prorrata activity binding from its register row."""

    resolver_id: ClassVar[str] = "prorrata_register_activity"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE,)

    def __init__(self, *, prorrata_register_repository: ProrrataRegisterRepositoryProtocol | None) -> None:
        """Bind the bucket's register repository; ``None`` refuses every declared binding."""
        self._repository = prorrata_register_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the revision's prorrata activity bindings for the context's ejercicio."""
        bindings = {
            binding.id: binding.provider
            for binding in context.revision.bindings
            if isinstance(binding.provider, ProrrataRegisterActivityProvider)
        }
        if not bindings:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        binding_ids = tuple(sorted(bindings))
        if self._repository is None:
            return self._unresolved(binding_ids, state="storage_unavailable", message="no prorrata register store")
        with source_context_operation(context) as operation:
            register = require_prorrata_register_coordinates_current(self._repository.load(), operation=operation)
        return self._resolve_rows(register, bindings, ejercicio=context.filing_year)

    def _resolve_rows(
        self,
        register: ProrrataRegister,
        bindings: Mapping[BindingId, ProrrataRegisterActivityProvider],
        *,
        ejercicio: int,
    ) -> CalculationSourceResolution:
        binding_ids = tuple(sorted(bindings))
        rows = {row.slot: row for row in register.activity_rows_for_ejercicio(ejercicio)}
        if not register.requires_activity_rows_for(ejercicio) and not rows:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=binding_ids,
                inapplicable_binding_ids=binding_ids,
            )
        if not register.activity_rows_complete_for(ejercicio):
            return self._unresolved(
                binding_ids,
                state="activity_rows_incomplete",
                message=f"the prorrata register does not hold every activity row for {ejercicio}",
            )
        decimals: dict[BindingId, Decimal] = {}
        texts: dict[BindingId, str] = {}
        empty: list[BindingId] = []
        for binding_id, provider in bindings.items():
            row = rows.get(provider.slot)
            if row is None:
                empty.append(binding_id)
                continue
            value = _row_fact(row, provider.field)
            if isinstance(value, Decimal):
                decimals[binding_id] = value
            else:
                texts[binding_id] = value
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=dict(sorted(decimals.items())),
            enum_binding_values=dict(sorted(texts.items())),
            unresolved_binding_ids=tuple(sorted(empty)),
            inapplicable_binding_ids=tuple(sorted(empty)),
            provenance=tuple(_provenance(rows[slot]) for slot in sorted(rows)),
        )

    def _unresolved(
        self, binding_ids: tuple[BindingId, ...], *, state: str, message: str
    ) -> CalculationSourceResolution:
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=(
                CalculationSourceDiagnostic(
                    reason="unresolved_binding",
                    source_kind=_SOURCE.value,
                    binding_source=_SOURCE,
                    resolver_id=self.resolver_id,
                    message=f"prorrata activity source {state}: {message}",
                ),
            ),
        )
