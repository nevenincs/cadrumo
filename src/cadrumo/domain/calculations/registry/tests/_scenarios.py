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

from .....core import STRICT_FROZEN_CONFIG, BindingSourceKind, CasillaId, Period, hydrate_scenario_filing_period
from .._authority import ValidatedRegistryAuthority
from ..errors import RegistrySnapshotError, RegistryValidationError
from .._formula_runtime import RegistryCalculationEntry, RegistryCalculationResult, calculate_registry_snapshot
from .._ids import BindingId, LegalRefId, RelationId, SourceRefId
from .._period_selector_match import selector_period_matches_request
from .._runtime_graph import expression_binding_refs
from .._schema import ModeloRevision
from .._schema_input_kind import InputKind
from .._snapshot_coordinate import registry_snapshot_id_for

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
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

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
    hand_typed_bound_casillas: dict[CasillaId, str] = Field(default_factory=dict)
    """Bound casillas this scenario deliberately supplies itself, each with its reason.

    A casilla the registry declares ``input_kind = "bound"`` carries a value the
    engine PRODUCES, by aggregating substrate and resolving a binding. A
    scenario that supplies one as an ``inputs`` entry hand-types that value and
    steps over both links, so whatever it goes on to assert says nothing about
    how the casilla is produced — while the scenario's name and its oracle
    evidence keep reading as end-to-end coverage.

    That is sometimes the right call: a scenario isolating one leg of a chain
    legitimately supplies the other leg rather than building substrate for it.
    What is never right is doing it silently. Declaring the casilla here with a
    stated reason makes the boundary of the scenario's claim explicit at the
    scenario, which is where the next reader looks — rather than in a central
    allowlist, which would drift from the scenarios exactly as the bypass it
    guards drifted from the registry.

    :func:`run_registry_calculation_scenario` refuses an undeclared bound input,
    an empty reason, and a declaration naming a casilla that is not bound (a
    stale excuse outliving the registry change that ended it).

    A bound value the caller obtained by RUNNING the aggregation and the binding
    resolver belongs in :attr:`chain_resolved_bound_casillas` instead; it is the
    opposite claim and must not be filed under this name.
    """
    chain_resolved_bound_casillas: dict[CasillaId, str] = Field(default_factory=dict)
    """Bound casillas whose value the caller PRODUCED through the real chain.

    The scenario harness has one channel for casilla values, so a bound value
    the caller resolved by running the production aggregation and binding
    resolver arrives here looking exactly like a hand-typed one. Without a
    second field the runner could not tell the two apart, and the check would
    force the honest case to file itself under
    :attr:`hand_typed_bound_casillas` — recording the precise opposite of what
    happened, in the field a later reader would trust.

    So the two claims get two names, and the value states which resolver
    produced it. This is a declaration rather than a proof: nothing stops a
    caller filing a hand-typed value here. What it buys is that the claim is
    written down and greppable instead of absent, so a reviewer can check it
    against the code that builds the mapping — the same discipline the fixture
    corpora use when they declare their own provenance.
    """

    @model_validator(mode="before")
    @classmethod
    def _hydrate_filing_period(cls, data: object) -> object:
        return hydrate_scenario_filing_period(data)

    @model_validator(mode="after")
    def _validate_scenario(self) -> RegistryCalculationScenario:
        if self.id.strip() != self.id:
            raise RegistryValidationError("scenario id must not include leading or trailing whitespace")
        if self.period.strip() != self.period:
            raise RegistryValidationError("scenario period must not include leading or trailing whitespace")
        if self.filing_period is not None and (
            self.filing_period.filing_year != self.filing_year
            or not selector_period_matches_request(self.period, self.filing_period.registry_token)
        ):
            raise RegistryValidationError("scenario filing_period must match filing_year and period")
        expected_targets = [expected.target_casilla_id for expected in self.expected_outputs]
        if len(set(expected_targets)) != len(expected_targets):
            raise RegistryValidationError("scenario expected outputs must target unique casillas")
        for field_name, declared in (
            ("hand_typed_bound_casillas", self.hand_typed_bound_casillas),
            ("chain_resolved_bound_casillas", self.chain_resolved_bound_casillas),
        ):
            blank = sorted(casilla_id for casilla_id, reason in declared.items() if not reason.strip())
            if blank:
                raise RegistryValidationError(
                    f"scenario {self.id!r} declares {field_name} with no stated reason: {blank!r}; the declaration "
                    "exists to record what happened to the value, so an empty reason is the silence it was added "
                    "to prevent",
                )
            missing = sorted(set(declared) - set(self.inputs))
            if missing:
                raise RegistryValidationError(
                    f"scenario {self.id!r} declares {field_name} the scenario does not supply as inputs: {missing!r}",
                )
        both = sorted(set(self.hand_typed_bound_casillas) & set(self.chain_resolved_bound_casillas))
        if both:
            raise RegistryValidationError(
                f"scenario {self.id!r} declares casillas as BOTH hand-typed and chain-resolved: {both!r}. The two "
                "are opposite claims about where the value came from, and a casilla cannot satisfy both.",
            )
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
    expected_legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    actual_legal_refs: tuple[LegalRefId, ...] = ()
    expected_source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    actual_source_refs: tuple[SourceRefId, ...] = ()
    detail: str | None = None


class RegistryScenarioRunReport(RegistryScenarioModel):
    """Result of executing one local registry calculation scenario."""

    scenario_id: str
    registry_snapshot_id: str
    status: ScenarioStatus
    comparisons: tuple[RegistryScenarioComparison, ...]
    calculation: RegistryCalculationResult

    @model_validator(mode="after")
    def _status_matches_comparisons(self) -> RegistryScenarioRunReport:
        expected_status: ScenarioStatus = (
            "match" if all(comparison.status == "match" for comparison in self.comparisons) else "mismatch"
        )
        if self.status != expected_status:
            raise RegistryValidationError(
                f"registry scenario report {self.scenario_id!r} status {self.status!r} "
                f"does not match comparison statuses; expected {expected_status!r}",
            )
        return self


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
    _reject_undeclared_hand_typed_bound_inputs(scenario, snapshot.revision)
    # A profile-source binding a formula references but the scenario does not
    # supply defaults to a neutral zero, mirroring the live calculate path where
    # the profile-derived-fact injector seeds an absent profile binding to 0
    # (e.g. a single filer's marriage-month integers, or the Madrid
    # nacimiento/adopción count for a scenario that exercises an unrelated
    # casilla). Without this the engine hard-fails on the unsupplied binding,
    # forcing every full-tree scenario to enumerate every profile binding.
    supplied_binding_ids = (
        set(scenario.binding_values) | set(scenario.enum_binding_values) | set(scenario.date_binding_values)
    )
    profile_binding_ids = {
        binding.id for binding in snapshot.revision.bindings if binding.source == BindingSourceKind.PROFILE
    }
    formula_referenced_binding_ids: set[BindingId] = set()
    for formula in snapshot.revision.formulas:
        formula_referenced_binding_ids.update(expression_binding_refs(formula.expression))
    unresolved_profile_binding_ids = tuple(
        sorted((formula_referenced_binding_ids & profile_binding_ids) - supplied_binding_ids)
    )
    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=scenario.inputs,
        date_context=scenario.date_context,
        binding_values=scenario.binding_values,
        enum_binding_values=scenario.enum_binding_values,
        relation_values=scenario.relation_values,
        date_binding_values=scenario.date_binding_values or None,
        unresolved_binding_ids=unresolved_profile_binding_ids,
    )
    entries_by_target = {entry.target_casilla_id: entry for entry in calculation.entries}
    comparisons = tuple(
        _compare_expected_output(expected, values=calculation.values, entries_by_target=entries_by_target)
        for expected in scenario.expected_outputs
    )
    status: ScenarioStatus = "match" if all(comparison.status == "match" for comparison in comparisons) else "mismatch"
    return RegistryScenarioRunReport(
        scenario_id=scenario.id,
        registry_snapshot_id=registry_snapshot_id_for(snapshot),
        status=status,
        comparisons=comparisons,
        calculation=calculation,
    )


def bound_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return every casilla ``revision`` declares ``input_kind = "bound"``.

    Read off the :class:`ModeloRevision` rather than listed anywhere, so a
    casilla that becomes bound is covered the moment the registry says so.
    """
    return frozenset(casilla.id for casilla in revision.casillas if casilla.input_kind is InputKind.BOUND)


def _reject_undeclared_hand_typed_bound_inputs(
    scenario: RegistryCalculationScenario,
    revision: ModeloRevision,
) -> None:
    """Refuse a scenario that hand-types a bound casilla without saying so.

    Placed in the runner rather than in a static scan of the test tree because
    this is the one point EVERY scenario passes through. A scan of the sources
    resolves only the scenarios whose ``inputs`` it can follow — measured at
    half of them, the rest passing ``inputs`` through factory parameters — and
    would report the unreadable half clean, which is worse than not checking:
    it is a checking instrument that lies about its own coverage.

    Two directions, because a one-way check rots. An input the registry binds
    and the scenario does not declare is the silent bypass. A declaration for a
    casilla that is NOT bound is a stale excuse: the registry changed, the
    reason outlived it, and the next reader is told a binding is being stepped
    over when none exists.

    Raises:
        RegistryValidationError: On either direction, naming every casilla and,
            for the undeclared case, the binding that was stepped over.
    """
    bound = bound_casilla_ids(revision)
    binding_by_casilla = {casilla.id: casilla.binding for casilla in revision.casillas}
    declared = set(scenario.hand_typed_bound_casillas) | set(scenario.chain_resolved_bound_casillas)

    undeclared = sorted((set(scenario.inputs) & bound) - declared)
    if undeclared:
        named = ", ".join(f"{casilla_id} (binding {binding_by_casilla.get(casilla_id)!r})" for casilla_id in undeclared)
        raise RegistryValidationError(
            f"scenario {scenario.id!r} supplies casillas the registry declares bound, without declaring them: "
            f"{named}. A bound casilla's value is produced by aggregating substrate and resolving its binding; "
            "supplying it as an input steps over both, so nothing this scenario asserts speaks to how the casilla "
            "is produced. Record each casilla in chain_resolved_bound_casillas naming the resolver that produced "
            "it, or in hand_typed_bound_casillas with the reason this scenario supplies it instead.",
        )

    stale = sorted(declared - bound)
    if stale:
        raise RegistryValidationError(
            f"scenario {scenario.id!r} declares bound-casilla provenance for casillas revision {revision.id!r} does "
            f"not declare bound: {stale!r}. The declaration has outlived the binding it described; drop it.",
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
            f"expected operand casillas {expected.operand_casilla_refs!r} but got {actual_operand_casilla_refs!r}",
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
