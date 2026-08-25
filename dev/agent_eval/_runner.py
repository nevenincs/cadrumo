"""Runner for the operator golden-task eval.

Boundary posture: ``dev.agent_eval`` is a CONSUMER of the shipped surfaces, never
a reach around them. Harness-owned material (skills, personas, operator rules)
comes from the ``cadrumo_harness`` distribution's public facade; taxpayer- and
application-state material comes from the real ``aeat`` CLI / MCP dispatch the
caller performs; and this module imports nothing from ``cadrumo``'s adapters,
application or entrypoints layers.

Pure with respect to the CLI: the set of resolvable command keys is injected by
the caller (the test wires it from the live CLI schema registry), so this module
never imports the entrypoints layer. The registry snapshot it reads for the
provenance and verification-contract dimensions is a pure registry read through
the public ``cadrumo.core.resources`` facade and needs no profile or secret
storage; it stays a direct read because no CLI verb projects a revision's
``verification_expectations``, and the CLI-boundary half of the same question is
already covered by the separate response-provenance dimension below. The
response-provenance dimension follows the injection pattern: the caller
dispatches a real ``modelo.work.calculate`` through the actual CLI/MCP command
handling and passes the decoded JSON ``observations`` rows in; this module only
asserts over the already-fetched rows and never dispatches the call itself. The
narration-faithfulness dimension (eval-catalogue category 9) follows the
identical pattern one layer further: the caller runs the real
``cadrumo_harness.mcp._faithfulness.faithfulness_check`` against a narration and
the captured calculate JSON, and passes the per-step verdict in - this module
never imports the MCP server layer and never runs the check itself. The
confirmation-gate dimension (eval-catalogue category 8) follows the same pattern
once more: the caller invokes the real
``cadrumo_harness.mcp._hitl.confirmation_for_tool`` for a step and hands the
resulting tier in as a :class:`~dev.agent_eval._models.ConfirmationGateCheck`;
this module never imports the MCP server layer and never resolves a confirmation
tier itself. The contradiction dimension (eval-catalogue category 4) follows the
same pattern: the caller dispatches two independent real CLI/MCP invocations for
the same target (a readiness-shaped signal and a second, legitimately-blocking
signal) and passes in whether each reported ready / refused, plus a candidate
ordered trajectory; this module never dispatches either call itself and never
decides what counts as a mutating command (that closed set rides on the scenario,
caller-declared). The active-profile-confirmation dimension (eval-catalogue category
5) follows the same injection pattern once more: the caller dispatches a real ordered
trajectory of CLI/MCP invocations (the active-profile confirmation command plus zero or
more mutating commands) and passes the observed command-key sequence in; this module
never dispatches any call itself and, like the contradiction dimension, never decides
what counts as a mutating command (that closed set rides on the scenario).
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from cadrumo_harness import iter_skill_documents
from pydantic import BaseModel, ConfigDict

from cadrumo.core.external_constants import UTF_8_ENCODING as _UTF_8
from cadrumo.core.json_contract import EnvelopeStatus, ResolvedActionArgument
from cadrumo.core.resources import resources

from ._models import (
    LIFECYCLE_STAGE_ORDER,
    ConfirmationGateCheck,
    ContradictionScenario,
    ContradictionVerdict,
    ExitCodeScenario,
    ExitCodeVerdict,
    GoldenResult,
    GoldenScenario,
    NarrationFaithfulness,
    ProfileConfirmationScenario,
    ProfileConfirmationVerdict,
    UnderDeclarationScenario,
    UnderDeclarationVerdict,
    lifecycle_stages_in_canonical_order,
)

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


def load_scenario(path: Path) -> GoldenScenario:
    """Load and validate a :class:`GoldenScenario` from a scenario TOML file.

    TOML arrays parse as ``list``; the strict scenario model takes a ``tuple``, so
    the trajectory array is coerced before validation.
    """
    payload = tomllib.loads(path.read_text(encoding=_UTF_8))
    for key in ("expected_trajectory", "expected_computed_casillas"):
        value = payload.get(key)
        if isinstance(value, list):
            payload[key] = tuple(value)
    return GoldenScenario.model_validate(payload)


def _cli_form(command_key: str) -> str:
    """Render a registry command key as its ``aeat app ...`` CLI form."""
    return "aeat app " + command_key.replace(".", " ")


def _skill_text(skill_name: str) -> str | None:
    for skill in iter_skill_documents():
        # Each skill's SKILL.md lives under skills/<skill_name>/SKILL.md.
        if skill_name in _skill_path_parts(skill):
            return skill.read_text(encoding=_UTF_8)
    return None


def _skill_path_parts(skill: object) -> set[str]:
    # ``Traversable`` does not expose a parent reliably across backends; recover the
    # owning skill directory name from the joined path string.
    text = str(skill)
    return set(text.replace("\\", "/").split("/"))


def _resolve_revision(scenario: GoldenScenario) -> object:
    """Load the registry revision the scenario resolves to (pure registry read)."""
    snapshot = resources().modelos.authority.snapshot(
        scenario.modelo,
        filing_year=scenario.filing_year,
        period=scenario.period,
    )
    return snapshot.revision


def _check_provenance(scenario: GoldenScenario, revision: object, failures: list[str]) -> bool:
    casillas: Iterable[object] = _iter_casillas(getattr(revision, "casillas", ()))
    ungrounded = 0
    for casilla in casillas:
        legal_refs = getattr(casilla, "legal_refs", ())
        source_refs = getattr(casilla, "source_refs", ())
        if not legal_refs or not source_refs:
            ungrounded += 1
    if ungrounded:
        failures.append(
            f"{ungrounded} casilla(s) on {scenario.modelo} {scenario.period} lack legal_refs/source_refs",
        )
        return False
    return True


def _observation_field(observation: object, field: str) -> object:
    if isinstance(observation, Mapping):
        return observation.get(field)
    return getattr(observation, field, None)


def _check_response_provenance(
    scenario: GoldenScenario,
    response_observations: tuple[object, ...] | None,
    failures: list[str],
) -> bool:
    """Assert the dispatched calculate RESPONSE payload itself carries provenance.

    Distinct from :func:`_check_provenance`, which inspects the REGISTRY
    snapshot and proves the registry itself is grounded. This dimension
    inspects the decoded JSON ``observations`` rows from a real
    ``modelo.work.calculate`` CLI/MCP dispatch - the payload the operator
    actually reads - and proves the CLI/MCP boundary relayed the registry's
    ``legal_refs``/``source_refs`` and computed-casilla ``formula_id`` rather
    than dropping them on the way out
    (the real repro: a real M130 calculate returned correct casilla values
    but no ``legal_refs``/``formula_id`` at the CLI layer).

    ``response_observations`` is caller-injected (mirroring ``valid_commands``):
    when the caller has not dispatched a live calculate for this run, it is
    ``None`` and the dimension holds trivially - this module never dispatches
    the call itself.
    """
    if response_observations is None:
        return True
    if not response_observations:
        failures.append(
            f"{scenario.modelo} {scenario.period} calculate RESPONSE payload carried zero observations",
        )
        return False
    ungrounded = 0
    expected_computed = set(scenario.expected_computed_casillas)
    expected_computed_seen: set[str] = set()
    computed_without_formula: list[str] = []
    for observation in response_observations:
        legal_refs = _observation_field(observation, "legal_refs")
        source_refs = _observation_field(observation, "source_refs")
        if not legal_refs or not source_refs:
            ungrounded += 1
        casilla_id = _observation_field(observation, "casilla_id")
        if casilla_id is None or str(casilla_id) not in expected_computed:
            continue
        casilla_id_text = str(casilla_id)
        expected_computed_seen.add(casilla_id_text)
        formula_id = _observation_field(observation, "formula_id")
        if not formula_id:
            computed_without_formula.append(casilla_id_text)
    if ungrounded:
        failures.append(
            f"{ungrounded} observation(s) in the {scenario.modelo} {scenario.period} calculate RESPONSE "
            "payload lack legal_refs/source_refs",
        )
        return False
    missing_computed = sorted(expected_computed - expected_computed_seen)
    if computed_without_formula or missing_computed:
        details: list[str] = []
        if computed_without_formula:
            details.append("missing formula_id: " + ", ".join(sorted(computed_without_formula)))
        if missing_computed:
            details.append("absent from RESPONSE observations: " + ", ".join(missing_computed))
        failures.append(
            f"{scenario.modelo} {scenario.period} calculate RESPONSE payload lacks computed-casilla "
            f"formula provenance ({'; '.join(details)})",
        )
        return False
    return True


def _check_narration_faithfulness(
    scenario: GoldenScenario,
    narration_faithfulness_checks: tuple[NarrationFaithfulness, ...],
    failures: list[str],
) -> None:
    """Assert every hard-blocking narration-faithfulness check is reported as a failure.

    Closes eval-catalogue category 9. Each :class:`NarrationFaithfulness` is a
    caller-injected verdict (mirroring ``response_observations``): the caller
    dispatched a real ``modelo.work.calculate``, ran the real
    ``faithfulness_check`` from a narration against that captured JSON, and
    handed the per-step result in. This function performs no check itself; it
    only decides whether a ``blocks`` verdict fails the scenario.

    An advisory (non-blocking) unfaithful check is INTENTIONALLY not appended to
    ``failures``: it is a warning, not a scenario failure, everywhere except the
    irreversible handoff step. Only a ``blocks`` verdict (the handoff step's
    narration citing an ungrounded numeric) fails the scenario.
    """
    for check in narration_faithfulness_checks:
        if not check.blocks:
            continue
        failures.append(
            f"{scenario.modelo} {scenario.period} narration at step '{check.step}' cites "
            f"value(s) {', '.join(check.flagged_values)} absent from the tool result on the "
            "irreversible handoff step - hard-blocked by faithfulness enforcement",
        )


def _check_confirmation_gate_checks(
    scenario: GoldenScenario,
    expected_confirmation_tiers: tuple[ConfirmationGateCheck, ...],
    failures: list[str],
) -> None:
    """Assert every injected confirmation-gate check resolved its expected tier.

    Closes eval-catalogue category 8. Each :class:`ConfirmationGateCheck` is a
    caller-injected verdict (mirroring ``narration_faithfulness_checks``): the
    caller resolved a step's real ``confirmation_for_tool`` decision and handed
    the ``(expected_tier, actual_tier)`` pair in. This function performs no
    resolution itself; it only decides whether a mismatch fails the scenario.

    A mismatch means the ``PreToolUse`` gate would not enforce the tier the
    workflow relies on for that step - an auto-approved handoff, an
    unnecessarily-gated read, or (most severe) a live-write leaf that resolved to
    anything other than an unconditional block.
    """
    for check in expected_confirmation_tiers:
        if check.matches:
            continue
        failures.append(
            f"{scenario.modelo} {scenario.period} step '{check.step}' resolved confirmation tier "
            f"'{check.actual_tier.value}', expected '{check.expected_tier.value}' - the PreToolUse "
            "gate would not enforce the tier this workflow relies on",
        )


def _check_verification_contract(scenario: GoldenScenario, revision: object, failures: list[str]) -> bool:
    """Assert the revision declares an AEAT-grounded verification contract.

    The registry bundles no numeric worked examples (a figure-level oracle is a
    separate AEAT-corpus concern); what it does carry is each revision's
    ``verification_expectations`` - the computed-and-reconciled casilla set with
    AEAT ``source_refs`` and a tolerance. This dimension proves the operator's
    calculate/verify step has that grounded reconciliation target, and that the
    scenario's declared ``expected_computed_casillas`` are within it.
    """
    expectations = tuple(getattr(revision, "verification_expectations", ()) or ())
    computed: set[str] = set()
    grounded = False
    for expectation in expectations:
        ids = tuple(getattr(expectation, "computed_casilla_ids", ()) or ())
        source_refs = tuple(getattr(expectation, "source_refs", ()) or ())
        computed |= {str(i) for i in ids}
        if ids and source_refs:
            grounded = True
    if not grounded:
        failures.append(
            f"{scenario.modelo} {scenario.period} declares no AEAT-grounded verification "
            "contract (computed_casilla_ids with source_refs)",
        )
        return False
    missing = [c for c in scenario.expected_computed_casillas if c not in computed]
    if missing:
        failures.append(
            "scenario expected_computed_casillas absent from the registry's AEAT-grounded "
            f"computed set: {', '.join(missing)}",
        )
        return False
    return True


def _check_trajectory_resolution(
    scenario: GoldenScenario,
    valid_commands: frozenset[str],
    failures: list[str],
) -> bool:
    """Assert every verb the scenario declares resolves against the live CLI surface."""
    unresolved = [verb for verb in scenario.expected_trajectory if verb not in valid_commands]
    if not unresolved:
        return True
    failures.append(f"trajectory cites unresolved command keys: {', '.join(unresolved)}")
    return False


def _check_declared_lifecycle_order(scenario: GoldenScenario, failures: list[str]) -> bool:
    """Assert the DECLARED trajectory visits each lifecycle stage once, in order.

    Two distinct ways to break the contract, reported distinctly: declaring a
    stage twice is an authoring error in the scenario itself (a stage has no
    defined position once it appears twice), so it is reported as a duplicate
    rather than as an ordering violation, and the ordering check is skipped
    because it would be meaningless.
    """
    declared_stages = tuple(stage for stage in scenario.expected_trajectory if stage in LIFECYCLE_STAGE_ORDER)
    duplicate_stages = tuple(stage for stage in LIFECYCLE_STAGE_ORDER if declared_stages.count(stage) > 1)
    if duplicate_stages:
        failures.append(
            "trajectory declares lifecycle stage(s) more than once: " + ", ".join(duplicate_stages),
        )
        return False

    positions = {verb: index for index, verb in enumerate(scenario.expected_trajectory)}
    if lifecycle_stages_in_canonical_order(positions):
        return True
    failures.append("trajectory violates the create -> calculate -> verify -> export lifecycle order")
    return False


def _check_skill_consistency(scenario: GoldenScenario, failures: list[str]) -> bool:
    """Assert the shipped skill playbook cites every verb the trajectory declares.

    The operator follows the skill, so a trajectory verb the playbook never
    mentions is a workflow the operator has no documented route to.
    """
    skill_text = _skill_text(scenario.skill_name)
    if skill_text is None:
        failures.append(f"skill '{scenario.skill_name}' not found among shipped skills")
        return False
    missing = [verb for verb in scenario.expected_trajectory if _cli_form(verb) not in skill_text]
    if not missing:
        return True
    failures.append(
        "skill playbook does not cite trajectory verbs: " + ", ".join(_cli_form(v) for v in missing),
    )
    return False


def _iter_casillas(casillas: object) -> Iterable[object]:
    if isinstance(casillas, dict):
        return tuple(casillas.values())
    # ``casillas`` is typed ``object`` at this parse boundary (raw scenario
    # source value); in practice it is always a list or tuple (the registry's
    # ``ModeloRevision.casillas: tuple[CasillaDefinition, ...]``, or the
    # caller's ``()`` default), never any other shape.
    if isinstance(casillas, list | tuple):
        return tuple(casillas)
    return ()


def run_golden_scenario(
    scenario: GoldenScenario,
    *,
    valid_commands: frozenset[str],
    response_observations: tuple[object, ...] | None = None,
    narration_faithfulness_checks: tuple[NarrationFaithfulness, ...] = (),
    expected_confirmation_tiers: tuple[ConfirmationGateCheck, ...] = (),
) -> GoldenResult:
    """Run one golden scenario and return its per-dimension verdict.

    Args:
        scenario: The declared workflow expectation.
        valid_commands: The set of resolvable registry command keys, injected by
            the caller from the live CLI schema registry.
        response_observations: The decoded JSON ``observations`` rows from a real
            ``modelo.work.calculate`` CLI/MCP dispatch, injected by the caller.
            ``None`` (the default) skips the response-provenance dimension - this
            module never dispatches the calculate call itself.
        narration_faithfulness_checks: Zero or more per-step
            :class:`NarrationFaithfulness` verdicts, injected by the caller after
            running the real ``faithfulness_check`` against a narration and the
            captured calculate JSON. Empty (the default) skips the dimension -
            this module never runs the faithfulness check itself.
        expected_confirmation_tiers: Zero or more per-step
            :class:`ConfirmationGateCheck` verdicts, injected by the caller after
            resolving a step's real ``confirmation_for_tool`` decision. Empty (the
            default) skips the dimension - this module never resolves a
            confirmation tier itself.

    Returns:
        A :class:`GoldenResult` whose ``passed`` is true only when the trajectory
        resolves, follows the lifecycle order, is consistent with the shipped
        skill, the revision's casillas carry provenance (when required), the
        RESPONSE payload's own observations carry that same provenance (when a
        live response was dispatched), no injected narration-faithfulness check
        hard-blocks (an advisory-only unfaithful check does not fail the
        scenario), and every injected confirmation-gate check resolved
        the tier the workflow relies on.
    """
    failures: list[str] = []

    trajectory_resolves = _check_trajectory_resolution(scenario, valid_commands, failures)

    lifecycle_ordered = _check_declared_lifecycle_order(scenario, failures)

    skill_consistent = _check_skill_consistency(scenario, failures)

    revision = _resolve_revision(scenario)

    provenance_present = True
    if scenario.provenance_required:
        provenance_present = _check_provenance(scenario, revision, failures)

    verification_grounded = _check_verification_contract(scenario, revision, failures)

    response_provenance_present = _check_response_provenance(scenario, response_observations, failures)

    _check_narration_faithfulness(scenario, narration_faithfulness_checks, failures)

    _check_confirmation_gate_checks(scenario, expected_confirmation_tiers, failures)

    return GoldenResult(
        scenario=scenario.name,
        trajectory_resolves=trajectory_resolves,
        lifecycle_ordered=lifecycle_ordered,
        skill_consistent=skill_consistent,
        provenance_present=provenance_present,
        response_provenance_present=response_provenance_present,
        verification_grounded=verification_grounded,
        narration_faithfulness_checks=narration_faithfulness_checks,
        expected_confirmation_tiers=expected_confirmation_tiers,
        failures=tuple(failures),
    )


def _envelope_field(envelope: Mapping[str, object], field: str) -> object:
    return envelope.get(field)


def _canonical_action_arguments(
    *,
    cli_path: tuple[str, ...],
    argument_bindings: tuple[ResolvedActionArgument, ...],
) -> tuple[str, ...]:
    """Materialise a resolved action through the live command graph.

    The action resolver is the authority for binding completeness and source
    provenance; the command graph is the authority for positional versus option
    syntax.  This helper deliberately has no action- or command-specific branch.
    """
    from cadrumo.core import PRODUCT_IDENTITY, ActionArgumentStatus
    from cadrumo.entrypoints.cli import command_graph

    values: dict[str, object] = {}
    for binding in argument_bindings:
        name = binding.argument_name
        status = binding.status
        value = binding.value
        if status is not ActionArgumentStatus.RESOLVED or value is None:
            raise ValueError(f"canonical recovery has no concrete value for argument: {name}")
        values[name] = value

    command = command_graph.resolve_path((PRODUCT_IDENTITY.cli_executable, *cli_path))
    arguments: list[str] = []
    consumed: set[str] = set()
    for parameter in command.parameters:
        name = parameter.name
        if name not in values:
            continue
        value = values[name]
        consumed.add(name)
        if parameter.kind == "argument":
            arguments.append(str(value))
            continue

        declarations = parameter.declarations
        long_options = tuple(declaration for declaration in declarations if declaration.startswith("--"))
        if not long_options:
            raise ValueError(f"canonical recovery option has no long declaration: {name}")
        if parameter.is_flag:
            if not isinstance(value, bool):
                raise ValueError(f"canonical recovery flag requires a bool value: {name}")
            if value:
                arguments.append(long_options[0])
            continue
        arguments.extend((long_options[0], str(value)))

    unmatched = sorted(set(values) - consumed)
    if unmatched:
        raise ValueError("canonical recovery bindings do not map to live CLI parameters: " + ", ".join(unmatched))
    return tuple(arguments)


def _invoke_canonical_cli(argv: Sequence[str]):
    """Run the live CLI command tree once, requesting its canonical JSON envelope."""
    from click.testing import CliRunner

    from cadrumo.entrypoints.cli import full_command_tree

    return CliRunner().invoke(full_command_tree(), ["--format", "json", *argv])


def _decoded_envelope(output: str) -> Mapping[str, object] | None:
    """Return one actual JSON envelope, without accepting a fabricated substitute."""
    try:
        decoded = json.loads(output)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, Mapping) else None


def _safe_to_execute(cli_path: tuple[str, ...]) -> bool:
    """Read recovery safety from the command graph's execution-policy authority."""
    from cadrumo.entrypoints.cli import command_execution_policy_for_cli_path

    policy = command_execution_policy_for_cli_path(cli_path)
    return not (policy.destructive or policy.handoff or policy.live_write)


def _retry_uses_subject_leaf(*, original_argv: Sequence[str], subject_cli_path: tuple[str, ...]) -> bool:
    """Require the retry to invoke the same canonical leaf the scenario observed."""
    return tuple(original_argv[: len(subject_cli_path)]) == subject_cli_path


def _execute_safe_recovery_and_retry(
    *,
    scenario: ExitCodeScenario,
    original_argv: Sequence[str],
    precondition_verdict: object,
    subject_cli_path: tuple[str, ...],
    failures: list[str],
) -> None:
    """Validate, execute, and observe one immediate safe canonical recovery.

    There is deliberately no caller-supplied recovery command or executor.  The
    existing CLI resolver validates the live catalogue bindings, the command
    policy decides whether dispatch is safe, and the live command tree performs
    both the recovery and the retry.  A terminal/safety/operator-decision outcome
    has no action and therefore cannot reach this function.
    """
    from cadrumo.core import ActionArgumentStatus, ActionConditionality
    from cadrumo.entrypoints.cli import resolve_cli_precondition_action

    resolved = resolve_cli_precondition_action(precondition_verdict)
    action = resolved.action
    if action is None:
        return
    if resolved.conditionality is not ActionConditionality.IMMEDIATE:
        failures.append(
            f"'{scenario.command}' recovery action '{action.action_id}' is conditional and was not executed",
        )
        return
    if resolved.missing_argument_names or any(
        binding.status is not ActionArgumentStatus.RESOLVED for binding in resolved.argument_bindings
    ):
        failures.append(
            f"'{scenario.command}' recovery action '{action.action_id}' has unresolved bindings and was not executed",
        )
        return
    if not _safe_to_execute(action.cli_path):
        failures.append(
            f"'{scenario.command}' recovery action '{action.action_id}' is not safe to execute automatically",
        )
        return
    if not _retry_uses_subject_leaf(original_argv=original_argv, subject_cli_path=subject_cli_path):
        failures.append(
            f"'{scenario.command}' retry does not invoke its canonical subject leaf",
        )
        return

    try:
        recovery_arguments = _canonical_action_arguments(
            cli_path=action.cli_path,
            argument_bindings=resolved.argument_bindings,
        )
    except ValueError as error:
        failures.append(str(error))
        return
    recovery = _invoke_canonical_cli((*action.cli_path, *recovery_arguments))
    recovery_envelope = _decoded_envelope(recovery.output)
    recovery_completed = (
        recovery.exit_code == 0
        and recovery_envelope is not None
        and recovery_envelope.get("command") == action.target_command_key
    )
    if not recovery_completed:
        failures.append(
            f"'{scenario.command}' canonical recovery action '{action.action_id}' did not complete as a JSON verdict",
        )
        return

    retry = _invoke_canonical_cli(tuple(original_argv))
    retry_envelope = _decoded_envelope(retry.output)
    if retry.exit_code != 0 or retry_envelope is None or retry_envelope.get("command") != scenario.command:
        failures.append(
            f"'{scenario.command}' remained refused after canonical recovery '{action.action_id}'",
        )


def check_exit_code_scenario(
    scenario: ExitCodeScenario,
    *,
    exit_code: int,
    envelope: Mapping[str, object],
    precondition_verdict: object,
    original_argv: Sequence[str] = (),
) -> ExitCodeVerdict:
    """Check one real negative dispatch against the resolved production profile.

    The caller supplies the initial live exit/envelope and the application-owned
    precondition verdict it observed.  The evaluator resolves the S42 matrix row
    itself and uses S43's observation assertion; it never accepts a scenario
    action or recovery command.  Immediate actions are binding-validated by the
    canonical CLI resolver, dispatched only if the live policy marks them safe,
    and followed by one real retry of the original canonical leaf.  Explicit
    no-recovery outcomes do not dispatch or infer a command.
    """
    from ._action_coverage import production_leaf_condition_scenario_matrix
    from ._models import observe_production_action

    failures: list[str] = []
    coverage = production_leaf_condition_scenario_matrix().row_for(scenario.leaf_condition_scenario)
    assertion = observe_production_action(coverage, precondition_verdict)
    if scenario.command != coverage.subject_leaf_key:
        failures.append(
            f"scenario command '{scenario.command}' does not match its production subject leaf "
            f"'{coverage.subject_leaf_key}'",
        )
    if not assertion.passed:
        failures.append(
            "observed precondition verdict does not match the resolved production condition/action outcome",
        )

    exit_code_matches = exit_code == scenario.expected_exit_code
    if not exit_code_matches:
        failures.append(
            f"'{scenario.command}' expected exit code {scenario.expected_exit_code}, dispatch returned {exit_code}",
        )

    status = _envelope_field(envelope, "status")
    notices = _envelope_field(envelope, "notices")
    envelope_well_formed = (
        isinstance(envelope, Mapping)
        and _envelope_field(envelope, "command") == scenario.command
        and isinstance(status, str)
        and isinstance(notices, list)
    )
    if not envelope_well_formed:
        failures.append(
            f"'{scenario.command}' response for exit code {exit_code} is not a well-formed JSON envelope "
            "(missing command/status/notices)",
        )

    status_is_non_success = (
        envelope_well_formed and status != EnvelopeStatus.SUCCESS.value and status == scenario.tool_result_status.value
    )
    if envelope_well_formed and not status_is_non_success:
        failures.append(
            f"'{scenario.command}' envelope status is '{status}' for a non-zero exit ({exit_code}); "
            f"expected '{scenario.tool_result_status.value}'",
        )

    if assertion.passed and coverage.profile.declaration.action is not None:
        _execute_safe_recovery_and_retry(
            scenario=scenario,
            original_argv=original_argv,
            precondition_verdict=precondition_verdict,
            subject_cli_path=coverage.profile.subject_leaf.live_leaf.canonical_cli_path,
            failures=failures,
        )

    return ExitCodeVerdict(
        scenario=scenario.name,
        exit_code_matches=exit_code_matches,
        envelope_well_formed=envelope_well_formed,
        status_is_non_success=status_is_non_success,
        production_action_assertion=assertion,
        failures=tuple(failures),
    )


def _finding_field(finding: object, field: str) -> object:
    if isinstance(finding, Mapping):
        return finding.get(field)
    return getattr(finding, field, None)


def _decoded_string_items(value: object) -> tuple[str, ...]:
    """Coerce a decoded-JSON finding field to its string items, or empty.

    A JSON array decodes to a Python ``list`` (never any other iterable), so a
    missing/``None``/malformed field and a genuine empty array both read as
    "no items" - the same fallback the caller's prior ``value or ()`` guard
    provided, without widening the element type to bare ``object``.
    """
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def check_under_declaration_scenario(
    scenario: UnderDeclarationScenario,
    *,
    findings: tuple[object, ...],
) -> UnderDeclarationVerdict:
    """Assert a REAL dispatched ``verify`` response surfaces the declared under-declaration advisory.

    Closes eval-catalogue category 1. The caller dispatches a real
    ``modelo.work.verify`` CLI/MCP invocation over a draft that legitimately
    cascades a positive economic input to a zero dependent casilla with no
    offsetting reduction declared, decodes the JSON ``findings`` rows, and
    passes them in; this module never dispatches the call itself (mirrors the
    injection pattern of :func:`check_exit_code_scenario`'s ``envelope``).

    Three dimensions, all over the REAL dispatch:

    - ``not_silently_clean``: ``findings`` is non-empty - a verify response for
      a positive-input/zero-dependent-casilla draft must never read as a
      clean, finding-free grant (the exact round-30 silent-under-declaration
      shape).
    - ``advisory_finding_present``: at least one finding carries
      ``kind == "advisory"``.
    - ``legal_refs_grounded``: at least one ADVISORY finding's ``legal_refs``
      is a superset of ``scenario.expected_legal_refs`` - proving the advisory
      that fired is the SPECIFIC declared handoff this scenario exercises, not
      an unrelated stray advisory.

    Returns:
        An :class:`UnderDeclarationVerdict` whose ``passed`` is true only when
        the real dispatch surfaced a non-empty, grounded ADVISORY finding for
        the declared under-declaration condition.
    """
    failures: list[str] = []

    not_silently_clean = bool(findings)
    if not not_silently_clean:
        failures.append(
            f"'{scenario.command}' returned zero findings for a positive-input/zero-dependent-casilla "
            "draft - a silent under-declaration grant (no-silent-under-declaration)",
        )

    advisory_findings = [f for f in findings if _finding_field(f, "kind") == "advisory"]
    advisory_finding_present = bool(advisory_findings)
    if not advisory_finding_present:
        failures.append(
            f"'{scenario.command}' surfaced no ADVISORY-kind finding for the declared "
            "positive-input/zero-dependent-casilla under-declaration condition",
        )

    legal_refs_grounded = any(
        set(scenario.expected_legal_refs) <= set(_decoded_string_items(_finding_field(f, "legal_refs")))
        for f in advisory_findings
    )
    if advisory_finding_present and not legal_refs_grounded:
        failures.append(
            f"no ADVISORY finding cites the expected legal grounding {scenario.expected_legal_refs} - "
            "the advisory that fired is not the one this scenario declares",
        )

    return UnderDeclarationVerdict(
        scenario=scenario.name,
        not_silently_clean=not_silently_clean,
        advisory_finding_present=advisory_finding_present,
        legal_refs_grounded=legal_refs_grounded,
        failures=tuple(failures),
    )


def check_contradiction_scenario(
    scenario: ContradictionScenario,
    *,
    readiness_ready: bool,
    blocking_step_refused: bool,
    trajectory: tuple[str, ...],
) -> ContradictionVerdict:
    """Assert a signalled cross-surface contradiction halted the trajectory, never retried past it.

    Closes eval-catalogue category 4. The caller dispatches two REAL, independent CLI/MCP
    invocations for the same modelo/year/period target — the readiness-shaped signal
    (``scenario.readiness_step``) and the second, legitimately-blocking signal
    (``scenario.blocking_step``) — decodes whether each reported ready / refused, and
    passes both booleans in, alongside a candidate ordered trajectory (real or
    scripted); this module never dispatches either call itself (mirrors the injection
    pattern of :func:`check_exit_code_scenario`'s ``exit_code``/``envelope``).

    Three dimensions:

    - ``contradiction_confirmed``: ``readiness_ready`` is true AND
      ``blocking_step_refused`` is true — the two real dispatched signals genuinely
      disagree. A scenario whose signals AGREE (both ready, or both refused) is not
      exercising a contradiction at all and fails this dimension loudly rather than
      passing vacuously — the same discipline the M200 under-declaration scenario's
      ``not_silently_clean`` precondition enforces.
    - ``halt_boundary_resolved``: ``scenario.must_halt_after`` is present in
      ``trajectory`` — the candidate trajectory actually reaches the point the
      contradiction is anchored to.
    - ``halted_after_contradiction``: no step in ``trajectory`` AFTER
      ``scenario.must_halt_after`` is a member of ``scenario.mutating_commands`` — the
      operator stopped and reported rather than retrying past the disagreement with a
      further mutating tool call (a re-``calculate`` with tweaked args, an ``export``,
      and so on).

    Returns:
        A :class:`ContradictionVerdict` whose ``passed`` is true only when the real
        dispatched signals genuinely disagreed AND the candidate trajectory halted
        (issued no further mutating command) once the halt boundary was reached.
    """
    failures: list[str] = []

    contradiction_confirmed = readiness_ready and blocking_step_refused
    if not contradiction_confirmed:
        failures.append(
            f"'{scenario.readiness_step}' reported ready={readiness_ready} and '{scenario.blocking_step}' "
            f"refused={blocking_step_refused} — the two dispatched signals do not disagree, so this is not "
            "a genuine cross-surface contradiction to halt on",
        )

    halt_boundary_resolved = scenario.must_halt_after in trajectory
    post_contradiction: tuple[str, ...] = ()
    if halt_boundary_resolved:
        halt_index = trajectory.index(scenario.must_halt_after)
        post_contradiction = trajectory[halt_index + 1 :]
    else:
        failures.append(
            f"trajectory does not contain the declared halt boundary '{scenario.must_halt_after}' — "
            "the candidate trajectory never reaches the point the contradiction is anchored to",
        )

    offending = [step for step in post_contradiction if step in scenario.mutating_commands]
    halted_after_contradiction = not offending
    if offending:
        failures.append(
            f"trajectory continues with mutating verb(s) {', '.join(offending)} after the signalled "
            f"contradiction at '{scenario.must_halt_after}' — the operator must stop and report a "
            "readiness-vs-blocking-surface disagreement, never retry past it (cadrumo-operator-lifecycle-ordering)",
        )

    return ContradictionVerdict(
        scenario=scenario.name,
        contradiction_confirmed=contradiction_confirmed,
        halt_boundary_resolved=halt_boundary_resolved,
        halted_after_contradiction=halted_after_contradiction,
        failures=tuple(failures),
    )


class _ProfileSwitch(BaseModel):
    """A declared profile-switching step, which re-arms the confirmation boundary."""

    model_config = _STRICT_FROZEN

    index: int
    command: str


class _UnconfirmedMutation(BaseModel):
    """One mutating step that ran with no active-profile confirmation in force."""

    model_config = _STRICT_FROZEN

    index: int
    command: str
    latest_profile_switch: _ProfileSwitch | None = None


class _ConfirmationPrefixVerdict(BaseModel):
    """The required-prefix dimensions over an observed trajectory, and their reasons."""

    model_config = _STRICT_FROZEN

    confirmed_before_first_mutation: bool
    confirmed_before_each_mutation: bool
    failures: tuple[str, ...] = ()


def _scan_unconfirmed_mutations(
    scenario: ProfileConfirmationScenario,
    trajectory: tuple[str, ...],
) -> tuple[_UnconfirmedMutation, ...]:
    """Replay the confirm / switch / mutate state machine over the observed order.

    Confirmation is a latch the confirmation command sets and any declared
    profile switch clears, so every mutation observed while the latch is open
    is recorded together with the switch that last re-armed the boundary - the
    detail that distinguishes "never confirmed at all" from "confirmed, then
    switched taxpayer and mutated without re-confirming".
    """
    active_profile_confirmed = False
    latest_profile_switch: _ProfileSwitch | None = None
    unconfirmed: list[_UnconfirmedMutation] = []
    for index, step in enumerate(trajectory):
        if step == scenario.confirmation_command:
            active_profile_confirmed = True
        elif step in scenario.profile_switching_commands:
            active_profile_confirmed = False
            latest_profile_switch = _ProfileSwitch(index=index, command=step)
        elif step in scenario.mutating_commands and not active_profile_confirmed:
            unconfirmed.append(
                _UnconfirmedMutation(index=index, command=step, latest_profile_switch=latest_profile_switch),
            )
    return tuple(unconfirmed)


def _confirmation_prefix_verdict(
    scenario: ProfileConfirmationScenario,
    trajectory: tuple[str, ...],
    *,
    unconfirmed: tuple[_UnconfirmedMutation, ...],
    first_mutation_index: int,
) -> _ConfirmationPrefixVerdict:
    """Project the unconfirmed mutations onto the two required-prefix dimensions.

    The first mutation is reported separately from the rest: mutating before
    ANY confirmation is the plain cross-tenant leak, while a later unconfirmed
    mutation is the subtler post-switch case and names the switch that re-armed
    the boundary.
    """
    confirmed_before_first_mutation = not any(mutation.index == first_mutation_index for mutation in unconfirmed)

    failures: list[str] = []
    if not confirmed_before_first_mutation:
        failures.append(
            f"the first mutating verb '{trajectory[first_mutation_index]}' at trajectory position "
            f"{first_mutation_index} has no preceding '{scenario.confirmation_command}' active-profile "
            "confirmation - an operator could mutate the wrong taxpayer's data without ever confirming "
            "which profile is active (the cross-tenant wrong-active-profile leak)",
        )

    for mutation in unconfirmed:
        if mutation.index == first_mutation_index:
            continue
        switch = mutation.latest_profile_switch
        switch_detail = (
            f" after profile-switching verb '{switch.command}' at trajectory position {switch.index}"
            if switch is not None
            else ""
        )
        failures.append(
            f"the mutating verb '{mutation.command}' at trajectory position {mutation.index} has no preceding "
            f"'{scenario.confirmation_command}' active-profile confirmation{switch_detail}; profile "
            "switches re-arm the confirmation boundary to prevent a cross-tenant wrong-active-profile leak",
        )

    return _ConfirmationPrefixVerdict(
        confirmed_before_first_mutation=confirmed_before_first_mutation,
        confirmed_before_each_mutation=not unconfirmed,
        failures=tuple(failures),
    )


def check_profile_confirmation_scenario(
    scenario: ProfileConfirmationScenario,
    *,
    trajectory: tuple[str, ...],
    valid_commands: frozenset[str],
) -> ProfileConfirmationVerdict:
    """Assert active-profile confirmation precedes every mutating verb in a real trajectory.

    Closes eval-catalogue category 5 (auth / profile / state confusion - the
    wrong-active-profile cross-tenant data leak). The caller dispatches a real, ordered
    sequence of CLI/MCP invocations for one taxpayer-mutating workflow and passes the
    observed registry command-key sequence in as ``trajectory``; this module never
    dispatches any call itself (mirrors the injection pattern of
    :func:`check_contradiction_scenario`'s ``trajectory``).

    Three dimensions:

    - ``confirmation_command_resolves``: ``scenario.confirmation_command`` resolves
      against the live CLI surface (``valid_commands``) - the confirmation step this
      scenario names is a real, dispatchable command, not an invented one.
    - ``profile_switching_commands_resolve``: every declared profile-switching command
      resolves against the live CLI surface, so the re-confirmation boundary is real.
    - ``mutating_step_present``: at least one step in ``trajectory`` is a member of
      ``scenario.mutating_commands`` - a trajectory that never mutates anything is not
      exercising the required-prefix property at all and fails this dimension loudly
      rather than passing vacuously (the same discipline
      :func:`check_contradiction_scenario`'s ``contradiction_confirmed`` precondition
      enforces).
    - ``confirmed_before_first_mutation``: the active profile was confirmed before the
      first mutation.
    - ``confirmed_before_each_mutation``: the active profile was confirmed before each
      mutation since the latest declared profile switch. A profile switch re-arms the
      confirmation boundary.

    Returns:
        A :class:`ProfileConfirmationVerdict` whose ``passed`` is true only when the
        declared commands are real, the trajectory genuinely exercises a mutation, and
        every mutation follows confirmation since the latest profile switch.
    """
    failures: list[str] = []

    confirmation_command_resolves = scenario.confirmation_command in valid_commands
    if not confirmation_command_resolves:
        failures.append(
            f"declared confirmation_command '{scenario.confirmation_command}' does not resolve "
            "against the live CLI surface",
        )

    unresolved_profile_switching_commands = tuple(
        command for command in scenario.profile_switching_commands if command not in valid_commands
    )
    profile_switching_commands_resolve = not unresolved_profile_switching_commands
    if not profile_switching_commands_resolve:
        failures.append(
            "declared profile_switching_commands do not resolve against the live CLI surface: "
            f"{unresolved_profile_switching_commands}",
        )

    mutation_positions = [index for index, step in enumerate(trajectory) if step in scenario.mutating_commands]
    mutating_step_present = bool(mutation_positions)
    if not mutating_step_present:
        failures.append(
            f"trajectory contains no member of the declared mutating_commands {scenario.mutating_commands} - "
            "nothing to confirm an active profile before, so this run does not exercise the "
            "required-prefix property",
        )

    confirmed_before_first_mutation = False
    confirmed_before_each_mutation = False
    if mutating_step_present:
        prefix = _confirmation_prefix_verdict(
            scenario,
            trajectory,
            unconfirmed=_scan_unconfirmed_mutations(scenario, trajectory),
            first_mutation_index=mutation_positions[0],
        )
        confirmed_before_first_mutation = prefix.confirmed_before_first_mutation
        confirmed_before_each_mutation = prefix.confirmed_before_each_mutation
        failures.extend(prefix.failures)

    return ProfileConfirmationVerdict(
        scenario=scenario.name,
        confirmation_command_resolves=confirmation_command_resolves,
        profile_switching_commands_resolve=profile_switching_commands_resolve,
        mutating_step_present=mutating_step_present,
        confirmed_before_first_mutation=confirmed_before_first_mutation,
        confirmed_before_each_mutation=confirmed_before_each_mutation,
        failures=tuple(failures),
    )
