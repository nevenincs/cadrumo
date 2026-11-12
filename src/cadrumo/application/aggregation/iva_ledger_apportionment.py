"""Resolve IVA ledger bindings with general and differentiated prorrata apportionment."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.decimal.constants import HUNDRED
from ...core.i18n.translatable import Translatable as tr
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.prorrata_register import (
    ProrrataRegisterRegime,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.iva_deduction_catalogue import (
    is_iva_deduction_kind,
    iva_deduction_fact_kinds,
)
from ...domain.calculations.registry.ledger_binding_selector_support import LedgerIvaFact
from ...domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    LedgerIvaProvider,
    resolve_ledger_iva_aggregation_binding_values,
)
from ...domain.calculations.registry.prorrata_register_catalogue import (
    especial_prorrata_register_regime,
    ninguna_prorrata_register_regime,
)
from ...domain.calculations.registry.prorrata_vocabulary import (
    default_input_classification,
    input_classification_tokens,
    resolve_input_classification_definition,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva.prorrata import (
    InputClassification,
    deductible_percentage_for,
)
from .errors import AggregationValidationError, UnacceptedLedgerRegistryValueError
from .iva_ledger import (
    IvaDifferentiatedDeductionContribution,
    IvaLedgerProrrataApportionment,
    IvaLedgerSectorApportionment,
    IvaLedgerSettlementApportionment,
)


def resolve_iva_ledger_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
    *,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
    operation: PinnedAuthorityOperation,
) -> dict[BindingId, Decimal]:
    """Resolve IVA ledger bindings, applying general-prorrata to deducible cuotas only.

    Args:
        revision: The :class:`ModeloRevision` whose IVA ledger bindings are
            resolved.
        observations: Typed :class:`IvaLedgerObservation` rows to aggregate.
        prorrata_apportionment: Optional
            :class:`IvaLedgerProrrataApportionment` applied only to deducible
            cuota bindings.
        operation: Caller-owned pinned authority operation for governed IVA
            binding projections.

    Under ``regime == GENERAL`` the single provisional percentage multiplies
    every deducible cuota binding (LIVA art. 104). Under ``regime == ESPECIAL``
    the deducible cuota is routed per the observation's ``input_classification``
    (LIVA art. 106.Uno: exclusively-deductible 100%, exclusively-non-deductible
    0%, common at the general percentage) by
    :func:`_apply_especial_apportionment`; the general-regime code path is
    unchanged.

    See Also:
        :func:`~domain.calculations.registry.ledger_iva_bindings.resolve_ledger_iva_aggregation_binding_values`
            Registry selector resolver that produces the unapportioned binding
            values before this wrapper applies prorrata.
        :class:`~domain.prorrata_register.register.ProrrataRegisterEntry`
            Source record for the active provisional percentage represented by
            :class:`IvaLedgerProrrataApportionment`.
    """
    observations = tuple(observations)
    binding_values = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    if prorrata_apportionment is None:
        return binding_values
    if prorrata_apportionment.settlement is not None:
        return _apply_settlement_apportionment(
            revision,
            observations,
            binding_values,
            prorrata_apportionment,
            operation=operation,
        )
    if prorrata_apportionment.sector_apportionments:
        # Sectores diferenciados (LIVA arts. 9.1.c / 101): route each input to
        # its sector's percentage; common-use (no sector) at art. 104.Dos.
        return _apply_sector_apportionment(
            revision,
            observations,
            binding_values,
            prorrata_apportionment,
            operation=operation,
        )
    if prorrata_apportionment.regime == especial_prorrata_register_regime(authority=operation):
        return _apply_especial_apportionment(
            revision,
            observations,
            binding_values,
            prorrata_apportionment,
            operation=operation,
        )
    # GENERAL regime — byte-identical to the pre-especial behaviour.
    if prorrata_apportionment.percentage == HUNDRED:
        return binding_values
    multiplier = prorrata_apportionment.percentage / HUNDRED
    deducible_binding_ids = deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    return {
        binding_id: value * multiplier if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _apply_settlement_apportionment(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    binding_values: dict[BindingId, Decimal],
    apportionment: IvaLedgerProrrataApportionment,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[BindingId, Decimal]:
    """Deduct the settlement liquidation's cuotas at the definitive percentages.

    LIVA art. 105.Cuatro: the year's last liquidation applies the definitive
    percentage to its own cuotas; earlier liquidations keep the provisional
    one. A differentiated sector applies its own settled definitive
    (art. 101.Uno) and prorrata especial applies the definitive only to the
    common-use slice (art. 106.Uno regla 3.ª), because the settlement side runs
    the same regime-aware apportionment as every other period. Only deducible
    cuota bindings are recombined -- every other binding keeps its
    unapportioned value from the whole observation set.

    Raises:
        AggregationValidationError: When the settlement's sector percentages
            do not name exactly the apportionment's declared sectors.
    """
    settlement = apportionment.settlement
    if settlement is None:
        return binding_values
    deducible_binding_ids = deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    provisional = apportionment.model_copy(update={"settlement": None})
    definitive = provisional.model_copy(
        update={
            "percentage": settlement.percentage,
            "sector_apportionments": _definitive_sector_apportionments(provisional, settlement),
        }
    )
    in_settlement = tuple(item for item in observations if settlement.period.contains(item.transaction_date))
    earlier = tuple(item for item in observations if not settlement.period.contains(item.transaction_date))
    settled_values = resolve_iva_ledger_binding_values(
        revision, in_settlement, prorrata_apportionment=definitive, operation=operation
    )
    earlier_values = resolve_iva_ledger_binding_values(
        revision, earlier, prorrata_apportionment=provisional, operation=operation
    )
    return {
        binding_id: (
            settled_values.get(binding_id, Decimal("0")) + earlier_values.get(binding_id, Decimal("0"))
            if binding_id in deducible_binding_ids
            else value
        )
        for binding_id, value in binding_values.items()
    }


def _definitive_sector_apportionments(
    provisional: IvaLedgerProrrataApportionment,
    settlement: IvaLedgerSettlementApportionment,
) -> tuple[IvaLedgerSectorApportionment, ...]:
    """Replace each declared sector's provisional percentage with its settled definitive one."""
    definitive_by_sector = {item.sector_id: item.percentage for item in settlement.sector_percentages}
    declared = {sector.sector_id for sector in provisional.sector_apportionments}
    if set(definitive_by_sector) != declared:
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.settlement_apportionment_sector_mismatch"),
            context={
                "period": settlement.period.registry_token,
                "declared_sector_count": len(declared),
                "settled_sector_count": len(definitive_by_sector),
            },
        )
    return tuple(
        sector.model_copy(update={"percentage": definitive_by_sector[sector.sector_id]})
        for sector in provisional.sector_apportionments
    )


def _apply_especial_apportionment(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    binding_values: dict[BindingId, Decimal],
    apportionment: IvaLedgerProrrataApportionment,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[BindingId, Decimal]:
    """Route deducible cuota bindings per LIVA art. 106 prorrata especial.

    The shared per-observation primitive applies the art. 106 classification
    percentages and canonical binding resolution. This wrapper replaces only
    deducible cuota values; every other binding retains its unapportioned value.
    """
    deducible_binding_ids = deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    apportioned = _apportioned_deducible_cuota(
        revision,
        observations,
        percentage=apportionment.percentage,
        regime=apportionment.regime,
        deducible_binding_ids=deducible_binding_ids,
        operation=operation,
    )
    return {
        binding_id: apportioned[binding_id] if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _partition_by_input_classification(
    observations: Sequence[IvaLedgerObservation],
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> dict[InputClassification, list[IvaLedgerObservation]]:
    """Bucket ``observations`` by their art. 106 input classification.

    Only rows bearing deduction authority carry a deducible cuota, so only they
    are partitioned. Art. 106.Uno makes the use of each input the taxpayer's own
    fact; a deducible row with no declared use has no lawful percentage, so it
    is refused exactly as the sectorised path refuses it, never routed to the
    common slice. Shared by the whole-entity especial apportionment and the
    per-partition primitive so both partition identically.

    Raises:
        AggregationValidationError: When a deducible observation declares no
            input classification.
        UnacceptedLedgerRegistryValueError: When an observation declares a
            classification the pinned vocabulary does not list. No deduction
            percentage exists for it, so it is refused rather than routed.
    """
    partitions: dict[InputClassification, list[IvaLedgerObservation]] = {
        classification: []
        for classification in input_classification_tokens(effective_date=effective_date, authority=operation)
    }
    for observation in observations:
        if observation.deduction_fact_kind is None:
            continue
        classification = observation.input_classification
        if classification is None:
            raise AggregationValidationError(
                tr("aggregation.iva_ledger.errors.especial_missing_input_classification"),
                context={"ledger_id": observation.ledger_id},
            )
        partition = partitions.get(classification)
        if partition is None:
            raise UnacceptedLedgerRegistryValueError(
                field="input_classification",
                value=str(classification),
                transaction_id=observation.ledger_id,
                effective_date=effective_date,
            )
        partition.append(observation)
    return partitions


@dataclass(frozen=True, slots=True)
class IvaDeducibleCuotaPartition:
    """One slice of deducible cuotas sharing a single deduction percentage.

    ``sector_id`` is the differentiated sector (``None`` for a whole-entity
    register, or for the cross-sector common-use inputs of a sectorized one).
    ``input_classification`` is the art. 106 slice under prorrata especial and
    ``None`` under general. ``deduction_percentage`` is the percentage the
    apportionment applies to the slice, and ``regularisable`` says whether that
    percentage is the art. 104 percentage whose art. 105 procedure the annual
    regularisation corrects: every general slice and the especial common slice
    (LIVA art. 106.Uno regla 3.ª); the fixed-percentage especial slices are
    final. ``gross_by_binding`` holds the slice's unapportioned deducible cuota
    per binding.
    """

    sector_id: str | None
    regime: ProrrataRegisterRegime
    input_classification: InputClassification | None
    deduction_percentage: Decimal
    regularisable: bool
    gross_by_binding: Mapping[BindingId, Decimal]

    def deduction_by_binding(self) -> dict[BindingId, Decimal]:
        """Return the slice's apportioned (unrounded) deducible cuota per binding."""
        multiplier = self.deduction_percentage / HUNDRED
        return {binding_id: value * multiplier for binding_id, value in self.gross_by_binding.items()}


def _regime_partitions(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    *,
    sector_id: str | None,
    percentage: Decimal,
    regime: ProrrataRegisterRegime,
    deducible_binding_ids: frozenset[BindingId],
    operation: PinnedAuthorityOperation,
) -> tuple[IvaDeducibleCuotaPartition, ...]:
    """Split one observation set into its regime's deduction slices.

    ``GENERAL`` is one slice at ``percentage`` (LIVA art. 104); ``ESPECIAL``
    is one slice per declared art. 106 input classification, with
    ``percentage`` as the common (regla 3.ª) percentage. Every slice resolves
    through the same canonical registry resolver.
    """
    if regime != especial_prorrata_register_regime(authority=operation):
        values = resolve_ledger_iva_aggregation_binding_values(revision, observations)
        return (
            IvaDeducibleCuotaPartition(
                sector_id=sector_id,
                regime=regime,
                input_classification=None,
                deduction_percentage=percentage,
                regularisable=True,
                gross_by_binding={
                    binding_id: values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids
                },
            ),
        )
    partitions: list[IvaDeducibleCuotaPartition] = []
    for classification, partition_observations in _partition_by_input_classification(
        observations, effective_date=revision.valid_from, operation=operation
    ).items():
        if not partition_observations:
            continue
        values = resolve_ledger_iva_aggregation_binding_values(revision, partition_observations)
        partitions.append(
            IvaDeducibleCuotaPartition(
                sector_id=sector_id,
                regime=regime,
                input_classification=classification,
                deduction_percentage=deductible_percentage_for(classification, percentage),
                regularisable=resolve_input_classification_definition(
                    classification, effective_date=revision.valid_from, authority=operation
                ).uses_general_percentage,
                gross_by_binding={
                    binding_id: values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids
                },
            )
        )
    return tuple(partitions)


def _apportioned_deducible_cuota(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    *,
    percentage: Decimal,
    regime: ProrrataRegisterRegime,
    deducible_binding_ids: frozenset[BindingId],
    operation: PinnedAuthorityOperation,
) -> dict[BindingId, Decimal]:
    """Return only the deducible-cuota binding contributions for one observation set.

    Sums the regime's deduction slices (:func:`_regime_partitions`), so the
    apportionment and the annual regularisation read one partition of the same
    cuotas. This is the per-partition primitive the sectores-diferenciados
    routing composes over each sector.
    """
    result: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    for partition in _regime_partitions(
        revision,
        observations,
        sector_id=None,
        percentage=percentage,
        regime=regime,
        deducible_binding_ids=deducible_binding_ids,
        operation=operation,
    ):
        if partition.deduction_percentage == 0:
            continue
        for binding_id, value in partition.deduction_by_binding().items():
            result[binding_id] += value
    return result


def resolve_iva_deducible_cuota_partitions(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
    *,
    apportionment: IvaLedgerProrrataApportionment,
    operation: PinnedAuthorityOperation,
) -> tuple[IvaDeducibleCuotaPartition, ...]:
    """Partition deducible cuotas exactly as the apportionment deducts them.

    A whole-entity register yields its regime's slices; a sectorized register
    (LIVA art. 101.Uno) yields each declared sector's slices at that sector's
    percentage and the cross-sector common-use slice at the whole-entity
    percentage, refusing missing or unknown sector identity as the
    apportionment does. The apportionment's own percentages are used; a
    settlement percentage, which applies only inside the settlement
    liquidation, is ignored here.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    rows = tuple(observations)
    deducible_binding_ids = deducible_cuota_binding_ids(revision)
    if not apportionment.sector_apportionments:
        return _regime_partitions(
            revision,
            rows,
            sector_id=None,
            percentage=apportionment.percentage,
            regime=apportionment.regime,
            deducible_binding_ids=deducible_binding_ids,
            operation=operation,
        )
    by_sector, sector_rows = _sectorized_deduction_partitions(apportionment, rows, operation=operation)
    partitions: list[IvaDeducibleCuotaPartition] = []
    for sector_key, partition_observations in sector_rows.items():
        percentage, regime = _partition_apportionment(apportionment, by_sector, sector_key)
        partitions.extend(
            _regime_partitions(
                revision,
                partition_observations,
                sector_id=sector_key,
                percentage=percentage,
                regime=regime,
                deducible_binding_ids=deducible_binding_ids,
                operation=operation,
            )
        )
    return tuple(partitions)


def _apply_sector_apportionment(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    binding_values: dict[BindingId, Decimal],
    apportionment: IvaLedgerProrrataApportionment,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[BindingId, Decimal]:
    """Route deducible cuota bindings per sector (LIVA arts. 9.1.c / 101).

    Partitions input ``observations`` by their exact ``prorrata_sector_id`` and recomputes each
    deducible cuota binding as the sum, over the partitions, of that sector's
    :func:`_apportioned_deducible_cuota` contribution (each sector applies its
    own percentage and regime). Missing or unknown sector identity refuses;
    the sole no-sector case is an explicitly classified cross-sector COMMON
    input, routed through the declared whole-entity common percentage.
    Non-deducible bindings keep their
    unapportioned aggregate. Resolution runs through the SAME canonical registry
    resolver, so the sectored path is one more consumer of the single
    aggregation path.
    """
    deducible_binding_ids = deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    by_sector, partitions = _sectorized_deduction_partitions(apportionment, observations, operation=operation)
    apportioned: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    for sector_key, partition_observations in partitions.items():
        percentage, regime = _partition_apportionment(apportionment, by_sector, sector_key)
        partition_deducible = _apportioned_deducible_cuota(
            revision,
            partition_observations,
            percentage=percentage,
            regime=regime,
            deducible_binding_ids=deducible_binding_ids,
            operation=operation,
        )
        for binding_id in deducible_binding_ids:
            apportioned[binding_id] += partition_deducible[binding_id]
    return {
        binding_id: apportioned[binding_id] if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _sectorized_deduction_partitions(
    apportionment: IvaLedgerProrrataApportionment,
    observations: Sequence[IvaLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[
    dict[str, IvaLedgerSectorApportionment],
    dict[str | None, list[IvaLedgerObservation]],
]:
    by_sector = _sector_apportionments_by_id(apportionment)
    partitions: dict[str | None, list[IvaLedgerObservation]] = {}
    for observation in observations:
        if observation.deduction_fact_kind is None:
            continue
        _append_sectorized_deduction_observation(partitions, by_sector, observation, operation=operation)
    return by_sector, partitions


def _sector_apportionments_by_id(
    apportionment: IvaLedgerProrrataApportionment,
) -> dict[str, IvaLedgerSectorApportionment]:
    by_sector = {sector.sector_id: sector for sector in apportionment.sector_apportionments}
    if len(by_sector) != len(apportionment.sector_apportionments):
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.sectorized_apportionment_duplicate_sectors"),
            context={"declared_sector_count": len(apportionment.sector_apportionments)},
        )
    return by_sector


def _append_sectorized_deduction_observation(
    partitions: dict[str | None, list[IvaLedgerObservation]],
    sectors: dict[str, IvaLedgerSectorApportionment],
    observation: IvaLedgerObservation,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    sector_key = observation.prorrata_sector_id
    if sector_key is None:
        _append_common_sector_observation(partitions, observation, operation=operation)
        return
    sector = _active_sector_apportionment(sectors, sector_key, operation=operation)
    _require_sector_input_classification(sector, observation, operation=operation)
    partitions.setdefault(sector_key, []).append(observation)


def _append_common_sector_observation(
    partitions: dict[str | None, list[IvaLedgerObservation]],
    observation: IvaLedgerObservation,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    if observation.input_classification != default_input_classification(authority=operation):
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.sectorized_input_missing_sector_identity"),
            context={"ledger_id": observation.ledger_id},
        )
    partitions.setdefault(None, []).append(observation)


def _active_sector_apportionment(
    sectors: dict[str, IvaLedgerSectorApportionment],
    sector_key: str,
    *,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerSectorApportionment:
    sector = sectors.get(sector_key)
    if sector is None:
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.sectorized_input_unknown_sector"), context={"sector_id": sector_key}
        )
    if sector.regime == ninguna_prorrata_register_regime(authority=operation):
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.sectorized_input_inactive_sector"), context={"sector_id": sector_key}
        )
    return sector


def _require_sector_input_classification(
    sector: IvaLedgerSectorApportionment,
    observation: IvaLedgerObservation,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    if (
        sector.regime == especial_prorrata_register_regime(authority=operation)
        and observation.input_classification is None
    ):
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.sectorized_especial_missing_input_classification"),
            context={"sector_id": sector.sector_id, "ledger_id": observation.ledger_id},
        )


def _partition_apportionment(
    apportionment: IvaLedgerProrrataApportionment,
    sectors: dict[str, IvaLedgerSectorApportionment],
    sector_key: str | None,
) -> tuple[Decimal, ProrrataRegisterRegime]:
    if sector_key is None:
        return apportionment.percentage, apportionment.regime
    sector = sectors[sector_key]
    return sector.percentage, sector.regime


def resolve_iva_differentiated_deduction_contributions(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
    *,
    apportionment: IvaLedgerProrrataApportionment,
    operation: PinnedAuthorityOperation,
) -> tuple[IvaDifferentiatedDeductionContribution, ...]:
    """Expose the canonical sector apportionment as immutable per-kind outputs.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    if not apportionment.sector_apportionments:
        return ()
    rows = tuple(observations)
    _validate_differentiated_observation_identities(rows, operation=operation)
    by_sector = _validated_differentiated_sectors(apportionment, rows, operation=operation)
    deducible_binding_ids = deducible_cuota_binding_ids(revision)
    return tuple(
        _differentiated_sector_contribution(
            revision,
            rows,
            sector_id,
            sector,
            kind,
            deducible_binding_ids,
            operation=operation,
        )
        for sector_id, sector in by_sector.items()
        for kind in iva_deduction_fact_kinds(effective_date=revision.valid_from, authority=operation)
    )


def _validate_differentiated_observation_identities(
    rows: tuple[IvaLedgerObservation, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    ledger_ids = tuple(row.ledger_id for row in rows)
    if len(ledger_ids) != len(set(ledger_ids)):
        raise ValueError("differentiated deduction observations contain duplicate ledger identity")
    if any(
        row.deduction_fact_kind is not None
        and is_iva_deduction_kind(row.deduction_fact_kind, "kind.owner_only", authority=operation)
        for row in rows
    ):
        raise ValueError("investment-goods regularisation is owned only by the bienes-inversion register")


def _validated_differentiated_sectors(
    apportionment: IvaLedgerProrrataApportionment,
    rows: tuple[IvaLedgerObservation, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> dict[str, IvaLedgerSectorApportionment]:
    by_sector = {item.sector_id: item for item in apportionment.sector_apportionments}
    if len(by_sector) != len(apportionment.sector_apportionments):
        raise ValueError("differentiated deduction apportionment carries duplicate sectors")
    unknown = sorted({row.prorrata_sector_id for row in rows if row.prorrata_sector_id not in by_sector}, key=str)
    if unknown:
        raise ValueError(f"differentiated deduction observations have missing or unknown sectors: {unknown!r}")
    for row in rows:
        _validate_differentiated_sector_row(by_sector, row, operation=operation)
    return by_sector


def _validate_differentiated_sector_row(
    by_sector: dict[str, IvaLedgerSectorApportionment],
    row: IvaLedgerObservation,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    sector_id = row.prorrata_sector_id
    if sector_id is None:
        raise ValueError("differentiated deduction observation is missing explicit sector identity")
    sector = by_sector[sector_id]
    if sector.regime == ninguna_prorrata_register_regime(authority=operation):
        raise ValueError(f"differentiated deduction sector {sector.sector_id!r} is inactive")
    if sector.regime == especial_prorrata_register_regime(authority=operation) and row.input_classification is None:
        raise ValueError("common-use classification must be explicit under differentiated prorrata especial")


def _differentiated_sector_contribution(
    revision: ModeloRevision,
    rows: tuple[IvaLedgerObservation, ...],
    sector_id: str,
    sector: IvaLedgerSectorApportionment,
    kind: IvaDeductionFactKind,
    deducible_binding_ids: frozenset[str],
    *,
    operation: PinnedAuthorityOperation,
) -> IvaDifferentiatedDeductionContribution:
    selected = tuple(row for row in rows if row.prorrata_sector_id == sector_id and row.deduction_fact_kind == kind)
    apportioned = _apportioned_deducible_cuota(
        revision,
        selected,
        percentage=sector.percentage,
        regime=sector.regime,
        deducible_binding_ids=deducible_binding_ids,
        operation=operation,
    )
    return IvaDifferentiatedDeductionContribution(
        sector_id=sector_id,
        deduction_fact_kind=kind,
        source_ledger_ids=tuple(row.ledger_id for row in selected),
        base_amount=sum((row.base_amount for row in selected), Decimal("0")),
        deducible_iva_amount=sum(apportioned.values(), Decimal("0")),
    )


def deducible_cuota_binding_ids(revision: ModeloRevision) -> frozenset[BindingId]:
    """Find bound deductible IVA amount identifiers in the revision.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    ledger_iva_amount_bindings = {
        binding.id
        for binding in revision.bindings
        if isinstance(binding.provider, LedgerIvaProvider) and binding.provider.fact == LedgerIvaFact.IVA_AMOUNT_SUM
    }
    binding_ids: set[BindingId] = set()
    for casilla in revision.casillas:
        if "deducible" not in casilla.section:
            continue
        for binding_id in bound_casilla_binding_ids(casilla):
            if binding_id in ledger_iva_amount_bindings:
                binding_ids.add(binding_id)
    return frozenset(binding_ids)
