"""Modelo 390 IVA compensation annual partition source resolver.

The resolver reads a :class:`~domain.calculations.registry.RegistrySnapshot`
for the annual Modelo 390 revision, inspects its
:class:`~domain.calculations.registry.ModeloRevision` bindings owned by
:attr:`~core.BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION`, and
derives the two annual compensation partition amounts from filed Modelo 303
:class:`~application.calculations.ObservationEnvelopePayload` records.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import ClassVar, Final

from ...adapters.persistence.storage import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    CasillaId,
    IvaCompensationStateProvenance,
    Modelo,
    Period,
)
from ...core.logging import get_logger
from ...core.time import now
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    iva_compensation_annual_partition_requirement,
)
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.temporal import select_revision
from ...domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from ...domain.iva_compensation import (
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    derive_iva_compensation_year_end_carry_partition,
)
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._iva_compensation_casillas import (
    M303_COMPENSACION_APLICADA_CASILLA,
    M303_DISPONIBLE_CASILLA,
    M303_GENERADA_CASILLA,
    M303_POSTERIOR_CASILLA,
)
from ._m303_carry_ingress import (
    M303CarryIngressError,
    validate_normalized_m303_carry_observation_envelope,
)
from ._observations_repository import CalculationObservationRepository, ObservationEnvelopePayload
from ._revision_carry_gate import revision_carry_outcome

_log = get_logger(__name__)

_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)
_SOURCE_KIND: Final = BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
_ZERO: Final = Decimal("0")
_303_GENERADA_ID: Final[CasillaId] = M303_GENERADA_CASILLA
_303_APLICADA_ID: Final[CasillaId] = M303_COMPENSACION_APLICADA_CASILLA
_303_DISPONIBLE_ID: Final[CasillaId] = M303_DISPONIBLE_CASILLA
_303_POSTERIOR_ID: Final[CasillaId] = M303_POSTERIOR_CASILLA


def _observed_value(values: Mapping[CasillaId, Decimal], casilla_id: CasillaId) -> Decimal | None:
    return values.get(casilla_id)


def _validate_303_observation_casilla_ids(observation: RegistryModeloObservation) -> None:
    from ...core.resources import bundled_path
    from ...domain.calculations.registry.loader import load_registry_tree

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(candidate for candidate in modelos if candidate.id == observation.modelo)
    revision = select_revision(
        modelo,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    invalid = undeclared_casilla_ids(revision, observation.casilla_values)
    if invalid:
        raise RegistryValidationError(
            translated_message=(
                "application.calculations.iva_compensation.errors.annual_partition_casilla_ids_noncanonical"
            ),
            context={
                "modelo": observation.modelo,
                "revision_id": revision.id,
                "casilla_ids": invalid,
            },
        )


def _period_state_from_303_envelope(envelope: ObservationEnvelopePayload) -> IvaCompensationPeriodState:
    """Build one FIFO state from a validated filed Modelo 303 envelope."""
    validated = validate_normalized_m303_carry_observation_envelope(envelope)
    observation = validated.observation
    _validate_303_observation_casilla_ids(observation)
    values = observation.casilla_values
    generated = _observed_value(values, _303_GENERADA_ID)
    if generated is None:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.generated_compensation_amount_missing",
            context={"casilla_id": _303_GENERADA_ID},
        )
    applied = _observed_value(values, _303_APLICADA_ID) or _ZERO
    posterior = _observed_value(values, _303_POSTERIOR_ID)
    available = _observed_value(values, _303_DISPONIBLE_ID)
    if available is None:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.available_compensation_amount_missing",
            context={"casilla_id": _303_DISPONIBLE_ID},
        )
    period = Period.from_year_and_code(observation.filing_year, observation.period)
    return IvaCompensationPeriodState(
        # A casilla observation records no taxpayer, and these states are
        # computational scaffold for the FIFO partition below - never
        # persisted, never shown. Declaring no subject is honest; a synthetic
        # label in the identity field reads downstream as if it named one.
        taxpayer_nif=None,
        provenance=IvaCompensationStateProvenance.CASILLA_RECONSTRUCTION,
        filing_year=observation.filing_year,
        period=period,
        presented_at=now(),
        prior_pending_amount=None,
        applied_amount=applied,
        pending_for_later_amount=posterior,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=generated,
        available_end_amount=available,
        source_observation_key=f"303:{observation.filing_year}:{observation.period}:iva-annual-partition",
    )


def resolve_iva_compensation_annual_partition_binding_values(
    revision: ModeloRevision,
    envelopes: tuple[ObservationEnvelopePayload, ...],
    *,
    filing_year: int,
) -> dict[BindingId, Decimal]:
    """Resolve Modelo 390 annual compensation bindings from filed M303 states.

    Args:
        revision: The annual Modelo 390 :class:`~domain.calculations.registry.ModeloRevision`
            whose partition bindings declare the target output slots.
        envelopes: Filed, already-normalized Modelo 303
            :class:`~application.calculations.ObservationEnvelopePayload`
            records used to reconstruct the compensation FIFO state.
        filing_year: Annual filing year used to select same-year Modelo 303
            observations.
    """
    requirement = iva_compensation_annual_partition_requirement(revision)
    if requirement is None:
        return {}
    states = tuple(
        _period_state_from_303_envelope(envelope)
        for envelope in envelopes
        if envelope.observation.modelo == Modelo.M303.value and envelope.observation.filing_year == filing_year
    )
    if not states:
        return {}
    report = build_iva_compensation_carry_forward_report(states, as_of_year=filing_year)
    partition = derive_iva_compensation_year_end_carry_partition(report, states, filing_year=filing_year)
    values: dict[BindingId, Decimal] = {}
    last_period_binding = requirement.last_period_amount_binding_id
    if last_period_binding is not None:
        values[last_period_binding] = partition.last_period_amount
    generated_not_in_last_binding = requirement.generated_not_in_last_amount_binding_id
    if generated_not_in_last_binding is not None:
        values[generated_not_in_last_binding] = partition.generated_not_in_last_amount
    return values


def _load_303_observations_for_partition(
    revision: ModeloRevision,
    *,
    filing_year: int,
    repository: CalculationObservationRepository,
) -> tuple[ObservationEnvelopePayload, ...]:
    requirement = iva_compensation_annual_partition_requirement(revision)
    if requirement is None:
        return ()
    envelopes: list[ObservationEnvelopePayload] = []
    for period_code in requirement.source_periods:
        payload = repository.load_observation(
            Modelo.M303.value,
            Period.from_year_and_code(filing_year, period_code),
        )
        if payload is None:
            continue
        observation = payload.observation
        refused = revision_carry_outcome(
            payload.stamped_revision_id,
            source_modelo=observation.modelo,
            source_filing_year=observation.filing_year,
            source_period=observation.period,
        ).refused
        if refused:
            _log.debug(
                "dropping unreconfirmable m303 observation from iva annual partition stamped_revision_id=%s period=%s",
                payload.stamped_revision_id,
                observation.period,
            )
            continue
        # Revalidate after decrypting persisted evidence. Legacy, incomplete, or
        # internally contradictory envelopes are readable records but never FIFO
        # input; the period state repeats this check before partitioning.
        validate_normalized_m303_carry_observation_envelope(payload)
        envelopes.append(payload)
    return tuple(envelopes)


def _unresolved_diagnostics(
    *,
    binding_ids: tuple[BindingId, ...],
    source_periods: tuple[str, ...],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    periods = ",".join(source_periods) if source_periods else "(none)"
    return tuple(
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_SOURCE_KIND.value,
            resolver_id=resolver_id,
            binding_id=binding_id,
            message=(
                f"binding {binding_id!r} requires filed Modelo 303 compensation states "
                f"for periods {periods}; the source filing history is missing or incomplete"
            ),
        )
        for binding_id in binding_ids
    )


class IvaCompensationAnnualPartitionSourceResolver:
    """Resolve Modelo 390 boxes 97 / 662 from the IVA compensation FIFO partition."""

    resolver_id: ClassVar[str] = _SOURCE_KIND.value
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE_KIND,)

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
    ) -> None:
        self._repository = repository
        self._registry_snapshot = registry_snapshot

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        revision = self._registry_snapshot.revision if self._registry_snapshot is not None else None
        if revision is None:
            from ...core.resources import bundled_path
            from ...domain.calculations.registry.loader import load_registry_tree

            modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
            modelo = next(candidate for candidate in modelos if candidate.id == context.modelo)
            revision = select_revision(
                modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        requirement = iva_compensation_annual_partition_requirement(revision)
        if requirement is None:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        repo = self._repository if self._repository is not None else CalculationObservationRepository()
        try:
            envelopes = _load_303_observations_for_partition(
                revision,
                filing_year=context.filing_year,
                repository=repo,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        binding_values = resolve_iva_compensation_annual_partition_binding_values(
            revision,
            envelopes,
            filing_year=context.filing_year,
        )
        unresolved = tuple(binding_id for binding_id in requirement.binding_ids if binding_id not in binding_values)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            unresolved_binding_ids=unresolved,
            diagnostics=_unresolved_diagnostics(
                binding_ids=unresolved,
                source_periods=requirement.source_periods,
                resolver_id=self.resolver_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=_SOURCE_KIND,
                    contributor_source_kind=_SOURCE_KIND.value,
                    contributor_binding_source=_SOURCE_KIND,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=(
                        "303:"
                        f"{envelope.observation.filing_year}:{envelope.observation.period}:"
                        "iva-compensation-annual-partition"
                    ),
                    parent_source_ref=None,
                    source_modelo=requirement.source_modelo,
                    source_filing_year=envelope.observation.filing_year,
                    source_periods=requirement.source_periods,
                    source_casilla_ids=requirement.source_casilla_ids,
                    legal_refs=requirement.legal_refs,
                    source_refs=requirement.source_refs,
                    dependency_treatment=requirement.dependency_treatment,
                )
                for envelope in envelopes
            ),
        )


__all__ = [
    "IvaCompensationAnnualPartitionSourceResolver",
    "resolve_iva_compensation_annual_partition_binding_values",
]
