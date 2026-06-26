"""Local registry calculation scenario verification harness.

Runs locally curated calculation scenarios against a
:class:`ValidatedRegistryAuthority` snapshot and compares computed outputs to
declared expected values, reporting any mismatches with full trace context.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ....core import STRICT_FROZEN_CONFIG, Period
from ._authority import ValidatedRegistryAuthority
from ._errors import RegistrySnapshotError, RegistryValidationError
from ._formula_runtime import RegistryCalculationEntry, RegistryCalculationResult, calculate_registry_snapshot
from ._ids import BindingId, CasillaId, RelationId

ScenarioStatus = Literal["match", "mismatch"]


class RegistryScenarioModel(BaseModel):
    """Strict frozen base for scenario verification records."""

    model_config = STRICT_FROZEN_CONFIG


class RegistryScenarioExpectedOutput(RegistryScenarioModel):
    """Expected value and trace contract for one scenario output."""

    target_casilla_id: CasillaId
    value: Decimal
    operand_refs: tuple[str, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _operand_casilla_refs_are_traced(self) -> RegistryScenarioExpectedOutput:
        missing = tuple(ref for ref in self.operand_casilla_refs if ref not in self.operand_refs)
        if missing:
            raise RegistryValidationError(
                f"scenario expected output for {self.target_casilla_id!r} declares operand_casilla_refs "
                f"that are absent from operand_refs: {missing!r}",
            )
        return self


class RegistryCalculationScenario(RegistryScenarioModel):
    """One locally curated scenario for registry-only calculation verification."""

    id: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1)
    inputs: dict[CasillaId, Decimal] = Field(default_factory=dict)
    binding_values: dict[BindingId, Decimal] = Field(default_factory=dict)
    enum_binding_values: dict[BindingId, str] = Field(default_factory=dict)
    relation_values: dict[RelationId, Decimal] = Field(default_factory=dict)
    date_context: dict[str, date] = Field(default_factory=dict)
    date_binding_values: dict[BindingId, date] = Field(default_factory=dict)
    expected_outputs: tuple[RegistryScenarioExpectedOutput, ...] = Field(min_length=1)
    notes: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _hydrate_filing_period(cls, data: object) -> object:
        if not isinstance(data, Mapping) or "filing_period" in data:
            return data
        filing_year = data.get("filing_year")
        period = data.get("period")
        if not isinstance(filing_year, int) or not isinstance(period, str):
            return data
        try:
            filing_period = Period.from_year_and_code(filing_year, period)
        except ValueError:
            return data
        return {**data, "filing_period": filing_period}

    @model_validator(mode="after")
    def _validate_scenario(self) -> RegistryCalculationScenario:
        if self.id.strip() != self.id:
            raise RegistryValidationError("scenario id must not include leading or trailing whitespace")
        if self.period.strip() != self.period:
            raise RegistryValidationError("scenario period must not include leading or trailing whitespace")
        if self.filing_period is not None and (
            self.filing_period.filing_year != self.filing_year or self.filing_period.registry_token != self.period
        ):
            raise RegistryValidationError("scenario filing_period must match filing_year and period")
        expected_targets = [expected.target_casilla_id for expected in self.expected_outputs]
        if len(set(expected_targets)) != len(expected_targets):
            raise RegistryValidationError("scenario expected outputs must target unique casillas")
        return self


class RegistryScenarioComparison(RegistryScenarioModel):
    """One expected-vs-actual output comparison for a scenario run."""

    target_casilla_id: CasillaId
    expected_value: Decimal
    actual_value: Decimal | None = None
    status: ScenarioStatus
    expected_operand_refs: tuple[str, ...] = ()
    actual_operand_refs: tuple[str, ...] = ()
    expected_operand_casilla_refs: tuple[CasillaId, ...] = ()
    actual_operand_casilla_refs: tuple[CasillaId, ...] = ()
    expected_legal_refs: tuple[str, ...] = ()
    actual_legal_refs: tuple[str, ...] = ()
    expected_source_refs: tuple[str, ...] = ()
    actual_source_refs: tuple[str, ...] = ()
    detail: str | None = None


class RegistryScenarioRunReport(RegistryScenarioModel):
    """Result of executing one local registry calculation scenario."""

    scenario_id: str
    registry_snapshot_id: str
    status: ScenarioStatus
    comparisons: tuple[RegistryScenarioComparison, ...]
    calculation: RegistryCalculationResult


def run_registry_calculation_scenario(
    scenario: RegistryCalculationScenario,
    *,
    registry_root: Path,
    source_root: Path,
) -> RegistryScenarioRunReport:
    """Execute ``scenario`` against the registry calculator and compare outputs.

    Returns:
        A :class:`RegistryScenarioRunReport` with per-casilla comparison results.
    """
    authority = ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
    try:
        authority.modelo(scenario.modelo)
    except RegistrySnapshotError as exc:
        raise RegistryValidationError(f"unknown modelo for registry scenario: {scenario.modelo!r}") from exc
    snapshot = authority.snapshot(
        scenario.modelo,
        filing_year=scenario.filing_year,
        period=scenario.period,
        revision_id=scenario.revision,
    )
    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=scenario.inputs,
        date_context=scenario.date_context,
        binding_values=scenario.binding_values,
        enum_binding_values=scenario.enum_binding_values,
        relation_values=scenario.relation_values,
        date_binding_values=scenario.date_binding_values or None,
    )
    entries_by_target = {entry.target_casilla_id: entry for entry in calculation.entries}
    comparisons = tuple(
        _compare_expected_output(expected, values=calculation.values, entries_by_target=entries_by_target)
        for expected in scenario.expected_outputs
    )
    status: ScenarioStatus = "match" if all(comparison.status == "match" for comparison in comparisons) else "mismatch"
    return RegistryScenarioRunReport(
        scenario_id=scenario.id,
        registry_snapshot_id=f"{snapshot.modelo.id}:{snapshot.revision.id}:{snapshot.period}",
        status=status,
        comparisons=comparisons,
        calculation=calculation,
    )


def assert_registry_scenario_matches(report: RegistryScenarioRunReport) -> None:
    """Raise with comparison details unless the scenario matched exactly."""
    if report.status == "match":
        return
    details = "\n".join(
        f" - {comparison.target_casilla_id}: {comparison.detail or 'mismatch'}"
        for comparison in report.comparisons
        if comparison.status == "mismatch"
    )
    raise RegistryValidationError(f"registry scenario {report.scenario_id!r} mismatched:\n{details}")


def _compare_expected_output(
    expected: RegistryScenarioExpectedOutput,
    *,
    values: Mapping[CasillaId, Decimal],
    entries_by_target: Mapping[CasillaId, RegistryCalculationEntry],
) -> RegistryScenarioComparison:
    actual = values.get(expected.target_casilla_id)
    entry = entries_by_target.get(expected.target_casilla_id)
    actual_operand_refs = entry.operand_refs if entry is not None else ()
    actual_operand_casilla_refs = entry.operand_casilla_refs if entry is not None else ()
    actual_legal_refs = entry.legal_refs if entry is not None else ()
    actual_source_refs = entry.source_refs if entry is not None else ()
    mismatches: list[str] = []
    if actual is None:
        mismatches.append("target was not calculated")
    elif actual != expected.value:
        mismatches.append(f"expected value {expected.value} but got {actual}")
    if expected.operand_refs and actual_operand_refs != expected.operand_refs:
        mismatches.append(f"expected operands {expected.operand_refs!r} but got {actual_operand_refs!r}")
    if expected.operand_refs and actual_operand_casilla_refs and not expected.operand_casilla_refs:
        mismatches.append(
            "expected operand casillas were not declared; "
            f"actual casilla operands were {actual_operand_casilla_refs!r}",
        )
    if expected.operand_casilla_refs and actual_operand_casilla_refs != expected.operand_casilla_refs:
        mismatches.append(
            f"expected operand casillas {expected.operand_casilla_refs!r} "
            f"but got {actual_operand_casilla_refs!r}",
        )
    if expected.legal_refs and actual_legal_refs != expected.legal_refs:
        mismatches.append(f"expected legal refs {expected.legal_refs!r} but got {actual_legal_refs!r}")
    if expected.source_refs and actual_source_refs != expected.source_refs:
        mismatches.append(f"expected source refs {expected.source_refs!r} but got {actual_source_refs!r}")
    status: ScenarioStatus = "match" if not mismatches else "mismatch"
    return RegistryScenarioComparison(
        target_casilla_id=expected.target_casilla_id,
        expected_value=expected.value,
        actual_value=actual,
        status=status,
        expected_operand_refs=expected.operand_refs,
        actual_operand_refs=actual_operand_refs,
        expected_operand_casilla_refs=expected.operand_casilla_refs,
        actual_operand_casilla_refs=actual_operand_casilla_refs,
        expected_legal_refs=expected.legal_refs,
        actual_legal_refs=actual_legal_refs,
        expected_source_refs=expected.source_refs,
        actual_source_refs=actual_source_refs,
        detail="; ".join(mismatches) or None,
    )


__all__ = [
    "RegistryCalculationScenario",
    "RegistryScenarioComparison",
    "RegistryScenarioExpectedOutput",
    "RegistryScenarioRunReport",
    "assert_registry_scenario_matches",
    "run_registry_calculation_scenario",
]
