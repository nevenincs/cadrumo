"""Calc-mesh source resolver for the per-perceptor-clave withholding store.

Reads the dedicated :class:`PercepcionObservationRepository` for the modelo's
annual window and materialises the Modelo 190 "número total de percepciones" box
with the DISTINCT (perceptor, clave, subclave) count (the ``percepcion_count``
withholding fact) — replacing the wrong sum-of-quarterly-M111-perceptor-counts
relations. The pull and calculate surfaces read this ONE store
(``aeat-calculation-aggregation``).

Lives in its own module (rather than ``_modelo_bindings.py``) so the percepciones
source is isolated from the contended retenciones/ledger mesh surface; it is
enrolled in ``merge_source_resolutions`` exactly like the other source resolvers.
It reads the withholding bindings declared on the snapshot's :class:`ModeloRevision`
and returns its result as a :class:`CalculationSourceResolution`.

Empty-store behaviour materialises an explicit ZERO count AND surfaces a
non-blocking advisory (NOT a hard refusal) — a legitimate nil-percepciones
filer must still be able to calculate, and the bound casilla requires its
fact (``no-silent-under-declaration``: the zero is loud, not silent).
"""

from __future__ import annotations

from typing import ClassVar

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
    resolve_withholding_binding_values,
)
from ._percepciones_observations_repository import PercepcionObservationRepository
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import storage_degradation_resolution

STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)

_WITHHOLDING_SOURCE = BindingSourceKind.WITHHOLDING


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
            source_ref=f"percepcion:{observation.perceptor_tax_id}:{observation.clave}:{observation.subclave or '-'}",
            parent_source_ref=None,
        )
        for observation in observations
    )


class WithholdingSourceResolver:
    """Source mesh resolver for the dedicated per-perceptor-clave withholding store.

    Materialises the Modelo 190 "número total de percepciones" box with the
    DISTINCT (perceptor_tax_id, clave, subclave) count (the ``percepcion_count``
    fact) over the persisted withholding detail — the percepciones counterpart of
    :class:`~._modelo_bindings.RetencionesAggregationSourceResolver` (which counts
    distinct perceptores for M180/M193). The pull and calculate surfaces read this
    one store (one-aggregation-path).
    """

    resolver_id: ClassVar[str] = _WITHHOLDING_SOURCE.value
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_WITHHOLDING_SOURCE,)

    def __init__(self, *, withholding_repository: PercepcionObservationRepository | None = None) -> None:
        self._withholding_repository = withholding_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_declares_withholding_scalar(context.revision):
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        repository = self._withholding_repository or PercepcionObservationRepository()
        try:
            observations = repository.load_observations(str(context.modelo), context.period)
        except STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
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
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            diagnostics=diagnostics,
            provenance=_provenance(observations),
        )


__all__ = ["WithholdingSourceResolver"]
