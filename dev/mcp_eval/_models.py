"""Typed models for the operator golden-task eval.

A :class:`GoldenScenario` is the declared expectation for one workflow: the modelo
context, the expected tool trajectory (in registry-key form), and whether the
result must carry registry provenance. A :class:`GoldenResult` is the runner's
per-dimension verdict.

:class:`ExitCodeScenario` and :class:`ExitCodeVerdict` verify that a non-zero
CLI exit code paired with a well-formed JSON body is a domain verdict the
operator must act on, not a crash to abort on.

:class:`ContradictionScenario` and :class:`ContradictionVerdict` verify wrong
lifecycle sequencing / cross-surface contradiction handling: when one surface
(e.g. ``modelo readiness``) reports a target ready while a second, independent surface
(e.g. ``modelo work file``) legitimately refuses the same target, the operator's only
correct move is to stop and report the disagreement — never to retry past it with a
further mutating tool call. This is the enforcement surface for the
``cadrumo-operator-lifecycle-ordering`` rule's "Contradictions between surfaces are a stop, not
a retry" rule the operating agent carries. This
pair follows the standalone ``check_*_scenario`` shape used by
:class:`ExitCodeScenario`/:class:`ExitCodeVerdict` and
:class:`UnderDeclarationScenario`/:class:`UnderDeclarationVerdict` rather
than being threaded through :class:`GoldenScenario`/:class:`GoldenResult`: a
cross-surface contradiction is not a property of one modelo-preparation workflow's
expected trajectory, it is a distinct assertion over two independently dispatched
responses plus a candidate post-contradiction trajectory.

:class:`ProfileConfirmationScenario` and :class:`ProfileConfirmationVerdict` verify
auth / profile / state confusion handling: "wrong active profile
silently shows another taxpayer's data" - the cross-tenant data leak, critical for a
gestor's multi-taxpayer use of the harness. ``docs/how-to/troubleshooting.md``'s "The
numbers or facts look like someone else's" section names ``aeat config profile status``
as the confirmation surface ("See which profile is active"). This pair follows the same
standalone ``check_*_scenario`` shape as :class:`ContradictionScenario` /
:class:`ContradictionVerdict` rather than being threaded through
:class:`GoldenScenario`/:class:`GoldenResult`: the property under test is a
required-prefix ordering constraint over an observed trajectory (the active-profile
confirmation command must precede the first mutating verb), not a property of one
modelo-preparation workflow's expected trajectory.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cadrumo.core.json_contract import EnvelopeStatus
from cadrumo.core.operator_action_enums import NoRecoveryOutcome

if TYPE_CHECKING:
    from cadrumo.application.operator_actions.models import PreconditionVerdict

    from ._action_coverage import LeafConditionScenario

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

LIFECYCLE_STAGE_ORDER: tuple[str, ...] = (
    "modelo.work.create",
    "modelo.work.calculate",
    "modelo.work.verify",
    "modelo.export",
)
"""Canonical command-stage order shared by declared and observed eval trajectories."""


def lifecycle_stages_in_canonical_order(positions: Mapping[str, int]) -> bool:
    """True when the lifecycle stages present in ``positions`` hold the canonical order.

    The one ordering predicate both trajectory dimensions share: the declared
    runner asserts it over a scenario's ``expected_trajectory``, the live scorer
    over the keys a persona actually issued. Stages ABSENT from ``positions``
    are unconstrained - a trajectory that legitimately stops at ``verify`` is
    ordered - so this asks only that the stages which do appear appear in order.
    """
    present = [stage for stage in LIFECYCLE_STAGE_ORDER if stage in positions]
    return all(positions[earlier] < positions[later] for earlier, later in pairwise(present))


class GoldenScenario(BaseModel):
    """One declared workflow expectation, loaded from a scenario TOML file.

    Attributes:
        name: Scenario identifier (e.g. ``"modelo-130-direct-estimation"``).
        modelo: The AEAT modelo code the workflow prepares (e.g. ``"130"``).
        filing_year: The filing year the scenario resolves the revision for.
        period: The AEAT period token (e.g. ``"1T"``).
        expected_trajectory: The ordered tool trajectory in registry-key form
            (e.g. ``("modelo.work.create", "modelo.work.calculate", ...)``).
        provenance_required: When true, every casilla on the resolved revision
            must carry non-empty ``legal_refs`` and ``source_refs``.
        expected_computed_casillas: Casilla ids the workflow expects the calculate
            step to compute and verify. Each must appear in the resolved revision's
            AEAT-grounded verification contract (``computed_casilla_ids``); empty
            disables the cross-check.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1)
    expected_trajectory: tuple[str, ...] = Field(min_length=1)
    provenance_required: bool = True
    expected_computed_casillas: tuple[str, ...] = ()


class GoldenResult(BaseModel):
    """Per-dimension verdict for one golden scenario run.

    Each boolean is one assertion dimension; ``failures`` carries a human-readable
    reason for every dimension that did not hold. The scenario passes only when
    every dimension is true.

    ``provenance_present`` and ``response_provenance_present`` are deliberately
    distinct dimensions. ``provenance_present`` inspects the REGISTRY snapshot
    (proves the registry itself is grounded); ``response_provenance_present``
    inspects the dispatched calculate RESPONSE payload the operator actually
    reads (proves the CLI/MCP layer relayed that grounding rather than dropping
    it on the way out). The real repro this dimension closes: a real M130
    calculate returned correct casilla values but no ``legal_refs`` /
    ``formula_id`` at the CLI layer.
    """

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    trajectory_resolves: bool
    lifecycle_ordered: bool
    provenance_present: bool
    response_provenance_present: bool
    verification_grounded: bool
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when every assertion dimension held and no failures were recorded."""
        return self._workflow_dimensions_passed and not self.failures

    @property
    def _workflow_dimensions_passed(self) -> bool:
        """Require the ordered workflow and evidence dimensions first."""
        return (
            self.trajectory_resolves
            and self.lifecycle_ordered
            and self.provenance_present
            and self.response_provenance_present
            and self.verification_grounded
        )


class ExitCodeScenario(BaseModel):
    """A declared expectation that a non-zero CLI exit code is a verdict, not a crash.

    Guards against exit-code misread as crash: a command such
    as ``modelo.work.verify`` legitimately raises a non-zero process exit code
    when findings exist, while still emitting a well-formed JSON envelope on
    stdout. This scenario declares the exit code that legitimately signals a
    verdict, the envelope ``status`` that verdict must carry, and the exact
    production ``(leaf, condition, scenario)`` row whose observed outcome is
    asserted. The row resolves through the live action-coverage matrix; this
    scenario deliberately cannot name its own continuation command or action.

    Attributes:
        name: Scenario identifier (e.g. ``"m130-verify-cross-period-unclean"``).
        command: The registry command key whose dispatch is under test (e.g.
            ``"modelo.work.verify"``).
        expected_exit_code: The process exit code the dispatch must return.
            Must be non-zero: an exit-code-as-verdict scenario is meaningless
            for a clean-success (``0``) exit.
        tool_result_status: The envelope ``status`` the JSON body must carry.
            Never :attr:`~core.json_contract.EnvelopeStatus.SUCCESS` - a
            non-zero exit paired with a "success" status would itself be the
            silent-crash-vs-verdict confusion this scenario exists to catch.
        leaf_condition_scenario: The S42 production matrix identity that
            declares the failed condition and either its canonical recovery
            action or its explicit no-recovery outcome.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    command: str = Field(min_length=1)
    expected_exit_code: int = Field(gt=0, le=255)
    tool_result_status: EnvelopeStatus
    leaf_condition_scenario: tuple[str, str, str]

    @field_validator("leaf_condition_scenario")
    @classmethod
    def _require_complete_production_identity(cls, value: tuple[str, str, str]) -> tuple[str, str, str]:
        if any(not part.strip() for part in value):
            raise ValueError("leaf_condition_scenario must contain three non-blank production identities")
        return value

    @model_validator(mode="after")
    def _reject_success_status_for_a_verdict_scenario(self) -> ExitCodeScenario:
        if self.tool_result_status is EnvelopeStatus.SUCCESS:
            raise ValueError(
                "an ExitCodeScenario declares a non-zero expected_exit_code; "
                "tool_result_status must not be EnvelopeStatus.SUCCESS "
                "(that would itself be the exit-code-as-crash confusion this "
                "scenario proves against)",
            )
        return self


class ObservedProductionActionAssertion(BaseModel):
    """One observed verdict compared with its resolved production profile.

    The report contains only the matrix identity, observed values, and derived
    matches. It has no expected-action field: the expected action and closed
    outcome remain inside the S42 resolved production profile used by
    :func:`observe_production_action`.
    """

    model_config = _STRICT_FROZEN

    leaf_condition_scenario: tuple[str, str, str]
    observed_condition_id: str = Field(min_length=1)
    observed_action_id: str | None = None
    observed_no_recovery_outcome: NoRecoveryOutcome | None = None
    condition_matches: bool
    action_matches: bool
    no_recovery_outcome_matches: bool

    @field_validator("leaf_condition_scenario")
    @classmethod
    def _require_complete_identity(cls, value: tuple[str, str, str]) -> tuple[str, str, str]:
        if any(not part.strip() for part in value):
            raise ValueError("leaf_condition_scenario must contain three non-blank production identities")
        return value

    @model_validator(mode="after")
    def _require_one_observed_outcome(self) -> ObservedProductionActionAssertion:
        if (self.observed_action_id is None) == (self.observed_no_recovery_outcome is None):
            raise ValueError("observed production verdict requires exactly one action or no-recovery outcome")
        return self

    @property
    def passed(self) -> bool:
        """True when the actual condition and outcome exactly match production."""
        return self.condition_matches and self.action_matches and self.no_recovery_outcome_matches


def observe_production_action(
    coverage: LeafConditionScenario,
    verdict: PreconditionVerdict,
) -> ObservedProductionActionAssertion:
    """Compare an actual verdict with its S42-resolved production declaration.

    The function takes the live matrix row rather than caller-supplied expected
    action data. It stays lazily typed so importing the general evaluator model
    surface does not eagerly materialise the application/CLI operator surface.
    """
    declared = coverage.profile.declaration
    observed_action_id = verdict.action.action_id if verdict.action is not None else None
    declared_action_id = declared.action.action_id if declared.action is not None else None
    return ObservedProductionActionAssertion(
        leaf_condition_scenario=coverage.identity,
        observed_condition_id=verdict.failed_condition_id,
        observed_action_id=observed_action_id,
        observed_no_recovery_outcome=verdict.no_recovery_outcome,
        condition_matches=verdict.failed_condition_id == declared.condition_id,
        action_matches=observed_action_id == declared_action_id,
        no_recovery_outcome_matches=verdict.no_recovery_outcome == declared.no_recovery_outcome,
    )


class ExitCodeVerdict(BaseModel):
    """Per-dimension verdict for one :class:`ExitCodeScenario` run.

    Each boolean is one assertion dimension over a REAL dispatched CLI
    invocation's exit code and decoded JSON envelope; ``failures`` carries a
    human-readable reason for every dimension that did not hold. The scenario
    passes only when every dimension is true.
    """

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    exit_code_matches: bool
    envelope_well_formed: bool
    status_is_non_success: bool
    production_action_assertion: ObservedProductionActionAssertion
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when every assertion dimension held and no failures were recorded."""
        return (
            self.exit_code_matches
            and self.envelope_well_formed
            and self.status_is_non_success
            and self.production_action_assertion.passed
            and not self.failures
        )


class UnderDeclarationScenario(BaseModel):
    """A declared expectation that ``verify`` surfaces an advisory for a cascading zero.

    This is the highest-severity legal-soundness dimension: an autonomous
    agent must not read a well-formed ``modelo.work.verify`` response as
    "safe to file" when a positive economic input cascades to a zero
    dependent casilla with no offsetting reduction declared. A positive
    resultado contable with the fiscal-base starting point left at manual
    zero must surface an ADVISORY finding, never a silent zero-finding grant.

    Attributes:
        name: Scenario identifier.
        command: The registry command key whose dispatch is under test (e.g.
            ``"modelo.work.verify"``).
        expected_legal_refs: The legal references the fired ADVISORY finding
            must cite. Grounds the check to the SPECIFIC declared handoff this
            scenario exercises (rather than accepting any stray advisory),
            the same discipline the registry calculation itself must satisfy.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    command: str = Field(min_length=1)
    expected_legal_refs: tuple[str, ...] = Field(min_length=1)


class UnderDeclarationVerdict(BaseModel):
    """Per-dimension verdict for one :class:`UnderDeclarationScenario` run.

    Each boolean is one assertion dimension over a REAL dispatched
    ``modelo.work.verify`` response's decoded JSON ``findings`` rows;
    ``failures`` carries a human-readable reason for every dimension that did
    not hold. The scenario passes only when every dimension is true.
    """

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    not_silently_clean: bool
    advisory_finding_present: bool
    legal_refs_grounded: bool
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when every assertion dimension held and no failures were recorded."""
        return (
            self.not_silently_clean and self.advisory_finding_present and self.legal_refs_grounded and not self.failures
        )


class ContradictionScenario(BaseModel):
    """A declared expectation that a signalled cross-surface contradiction halts the trajectory.

    Guards against wrong lifecycle sequencing / cross-surface
    contradiction: a readiness-shaped signal (``readiness_step``) and a second,
    independent, legitimately-blocking signal (``blocking_step``) may disagree — one
    reports the target ready, the other refuses it. ``cadrumo-operator-lifecycle-ordering``
    makes the disagreement itself, not either signal alone, the trigger: the operator
    must stop and report, never retry past it. ``must_halt_after`` names the trajectory
    position the disagreement is anchored to; ``mutating_commands`` is the scenario's own
    declared closed set of registry command keys that count as a further mutating attempt
    for this scenario (caller-supplied, e.g. derived from the real
    ``OperatorMutability``-derived command classification).

    Attributes:
        name: Scenario identifier.
        readiness_step: The registry command key for the readiness-shaped signal (e.g.
            ``"modelo.readiness"``).
        blocking_step: The registry command key for the second, independent signal that
            legitimately refuses the same target (e.g. ``"modelo.work.file"``).
        must_halt_after: The registry command key in the observed trajectory after which
            no member of ``mutating_commands`` may appear once the contradiction fires.
            Ordinarily equal to ``blocking_step`` (halt right after the refusal is
            observed), declared separately so a scenario can anchor the halt boundary to
            a later checkpoint if its trajectory narrates one.
        mutating_commands: The closed set of registry command keys this scenario treats
            as a further mutating attempt (a retry, a tweaked recalculation, an export)
            that must not appear after ``must_halt_after``.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    readiness_step: str = Field(min_length=1)
    blocking_step: str = Field(min_length=1)
    must_halt_after: str = Field(min_length=1)
    mutating_commands: tuple[str, ...] = Field(min_length=1)


class ContradictionVerdict(BaseModel):
    """Per-dimension verdict for one :class:`ContradictionScenario` run.

    Each boolean is one assertion dimension over REAL caller-dispatched signals plus a
    caller-supplied candidate trajectory; ``failures`` carries a human-readable reason
    for every dimension that did not hold. The scenario passes only when every dimension
    is true.
    """

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    contradiction_confirmed: bool
    halt_boundary_resolved: bool
    halted_after_contradiction: bool
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when a genuine contradiction was confirmed and the trajectory halted after it."""
        return (
            self.contradiction_confirmed
            and self.halt_boundary_resolved
            and self.halted_after_contradiction
            and not self.failures
        )


class ProfileConfirmationScenario(BaseModel):
    """A declared expectation that active-profile confirmation precedes each mutation.

    Guards against auth / profile / state confusion - the
    wrong-active-profile cross-tenant data leak: "wrong active profile silently shows
    another taxpayer's data." A gestor operating the harness across several taxpayer
    profiles must never let an autonomous agent run a mutating command sequence without
    first confirming which profile is active - a silent wrong-profile mutation writes
    (or reads) one taxpayer's data under another's identity.

    Attributes:
        name: Scenario identifier.
        confirmation_command: The registry command key for the active-profile
            confirmation step (e.g. ``"config.profile.status"`` - the command
            ``docs/how-to/troubleshooting.md`` names to "see which profile is active").
        mutating_commands: The scenario's own declared closed set of registry command
            keys that count as a mutating verb for this scenario (caller-supplied, e.g.
            derived from the real MCP tool-descriptor mutability classification,
            mirroring how :class:`ContradictionScenario.mutating_commands` is declared
            scenario data rather than resolved by this module).
        profile_switching_commands: Registry command keys that switch the active
            profile and therefore require a new confirmation before a later mutation.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    confirmation_command: str = Field(min_length=1)
    mutating_commands: tuple[str, ...] = Field(min_length=1)
    profile_switching_commands: tuple[str, ...] = ()


class ProfileConfirmationVerdict(BaseModel):
    """Per-dimension verdict for one :class:`ProfileConfirmationScenario` run.

    Each boolean is one assertion dimension over an observed trajectory (real,
    caller-dispatched command keys in the order they were actually run); ``failures``
    carries a human-readable reason for every dimension that did not hold. The scenario
    passes only when every dimension is true.
    """

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    confirmation_command_resolves: bool
    profile_switching_commands_resolve: bool
    mutating_step_present: bool
    confirmed_before_first_mutation: bool
    confirmed_before_each_mutation: bool
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when every exercised mutation followed a valid active-profile confirmation."""
        return (
            self.confirmation_command_resolves
            and self.profile_switching_commands_resolve
            and self.mutating_step_present
            and self.confirmed_before_first_mutation
            and self.confirmed_before_each_mutation
            and not self.failures
        )
