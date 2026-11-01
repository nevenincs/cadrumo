"""Earlier-liquidation totals the annual prorrata regularisation re-derives (LIVA arts. 101, 105, 106).

The settlement liquidation's regularisation box reaches only the earlier
liquidations of the year. For each of them this module re-derives the gross
deducible cuotas from the IVA ledger, partitioned exactly as the in-year
apportionment deducted them, and reads the practised deduction from the filed
observation. A filed liquidation that the ledger cannot reproduce, that holds
no derivable gross base, or that is absent or refused stays a refusal naming
the cause; nothing defaults to zero.

See Also:
    :mod:`~application.calculations.prorrata_regularizacion`
        Source resolver that combines these totals with the definitive
        percentages.
    :func:`~application.aggregation.iva_ledger_apportionment.resolve_iva_deducible_cuota_partitions`
        Ledger partitions per differentiated sector and prorrata especial slice.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.i18n.render import tr
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...domain.bienes_inversion.register import BienesInversionIvaRegister
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.calculations.registry.prorrata_register_catalogue import (
    carried_prior_definitiva_prorrata_provenance,
    general_prorrata_register_regime,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import ProrrataRegister
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.errors import AggregationValidationError, UnacceptedLedgerRegistryValueError
from ..aggregation.iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerProrrataApportionment,
    aggregate_iva_ledger_observations_from_repositories,
)
from ..aggregation.iva_ledger_apportionment import (
    IvaDeducibleCuotaPartition,
    deducible_cuota_binding_ids,
    resolve_iva_deducible_cuota_partitions,
)
from ..aggregation.modelo_bindings import aggregation_period_for_modelo
from ..aggregation.source_mesh import CalculationSourceContext
from .observations_repository import CalculationObservationRepositoryProtocol, ObservationEnvelopePayload
from .revision_carry_gate import revision_carry_outcome


def format_period_list(periods: Iterable[Period]) -> str:
    """Render liquidation periods as their comma-separated registry tokens."""
    return ", ".join(period.registry_token for period in periods)


@dataclass(frozen=True, slots=True)
class RegularisedPeriodTotals:
    """Gross cuotas and practised deductions of the liquidations the box regularises.

    ``gross_by_partition`` holds, per differentiated sector (``None`` for the
    whole entity or for cross-sector common use), the gross cuotas the art. 105
    procedure reaches: every general slice and the prorrata especial common
    slice (LIVA arts. 101.Uno, 105.Seis, 106.Uno regla 3.ª). ``practised`` is
    the deduction the filed liquidations practised on exactly those cuotas:
    their filed deducible boxes less what the final especial slices deducted.
    ``common_use_sector_input`` records a cross-sector common-use input of a
    sectorized register.
    """

    gross_by_partition: dict[str | None, Decimal]
    practised: Decimal
    casilla_ids: tuple[CasillaId, ...]
    common_use_sector_input: bool


@dataclass(frozen=True, slots=True)
class RegularisedPeriodRefusal:
    """Finding naming why the earlier liquidations' totals are not derivable."""

    message: str


def negative_gross_base_finding(gross_by_partition: Mapping[str | None, Decimal]) -> str | None:
    """Name a negative gross base the annual regularisation has no defined treatment for.

    LIVA art. 105.Seis applies the definitive percentage to "la suma de las
    cuotas soportadas"; a sum driven below zero by rectifications has no stated
    regularisation, and art. 114.Dos has a rectification that reduces an earlier
    deduction corrected in the liquidations it names. The negative partitions'
    total is reported instead of being regularised or raised as a domain error.
    """
    negative = sum((gross for gross in gross_by_partition.values() if gross < 0), Decimal("0"))
    if negative >= 0:
        return None
    return tr("application.calculations.prorrata_regularizacion.unresolved.gross_negative", amount=negative)


def partition_definitive_percentages(
    context: CalculationSourceContext,
    register: ProrrataRegister,
    totals: RegularisedPeriodTotals,
    *,
    whole_entity_definitive: Decimal,
    cross_sector_common_use: bool,
) -> dict[str | None, Decimal] | RegularisedPeriodRefusal:
    """Return each partition's definitive percentage, or name why one is not derivable.

    The whole entity's definitive percentage is the current calculation's
    own. A differentiated sector's is its settled register entry
    (LIVA arts. 101.Uno, 105.Cuatro). Cross-sector common use takes the
    art. 104 percentage computed over the sectors sharing the use, with the
    agriculture and equivalence-surcharge operations counted as without the
    right to deduct (art. 101.Uno); the declared whole-entity volumes do not
    evidence that computation, so it stays unresolved.
    """
    negative = negative_gross_base_finding(totals.gross_by_partition)
    if negative is not None:
        return RegularisedPeriodRefusal(negative)
    if cross_sector_common_use:
        return RegularisedPeriodRefusal(
            tr(
                "application.calculations.prorrata_regularizacion.unresolved.regime_not_derived",
                year=context.filing_year,
            )
        )
    definitives: dict[str | None, Decimal] = {}
    unsettled: list[str] = []
    for sector_id in totals.gross_by_partition:
        if sector_id is None:
            definitives[None] = whole_entity_definitive
            continue
        entry = register.entry_for(context.filing_year, sector_id=sector_id)
        if entry is None or entry.definitive_percentage is None:
            unsettled.append(sector_id)
        else:
            definitives[sector_id] = entry.definitive_percentage
    if unsettled:
        return RegularisedPeriodRefusal(
            tr(
                "application.calculations.prorrata_regularizacion.unresolved.sector_definitive_missing",
                year=context.filing_year,
                sectors=", ".join(unsettled),
            )
        )
    return definitives


def _deducible_casilla_bindings(revision: ModeloRevision) -> dict[CasillaId, BindingId]:
    """Map each deducible cuota casilla to its bound ledger binding."""
    deducible = deducible_cuota_binding_ids(revision)
    bindings: dict[CasillaId, BindingId] = {}
    for casilla in revision.casillas:
        binding_id = next(
            (candidate for candidate in bound_casilla_binding_ids(casilla) if candidate in deducible),
            None,
        )
        if binding_id is not None:
            bindings[casilla.id] = binding_id
    return bindings


def _provisional_apportionment(
    ledger_apportionment: IvaLedgerProrrataApportionment | None,
    *,
    provisional_percentage: Decimal,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerProrrataApportionment:
    """Return the in-year apportionment the earlier liquidations deducted under.

    The register's own apportionment keeps its regime and differentiated
    sectors; its whole-entity percentage is the resolved provisional one, which
    a register without an entry for the year takes from the prior year's filed
    definitive percentage (LIVA art. 105.Uno).
    """
    if ledger_apportionment is None:
        return IvaLedgerProrrataApportionment(
            percentage=provisional_percentage,
            provenance=carried_prior_definitiva_prorrata_provenance(authority=operation),
            regime=general_prorrata_register_regime(authority=operation),
        )
    return ledger_apportionment.model_copy(update={"percentage": provisional_percentage, "settlement": None})


def _has_deducible_input(observations: Iterable[IvaLedgerObservation]) -> bool:
    return any(observation.deduction_fact_kind is not None for observation in observations)


def _filed_deduction_divergence(
    period: Period,
    filed: Mapping[CasillaId, Decimal],
    casilla_bindings: Mapping[CasillaId, BindingId],
    partitions: tuple[IvaDeducibleCuotaPartition, ...],
) -> RegularisedPeriodRefusal | None:
    """Name the first filed deducible box the in-year apportionment does not reproduce."""
    for casilla_id, binding_id in casilla_bindings.items():
        expected = round_to_cents(
            sum(
                (partition.deduction_by_binding().get(binding_id, Decimal("0")) for partition in partitions),
                Decimal("0"),
            )
        )
        if filed[casilla_id] != expected:
            return RegularisedPeriodRefusal(
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.source_period_ledger_divergence",
                    period=period.registry_token,
                    casilla=casilla_id,
                    filed=filed[casilla_id],
                    expected=expected,
                )
            )
    return None


def _partitioned_totals(
    partitions: tuple[IvaDeducibleCuotaPartition, ...],
    *,
    filed_total: Decimal,
    casilla_ids: tuple[CasillaId, ...],
    sectorized: bool,
) -> RegularisedPeriodTotals:
    """Split one liquidation's partitions into the regularisable gross and its practised deduction."""
    gross_by_partition: dict[str | None, Decimal] = {}
    final_slice_deduction = Decimal("0")
    for partition in partitions:
        if partition.regularisable:
            gross = sum(partition.gross_by_binding.values(), Decimal("0"))
            gross_by_partition[partition.sector_id] = gross_by_partition.get(partition.sector_id, Decimal("0")) + gross
        else:
            final_slice_deduction += sum(partition.deduction_by_binding().values(), Decimal("0"))
    return RegularisedPeriodTotals(
        gross_by_partition=gross_by_partition,
        practised=filed_total - round_to_cents(final_slice_deduction),
        casilla_ids=casilla_ids,
        common_use_sector_input=sectorized and any(partition.sector_id is None for partition in partitions),
    )


def _merge_totals(totals: Iterable[RegularisedPeriodTotals]) -> RegularisedPeriodTotals:
    gross_by_partition: dict[str | None, Decimal] = {}
    practised = Decimal("0")
    common_use_sector_input = False
    casilla_ids: list[CasillaId] = []
    for period_totals in totals:
        for sector_id, gross in period_totals.gross_by_partition.items():
            gross_by_partition[sector_id] = gross_by_partition.get(sector_id, Decimal("0")) + gross
        practised += period_totals.practised
        common_use_sector_input = common_use_sector_input or period_totals.common_use_sector_input
        casilla_ids.extend(casilla_id for casilla_id in period_totals.casilla_ids if casilla_id not in casilla_ids)
    return RegularisedPeriodTotals(
        gross_by_partition=gross_by_partition,
        practised=practised,
        casilla_ids=tuple(casilla_ids),
        common_use_sector_input=common_use_sector_input,
    )


class RegularisedPeriodLedger:
    """Read the earlier liquidations' filed deductions and re-derive their gross ledger cuotas."""

    def __init__(
        self,
        *,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        observation_repository: CalculationObservationRepositoryProtocol,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        investment_asset_register: BienesInversionIvaRegister | None,
        investment_asset_profile_id: str | None,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Bind the repositories the ledger aggregation and the filed observations come from."""
        self._prorrata_register_repository = prorrata_register_repository
        self._observation_repository = observation_repository
        self._transaction_repository = transaction_repository
        self._investment_asset_register = investment_asset_register
        self._investment_asset_profile_id = investment_asset_profile_id
        self._operation = operation

    def totals(
        self,
        context: CalculationSourceContext,
        periods: tuple[Period, ...],
        *,
        source_modelo: str,
        provisional_percentage: Decimal,
    ) -> RegularisedPeriodTotals | RegularisedPeriodRefusal:
        """Sum the earlier liquidations' gross ledger cuotas and their filed deductions."""
        payloads = self._filed_payloads(periods, source_modelo=source_modelo)
        if isinstance(payloads, RegularisedPeriodRefusal):
            return payloads
        collected: list[RegularisedPeriodTotals] = []
        for period, payload in payloads.items():
            period_totals = self._period_totals(
                context,
                period,
                payload,
                source_modelo=source_modelo,
                provisional_percentage=provisional_percentage,
            )
            if isinstance(period_totals, RegularisedPeriodRefusal):
                return period_totals
            collected.append(period_totals)
        return _merge_totals(collected)

    def settlement_common_use_input(self, context: CalculationSourceContext, period: Period) -> bool:
        """Whether the settlement liquidation itself holds a cross-sector common-use input."""
        return any(
            observation.deduction_fact_kind is not None and observation.prorrata_sector_id is None
            for observation in self._aggregate(context, period).observations
        )

    def _aggregate(self, context: CalculationSourceContext, period: Period) -> IvaLedgerAggregation:
        return aggregate_iva_ledger_observations_from_repositories(
            bucket_id=context.bucket_id,
            period=aggregation_period_for_modelo(filing_year=period.filing_year, code=period.registry_token),
            transaction_repository=self._transaction_repository,
            prorrata_register_repository=self._prorrata_register_repository,
            investment_asset_register=self._investment_asset_register,
            investment_asset_profile_id=self._investment_asset_profile_id,
            operation=self._operation,
        )

    def _filed_payloads(
        self,
        periods: tuple[Period, ...],
        *,
        source_modelo: str,
    ) -> dict[Period, ObservationEnvelopePayload] | RegularisedPeriodRefusal:
        """Load each earlier liquidation's filed observation, naming absent and refused ones."""
        payloads: dict[Period, ObservationEnvelopePayload] = {}
        missing: list[Period] = []
        refused: list[Period] = []
        for period in periods:
            payload = self._observation_repository.load_observation(source_modelo, period)
            if payload is None:
                missing.append(period)
            elif revision_carry_outcome(payload.registry_snapshot_ref, operation=self._operation).refused:
                refused.append(period)
            else:
                payloads[period] = payload
        reasons: list[str] = []
        if missing:
            reasons.append(
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.source_periods_missing",
                    periods=format_period_list(missing),
                )
            )
        if refused:
            reasons.append(
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.source_periods_refused",
                    periods=format_period_list(refused),
                )
            )
        if reasons:
            return RegularisedPeriodRefusal(" ".join(reasons))
        return payloads

    def _period_totals(
        self,
        context: CalculationSourceContext,
        period: Period,
        payload: ObservationEnvelopePayload,
        *,
        source_modelo: str,
        provisional_percentage: Decimal,
    ) -> RegularisedPeriodTotals | RegularisedPeriodRefusal:
        """Re-derive one earlier liquidation's gross cuotas per partition and check its filed deductions.

        The ledger rows are partitioned exactly as the in-year apportionment
        deducted them; each filed deducible box must equal that apportionment
        rounded to cents. A liquidation that declared deductible cuotas while
        the ledger holds no deductible input has no derivable gross base.
        """
        period_revision = self._operation.revision_for_context(
            source_modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
            on=period.end_date,
        )
        filed = payload.observation.casilla_values
        casilla_bindings = _deducible_casilla_bindings(period_revision)
        absent = tuple(casilla_id for casilla_id in casilla_bindings if casilla_id not in filed)
        if absent:
            return RegularisedPeriodRefusal(
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.source_period_cuotas_missing",
                    period=period.registry_token,
                    casillas=", ".join(absent),
                )
            )
        try:
            aggregation = self._aggregate(context, period)
            apportionment = _provisional_apportionment(
                aggregation.prorrata_apportionment,
                provisional_percentage=provisional_percentage,
                operation=self._operation,
            )
            partitions = resolve_iva_deducible_cuota_partitions(
                period_revision,
                aggregation.observations,
                apportionment=apportionment,
                operation=self._operation,
            )
        except (AggregationValidationError, UnacceptedLedgerRegistryValueError):
            return RegularisedPeriodRefusal(
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.source_period_ledger_refused",
                    period=period.registry_token,
                )
            )
        filed_total = sum((filed[casilla_id] for casilla_id in casilla_bindings), Decimal("0"))
        if not _has_deducible_input(aggregation.observations):
            if filed_total != 0:
                return RegularisedPeriodRefusal(
                    tr(
                        "application.calculations.prorrata_regularizacion.unresolved.source_period_gross_unavailable",
                        period=period.registry_token,
                    )
                )
            return _partitioned_totals(
                (), filed_total=filed_total, casilla_ids=tuple(casilla_bindings), sectorized=False
            )
        divergence = _filed_deduction_divergence(period, filed, casilla_bindings, partitions)
        if divergence is not None:
            return divergence
        return _partitioned_totals(
            partitions,
            filed_total=filed_total,
            casilla_ids=tuple(casilla_bindings),
            sectorized=bool(apportionment.sector_apportionments),
        )


__all__ = [
    "RegularisedPeriodLedger",
    "RegularisedPeriodRefusal",
    "RegularisedPeriodTotals",
    "format_period_list",
    "negative_gross_base_finding",
    "partition_definitive_percentages",
]
