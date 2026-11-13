"""Calculate a work unit through the input builder the registered calculate operation uses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo.application.modelo.calculate_input import build_work_calculate_input_bundle
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date, datetime
    from decimal import Decimal

    from cadrumo.application.modelo.calculation_action_ports import CalculationActionPorts
    from cadrumo.application.modelo.calculation_bucket_actions import BucketAggregationCalculationResult
    from cadrumo.domain.calculations.registry.ids import BindingId
    from cadrumo.domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence


def calculate_as_filer_enters(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    actor: str,
    casilla_inputs: Mapping[str, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    clock: datetime | None = None,
    iva_compensation_decision: object | None = None,
    filing_period_date: date | None = None,
) -> BucketAggregationCalculationResult:
    """Calculate with the filer's own casilla and binding entries, as the registered operation records them.

    The entries go through the same override resolution and input bundle the
    registered executor builds, and the calculation takes every channel from
    that bundle, so the revision records the entries as the filer's layer. The
    clock, compensation decision and filing date are the scenario's timeline,
    which the registered operation reads from the world instead.
    """
    bundle = build_work_calculate_input_bundle(
        work_unit_id=work_unit_id,
        ports=ports,
        casilla_overrides={key: str(value) for key, value in casilla_inputs.items()},
        binding_overrides={key: str(value) for key, value in binding_values.items()},
        relation_overrides={},
        detail_rows=(),
        borrador_snapshot_id=None,
        filing_instance_evidence=filing_instance_evidence,
        operation=ports.operation,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        ports=ports,
        actor=actor,
        casilla_inputs=bundle.casilla_inputs,
        text_casilla_inputs=bundle.optional_text_casilla_inputs(),
        cleared_casilla_ids=bundle.cleared_casilla_ids,
        record_operator_layer=bundle.record_operator_layer,
        attested_binding_ids=bundle.attested_binding_ids,
        value_attestations=bundle.value_attestations,
        income_family_entry_digests=bundle.income_family_entry_digests,
        row_attestations=bundle.row_attestations,
        m210_official_tipo_renta_code=bundle.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=bundle.m210_gross_income_source_mode,
        binding_values=bundle.optional_binding_values(),
        enum_binding_values=bundle.optional_enum_binding_values(),
        borrador_snapshot_id=bundle.borrador_snapshot_id,
        relation_values=bundle.optional_relation_values(),
        detail_rows=bundle.detail_rows,
        filing_instance_evidence=bundle.filing_instance_evidence,
        iva_compensation_decision=iva_compensation_decision,
        filing_period_date=filing_period_date,
        clock=clock,
    )
