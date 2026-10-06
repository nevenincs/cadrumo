"""Historical spreadsheet parity records and pure local scenario helpers.

The former remote parity workflow is retired. These records remain readable;
this module does not create workbooks or read remote calculation values.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ....core.casilla_id import CasillaId
from ....core.casilla_value_absence import AbsentCasillaReading
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.period import Period
from ....domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import (
    BindingId,
    RelationId,
    RevisionId,
)
from ....domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ....domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    relation_prefill_bindings_for_period,
    relation_source_requirements,
)
from ....domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.period import calculation_filing_date
from .casilla_parity import CasillaParity
from .errors import CalcSheetsParityError
from .records import (
    OperatorInput,
    OperatorInputs,
    RelationValue,
    RelationValues,
)


class ParityReport(BaseModel):
    """Aggregate parity verdict across every computed casilla.

    `verdict` collapses the per-casilla flags into a single answer:

    - `all_match` — every pair compared matches; no surface lies.
    - `divergence` — at least one pair disagrees somewhere. The
      `divergences` field lists offending casillas with both values
      for inspection.
    - `inconclusive` — the AEAT oracle is absent so we can only
      compare backend↔Sheets; that pair matches.
    """

    model_config = _STRICT_FROZEN

    modelo_id: str
    revision_id: RevisionId
    period: Period
    filing_year: int
    spreadsheet_id: str
    spreadsheet_url: str
    casillas: tuple[CasillaParity, ...]
    aeat_oracle_present: bool
    verdict: Literal["all_match", "divergence", "inconclusive"]
    divergences: tuple[CasillaParity, ...] = ()


class OperatorInputScenario(BaseModel):
    """Caller-supplied scenario for the parity harness.

    ``inputs_by_casilla_id`` maps canonical registry ``casilla.id`` values to
    input Decimals. ``expected_by_casilla_id`` mirrors that shape for
    AEAT-published expected outputs; an empty mapping is allowed and signals
    "no AEAT oracle available, fall back to backend↔Sheets only".
    """

    model_config = _STRICT_FROZEN

    inputs_by_casilla_id: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    bindings: Mapping[BindingId, Decimal] = Field(default_factory=dict)
    enum_bindings: Mapping[BindingId, str] = Field(default_factory=dict)
    relation_values: Mapping[RelationId, Decimal] = Field(default_factory=dict)
    expected_by_casilla_id: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    scenario_label: str = ""


def _build_operator_inputs(
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
) -> tuple[OperatorInputs, dict[CasillaId, Decimal]]:
    """Translate canonical-id-keyed scenario inputs into sheet input rows."""
    _reject_unknown_scenario_casilla_ids(snapshot, scenario)
    operator_input_records: list[OperatorInput] = []
    inputs_by_id: dict[CasillaId, Decimal] = {}
    for casilla_id, value in scenario.inputs_by_casilla_id.items():
        operator_input_records.append(OperatorInput(casilla_id=casilla_id, value=value))
        inputs_by_id[casilla_id] = value
    return OperatorInputs(values=tuple(operator_input_records)), inputs_by_id


def _reject_unknown_scenario_casilla_ids(
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
) -> None:
    unknown = (
        *undeclared_casilla_ids(snapshot.revision, scenario.inputs_by_casilla_id),
        *undeclared_casilla_ids(snapshot.revision, scenario.expected_by_casilla_id),
    )
    if unknown:
        raise CalcSheetsParityError(
            "scenario references unknown casilla ids",
            context={"unknown_count": len(unknown), "modelo": snapshot.modelo.id},
            translated_message="application.storage.calc_sheets.parity.errors.unknown_casilla_ids",
        )


def _relation_requirements_by_id(
    snapshot: RegistrySnapshot,
) -> dict[RelationId, RegistryFoldRequirement]:
    """Index registry-derived relation requirements by each relation id they cover."""
    return {
        relation_id: requirement
        for requirement in relation_source_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        for relation_id in requirement.target_bindings
    }


def _build_relation_value(
    relation_id: RelationId,
    value: Decimal,
    binding: BindingDefinition,
    provider: RelationPrefillProvider,
    requirement: RegistryFoldRequirement | None,
) -> RelationValue:
    """Build one parity fold value from the slot declaration or its requirement."""
    if requirement is None:
        return RelationValue(
            relation=relation_id,
            value=value,
            source_modelo=provider.source_modelo,
            source_filing_year=None,
            source_periods=provider.required_source_periods,
            source_casilla_ids=provider.declared_source_casilla_ids,
            legal_refs=tuple(binding.legal_refs),
            source_refs=tuple(binding.source_refs),
        )
    return RelationValue(
        relation=relation_id,
        value=value,
        source_modelo=requirement.source_modelo,
        source_filing_year=requirement.filing_year,
        source_periods=requirement.periods,
        source_casilla_ids=requirement.source_casilla_ids,
        legal_refs=requirement.legal_refs,
        source_refs=requirement.source_refs,
    )


def _build_relation_values(snapshot: RegistrySnapshot, scenario: OperatorInputScenario) -> RelationValues:
    folds_by_id = {
        binding.id: (binding, provider) for binding, provider in relation_prefill_bindings_for_period(snapshot.revision)
    }
    requirements_by_relation = _relation_requirements_by_id(snapshot)
    unknown_relation_ids = sorted(set(scenario.relation_values).difference(folds_by_id))
    if unknown_relation_ids:
        raise CalcSheetsParityError(
            "scenario references unknown relation ids",
            context={"unknown_count": len(unknown_relation_ids), "modelo": snapshot.modelo.id},
        )
    return RelationValues(
        values=tuple(
            _build_relation_value(
                relation_id=relation_id,
                value=value,
                binding=folds_by_id[relation_id][0],
                provider=folds_by_id[relation_id][1],
                requirement=requirements_by_relation.get(relation_id),
            )
            for relation_id, value in scenario.relation_values.items()
        ),
    )


def _compute_local(
    snapshot: RegistrySnapshot,
    inputs_by_id: Mapping[CasillaId, Decimal],
    scenario: OperatorInputScenario,
) -> Mapping[CasillaId, Decimal]:
    revision = snapshot.revision
    # Default every operator-input casilla absent from the scenario
    # to zero so the runtime contract (every non-computed casilla
    # has a value) holds without forcing the caller to enumerate them.
    full_inputs: dict[CasillaId, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind == InputKind.COMPUTED:
            continue
        if casilla.input_kind == InputKind.INFORMATIONAL:
            continue
        full_inputs[casilla.id] = AbsentCasillaReading.UNSUPPLIED_INPUT.read(inputs_by_id, casilla.id)
    binding_defaults = {binding.id: scenario.bindings.get(binding.id, Decimal("0")) for binding in revision.bindings}
    relation_defaults = {
        binding.id: scenario.relation_values.get(binding.id, Decimal("0"))
        for binding, _ in relation_prefill_bindings_for_period(revision)
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=full_inputs,
        date_context={
            "filing_period": (
                calculation_filing_date(snapshot.filing_period)
                if snapshot.filing_period is not None
                else date(snapshot.filing_year, 12, 31)
            ),
        },
        binding_values=binding_defaults,
        enum_binding_values=dict(scenario.enum_bindings),
        relation_values=relation_defaults,
        # The parity harness drives a scenario's operator inputs, not a filing
    )
    return result.values


__all__ = ["OperatorInputScenario", "ParityReport"]
