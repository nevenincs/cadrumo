"""Annual ledger reconciliation beside the authoritative declared prorrata volumes."""

from __future__ import annotations

from decimal import Decimal

from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.iva_flow_catalogue import resolve_iva_flow_direction_catalogue
from ...domain.calculations.registry.prorrata_volume_catalogue import resolve_prorrata_volume_catalogue
from ...domain.iva.schema import IvaLedgerObservationRole, is_iva_cash_accounting_none
from ..calculations.prorrata_regularizacion import ProrrataDeclaredVolumeLedgerRollup
from .iva_ledger import IvaLedgerAggregation


def project_prorrata_declared_volume_rollup(
    aggregation: IvaLedgerAggregation,
    *,
    declared_volume_total: Decimal | None,
    declared_volume_con_derecho: Decimal | None,
    operation: PinnedAuthorityOperation,
) -> ProrrataDeclaredVolumeLedgerRollup:
    """Count each output operation once; cuotas and cash-payment fragments are excluded."""
    annual = Period.from_year_and_code(aggregation.period.filing_year, "0A")
    if aggregation.period != annual:
        raise ValueError("prorrata reconciliation requires the complete annual ledger window")
    catalogue = resolve_prorrata_volume_catalogue(effective_date=annual.end_date, authority=operation)
    flows = resolve_iva_flow_direction_catalogue(effective_date=annual.end_date, authority=operation)
    output_flows = {flows.issued_token, flows.supplier_reverse_charge_token}
    excluded = frozenset(aggregation.art_104_tres_excluded_ledger_ids)
    included: list[str] = []
    unknown = set(aggregation.unclassified_output_ledger_ids)
    con_derecho = Decimal(0)
    sin_derecho = Decimal(0)
    for observation in aggregation.observations:
        if observation.flow_direction not in output_flows or not annual.contains(observation.transaction_date):
            continue
        # The cash operation information carries its whole volume; payments carry only portions.
        cash = not is_iva_cash_accounting_none(observation.cash_accounting_treatment)
        role = IvaLedgerObservationRole.OPERATION_INFORMATIONAL if cash else IvaLedgerObservationRole.SETTLEMENT
        if observation.observation_role is not role:
            continue
        if observation.ledger_id in excluded:
            continue
        if observation.category in catalogue.con_derecho:
            con_derecho += observation.base_amount
        elif (
            observation.category in catalogue.sin_derecho
            and observation.exemption_article in catalogue.sin_derecho_exemption_articles
        ):
            sin_derecho += observation.base_amount
        else:
            unknown.add(observation.ledger_id)
            continue
        included.append(observation.ledger_id)
    return ProrrataDeclaredVolumeLedgerRollup(
        declared_volume_total=declared_volume_total,
        declared_volume_con_derecho=declared_volume_con_derecho,
        declared_volume_sin_derecho=(declared_volume_total - declared_volume_con_derecho)
        if declared_volume_total is not None and declared_volume_con_derecho is not None
        else None,
        ledger_volume_total=con_derecho + sin_derecho,
        ledger_volume_con_derecho=con_derecho,
        ledger_volume_sin_derecho=sin_derecho,
        included_ledger_ids=tuple(included),
        unclassified_ledger_ids=tuple(sorted(unknown)),
        art_104_tres_excluded_ledger_ids=tuple(sorted(excluded)),
    )
