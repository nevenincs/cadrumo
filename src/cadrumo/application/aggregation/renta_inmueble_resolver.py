"""Resolve the ``renta_inmueble`` columns of a Modelo 100 revision from the profile and the ledger.

Each occurrence becomes one row of every column the revision declares, at the
occurrence's own index, so the return carries one ``Inmueble`` per property held
in the ejercicio. A refusal anywhere withholds every row: the block is numbered,
and leaving one property out would move the others to rows that are not theirs.
A blocking finding keeps the rows and withholds checking, export and filing; a
limitation is shown and withholds nothing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.gasto_capital_inmobiliario import (
    GastoCapitalInmobiliarioCatalogue,
    resolve_gasto_capital_inmobiliario_catalogue,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.renta_inmueble_bindings import RentaInmuebleProvider, renta_inmueble_columns
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.row_source_identity import RowSourceIdentity
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..user_profile.projections import record_to_path_values
from .modelo_bindings_support import STORAGE_DEGRADATION_ERRORS
from .renta_inmueble_findings import RentaInmuebleFinding, RentaInmuebleFindingKind
from .renta_inmueble_source import (
    GASTO_COLUMN_PREFIX,
    RentaInmuebleColumnValue,
    RentaInmuebleOccurrence,
    RentaInmuebleOccurrences,
    RentaInmuebleRowField,
    renta_inmueble_occurrences,
)
from .source_diagnostic_reason import CalculationSourceDiagnosticReason
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import source_context_operation, storage_degradation_resolution

_SOURCE: Final = BindingSourceKind.RENTA_INMUEBLE
_TRANSACTION_CONTRIBUTOR: Final = "transaction"


@dataclass(frozen=True, slots=True)
class _Column:
    """One declared column: an occurrence field, or the expense concept whose rows it states."""

    binding: BindingDefinition
    field: RentaInmuebleRowField | None
    concept: str | None

    def value(self, occurrence: RentaInmuebleOccurrence) -> RentaInmuebleColumnValue | None:
        if self.concept is not None:
            return occurrence.gasto(self.concept)
        return None if self.field is None else occurrence.column(self.field)


def _diagnostic(
    *,
    reason: CalculationSourceDiagnosticReason,
    message: str,
    source_ref: str | None = None,
    remedy: str | None = None,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=reason,
        source_kind=_SOURCE.value,
        binding_source=_SOURCE,
        message=f"renta_inmueble source: {message}",
        remedy=remedy,
        resolver_id=RentaInmuebleSourceResolver.resolver_id,
        source_ref=source_ref,
    )


def _finding_diagnostic(finding: RentaInmuebleFinding) -> CalculationSourceDiagnostic:
    door = finding.door
    return _diagnostic(
        reason="deferred_binding_source"
        if finding.kind is RentaInmuebleFindingKind.LIMITATION
        else "source_domain_not_ready",
        message=finding.message,
        source_ref=finding.subject,
        remedy=None if door is None else f"Settle it with {door.value}, then calculate again.",
    )


def _typed_column(
    binding: BindingDefinition, provider: RentaInmuebleProvider, concepts: GastoCapitalInmobiliarioCatalogue
) -> _Column | str:
    """Read one declared column, or say why no source can read it."""
    token = provider.row_field
    if token.startswith(GASTO_COLUMN_PREFIX):
        concept = token.removeprefix(GASTO_COLUMN_PREFIX)
        declared = next((item for item in concepts.concepts if str(item.token) == concept), None)
        if declared is None or declared.capitalised:
            return f"column {binding.id} names no deductible expense concept of the ejercicio"
        if declared.casilla_id != provider.target_casilla_id:
            return f"column {binding.id} fills a box other than the one the concept vocabulary gives {concept}"
        return _Column(binding=binding, field=None, concept=concept)
    try:
        return _Column(binding=binding, field=RentaInmuebleRowField(token), concept=None)
    except ValueError:
        return f"no source reads column {binding.id}"


def _typed_columns(
    declared: Iterable[tuple[BindingDefinition, RentaInmuebleProvider]], concepts: GastoCapitalInmobiliarioCatalogue
) -> tuple[tuple[_Column, ...], tuple[str, ...]]:
    """Split the declared columns into those a source reads and the reasons the others cannot be read."""
    read = tuple(_typed_column(binding, provider, concepts) for binding, provider in declared)
    return (
        tuple(column for column in read if isinstance(column, _Column)),
        tuple(reason for reason in read if isinstance(reason, str)),
    )


def _unrouted_expenses(
    built: RentaInmuebleOccurrences, columns: tuple[_Column, ...]
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report each prorated expense concept the revision gives no column, so it is never dropped."""
    routed = frozenset(column.concept for column in columns if column.concept is not None)
    return tuple(
        _diagnostic(
            reason="unrouted_observation",
            message=f"the expense concept {concept} has no column on this revision",
            source_ref=occurrence.source_identity,
        )
        for occurrence in built.occurrences
        for concept in sorted(occurrence.gastos)
        if concept not in routed
    )


def _fingerprint(occurrence: RentaInmuebleOccurrence) -> str:
    return content_hash_hex(
        {
            "inmueble": occurrence.inmueble.model_dump(mode="json"),
            "leases": [lease.model_dump(mode="json") for lease in occurrence.leases],
            "dias_arrendado": occurrence.dias_arrendado,
            "ingresos": None if occurrence.ingresos is None else str(occurrence.ingresos),
            "gastos": {concept: str(amount) for concept, amount in sorted(occurrence.gastos.items())},
            "transactions": list(occurrence.transaction_ids),
        }
    )


def _rows(
    built: RentaInmuebleOccurrences, columns: tuple[_Column, ...]
) -> tuple[dict[tuple[BindingId, int], RentaInmuebleColumnValue], dict[tuple[BindingId, int], RowSourceIdentity]]:
    values: dict[tuple[BindingId, int], RentaInmuebleColumnValue] = {}
    identities: dict[tuple[BindingId, int], RowSourceIdentity] = {}
    for occurrence in built.occurrences:
        identity = RowSourceIdentity(
            source_kind=_SOURCE,
            source_row_identity=occurrence.source_identity,
            fingerprint=_fingerprint(occurrence),
        )
        for column in columns:
            value = column.value(occurrence)
            if value is not None:
                values[(column.binding.id, occurrence.index)] = value
                identities[(column.binding.id, occurrence.index)] = identity
    return values, identities


def _provenance(built: RentaInmuebleOccurrences) -> tuple[CalculationSourceProvenance, ...]:
    nodes: list[CalculationSourceProvenance] = []
    for occurrence in built.occurrences:
        nodes.append(
            CalculationSourceProvenance(
                resolver_id=RentaInmuebleSourceResolver.resolver_id,
                resolved_binding_source=_SOURCE,
                contributor_source_kind=_SOURCE.value,
                contributor_binding_source=_SOURCE,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=occurrence.source_identity,
                parent_source_ref=None,
                fingerprint=_fingerprint(occurrence),
                terminal_origin=TerminalOriginClass.PROFILE_FIELD,
            )
        )
        nodes.extend(
            CalculationSourceProvenance(
                resolver_id=RentaInmuebleSourceResolver.resolver_id,
                resolved_binding_source=_SOURCE,
                contributor_source_kind=_TRANSACTION_CONTRIBUTOR,
                contributor_binding_source=None,
                lineage_role=CalculationSourceLineageRole.CONTRIBUTOR,
                source_ref=f"transaction:{transaction_id}",
                parent_source_ref=occurrence.source_identity,
                terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
            )
            for transaction_id in occurrence.transaction_ids
        )
    return tuple(nodes)


class RentaInmuebleSourceResolver:
    """Resolve ``renta_inmueble`` row columns: one row per property held in the ejercicio.

    Reads the profile the calculation loaded and every ledger row of the profile;
    the occurrence function owns every join, figure and finding.
    """

    resolver_id: ClassVar[str] = "renta_inmueble"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol) -> None:
        """Bind the ledger the rent and expense rows are read from."""
        self._transaction_repository = transaction_repository

    def _withheld(
        self, binding_ids: tuple[BindingId, ...], reasons: Iterable[CalculationSourceDiagnostic | str]
    ) -> CalculationSourceResolution:
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=tuple(
                _diagnostic(reason="source_domain_not_ready", message=reason) if isinstance(reason, str) else reason
                for reason in reasons
            ),
        )

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve every ``renta_inmueble`` column the revision declares for ``context``.

        Returns:
            An empty resolution when the revision declares none; every column
            unresolved with its reasons when the occurrences cannot be built;
            otherwise one row per occurrence with its findings and provenance.
        """
        declared = renta_inmueble_columns(context.revision)
        if not declared:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        binding_ids = tuple(sorted(binding.id for binding, _provider in declared))
        if context.profile is None:
            return self._withheld(binding_ids, ("the profile was not loaded",))
        try:
            transactions = self._transaction_repository.load()
        except STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=(_SOURCE.value,),
                error=exc,
            )
        with source_context_operation(context) as operation:
            concepts = resolve_gasto_capital_inmobiliario_catalogue(
                effective_date=context.period.end_date, authority=operation
            )
        columns, unreadable = _typed_columns(declared, concepts)
        if unreadable:
            return self._withheld(binding_ids, unreadable)
        built = renta_inmueble_occurrences(
            path_values=record_to_path_values(context.profile.record, as_of=context.period.end_date),
            transactions=transactions.values(),
            ejercicio=context.filing_year,
            concepts=concepts,
        )
        return self._resolution(built, columns, binding_ids)

    def _resolution(
        self,
        built: RentaInmuebleOccurrences,
        columns: tuple[_Column, ...],
        binding_ids: tuple[BindingId, ...],
    ) -> CalculationSourceResolution:
        diagnostics = (
            *(_finding_diagnostic(finding) for finding in built.findings),
            *_unrouted_expenses(built, columns),
        )
        if built.refused or any(diagnostic.reason == "unrouted_observation" for diagnostic in diagnostics):
            return self._withheld(binding_ids, diagnostics)
        values, identities = _rows(built, columns)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            row_binding_values=values,
            row_source_identities=identities,
            diagnostics=diagnostics,
            provenance=_provenance(built),
        )


__all__ = ["RentaInmuebleSourceResolver"]
