"""When the manager offers the filed-history sweep, and what it reports.

``aeat app live filed pull-all`` already sequences discovery, bulk filed
capture, IVA wallet reconciliation and the notificaciones pull; this action
is a second door onto the same composed service, not a second
implementation of it. What is worth pinning here is that the manager reuses
the CLI verb's own gate rather than inventing a laxer one -- the sweep is a
long authenticated read that can push a Cl@ve prompt to the operator's
phone, and spending it on a run that cannot authenticate is worse than
saying so first -- and that the summary reports every stage the run model
carries rather than only the headline capture count.
"""

from __future__ import annotations

import inspect

import pytest

from .._manager_actions import (
    _filed_history_pull_all_summary,
    _run_filed_history_pull_all,
    manager_actions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_sweep_is_offered_beside_the_other_manager_actions() -> None:
    """A capability nothing offers is not a capability."""
    assert "filed-history-pull-all" in [action.key for action in manager_actions()]


def test_the_sweep_is_offered_after_the_action_that_unblocks_it() -> None:
    """Same auth dependency as the censal pull, so the same ordering rule applies."""
    keys = [action.key for action in manager_actions()]
    assert keys.index("certificate") < keys.index("filed-history-pull-all"), (
        "the authentication action must come before the sweep it gates"
    )


def test_the_sweep_reuses_the_censal_pulls_own_auth_gate() -> None:
    """One auth-readiness opinion, not two that could drift apart.

    ``_censal_pull_unavailable`` already asks the same predicate the live
    session entry uses. A second, independently-written gate here could
    disagree with it -- refusing a working setup or promising a sweep that
    fails at the browser -- so the action is pinned to call the same
    function rather than restate its rule.
    """
    source = inspect.getsource(_run_filed_history_pull_all)
    assert "_censal_pull_unavailable()" in source, "the sweep must reuse the censal pull's own auth gate"


def test_the_sweep_composes_the_existing_orchestration_service() -> None:
    """No second implementation of discovery, capture, wallet and notificaciones.

    ``pull_filed_history`` already sequences every stage the CLI's
    ``pull-all`` verb reports. A parallel call sequence built here instead
    would duplicate that composition and could drift from it silently.
    """
    source = inspect.getsource(_run_filed_history_pull_all)
    assert "pull_filed_history(" in source, "the action must delegate to the existing orchestration service"


def test_the_summary_names_every_stage_the_run_carries() -> None:
    """A sweep touches four stages; a summary naming one of them buries the rest."""
    from .....application.live import FiledHistoryOnboardingRun

    run = FiledHistoryOnboardingRun(
        pairs=(),
        captured_count=7,
        iva_wallet_status="reconciled",
        notificaciones_status="pulled",
    )

    summary = _filed_history_pull_all_summary(run)

    assert "7" in summary
    assert "reconciled" in summary
    assert "pulled" in summary


def test_a_refused_pair_is_named_rather_than_silently_folded_into_the_count() -> None:
    """A refusal is not evidence of an empty period, so it must stay legible.

    The register walker refuses a truncated page rather than reporting it
    as zero rows; a summary that only reported the aggregate capture count
    would make that refusal indistinguishable from a genuine empty answer.
    """
    from .....application.live import FiledHistoryOnboardingRun, FiledHistoryPairOutcome
    from .....core import FiledHistoryDiscoverySignal

    refused_pair = FiledHistoryPairOutcome(
        modelo="303",
        ejercicio=2024,
        signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
        refused=True,
        failure_type="register_truncated",
        failure_message="the register page reported more rows than it rendered",
    )
    run = FiledHistoryOnboardingRun(pairs=(refused_pair,), captured_count=0)

    summary = _filed_history_pull_all_summary(run)

    assert "303/2024" in summary, "a refused pair must be named, not folded into a silent zero"


def test_a_clean_sweep_names_no_refused_pair() -> None:
    """Naming a refusal that did not happen trains operators to ignore the line.

    The headline sentence always states the refused COUNT (zero included,
    the way the CLI's own metric line does), so this pins the absence of
    the separate refused-pairs sentence -- which names pairs as
    ``modelo/ejercicio`` -- rather than the bare word "refused", which a
    "0 refused" headline legitimately contains.
    """
    from .....application.live import FiledHistoryOnboardingRun

    run = FiledHistoryOnboardingRun(pairs=(), captured_count=3)

    assert "/" not in _filed_history_pull_all_summary(run), "no refused pair to name, so none should be named"


def test_the_summary_carries_the_runs_own_denominator_note() -> None:
    """The run states its own denominator; the action must not re-derive one.

    Re-deriving a coverage claim here would risk drifting from the
    taxpayer-specific-denominator rule the run model already enforces --
    no percentage or fraction over AEAT-offered pairs whose NIF-scoping is
    unconfirmed.
    """
    from .....application.live import FiledHistoryOnboardingRun

    run = FiledHistoryOnboardingRun(pairs=(), captured_count=0)

    assert run.denominator_note in _filed_history_pull_all_summary(run)


def test_the_summary_preserves_each_bounded_stage_failure() -> None:
    """A partial sweep must name the stage failures the service retained."""
    from .....application.live import FiledHistoryOnboardingRun

    failures = (
        "iva_wallet: AEAT refused the wallet view",
        "notificaciones: authentication expired",
    )
    run = FiledHistoryOnboardingRun(pairs=(), captured_count=2, stage_failures=failures)

    summary = _filed_history_pull_all_summary(run)

    for failure in failures:
        assert failure in summary, f"the manager dropped the actionable stage failure {failure!r}"
