"""Lifecycle-contradiction golden gate for the operator eval.

Guards against wrong lifecycle sequencing surfacing as a cross-surface contradiction:
``modelo readiness`` reporting ``ready: True`` for a modelo whose ``work`` verb is
blocked. This is the enforcement surface for the "Contradictions between surfaces are a
stop, not a retry" section of
``src/cadrumo-harness/src/cadrumo_harness/_data/agent/rules/cadrumo-operator-lifecycle-ordering.md``.

The only deterministic, clock-free CLI reproduction of the contradiction relied on a
modelo revision with ZERO registry calculation bindings: Modelo 347
``2008-2024`` was such a revision, so ``modelo readiness`` reported ``ready:
true`` for a freshly-created, casilla-empty draft (the binding axis had nothing to fail
on) while ``modelo work verify`` legitimately refused to grant ``VERIFICADO_COMPLETO``.
M347 now carries real counterpart-summary bindings, so ``modelo readiness`` reports the
casilla-empty draft NOT ready and the readiness/verify pair no longer disagrees - the
live CLI reproduction is permanently closed.

The pure checker :func:`check_contradiction_scenario` (``.._runner``) still encodes the
contradiction contract, so it is now covered STRUCTURALLY: the trajectory tests inject the
``readiness_ready=True, blocking_step_refused=True`` disagreement directly (the module's
own established idiom - see ``test_runner_rejects_a_scenario_where_the_signals_agree`` and
``test_runner_rejects_a_trajectory_that_never_reaches_the_halt_boundary``), giving
full four-quadrant coverage (PASS, retry-FAIL, signals-agree-FAIL,
never-reaches-boundary-FAIL) with no live dispatch and no clock dependency.

``test_registry_grounding_closed_the_readiness_verify_contradiction`` is the reinstatement
tripwire: it drives the real ``config profile create`` -> ``work create`` -> ``work
calculate`` -> ``modelo readiness`` CLI path for the same M347 target and asserts
readiness now reports NOT ready. If a registry edit ever unbinds M347 (or the binding axis
otherwise stops firing), this fails loudly and the golden contradiction should be
re-instated as a live scenario.

No mocks: every seeded profile fact and every dispatched CLI response is what the real
profile-preflight, registry engine, and CLI envelope serializer produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cadrumo_harness.mcp import build_tool_descriptors

from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture

from .. import ContradictionScenario, check_contradiction_scenario

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "operator"
_MODELO = "347"
_FILING_YEAR = 2024
_PERIOD = "0A"
_REVISION = "2008-2024"

_READINESS_STEP = "modelo.readiness"
_BLOCKING_STEP = "modelo.work.verify"
# Command keys this scenario treats as a further mutating attempt that must not follow
# the signalled contradiction. Declared scenario data (mirrors
# `UnderDeclarationScenario.expected_legal_refs`), cross-checked below against the live
# MCP tool-descriptor mutability classification
# (`cadrumo_harness.mcp._tools.build_tool_descriptors`, the same classification the
# PreToolUse confirmation gate reads) so the declared set is not a hand-wavy guess.
_MUTATING_COMMANDS = (
    "modelo.work.create",
    "modelo.work.calculate",
    "modelo.work.verify",
    "modelo.work.file",
    "modelo.export",
)


def _create_profile() -> None:
    result = invoke_cached_cli(
        [
            "config", "profile", "create", _PROFILE_ID,
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "actividad_economica",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Contradiction",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _prepare_calculated_m347_draft() -> None:
    """Create -> calculate a real M347 2024 annual draft; no casillas supplied.

    Modelo 347 declares zero registry calculation bindings for this revision, so
    ``work calculate`` succeeds with no ``--casilla``/``--binding``/``--row`` input at
    all - the resulting draft is the minimal, real, precondition for the
    readiness-vs-verify disagreement this module reproduces.
    """
    _create_profile()

    created = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", _MODELO, "--year", str(_FILING_YEAR), "--period", _PERIOD,
            "--revision", _REVISION,
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output

    calculated = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", _MODELO, "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output


def _dispatch_readiness() -> bool:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", _MODELO, "--revision-id", _REVISION,
            "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    assert payload["operation"] == "modelo.readiness"  # sanity: real payload shape, not a stray success envelope
    return bool(payload["ready"])


def _scenario() -> ContradictionScenario:
    return ContradictionScenario(
        name="m347-readiness-vs-verify-missing-required-casillas",
        readiness_step=_READINESS_STEP,
        blocking_step=_BLOCKING_STEP,
        must_halt_after=_BLOCKING_STEP,
        mutating_commands=_MUTATING_COMMANDS,
    )


def test_mutating_commands_are_confirmed_non_read_only_on_the_live_manifest() -> None:
    """Anti-rubber-stamp: every declared mutating command genuinely resolves non-read-only.

    Cross-checks ``_MUTATING_COMMANDS`` against the REAL MCP tool-descriptor mutability
    classification (the same classification the ``PreToolUse`` confirmation gate reads
    via ``cadrumo_harness.mcp._hitl.confirmation_for_tool``), so the scenario's declared set
    is not an invented label.
    """
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    for command in _MUTATING_COMMANDS:
        assert command in by_key, f"'{command}' is not an exposed MCP tool"
        assert not by_key[command].annotations.read_only_hint, (
            f"'{command}' is declared mutating in this scenario but the live manifest reports it read-only"
        )


def test_registry_grounding_closed_the_readiness_verify_contradiction(
    _isolated_cli_backend: Path,  # noqa: F811
) -> None:
    """Closure regression / reinstatement tripwire: readiness no longer says ready.

    Commit ``8220834c35`` (``feat(modelo-347): bind invoice-source summary totals``) gave
    Modelo 347 ``2008-2024`` real registry calculation bindings. Before it, the
    casilla-empty M347 draft was the only deterministic, clock-free CLI reproduction of
    the category-4 readiness-says-ready / verify-blocks contradiction, because the binding
    axis had nothing to fail on. Now readiness's binding axis fires, so ``modelo
    readiness`` reports the freshly-created casilla-empty draft NOT ready and the
    readiness/verify pair no longer disagrees.

    This drives the real ``config profile create`` -> ``work create`` -> ``work
    calculate`` -> ``modelo readiness`` CLI path (no mocks, no clock dependency) and
    asserts readiness is NOT ready. It is the reinstatement tripwire: if a registry edit
    ever unbinds M347 (or the binding axis otherwise stops firing) readiness would report
    ready again, this assertion fails loudly, and the golden contradiction should be
    re-instated as a live scenario.
    """
    _prepare_calculated_m347_draft()

    readiness_ready = _dispatch_readiness()

    assert readiness_ready is False, (
        "M347 registry grounding (commit 8220834c35) closed the live readiness-vs-verify "
        "contradiction: readiness must report the casilla-empty draft NOT ready. Readiness "
        "reporting ready again means M347 was unbound - re-instate the golden contradiction "
        "as a live scenario."
    )


def test_halted_trajectory_passes_the_contradiction_dimension() -> None:
    """PASS: a trajectory that stops at the blocking step (never retries) passes.

    Pure structural proof (no live dispatch needed): injects the signalled disagreement
    (``readiness_ready=True, blocking_step_refused=True``) directly and feeds
    ``check_contradiction_scenario`` a trajectory that halts exactly at the blocking
    step - the correct stop-and-report response to the disagreement.
    """
    trajectory = (
        _READINESS_STEP,
        "modelo.work.create",
        "modelo.work.calculate",
        _BLOCKING_STEP,
    )

    result = check_contradiction_scenario(
        _scenario(),
        readiness_ready=True,
        blocking_step_refused=True,
        trajectory=trajectory,
    )

    assert result.passed, result.failures
    assert result.contradiction_confirmed
    assert result.halt_boundary_resolved
    assert result.halted_after_contradiction


def test_retry_past_the_contradiction_fails_the_dimension() -> None:
    """FAIL-catch (anti-tautology): a mutating verb AFTER the halt boundary MUST fail.

    Pure structural proof: takes the same injected contradiction
    (``readiness_ready=True, blocking_step_refused=True``) and appends retry-shaped
    mutating steps (``modelo.work.calculate`` with tweaked args, then ``modelo.export``)
    after the blocking-step boundary - reproducing the exact "retry-until-it-works"
    pattern ``cadrumo-operator-lifecycle-ordering`` forbids ("never to re-run export or file
    against an unverified or previously-blocked revision to route around the finding") -
    and proves the checker catches it. Without this proof the dimension could pass
    vacuously regardless of what trajectory it was handed.
    """
    violating_trajectory = (
        _READINESS_STEP,
        "modelo.work.create",
        "modelo.work.calculate",
        _BLOCKING_STEP,
        "modelo.work.calculate",
        "modelo.export",
    )

    result = check_contradiction_scenario(
        _scenario(),
        readiness_ready=True,
        blocking_step_refused=True,
        trajectory=violating_trajectory,
    )

    assert not result.passed
    assert result.contradiction_confirmed
    assert result.halt_boundary_resolved
    assert not result.halted_after_contradiction
    assert any(
        "modelo.work.calculate" in failure and "modelo.export" in failure and "must stop and report" in failure
        for failure in result.failures
    )


def test_runner_rejects_a_scenario_where_the_signals_agree() -> None:
    """Anti-tautology: signals that AGREE are not a contradiction, even with a clean trajectory.

    Pure structural proof (no live dispatch needed): both ``readiness_ready=True`` and
    ``blocking_step_refused=False`` describe an ordinary clean pass, not a disagreement -
    ``contradiction_confirmed`` must be false, and the scenario must not pass even though
    the supplied trajectory never retries past anything.
    """
    trajectory = (
        _READINESS_STEP,
        "modelo.work.create",
        "modelo.work.calculate",
        _BLOCKING_STEP,
    )

    result = check_contradiction_scenario(
        _scenario(),
        readiness_ready=True,
        blocking_step_refused=False,
        trajectory=trajectory,
    )

    assert not result.passed
    assert not result.contradiction_confirmed
    assert any("do not disagree" in failure for failure in result.failures)


def test_runner_rejects_a_trajectory_that_never_reaches_the_halt_boundary() -> None:
    """Anti-tautology: a trajectory that never reaches the declared halt boundary MUST fail.

    Pure structural proof: even with a genuinely confirmed contradiction, a trajectory
    that stops before ``must_halt_after`` is not evidence the operator actually reached
    and reacted to the disagreement - ``halt_boundary_resolved`` must be false.
    """
    trajectory = (
        _READINESS_STEP,
        "modelo.work.create",
        "modelo.work.calculate",
    )

    result = check_contradiction_scenario(
        _scenario(),
        readiness_ready=True,
        blocking_step_refused=True,
        trajectory=trajectory,
    )

    assert not result.passed
    assert result.contradiction_confirmed
    assert not result.halt_boundary_resolved
    assert any("never reaches the point" in failure for failure in result.failures)
