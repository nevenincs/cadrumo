"""Modelo 390 IVA compensation annual partition source resolver.

The resolver reads a :class:`~aeat.domain.calculations.registry.RegistrySnapshot`
for the annual Modelo 390 revision, inspects its
:class:`~aeat.domain.calculations.registry.ModeloRevision` bindings owned by
:attr:`~aeat.core.BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION`, and
derives the two annual compensation partition amounts from filed Modelo 303
:class:`~aeat.domain.calculations.registry.RegistryModeloObservation` rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core import BindingSourceKind, Modelo, Period
from ...core.logging import get_logger
from ...core.time import now
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    ModeloRevision,
    RegistryModeloObservation,
    RegistrySnapshot,
    RegistryValidationError,
    undeclared_casilla_ids,
    validated_casilla_id,
)
from ...domain.iva_compensation import (
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    derive_iva_compensation_year_end_carry_partition,
)
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._observations_repository import CalculationObservationRepository
from ._revision_carry_gate import revision_carry_outcome

_log = get_logger(__name__)

_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)
_SOURCE_KIND: Final = BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
_ZERO: Final = Decimal("0")
_LAST_PERIOD_OUTPUT: Final = "last_period_amount"
_GENERATED_NOT_IN_LAST_OUTPUT: Final = "generated_not_in_last_amount"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="iva annual partition casilla constant")
    except ValueError as exc:
        raise RuntimeError(f"iva annual partition casilla constant {value!r} is not a CasillaId") from exc


_303_GENERADA_ID: Final[CasillaId] = _casilla_id("iva.compensacion-generada-periodo")
_303_APLICADA_ID: Final[CasillaId] = _casilla_id("iva.compensacion-aplicada-periodo")
_303_DISPONIBLE_ID: Final[CasillaId] = _casilla_id("iva.compensacion-disponible-fin-periodo")
_303_POSTERIOR_ID: Final[CasillaId] = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")


def _partition_selector(binding: object) -> object:
    return getattr(binding, "selector", None)


def _partition_bindings_by_output(revision: ModeloRevision) -> dict[str, BindingId]:
    bindings: dict[str, BindingId] = {}
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        output = getattr(_partition_selector(binding), "partition_output", None)
        if isinstance(output, str):
            bindings[output] = binding.id
    return bindings


def _partition_source_periods(revision: ModeloRevision) -> tuple[str, ...]:
    periods: list[str] = []
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        for period in getattr(_partition_selector(binding), "source_periods", ()):
            if period not in periods:
                periods.append(period)
    return tuple(periods)


def _observed_value(values: Mapping[CasillaId, Decimal], casilla_id: CasillaId) -> Decimal | None:
    return values.get(casilla_id)


def _validate_303_observation_casilla_ids(observation: RegistryModeloObservation) -> None:
    from ...core.resources import resources

    snapshot = resources().modelos.authority.snapshot(
        observation.modelo,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    invalid = undeclared_casilla_ids(snapshot.revision, observation.casilla_values)
    if invalid:
        raise RegistryValidationError(
            "Modelo 303 compensation observations must use canonical casilla.id values declared by "
            f"revision {snapshot.revision.id}; got noncanonical references {invalid!r}",
        )


def _period_state_from_303_observation(observation: RegistryModeloObservation) -> IvaCompensationPeriodState:
    """Reconstruct one filed Modelo 303 period's FIFO compensation state."""
    _validate_303_observation_casilla_ids(observation)
    values = observation.casilla_values
    generated = _observed_value(values, _303_GENERADA_ID) or _ZERO
    applied = _observed_value(values, _303_APLICADA_ID) or _ZERO
    posterior = _observed_value(values, _303_POSTERIOR_ID)
    available = _observed_value(values, _303_DISPONIBLE_ID)
    if available is None:
        available = (posterior or _ZERO) + generated
    period = Period.from_year_and_code(observation.filing_year, observation.period)
    return IvaCompensationPeriodState(
        taxpayer_nif="iva-annual-partition",
        filing_year=observation.filing_year,
        period=period,
        expediente_id=f"obs-{observation.filing_year}-{observation.period}",
        status="filed",
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
    observations: tuple[RegistryModeloObservation, ...],
    *,
    filing_year: int,
) -> dict[BindingId, Decimal]:
    """Resolve Modelo 390 annual compensation bindings from filed M303 states.

    Args:
        revision: The annual Modelo 390 :class:`~aeat.domain.calculations.registry.ModeloRevision`
            whose partition bindings declare the target output slots.
        observations: Filed Modelo 303
            :class:`~aeat.domain.calculations.registry.RegistryModeloObservation`
            rows used to reconstruct the compensation FIFO state.
        filing_year: Annual filing year used to select same-year Modelo 303
            observations.
    """
    binding_by_output = _partition_bindings_by_output(revision)
    if not binding_by_output:
        return {}
    states = tuple(
        _period_state_from_303_observation(observation)
        for observation in observations
        if observation.modelo == Modelo.M303.value and observation.filing_year == filing_year
    )
    if not states:
        return {}
    report = build_iva_compensation_carry_forward_report(states, as_of_year=filing_year)
    partition = derive_iva_compensation_year_end_carry_partition(report, states, filing_year=filing_year)
    values: dict[BindingId, Decimal] = {}
    last_period_binding = binding_by_output.get(_LAST_PERIOD_OUTPUT)
    if last_period_binding is not None:
        values[last_period_binding] = partition.last_period_amount
    generated_not_in_last_binding = binding_by_output.get(_GENERATED_NOT_IN_LAST_OUTPUT)
    if generated_not_in_last_binding is not None:
        values[generated_not_in_last_binding] = partition.generated_not_in_last_amount
    return values


def _load_303_observations_for_partition(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
) -> tuple[RegistryModeloObservation, ...]:
    observations: list[RegistryModeloObservation] = []
    for period_code in _partition_source_periods(snapshot.revision):
        payload = repository.load_observation(
            Modelo.M303.value,
            Period.from_year_and_code(snapshot.filing_year, period_code),
        )
        if payload is None:
            continue
        observation = payload.observation
        diverges, _advisory = revision_carry_outcome(
            payload.stamped_revision_id,
            source_modelo=observation.modelo,
            source_filing_year=observation.filing_year,
            source_period=observation.period,
        )
        if diverges:
            _log.debug(
                "dropping stale m303 observation from iva annual partition stamped_revision_id=%s period=%s",
                payload.stamped_revision_id,
                observation.period,
            )
            continue
        observations.append(observation)
    return tuple(observations)


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

    resolver_id = _SOURCE_KIND.value
    owned_sources: tuple[BindingSourceKind, ...] = (_SOURCE_KIND,)

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
    ) -> None:
        self._repository = repository
        self._registry_snapshot = registry_snapshot

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        declared_binding_ids = tuple(
            sorted(binding.id for binding in snapshot.revision.bindings if binding.source == _SOURCE_KIND),
        )
        if not declared_binding_ids:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        repo = self._repository if self._repository is not None else CalculationObservationRepository()
        try:
            observations = _load_303_observations_for_partition(snapshot, repository=repo)
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        binding_values = resolve_iva_compensation_annual_partition_binding_values(
            snapshot.revision,
            observations,
            filing_year=snapshot.filing_year,
        )
        unresolved = tuple(binding_id for binding_id in declared_binding_ids if binding_id not in binding_values)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            unresolved_binding_ids=unresolved,
            diagnostics=_unresolved_diagnostics(
                binding_ids=unresolved,
                source_periods=_partition_source_periods(snapshot.revision),
                resolver_id=self.resolver_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind=_SOURCE_KIND.value,
                    source_ref=f"303:{observation.filing_year}:{observation.period}:iva-compensation-annual-partition",
                )
                for observation in observations
            ),
        )


__all__ = [
    "IvaCompensationAnnualPartitionSourceResolver",
    "resolve_iva_compensation_annual_partition_binding_values",
]
