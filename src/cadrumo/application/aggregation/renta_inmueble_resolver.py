"""Resolve the ``renta_inmueble`` columns of a Modelo 100 revision from the profile and the ledger.

Each occurrence becomes one row of every column the revision declares, at the
occurrence's own index, so the return carries one ``Inmueble`` per property held
in the ejercicio. A refusal anywhere withholds every row: the block is numbered,
and leaving one property out would move the others to rows that are not theirs.
A blocking finding keeps the rows and withholds checking, export and filing; a
limitation is shown and withholds nothing.

A results box the rows account for is the total of one column over every let
property; it is unresolved while any let property's value of that column is.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.calculations.registry.binding_selector_utils import provider_member
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.formula_runtime_ops import read_parameter
from ...domain.calculations.registry.gasto_capital_inmobiliario import (
    GastoCapitalInmobiliarioCatalogue,
    resolve_gasto_capital_inmobiliario_catalogue,
)
from ...domain.calculations.registry.ids import BindingId, RevisionId
from ...domain.calculations.registry.renta_inmueble_bindings import (
    CARRY_YEARS_PARAMETER,
    RentaInmuebleOrigin,
    RentaInmuebleOriginPart,
    RentaInmuebleProvider,
    renta_inmueble_columns,
    renta_inmueble_origin_columns,
    renta_inmueble_origin_failures,
    renta_inmueble_totals,
)
from ...domain.calculations.registry.rental_reduction import (
    resolve_rental_reduction_art232_rates,
    resolve_rental_reduction_art232_rules,
)
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.row_source_identity import RowSourceIdentity
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..user_profile.projections import record_to_path_values
from .modelo_bindings_support import STORAGE_DEGRADATION_ERRORS
from .renta_inmueble_carry import PendingStatements
from .renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleFinding, RentaInmuebleFindingKind
from .renta_inmueble_net import RentaInmuebleTerms
from .renta_inmueble_source import (
    GASTO_COLUMN_PREFIX,
    SUMMABLE_COLUMNS,
    RentaInmuebleColumnValue,
    RentaInmuebleOccurrence,
    RentaInmuebleOccurrences,
    RentaInmuebleRowField,
    renta_inmueble_occurrences,
)
from .retencion_soportada_repository import RetencionSoportadaPersistenceError, RetencionSoportadaPorts
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
_AMORTISATION_RATE: Final = "renta-rental-amortizacion-rate"
_NO_AMOUNT: Final = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class _Column:
    """One declared column: an occurrence field, or the expense concept whose rows it states."""

    binding: BindingDefinition
    field: RentaInmuebleRowField | None
    concept: str | None
    origin: RentaInmuebleOrigin | None = None

    def value(self, occurrence: RentaInmuebleOccurrence) -> RentaInmuebleColumnValue | None:
        if self.concept is not None:
            return occurrence.gasto(self.concept)
        if self.origin is not None:
            return occurrence.origin(self.origin)
        return None if self.field is None else occurrence.column(self.field)


def _diagnostic(
    *,
    reason: CalculationSourceDiagnosticReason,
    message: str,
    source_ref: str | None = None,
    remedy: str | None = None,
    fact: CalculationNoteFact | None = None,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=reason,
        source_kind=_SOURCE.value,
        binding_source=_SOURCE,
        message=f"renta_inmueble source: {message}",
        remedy=remedy,
        resolver_id=RentaInmuebleSourceResolver.resolver_id,
        source_ref=source_ref,
        fact=fact,
    )


_NAMED_RECORDS: Final = frozenset({"inmueble", "arrendamiento"})
"""The subject kinds a finding's sentence names by the record's own number."""

_FINDING_SENTENCES: Final = {
    cause: CalculationNoteSentence(f"renta_inmueble_{cause.value}") for cause in RentaInmuebleCause
}
"""The catalogue sentence that states each finding, so it reads in every language."""


type _Openings = dict[int, BindingDefinition]
"""The anexo C.1 opening column of each origin year, by origin back."""


def _finding_fact(finding: RentaInmuebleFinding, openings: _Openings) -> CalculationNoteFact:
    kind, _separator, record = finding.subject.partition(":")
    named: dict[str, str] = {"record": record} if kind in _NAMED_RECORDS and record else {}
    opening = None if finding.back is None else openings.get(finding.back)
    if opening is not None:
        named["box"] = _target_casilla(opening)
        named["binding"] = opening.id
    return CalculationNoteFact.of(_FINDING_SENTENCES[finding.cause], rows=(finding.subject,), **named)


def _target_casilla(binding: BindingDefinition) -> str:
    return str(provider_member(binding, RentaInmuebleProvider).target_casilla_id)


def _door_text(finding: RentaInmuebleFinding, openings: _Openings) -> str | None:
    """Return the command that settles ``finding``, naming the column and row where the command takes them.

    A statement of one origin year's carry names that year's opening column; the work unit is the
    caller's, so it stands as a placeholder.
    """
    door = finding.door
    if door is None:
        return None
    if not door.takes_row:
        return door.value
    opening = None if finding.back is None else openings.get(finding.back)
    column = "" if opening is None else f" <work-unit> {opening.id}"
    return f"{door.value}{column} --row {finding.subject}"


def _finding_diagnostic(finding: RentaInmuebleFinding, openings: _Openings) -> CalculationSourceDiagnostic:
    door = _door_text(finding, openings)
    return _diagnostic(
        reason="deferred_binding_source"
        if finding.kind is RentaInmuebleFindingKind.LIMITATION
        else "source_domain_not_ready",
        message=finding.message,
        source_ref=finding.subject,
        remedy=None if door is None else f"Settle it with {door}, then calculate again.",
        fact=_finding_fact(finding, openings),
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
    if provider.origin is not None:
        return _Column(
            binding=binding, field=RentaInmuebleRowField.GASTOS_PENDIENTES_ORIGEN, concept=None, origin=provider.origin
        )
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


def _unreadable_totals(totals: Iterable[tuple[BindingDefinition, RentaInmuebleProvider]]) -> tuple[str, ...]:
    """Say why a declared total cannot be summed: it names no column of the net chain's amounts."""
    reasons: list[str] = []
    for binding, provider in totals:
        try:
            field = RentaInmuebleRowField(provider.row_field)
        except ValueError:
            reasons.append(f"no source reads the column total {binding.id}")
            continue
        if field not in SUMMABLE_COLUMNS:
            reasons.append(f"the column total {binding.id} names a column that is not an amount")
    return tuple(reasons)


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
            "retenciones": sorted(
                (record.payer_ref, str(record.pago_a_cuenta), record.captured_at.isoformat())
                for record in occurrence.withholding
            ),
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


def _totals(
    built: RentaInmuebleOccurrences, totals: Iterable[tuple[BindingDefinition, RentaInmuebleProvider]]
) -> tuple[dict[BindingId, Decimal], tuple[BindingId, ...]]:
    """Sum each total's column over the let properties; leave a total unresolved while one value is unknown."""
    values: dict[BindingId, Decimal] = {}
    unresolved: list[BindingId] = []
    let = tuple(occurrence for occurrence in built.occurrences if occurrence.net is not None)
    for binding, provider in totals:
        column = RentaInmuebleRowField(provider.row_field)
        amounts = [occurrence.column(column) for occurrence in let]
        if all(isinstance(amount, Decimal) for amount in amounts):
            values[binding.id] = sum((amount for amount in amounts if isinstance(amount, Decimal)), _NO_AMOUNT)
        else:
            unresolved.append(binding.id)
    return values, tuple(unresolved)


def _pending_stated(
    declared: Iterable[tuple[BindingDefinition, RentaInmuebleProvider]],
    openings: _Openings,
    context: CalculationSourceContext,
) -> PendingStatements:
    """Read the filer's per-property statements of the carry, keyed by the column and row each names.

    A statement on an opening column, which the family takes, speaks of that column's origin year.
    A statement on the column of the whole carry, from before the carry was split by origin year,
    is kept as that property's total.
    """
    backs = {
        binding.id: back
        for back, binding in openings.items()
        if binding.absence_attestation is AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES
    }
    whole = {
        binding.id
        for binding, provider in declared
        if provider.row_field == RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES.value
        and binding.absence_attestation is None
    }
    by_origin: dict[int, dict[str, Decimal]] = {}
    totals: dict[str, Decimal] = {}
    for statement in context.caller_row_attestations:
        back = backs.get(statement.binding_id)
        if back is not None:
            by_origin.setdefault(back, {})[statement.source_row_identity] = statement.stated_amount
        elif statement.binding_id in whole:
            totals[statement.source_row_identity] = statement.stated_amount
    return PendingStatements(by_origin=by_origin, totals=totals)


def _whole_years(value: Decimal) -> int:
    if value != value.to_integral_value() or value < 1:
        raise ValueError(f"{CARRY_YEARS_PARAMETER} must be a whole number of years of at least one, got {value}")
    return int(value)


def resolve_renta_inmueble_terms(
    *, modelo: str, revision_id: RevisionId, devengo: date, operation: PinnedAuthorityOperation
) -> RentaInmuebleTerms:
    """Resolve the dated registry data the net chain reads at the ejercicio's devengo."""
    return RentaInmuebleTerms(
        amortizacion_rate=read_parameter(
            modelo,
            revision_id,
            _AMORTISATION_RATE,
            date_context={DateAxis.FILING_PERIOD.value: devengo},
            operation=operation,
        ),
        carry_years=_whole_years(
            read_parameter(
                modelo,
                revision_id,
                CARRY_YEARS_PARAMETER,
                date_context={DateAxis.FILING_PERIOD.value: devengo},
                operation=operation,
            )
        ),
        reduction_rules=resolve_rental_reduction_art232_rules(
            modelo_id=modelo, revision_id=revision_id, devengo=devengo, operation=operation
        ),
        reduction_rates=resolve_rental_reduction_art232_rates(
            modelo_id=modelo, revision_id=revision_id, devengo=devengo, operation=operation
        ),
    )


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


type PriorReturnHeld = Callable[[CalculationSourceContext], bool]
"""Whether the profile holds a filed return of the context's modelo and period for the previous ejercicio."""


class RentaInmuebleSourceResolver:
    """Resolve ``renta_inmueble`` row columns: one row per property held in the ejercicio.

    Reads the profile the calculation loaded and every ledger row of the profile;
    the occurrence function owns every join, figure and finding.
    """

    resolver_id: ClassVar[str] = "renta_inmueble"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        retencion_soportada_ports: RetencionSoportadaPorts,
        prior_return_held: PriorReturnHeld | None = None,
    ) -> None:
        """Bind the ledger the rent and expense rows are read from, and the suffered-withholding store.

        ``prior_return_held`` reads whether the previous ejercicio's return is held, which words the
        finding on a property whose earlier pending amounts are unstated. A caller that reads only the
        rows' identities passes none, and every unstated property is worded as having no return held.
        """
        self._transaction_repository = transaction_repository
        self._retencion_soportada_ports = retencion_soportada_ports
        self._prior_return_held = prior_return_held

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
        totals = renta_inmueble_totals(context.revision)
        if not declared and not totals:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        binding_ids = tuple(sorted(binding.id for binding, _provider in (*declared, *totals)))
        if context.profile is None:
            return self._withheld(binding_ids, ("the profile was not loaded",))
        try:
            transactions = self._transaction_repository.load()
            withholding = self._retencion_soportada_ports.repository.load_records(context.filing_year)
            prior_return_held = self._prior_return_held is not None and self._prior_return_held(context)
        except (RetencionSoportadaPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
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
            terms = resolve_renta_inmueble_terms(
                modelo=context.modelo,
                revision_id=context.revision.id,
                devengo=context.period.end_date,
                operation=operation,
            )
        columns, unreadable = _typed_columns(declared, concepts)
        unreadable = (*unreadable, *_unreadable_totals(totals), *renta_inmueble_origin_failures(context.revision))
        if unreadable:
            return self._withheld(binding_ids, unreadable)
        openings = renta_inmueble_origin_columns(context.revision).get(RentaInmuebleOriginPart.OPENING, {})
        built = renta_inmueble_occurrences(
            path_values=record_to_path_values(context.profile.record, as_of=context.period.end_date),
            transactions=transactions.values(),
            ejercicio=context.filing_year,
            concepts=concepts,
            terms=terms,
            withholding=withholding,
            pending_stated=_pending_stated(declared, openings, context),
            prior_return_held=prior_return_held,
        )
        return self._resolution(built, columns, totals, binding_ids, openings)

    def _resolution(
        self,
        built: RentaInmuebleOccurrences,
        columns: tuple[_Column, ...],
        totals: tuple[tuple[BindingDefinition, RentaInmuebleProvider], ...],
        binding_ids: tuple[BindingId, ...],
        openings: _Openings,
    ) -> CalculationSourceResolution:
        diagnostics = (
            *(_finding_diagnostic(finding, openings) for finding in built.findings),
            *_unrouted_expenses(built, columns),
        )
        if built.refused or any(diagnostic.reason == "unrouted_observation" for diagnostic in diagnostics):
            return self._withheld(binding_ids, diagnostics)
        values, identities = _rows(built, columns)
        total_values, unresolved = _totals(built, totals)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=total_values,
            unresolved_binding_ids=unresolved,
            row_binding_values=values,
            row_source_identities=identities,
            diagnostics=diagnostics,
            provenance=_provenance(built),
        )


__all__ = ["PriorReturnHeld", "RentaInmuebleSourceResolver", "resolve_renta_inmueble_terms"]
