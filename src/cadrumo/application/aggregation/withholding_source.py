"""Calc-mesh source resolver for the per-perceptor-clave withholding store.

Reads the dedicated :class:`PercepcionObservationRepository` for the modelo's
annual window and materialises the Modelo 190 "número total de percepciones" box
with the DISTINCT (perceptor, clave, subclave) count (the ``percepcion_count``
withholding fact) — replacing the wrong sum-of-quarterly-M111-perceptor-counts
relations. The pull and calculate surfaces read this ONE store
(``aeat-calculation-aggregation``).

Each annual modelo declares how its source is composed in
:data:`_ANNUAL_WITHHOLDING_SOURCES`: Modelo 190 folds the active quarterly
Modelo 111 projections, and Modelo 193 adds the pending and settled
disclosure phases of captured Modelo 123 capital allocations to its manual
window. Every other modelo reads its own window.

Lives in its own module (rather than ``modelo_bindings.py``) so the percepciones
source is isolated from the contended retenciones/ledger mesh surface; it is
enrolled in ``merge_source_resolutions`` exactly like the other source resolvers.
It reads the withholding bindings declared on the snapshot's :class:`ModeloRevision`
and returns its result as a :class:`CalculationSourceResolution`.

Empty-store behaviour materialises an explicit ZERO count AND surfaces a
non-blocking advisory (NOT a hard refusal) — a legitimate nil-percepciones
filer must still be able to calculate, and the bound casilla requires its
fact (``no-silent-under-declaration``: the zero is loud, not silent).

A settled prior-accrual Modelo 193 row carries amounts no official source
settles, so each one surfaces its own non-blocking advisory beside its values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.hashing import sha256_hex
from ...core.i18n.translatable import Translatable as tr
from ...core.modelo import Modelo
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
    resolve_withholding_binding_row_values,
    resolve_withholding_binding_values,
)
from .errors import AggregationValidationError
from .m193_phase_materialization import (
    Modelo193PhaseAmountField,
    Modelo193PhaseRow,
    materialize_modelo_193_disclosure_phases,
)
from .percepciones_observations_repository import (
    PercepcionObservationPersistenceError,
    PercepcionObservationPorts,
)
from .retencion_observations_repository import (
    RetencionObservationPersistenceError,
    RetencionObservationPorts,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import storage_degradation_resolution

_WITHHOLDING_SOURCE = BindingSourceKind.WITHHOLDING


@dataclass(frozen=True, slots=True)
class _AnnualWithholdingSource:
    """How one annual modelo composes its per-perceptor-clave source.

    ``periodic_percepciones`` names the periodic modelo whose active
    projections replace the annual window; ``None`` reads the modelo's own
    window. ``capital_disclosure_retenciones`` names the periodic retención
    modelo whose captured capital allocations materialise Modelo 193 disclosure
    phases next to that window; ``None`` adds no phase rows.
    """

    periodic_percepciones: Modelo | None = None
    capital_disclosure_retenciones: Modelo | None = None


_OWN_WINDOW = _AnnualWithholdingSource()

_ANNUAL_WITHHOLDING_SOURCES: Mapping[str, _AnnualWithholdingSource] = MappingProxyType(
    {
        Modelo("190").value: _AnnualWithholdingSource(periodic_percepciones=Modelo("111")),
        Modelo("193").value: _AnnualWithholdingSource(capital_disclosure_retenciones=Modelo("123")),
    }
)


def _revision_declares_withholding_scalar(revision: ModeloRevision) -> bool:
    """True when the revision carries any scalar withholding binding to materialise."""
    return any(binding.source == BindingSourceKind.WITHHOLDING for binding in revision.bindings)


def _provenance(observations: tuple[WithholdingObservation, ...]) -> tuple[CalculationSourceProvenance, ...]:
    return tuple(
        CalculationSourceProvenance(
            resolver_id=WithholdingSourceResolver.resolver_id,
            resolved_binding_source=BindingSourceKind.WITHHOLDING,
            contributor_source_kind=_WITHHOLDING_SOURCE,
            contributor_binding_source=BindingSourceKind.WITHHOLDING,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=_percepcion_source_ref(observation),
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.PERCEPTOR_OBSERVATION,
        )
        for observation in observations
    )


def _phase_contributor_provenance(
    phase_rows: tuple[Modelo193PhaseRow, ...],
    *,
    source_modelo: Modelo,
) -> tuple[CalculationSourceProvenance, ...]:
    """Link each phase row's annual detail to the captured allocation it derives from."""
    return tuple(
        CalculationSourceProvenance(
            resolver_id=WithholdingSourceResolver.resolver_id,
            resolved_binding_source=BindingSourceKind.WITHHOLDING,
            contributor_source_kind=row.source_kind.value,
            contributor_binding_source=row.source_kind,
            lineage_role=CalculationSourceLineageRole.CONTRIBUTOR,
            source_ref=f"retencion:{_phase_allocation_token(row)}",
            parent_source_ref=_percepcion_source_ref(row.annual_detail),
            terminal_origin=TerminalOriginClass.PERCEPTOR_OBSERVATION,
            source_modelo=source_modelo.value,
            source_filing_year=row.original_accrual_year,
        )
        for row in phase_rows
    )


def _percepcion_source_ref(observation: WithholdingObservation) -> str:
    return f"percepcion:{_provenance_token(observation)}"


def _provenance_token(observation: WithholdingObservation) -> str:
    """Return a stable opaque per-allocation provenance reference."""
    value = ":".join(
        (
            observation.perceptor_tax_id,
            observation.clave,
            observation.subclave or "-",
            observation.source_id,
            observation.source_allocation_id or observation.transaction_date.isoformat(),
        )
    )
    return sha256_hex(value.encode("utf-8"))


def _phase_allocation_token(row: Modelo193PhaseRow) -> str:
    """Return an opaque reference to the recognition and settlement behind one phase row."""
    value = ":".join(
        (
            row.phase.value,
            row.source_kind.value,
            row.source_object_id,
            row.allocation_id,
            row.recognition_event_id,
            row.settlement_event_id or "-",
        )
    )
    return sha256_hex(value.encode("utf-8"))


_AMOUNT_FIELD_LABELS: Mapping[Modelo193PhaseAmountField, str] = MappingProxyType(
    {
        Modelo193PhaseAmountField.BASE_RETENCIONES: "base retenciones e ingresos a cuenta",
        Modelo193PhaseAmountField.RETENCION_PRACTICADA: "retenciones e ingresos a cuenta",
    }
)


def _settled_amount_authority_diagnostics(
    phase_rows: tuple[Modelo193PhaseRow, ...],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Surface each settled prior-accrual row's unresolved amount authority, one advisory per row.

    ``source_ref`` is the row's contributor provenance reference, so a consumer
    joins the advisory to the captured allocation it speaks about.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for row in phase_rows:
        advisory = row.amount_authority_advisory
        if advisory is None:
            continue
        fields = " and ".join(f"{_AMOUNT_FIELD_LABELS[field]} ({field.value})" for field in advisory.affected_fields)
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason=advisory.reason,
                source_kind=_WITHHOLDING_SOURCE,
                resolver_id=WithholdingSourceResolver.resolver_id,
                source_ref=f"retencion:{_phase_allocation_token(row)}",
                message=(
                    f"Modelo {advisory.modelo} {advisory.filing_year}: a record settles income accrued in "
                    f"{advisory.accrual_year} from captured capital withholding (Modelo "
                    f"{advisory.source_modelo} allocation, {row.phase.value} disclosure phase). Its "
                    f"{fields} carry the full accrual amounts, but no official source settles what this "
                    f"payment-year record declares in those fields; the withholding was declared in the "
                    f"{advisory.accrual_year} Modelo {advisory.source_modelo}."
                ),
                remedy=(
                    "Confirm the base and withholding amounts of this record with AEAT before filing; "
                    "they are not filing grade."
                ),
            )
        )
    return tuple(diagnostics)


def _refuse_allocation_collisions(
    context: CalculationSourceContext,
    window: tuple[WithholdingObservation, ...],
    phase_rows: tuple[Modelo193PhaseRow, ...],
) -> None:
    """Refuse a phase row whose allocation the manual window already declares.

    Both sides would carry the same economic allocation into the annual rows;
    keeping either silently double-counts or drops it, so the operator decides.
    """
    window_allocations = {(observation.source_id, observation.source_allocation_id) for observation in window}
    colliding = sorted(
        {
            (row.source_object_id, row.allocation_id)
            for row in phase_rows
            if (row.source_object_id, row.allocation_id) in window_allocations
        }
    )
    if colliding:
        raise AggregationValidationError(
            tr("aggregation.retenciones.errors.m193_phase_allocation_collision"),
            context={
                "modelo": str(context.modelo),
                "filing_year": str(context.filing_year),
                "source_allocations": ", ".join(
                    f"{source_id}/{allocation_id}" for source_id, allocation_id in colliding
                ),
            },
        )


class WithholdingSourceResolver:
    """Source mesh resolver for the dedicated per-perceptor-clave withholding store.

    Materialises the Modelo 190 "número total de percepciones" box with the
    DISTINCT (perceptor_tax_id, clave, subclave) count (the ``percepcion_count``
    fact) over the persisted withholding detail — the percepciones counterpart of
    :class:`~.modelo_bindings_retenciones.RetencionesAggregationSourceResolver` (which counts
    distinct perceptores for M180/M193). The pull and calculate surfaces read this
    one store (one-aggregation-path).
    """

    resolver_id: ClassVar[str] = _WITHHOLDING_SOURCE.value
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_WITHHOLDING_SOURCE,)

    def __init__(self, *, ports: PercepcionObservationPorts, retencion_ports: RetencionObservationPorts) -> None:
        """Bind the bucket-scoped percepciones and retención capabilities."""
        self._ports = ports
        self._retencion_ports = retencion_ports

    def _window(
        self,
        composition: _AnnualWithholdingSource,
        context: CalculationSourceContext,
    ) -> tuple[WithholdingObservation, ...]:
        repository = self._ports.repository
        if composition.periodic_percepciones is not None:
            return repository.load_annual_source_observations(
                composition.periodic_percepciones.value,
                context.filing_year,
            )
        return repository.load_observations(str(context.modelo), context.period)

    def _disclosure_phase_rows(
        self,
        composition: _AnnualWithholdingSource,
        context: CalculationSourceContext,
    ) -> tuple[Modelo193PhaseRow, ...]:
        if composition.capital_disclosure_retenciones is None:
            return ()
        allocations = self._retencion_ports.repository.load_source_observations_through_year(
            composition.capital_disclosure_retenciones.value,
            context.filing_year,
        )
        return materialize_modelo_193_disclosure_phases(allocations, filing_year=context.filing_year)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve withholding totals from the bucket-scoped observation store."""
        if not _revision_declares_withholding_scalar(context.revision):
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        composition = _ANNUAL_WITHHOLDING_SOURCES.get(str(context.modelo), _OWN_WINDOW)
        try:
            window = self._window(composition, context)
            phase_rows = self._disclosure_phase_rows(composition, context)
        except (PercepcionObservationPersistenceError, RetencionObservationPersistenceError) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        _refuse_allocation_collisions(context, window, phase_rows)
        observations = (*window, *(row.annual_detail for row in phase_rows))
        # resolve_withholding_binding_values over an EMPTY set materialises the
        # scalar facts as zero (distinct of nothing) — the bound casilla still gets
        # its fact, so a nil-percepciones filer can calculate; the advisory below
        # makes the zero loud (no-silent-under-declaration), never a hard refusal.
        binding_values = resolve_withholding_binding_values(context.revision, observations)
        diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
        if not observations:
            diagnostics = (
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind=_WITHHOLDING_SOURCE,
                    resolver_id=self.resolver_id,
                    message=(
                        f"Modelo {context.modelo} declares a withholding percepción binding but no "
                        f"per-perceptor-clave observations are persisted for "
                        f"{context.period.registry_token} {context.filing_year}; the distinct "
                        "percepciones count is materialised as zero. Supply the per-perceptor records "
                        "through the modelo aggregate surface before filing."
                    ),
                ),
            )
        phase_provenance: tuple[CalculationSourceProvenance, ...] = ()
        if composition.capital_disclosure_retenciones is not None:
            phase_provenance = _phase_contributor_provenance(
                phase_rows,
                source_modelo=composition.capital_disclosure_retenciones,
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            row_binding_values=resolve_withholding_binding_row_values(context.revision, observations),
            diagnostics=(*diagnostics, *_settled_amount_authority_diagnostics(phase_rows)),
            provenance=(*_provenance(observations), *phase_provenance),
        )


__all__ = ["WithholdingSourceResolver"]
