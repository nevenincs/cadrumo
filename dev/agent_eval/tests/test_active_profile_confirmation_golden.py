"""Active-profile-confirmation golden gate for the operator eval.

Guards against auth / profile / state confusion: a wrong active profile silently
showing another taxpayer's data - a cross-tenant data leak, critical for a gestor's
multi-taxpayer use of the harness. The operator must confirm the active profile before
every mutating sequence. ``docs/how-to/troubleshooting.md``'s "The numbers or facts look
like someone else's" section names the confirmation surface: "See which profile is
active: ``aeat config profile status``" - the registry command key
``config.profile.status``, resolved against the live CLI schema registry below rather
than assumed.

This module proves a required-prefix ordering property over a REAL, dispatched
trajectory: for a taxpayer-mutating command sequence, the active-profile confirmation
step must precede the first mutating verb. Two real repros anchor the dimension - a
confirmed trajectory (create the profile, confirm it is active, then create and
calculate an M347 draft) and an unconfirmed one (the same mutating sequence with the
confirmation step omitted) - both dispatched through the live CLI, not scripted.

No mocks: every dispatched CLI response is what the real profile-lifecycle and modelo
work-unit commands produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from cadrumo_harness.mcp import ConfirmationPolicy, build_tool_descriptors, confirmation_for_tool

from .._models import ProfileConfirmationScenario
from .._runner import check_profile_confirmation_scenario
from ._real_cli_support import valid_cli_commands
from ...scripted_registration_channels import scripted_registration_descriptors
from ._scripted_registration_channels import (
    creation_secrets_payload,
    login_secrets_payload,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "operator"
_MODELO = "347"
_FILING_YEAR = 2024
_PERIOD = "0A"
_REVISION = "2011-2024"
"""The law-determined M347 revision for the 2024 annual period.

Not a free choice: the CLI refuses a requested revision that is not the one
the period-to-revision binding fixes, and it names the correct one in the
refusal. This constant read ``2008-2024`` until that refusal started firing,
which is the binding doing exactly what it exists to do.
"""

_CONFIRMATION_COMMAND = "config.profile.status"
# Command keys this scenario treats as a mutating attempt on the active profile's
# state. Declared scenario data (mirrors `ContradictionScenario.mutating_commands`),
# cross-checked below against the live MCP tool-descriptor command-policy projection
# (the same classification the PreToolUse confirmation gate reads) so the declared
# set is not a hand-wavy guess.
_MUTATING_COMMANDS = (
    "modelo.work.create",
    "modelo.work.calculate",
    "modelo.work.verify",
    "modelo.work.file",
    "modelo.export",
)


def _create_profile() -> None:
    with scripted_registration_descriptors() as (handoff, verification):
        result = invoke_cached_cli(
            [
                "config", "profile", "create", _PROFILE_ID,
                "--quiet", "--accept-defaults",
                "--entity-type", "natural_person",
                "--irpf-income-categories", "actividad_economica",
                "--tax-id", "12345678Z",
                "--name", "Operator",
                "--surnames", "Confirmation",
                "--activity", "design",
                "--tax-residence-jurisdiction-scope", "common_regime",
                "--tax-residence-ccaa", "madrid",
                "--iva-regime", "GENERAL",
                "--iva-m303-regime-composition", "general",
                "--no-iva-redeme-enrolled",
                "--no-iva-cash-accounting-regime-enrolled",
                "--no-iva-voluntary-sii-enrolled",
                "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
                "--secrets-stdin",
                "--recovery-handoff-fd", str(handoff),
                "--recovery-verification-fd", str(verification),
            ],
            input=creation_secrets_payload(),
        )  # fmt: skip
    assert result.exit_code == 0, result.output

    session = invoke_cached_cli(
        ["config", "login", _PROFILE_ID, "--secrets-stdin"],
        input=login_secrets_payload(),
    )
    assert session.exit_code == 0, session.output

    completed = invoke_cached_cli(["config", "profile", "complete-setup"])
    assert completed.exit_code == 0, completed.output


def _dispatch_confirmation() -> str | None:
    """Dispatch the real ``config profile status`` and return the reported active profile."""
    result = invoke_cached_cli(["--format", "json", "config", "profile", "status"])
    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    return payload["active_profile"]


def _dispatch_create() -> None:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", _MODELO, "--year", str(_FILING_YEAR), "--period", _PERIOD,
            "--revision", _REVISION,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _dispatch_calculate() -> None:
    """M347 declares zero registry calculation bindings for this revision, so ``work
    calculate`` succeeds with no ``--casilla``/``--binding``/``--row`` input at all -
    the minimal, real mutating step this module needs (mirrors
    `test_lifecycle_contradiction_golden.py::_prepare_calculated_m347_draft`).
    """
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", _MODELO, "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _scenario() -> ProfileConfirmationScenario:
    return ProfileConfirmationScenario(
        name="m347-active-profile-confirmed-before-mutation",
        confirmation_command=_CONFIRMATION_COMMAND,
        mutating_commands=_MUTATING_COMMANDS,
        profile_switching_commands=("config.login",),
    )


def test_confirmation_command_resolves_and_mutating_commands_are_non_read_only_on_the_live_manifest() -> None:
    """Anti-rubber-stamp: the confirmation command is freely callable; the mutating commands mutate.

    Cross-checks ``_CONFIRMATION_COMMAND`` and ``_MUTATING_COMMANDS`` against the REAL MCP
    tool-descriptor classification and confirmation gate (the same authority the ``PreToolUse``
    gate reads via ``cadrumo_harness.mcp._hitl.confirmation_for_tool``), so neither declared set is
    an invented label. Under the declared-risk model the
    ``config profile`` family is ``LOCAL_STATE_MUTATING`` at whole-family granularity (it also
    owns ``create``/``edit``/``delete``), so ``config.profile.status`` is non-read-only like the
    mutating leaves; the risk table carries only the destructive/handoff/live-write axes, so the
    two are not distinguished by ``idempotent_hint``. The meaningful, gate-relevant properties
    are asserted instead: the confirmation step is safe to call before any mutation - it carries
    no destructive/handoff/live-write risk, so the gate AUTO_APPROVEs it - while every declared
    mutating command is genuinely non-read-only on the manifest.
    """
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}

    assert _CONFIRMATION_COMMAND in by_key, f"'{_CONFIRMATION_COMMAND}' is not an exposed MCP tool"
    confirm_annotations = by_key[_CONFIRMATION_COMMAND].annotations
    assert not confirm_annotations.destructive_hint, (
        f"'{_CONFIRMATION_COMMAND}' is this scenario's active-profile confirmation step but the "
        "live manifest reports it as destructive - a pre-mutation confirmation read must not be"
    )
    assert confirmation_for_tool(command_key=_CONFIRMATION_COMMAND) is ConfirmationPolicy.AUTO_APPROVE, (
        f"'{_CONFIRMATION_COMMAND}' must be freely callable as the pre-mutation confirmation step; "
        "the gate must not require a human approval loop to read which profile is active"
    )

    for command in _MUTATING_COMMANDS:
        assert command in by_key, f"'{command}' is not an exposed MCP tool"
        assert not by_key[command].annotations.read_only_hint, (
            f"'{command}' is declared mutating in this scenario but the live command policy classifies it read-only"
        )


def test_confirmation_command_reports_the_real_active_profile(_isolated_cli_backend: Path) -> None:  # noqa: F811
    """Real repro: ``config profile status`` genuinely surfaces which profile is active.

    Grounds the confirmation step against a live dispatch before it is used as a
    trajectory element below: the reported ``active_profile`` must be the profile this
    test just created, not a stale or fabricated value.
    """
    _create_profile()
    active_profile = _dispatch_confirmation()
    assert active_profile == _PROFILE_ID


def test_confirmed_trajectory_passes_the_dimension(_isolated_cli_backend: Path) -> None:  # noqa: F811
    """PASS: a real trajectory that confirms the active profile before mutating it passes.

    Dispatches the real sequence an onboarding-then-preparer handoff must follow -
    confirm which profile is active, then create and calculate the M347 draft - and
    feeds the observed real trajectory to ``check_profile_confirmation_scenario``.
    """
    _create_profile()

    trajectory: list[str] = []
    _dispatch_confirmation()
    trajectory.append(_CONFIRMATION_COMMAND)
    _dispatch_create()
    trajectory.append("modelo.work.create")
    _dispatch_calculate()
    trajectory.append("modelo.work.calculate")

    result = check_profile_confirmation_scenario(
        _scenario(),
        trajectory=tuple(trajectory),
        valid_commands=valid_cli_commands(),
    )

    assert result.passed, result.failures
    assert result.confirmation_command_resolves
    assert result.profile_switching_commands_resolve
    assert result.mutating_step_present
    assert result.confirmed_before_first_mutation
    assert result.confirmed_before_each_mutation


def test_trajectory_missing_confirmation_fails_the_dimension(_isolated_cli_backend: Path) -> None:  # noqa: F811
    """FAIL-catch (anti-tautology): a real mutating sequence with no prior confirmation MUST fail.

    Dispatches the SAME real mutating sequence with the confirmation step omitted -
    reproducing the exact wrong-active-profile hazard this gate guards: an
    operator (or an autonomous agent acting on its behalf) mutates a taxpayer's draft
    without ever having confirmed which profile is active. Without this proof the
    dimension could pass vacuously regardless of what trajectory it was handed.
    """
    _create_profile()

    _dispatch_create()
    _dispatch_calculate()
    unconfirmed_trajectory = ("modelo.work.create", "modelo.work.calculate")

    result = check_profile_confirmation_scenario(
        _scenario(),
        trajectory=unconfirmed_trajectory,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert result.confirmation_command_resolves
    assert result.mutating_step_present
    assert not result.confirmed_before_first_mutation
    assert not result.confirmed_before_each_mutation
    assert any(
        "modelo.work.create" in failure and "config.profile.status" in failure and "cross-tenant" in failure
        for failure in result.failures
    )


def test_confirmation_after_the_first_mutation_still_fails_the_dimension(_isolated_cli_backend: Path) -> None:  # noqa: F811
    """FAIL-catch: a confirmation dispatched AFTER the first mutating verb does not satisfy the prefix.

    A trajectory that eventually confirms - just too late - is the same hazard as never
    confirming at all: the first mutating command already ran against whatever profile
    happened to be active. Proves the dimension checks ordering, not mere presence.
    """
    _create_profile()

    _dispatch_create()
    _dispatch_confirmation()
    _dispatch_calculate()
    late_confirmation_trajectory = ("modelo.work.create", _CONFIRMATION_COMMAND, "modelo.work.calculate")

    result = check_profile_confirmation_scenario(
        _scenario(),
        trajectory=late_confirmation_trajectory,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert result.mutating_step_present
    assert not result.confirmed_before_first_mutation
    assert not result.confirmed_before_each_mutation


def test_profile_switch_requires_reconfirmation_before_later_mutation(_isolated_cli_backend: Path) -> None:  # noqa: F811
    """FAIL-catch: an observed profile switch invalidates earlier confirmation before the next mutation."""
    _create_profile()

    _dispatch_confirmation()
    _dispatch_create()
    switch_trajectory = (_CONFIRMATION_COMMAND, "modelo.work.create", "config.login", "modelo.work.calculate")

    result = check_profile_confirmation_scenario(
        _scenario(),
        trajectory=switch_trajectory,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert result.confirmed_before_first_mutation
    assert not result.confirmed_before_each_mutation
    assert any(
        "config.login" in failure and "modelo.work.calculate" in failure and "re-arm" in failure
        for failure in result.failures
    )


def test_runner_rejects_a_scenario_with_no_mutating_step() -> None:
    """Anti-tautology: a trajectory that never mutates anything does not exercise the property.

    Pure structural proof (no live dispatch needed): a trajectory carrying only the
    confirmation command (or other reads) never reaches a mutating verb, so
    ``mutating_step_present`` must be false and the scenario must not pass even though
    no mutation ever ran unconfirmed.
    """
    trajectory = (_CONFIRMATION_COMMAND, "modelo.describe", "modelo.casillas")

    result = check_profile_confirmation_scenario(
        _scenario(),
        trajectory=trajectory,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert result.confirmation_command_resolves
    assert not result.mutating_step_present
    assert any("nothing to confirm" in failure for failure in result.failures)


def test_runner_rejects_an_unresolvable_confirmation_command() -> None:
    """Anti-tautology: a confirmation command that does not resolve on the live CLI fails loudly.

    Pure structural proof: a scenario declaring an invented confirmation command must
    not silently pass just because the rest of the trajectory happens to be ordered
    correctly.
    """
    scenario = ProfileConfirmationScenario(
        name="invented-confirmation-command",
        confirmation_command="config.profile.nonexistent_confirmation_verb",
        mutating_commands=_MUTATING_COMMANDS,
    )
    trajectory = ("config.profile.nonexistent_confirmation_verb", "modelo.work.create")

    result = check_profile_confirmation_scenario(
        scenario,
        trajectory=trajectory,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert not result.confirmation_command_resolves
    assert any("does not resolve against the live CLI surface" in failure for failure in result.failures)
