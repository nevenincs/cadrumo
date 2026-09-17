"""Previous-filing source-mesh adapter.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..aggregation.source_resolution_operations import storage_degradation_resolution
from ..persistence_errors import PersistenceDegradationError
from ..user_profile.profile_read_ports import ProfileReadPorts
from .iva_compensation_history_ports import (
    IvaCompensationHistoryPersistenceError,
    IvaCompensationHistoryRepositoryProtocol,
)
from .observations_repository import CalculationObservationRepositoryProtocol

if TYPE_CHECKING:
    from .binding_prefill import PrefilledBinding


def _prefill_source_ref(item: PrefilledBinding, unknown: str) -> str:
    """Render one prefilled carry's source coordinate, naming each unknown axis.

    A coordinate axis the prefill could not establish is carried as ``None``, so
    it is rendered as an explicit unknown token: a blank segment would read as a
    coordinate that was established and found empty.
    """
    periods = ",".join(item.source_periods)
    return (
        f"{item.source_modelo or unknown}:"
        f"{item.source_filing_year if item.source_filing_year is not None else unknown}:"
        f"{periods or unknown}:{item.binding_id}"
    )


class PreviousFilingSourceResolver:
    """Resolve previous-filing bindings from the prior-year local store."""

    resolver_id: ClassVar[str] = "previous_filing"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.PREVIOUS_FILING,)

    def __init__(
        self,
        *,
        operation: PinnedAuthorityOperation,
        repository: CalculationObservationRepositoryProtocol,
        iva_history_repository: IvaCompensationHistoryRepositoryProtocol,
        profile_read_ports: ProfileReadPorts,
        registry_snapshot: RegistrySnapshot | None = None,
        excluded_binding_ids: frozenset[BindingId] | None = None,
    ) -> None:
        """Bind the composed observation repository and registry collaborators."""
        self._repository = repository
        self._operation = operation
        self._iva_history_repository = iva_history_repository
        self._profile_read_ports = profile_read_ports
        self._registry_snapshot = registry_snapshot
        self._excluded_binding_ids = excluded_binding_ids or frozenset()

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve prior-filing bindings for one calculation context."""
        if self._registry_snapshot is not None:
            snapshot = self._registry_snapshot
        else:
            snapshot = self._operation.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        from .binding_prefill import UNKNOWN_SOURCE_COORDINATE, resolve_bindings_from_local_store
        from .relation_prefill import activity_start_date_for_bucket

        try:
            report = resolve_bindings_from_local_store(
                snapshot,
                operation=self._operation,
                repository=self._repository,
                iva_history_repository=self._iva_history_repository,
                activity_start_date=activity_start_date_for_bucket(
                    str(context.bucket_id),
                    profile_path_values_reader=self._profile_read_ports.path_values,
                ),
                excluded_binding_ids=self._excluded_binding_ids,
            )
        except (PersistenceDegradationError, IvaCompensationHistoryPersistenceError) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=report.binding_values,
            unresolved_binding_ids=tuple(item.binding_id for item in report.unsatisfied),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="unresolved_binding",
                    source_kind="previous_filing",
                    resolver_id=self.resolver_id,
                    binding_id=item.binding_id,
                    message=(
                        f"Modelo {context.modelo} declares previous-filing binding {item.binding_id!r}, "
                        f"but no observation for modelo {item.source_modelo} {item.source_filing_year} "
                        f"{'+'.join(item.source_periods) if item.source_periods else '(any period)'} "
                        "is in the local store, so the carry contributes nothing. File or capture the "
                        "prior filing, or enter the value by hand, before filing."
                    ),
                )
                for item in report.unsatisfied
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.PREVIOUS_FILING,
                    contributor_source_kind="previous_filing",
                    contributor_binding_source=BindingSourceKind.PREVIOUS_FILING,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=_prefill_source_ref(item, UNKNOWN_SOURCE_COORDINATE),
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.FILED_MODELO_CASILLA,
                    dependency_treatment=item.dependency_treatment,
                )
                for item in report.prefilled
            ),
        )


__all__ = ["PreviousFilingSourceResolver"]
