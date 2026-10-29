"""Resolve IVA ledger bindings with general and differentiated prorrata apportionment."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from ...core.decimal.constants import HUNDRED
from ...core.i18n.translatable import Translatable as tr
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.prorrata_register import (
    ProrrataRegisterRegime,
)
from ...core.time.clock import today_madrid
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
    operation: PinnedAuthorityOperation,
) -> dict[InputClassification, list[IvaLedgerObservation]]:
    """Bucket ``observations`` by their art. 106 input classification.

    An unclassified observation defaults to the registry-declared mixed-use token
    (the mixed-use default). Shared by the general especial-regime
    apportionment and the per-partition primitive so both partition
    identically.

    Raises:
        UnacceptedLedgerRegistryValueError: When an observation declares a
            classification the pinned vocabulary does not list. No deduction
            percentage exists for it, so it is refused rather than routed.
    """
    effective_date = today_madrid()
    partitions: dict[InputClassification, list[IvaLedgerObservation]] = {
        classification: []
        for classification in input_classification_tokens(effective_date=effective_date, authority=operation)
    }
    for observation in observations:
        classification = observation.input_classification or default_input_classification(
            effective_date=effective_date,
            authority=operation,
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

    Applies the observation set's regime at ``percentage``: ``GENERAL`` multiplies
    every deducible cuota by ``percentage`` (LIVA art. 104); ``ESPECIAL`` routes
    each deducible cuota per the observation's ``input_classification`` (LIVA
    art. 106.Uno reglas 100%/0%/general), with ``percentage`` as the common
    (regla 3.ª) percentage. Both branches resolve through the SAME canonical
    registry resolver, so one aggregation path drives every regime. This is the
    per-partition primitive the sectores-diferenciados routing composes over each
    sector.
    """
    result: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    if regime == especial_prorrata_register_regime(authority=operation):
        partitions = _partition_by_input_classification(observations, operation=operation)
        for classification, partition_observations in partitions.items():
            if not partition_observations:
                continue
            multiplier = deductible_percentage_for(classification, percentage) / HUNDRED
            if multiplier == 0:
                continue
            partition_values = resolve_ledger_iva_aggregation_binding_values(revision, partition_observations)
            for binding_id in deducible_binding_ids:
                result[binding_id] += partition_values.get(binding_id, Decimal("0")) * multiplier
        return result
    # GENERAL regime: a single multiplier over the whole observation set.
    multiplier = percentage / HUNDRED
    partition_values = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    for binding_id in deducible_binding_ids:
        result[binding_id] = partition_values.get(binding_id, Decimal("0")) * multiplier
    return result


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
