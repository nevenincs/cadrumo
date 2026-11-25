"""Earlier-liquidation totals the annual prorrata regularisation re-derives (LIVA arts. 101, 105, 106).

The settlement liquidation's regularisation box reaches only the earlier
liquidations of the year. For each of them this module re-derives the gross
deducible cuotas from the IVA ledger, partitioned exactly as the in-year
apportionment deducted them, and reads the practised deduction from the filed
observation. A liquidation entered by hand, whose ledger holds no
deducible input, takes the gross base the operator declared for it in the
prorrata register; a ledger that does hold input wins, and must agree with any
declaration for the same period. A filed liquidation that neither source
reproduces, that holds no derivable gross base, or that is absent or refused
stays a refusal naming the cause; nothing defaults to zero.

See Also:
    :mod:`~application.calculations.prorrata_regularizacion`
        Source resolver that combines these totals with the definitive
        percentages.
    :func:`~application.aggregation.iva_ledger_apportionment.resolve_iva_deducible_cuota_partitions`
        Ledger partitions per differentiated sector and prorrata especial slice;
:class:`ModeloRevision`, the registry revision a modelo is calculated against.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.decimal.constants import HUNDRED
from ...core.i18n.render import tr
from ...core.money.rounding import CENT, round_to_cents
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
from ...domain.prorrata_register.register import ProrrataOperatorGrossDeclaration, ProrrataRegister
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
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReader
from .observations_repository import CalculationObservationRepositoryProtocol, ObservationEnvelopePayload
from .revision_carry_gate import revision_carry_outcome

#: The most one filed box can differ from its unrounded deduction: half a cent.
_HALF_CENT = CENT / 2


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
    sectorized register. ``operator_declared`` holds the register declarations
    that supplied a gross base in place of an empty ledger, so the result can
    name them as its operator-declared sources.
    """

    gross_by_partition: dict[str | None, Decimal]
    practised: Decimal
    casilla_ids: tuple[CasillaId, ...]
    common_use_sector_input: bool
    operator_declared: tuple[ProrrataOperatorGrossDeclaration, ...] = ()


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


def _declared_expected_deduction(
    period: Period,
    declarations: tuple[ProrrataOperatorGrossDeclaration, ...],
    apportionment: IvaLedgerProrrataApportionment,
) -> Decimal | RegularisedPeriodRefusal:
    """Apply each declared gross cuota's provisional percentage, refusing an unknown sector."""
    sector_percentages = {sector.sector_id: sector.percentage for sector in apportionment.sector_apportionments}
    expected = Decimal("0")
    for declaration in declarations:
        if declaration.sector_id is None:
            percentage = apportionment.percentage
        elif declaration.sector_id in sector_percentages:
            percentage = sector_percentages[declaration.sector_id]
        else:
            return RegularisedPeriodRefusal(
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.source_period_ledger_refused",
                    period=period.registry_token,
                )
            )
        expected += declaration.gross_cuota * percentage / HUNDRED
    return expected


def _operator_declared_totals(
    period: Period,
    declarations: tuple[ProrrataOperatorGrossDeclaration, ...],
    *,
    filed: Mapping[CasillaId, Decimal],
    casilla_bindings: Mapping[CasillaId, BindingId],
    apportionment: IvaLedgerProrrataApportionment,
) -> RegularisedPeriodTotals | RegularisedPeriodRefusal:
    """Take one hand-entered liquidation's gross base from the operator's declarations.

    The filed deducible boxes must still be the declared gross cuotas at the
    provisional percentages the period deducted under. Each filed box is
    rounded to cents on its own, so the filed total may differ from the
    unrounded deduction by at most half a cent per non-zero box.
    """
    expected = _declared_expected_deduction(period, declarations, apportionment)
    if isinstance(expected, RegularisedPeriodRefusal):
        return expected
    filed_total = sum((filed[casilla_id] for casilla_id in casilla_bindings), Decimal("0"))
    filed_boxes = sum(1 for casilla_id in casilla_bindings if filed[casilla_id] != 0)
    if abs(filed_total - expected) > _HALF_CENT * filed_boxes:
        return RegularisedPeriodRefusal(
            tr(
                "application.calculations.prorrata_regularizacion.unresolved.source_period_operator_divergence",
                period=period.registry_token,
                filed=filed_total,
                expected=round_to_cents(expected),
            )
        )
    gross_by_partition: dict[str | None, Decimal] = {}
    for declaration in declarations:
        gross_by_partition[declaration.sector_id] = declaration.gross_cuota
    return RegularisedPeriodTotals(
        gross_by_partition=gross_by_partition,
        practised=filed_total,
        casilla_ids=tuple(casilla_bindings),
        common_use_sector_input=bool(apportionment.sector_apportionments)
        and any(declaration.sector_id is None for declaration in declarations),
        operator_declared=declarations,
    )


def _missing_cuotas_refusal(
    period: Period,
    filed: Mapping[CasillaId, Decimal],
    casilla_bindings: Mapping[CasillaId, BindingId],
) -> RegularisedPeriodRefusal | None:
    """Name the deducible boxes the filed observation does not state."""
    absent = tuple(casilla_id for casilla_id in casilla_bindings if casilla_id not in filed)
    if not absent:
        return None
    return RegularisedPeriodRefusal(
        tr(
            "application.calculations.prorrata_regularizacion.unresolved.source_period_cuotas_missing",
            period=period.registry_token,
            casillas=", ".join(absent),
        )
    )


def _empty_ledger_totals(
    period: Period,
    declarations: tuple[ProrrataOperatorGrossDeclaration, ...],
    *,
    filed: Mapping[CasillaId, Decimal],
    casilla_bindings: Mapping[CasillaId, BindingId],
    apportionment: IvaLedgerProrrataApportionment,
    filed_total: Decimal,
) -> RegularisedPeriodTotals | RegularisedPeriodRefusal:
    """Take a liquidation whose ledger holds no deducible input from the operator's declarations."""
    if declarations:
        return _operator_declared_totals(
            period,
            declarations,
            filed=filed,
            casilla_bindings=casilla_bindings,
            apportionment=apportionment,
        )
    if filed_total != 0:
        return RegularisedPeriodRefusal(
            tr(
                "application.calculations.prorrata_regularizacion.unresolved.source_period_gross_unavailable",
                period=period.registry_token,
            )
        )
    return _partitioned_totals((), filed_total=filed_total, casilla_ids=tuple(casilla_bindings), sectorized=False)


def _ledger_operator_disagreement(
    period: Period,
    partitions: tuple[IvaDeducibleCuotaPartition, ...],
    declarations: tuple[ProrrataOperatorGrossDeclaration, ...],
) -> RegularisedPeriodRefusal | None:
    """Name the first operator declaration the period's ledger gross base contradicts.

    The ledger wins whenever it holds deducible input for the period, but a
    declaration that disagrees with it means one of the two is wrong; neither
    is used until they are reconciled.
    """
    ledger_gross: dict[str | None, Decimal] = {}
    for partition in partitions:
        if partition.regularisable:
            gross = sum(partition.gross_by_binding.values(), Decimal("0"))
            ledger_gross[partition.sector_id] = ledger_gross.get(partition.sector_id, Decimal("0")) + gross
    for declaration in declarations:
        ledger = round_to_cents(ledger_gross.get(declaration.sector_id, Decimal("0")))
        if ledger == declaration.gross_cuota:
            continue
        if declaration.sector_id is None:
            return RegularisedPeriodRefusal(
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.source_period_gross_disagreement",
                    period=period.registry_token,
                    ledger=ledger,
                    declared=declaration.gross_cuota,
                )
            )
        return RegularisedPeriodRefusal(
            tr(
                "application.calculations.prorrata_regularizacion.unresolved.source_period_sector_gross_disagreement",
                period=period.registry_token,
                sector=declaration.sector_id,
                ledger=ledger,
                declared=declaration.gross_cuota,
            )
        )
    return None


def _merge_totals(totals: Iterable[RegularisedPeriodTotals]) -> RegularisedPeriodTotals:
    gross_by_partition: dict[str | None, Decimal] = {}
    practised = Decimal("0")
    common_use_sector_input = False
    casilla_ids: list[CasillaId] = []
    operator_declared: list[ProrrataOperatorGrossDeclaration] = []
    for period_totals in totals:
        for sector_id, gross in period_totals.gross_by_partition.items():
            gross_by_partition[sector_id] = gross_by_partition.get(sector_id, Decimal("0")) + gross
        practised += period_totals.practised
        common_use_sector_input = common_use_sector_input or period_totals.common_use_sector_input
        casilla_ids.extend(casilla_id for casilla_id in period_totals.casilla_ids if casilla_id not in casilla_ids)
        operator_declared.extend(period_totals.operator_declared)
    return RegularisedPeriodTotals(
        gross_by_partition=gross_by_partition,
        practised=practised,
        casilla_ids=tuple(casilla_ids),
        common_use_sector_input=common_use_sector_input,
        operator_declared=tuple(operator_declared),
    )


class RegularisedPeriodLedger:
    """Read the earlier liquidations' filed deductions and re-derive their gross ledger cuotas."""

    def __init__(
        self,
        *,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        observation_repository: CalculationObservationRepositoryProtocol,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        invoice_reader: InvoiceCatalogueReader,
        investment_asset_register: BienesInversionIvaRegister | None,
        investment_asset_profile_id: str | None,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Bind the repositories the ledger aggregation and the filed observations come from."""
        self._prorrata_register_repository = prorrata_register_repository
        self._observation_repository = observation_repository
        self._transaction_repository = transaction_repository
        self._invoice_reader = invoice_reader
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
        register = self._prorrata_register_repository.load()
        collected: list[RegularisedPeriodTotals] = []
        for period, payload in payloads.items():
            period_totals = self._period_totals(
                context,
                period,
                payload,
                source_modelo=source_modelo,
                provisional_percentage=provisional_percentage,
                declarations=register.gross_declarations_for_period(period),
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
            invoice_reader=self._invoice_reader,
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
        declarations: tuple[ProrrataOperatorGrossDeclaration, ...],
    ) -> RegularisedPeriodTotals | RegularisedPeriodRefusal:
        """Re-derive one earlier liquidation's gross cuotas per partition and check its filed deductions.

        The ledger rows are partitioned exactly as the in-year apportionment
        deducted them; each filed deducible box must equal that apportionment
        rounded to cents. A liquidation that declared deductible cuotas while
        the ledger holds no deductible input takes the operator's declared gross
        base, and without one has no derivable gross base. A declaration for a
        period whose ledger does hold input must agree with the ledger.
        """
        period_revision = self._operation.revision_for_context(
            source_modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
            on=period.end_date,
        )
        filed = payload.observation.casilla_values
        casilla_bindings = _deducible_casilla_bindings(period_revision)
        missing = _missing_cuotas_refusal(period, filed, casilla_bindings)
        if missing is not None:
            return missing
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
            return _empty_ledger_totals(
                period,
                declarations,
                filed=filed,
                casilla_bindings=casilla_bindings,
                apportionment=apportionment,
                filed_total=filed_total,
            )
        disagreement = _ledger_operator_disagreement(period, partitions, declarations)
        if disagreement is not None:
            return disagreement
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
