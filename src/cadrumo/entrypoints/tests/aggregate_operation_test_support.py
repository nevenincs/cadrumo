"""Canonical counterpart inputs for supervised aggregation conformance."""

from decimal import Decimal

from ...application.aggregation.counterpart import CounterpartObservation
from ...application.aggregation.service import PerModeloAggregationCommand
from ...core.aggregation import BindingSourceKind
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts


def aggregate_conformance_command(*, operation: PinnedAuthorityOperation) -> PerModeloAggregationCommand:
    """Use two independent source rows that aggregate to one counterpart row."""
    with validating_governed_facts(operation):
        return PerModeloAggregationCommand(
            modelo="349",
            period=Period.from_year_and_code(2025, "1T"),
            counterpart_observations=tuple(
                CounterpartObservation(
                    source_kind=BindingSourceKind.PAYABLE_INVOICE,
                    source_object_id=f"aggregate-conformance-{index}",
                    counterparty_nif="FR12345678901",
                    counterparty_name="Synthetic counterpart",
                    counterparty_country="FR",
                    operation_kind="E",
                    operation_period="1T",
                    taxable_base=amount,
                    invoice_total=amount,
                    accrued_on="2025-02-10",
                )
                for index, amount in enumerate((Decimal("200.10"), Decimal("99.90")), start=1)
            ),
        )
