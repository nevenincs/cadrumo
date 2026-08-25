"""Behavioural proof for the alerting that pays for the removed approval click.

The click was the only moment a human was structurally guaranteed to look at a
release. Every test here defends one consequence of removing it: an alert must
reach somewhere the operator sees without being told to look, it must not flood,
and it must never replace the failure it is reporting with a failure of its own.
"""

from __future__ import annotations

import json
import re
import stat
import sys
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import iter_directory, scan_directory

from ..._paths import REPO_ROOT
from .. import alerting
from ..alerting import AlertError, ReleaseAlert, alert_payload, emit_alert

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final[Path] = REPO_ROOT
_WORKFLOW_DIR: Final[Path] = _REPO_ROOT / ".github" / "workflows"


def _alert(*, workflow: str = "Cadrumo Release Orchestrator", run_id: str = "4242") -> ReleaseAlert:
    return ReleaseAlert(
        workflow=workflow,
        run_id=run_id,
        run_url=f"https://github.com/nevenincs/cadrumo/actions/runs/{run_id}",
        stage="bump",
        detail="REFUSED: version 1.2.3 is burned",
    )


def _write_recording_gh(bin_dir: Path, *, stdout: str = "[]", log: Path | None = None) -> Path:
    """Write a real `gh` stub that records argv and emits fixed output."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "gh.bat"
        lines = ["@echo off"]
        if log is not None:
            # Leading args only. The alert body is deliberately multi-line, and
            # echoing a multi-line argv breaks both shells - which is a fact
            # about the stub, not about the code under test. The subcommand and
            # its target live in the first three arguments.
            lines.append(f'echo %1 %2 %3 %4 %5 >> "{log}"')
        for line in stdout.splitlines() or [""]:
            lines.append(f"echo {line}" if line else "echo.")
        script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    else:
        script = bin_dir / "gh"
        body = ["#!/usr/bin/env bash"]
        if log is not None:
            body.append(f'echo "$1 $2 $3 $4 $5" >> "{log}"')
        body.append(f"cat <<'OUT'\n{stdout}\nOUT")
        script.write_text("\n".join(body) + "\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_the_default_path_opens_a_labelled_issue(tmp_path: Path) -> None:
    """Alerting works before any channel is nominated.

    The default needs no secret, no variable, and no operator decision, which
    is the whole point: alerting that waits on provisioning is absent for
    exactly the period between removing the click and finishing the setup.
    """
    log = tmp_path / "argv.log"
    script = _write_recording_gh(tmp_path / "bin", stdout="[]", log=log)

    result = emit_alert(_alert(), repository="nevenincs/cadrumo", gh_executable=str(script))

    recorded = log.read_text(encoding="utf-8")
    assert "issue create" in recorded
    assert alerting.ALERT_LABEL == "release-alert"
    assert "opened alert" in result


def test_a_second_alert_for_the_same_run_updates_rather_than_duplicates(tmp_path: Path) -> None:
    """A flooding channel is one the operator learns to filter.

    Which returns us to nobody looking, by a slower route. A re-run, or several
    failing jobs in one run, must land on one thread.
    """
    existing = json.dumps(
        [
            {
                "number": 77,
                "title": "Release alert: Cadrumo Release Orchestrator failed (Cadrumo Release Orchestrator#4242)",
            }
        ]
    )
    log = tmp_path / "argv.log"
    script = _write_recording_gh(tmp_path / "bin", stdout=existing, log=log)

    result = emit_alert(_alert(), repository="nevenincs/cadrumo", gh_executable=str(script))

    recorded = log.read_text(encoding="utf-8")
    assert "issue comment 77" in recorded
    assert "issue create" not in recorded
    assert "updated open alert #77" in result


def test_a_different_run_gets_its_own_alert(tmp_path: Path) -> None:
    """Control for the deduplication: two real failures are two alerts.

    Without this, a deduplicator keyed too broadly - by workflow rather than by
    run - would silently collapse every future failure into one stale thread
    and look identical to correct behaviour in the test above.
    """
    existing = json.dumps(
        [
            {
                "number": 77,
                "title": "Release alert: Cadrumo Release Orchestrator failed (Cadrumo Release Orchestrator#4242)",
            }
        ]
    )
    log = tmp_path / "argv.log"
    script = _write_recording_gh(tmp_path / "bin", stdout=existing, log=log)

    emit_alert(_alert(run_id="9999"), repository="nevenincs/cadrumo", gh_executable=str(script))

    assert "issue create" in log.read_text(encoding="utf-8")


def test_a_nominated_webhook_replaces_the_issue_path(tmp_path: Path) -> None:
    """One event, one channel. Two would train the operator to read the quieter."""
    log = tmp_path / "argv.log"
    script = _write_recording_gh(tmp_path / "bin", log=log)
    delivered: list[tuple[str, ReleaseAlert]] = []

    result = emit_alert(
        _alert(),
        repository="nevenincs/cadrumo",
        webhook_url="https://alerts.example/hook",
        gh_executable=str(script),
        webhook_sender=lambda url, alert: delivered.append((url, alert)),
    )

    assert [url for url, _ in delivered] == ["https://alerts.example/hook"]
    assert "alerted via webhook" in result
    assert not log.exists() or "issue create" not in log.read_text(encoding="utf-8")


def test_the_payload_leads_with_the_run_url() -> None:
    """The operator's next action is always to open the run."""
    body = alert_payload(_alert())

    assert "actions/runs/4242" in body
    assert "bump" in body
    assert "version 1.2.3 is burned" in body


def test_a_failing_alert_transport_never_replaces_the_original_failure(tmp_path: Path) -> None:
    """The run is already red; the operator needs the FIRST error, not the second.

    An alerting handler that raised would overwrite the failure it was
    reporting, which is worse than not alerting at all - the release still
    failed, and now its cause is gone too.
    """
    missing = tmp_path / "bin" / "definitely-not-gh"

    with pytest.raises(AlertError):
        emit_alert(_alert(), repository="nevenincs/cadrumo", gh_executable=str(missing))

    # ...but the CLI entry point swallows it into a warning and exits 0.
    exit_code = alerting.main(
        [
            "--repository",
            "nevenincs/cadrumo",
            "--workflow",
            "Cadrumo Release Orchestrator",
            "--run-id",
            "4242",
            "--stage",
            "bump",
            "--detail",
            "boom",
            "--webhook",
            "",
            # Explicit, so this never reaches a real `gh` on the developer's
            # PATH and can never file an issue against the live repository.
            "--gh",
            str(missing),
        ],
    )
    assert exit_code == 0


# --------------------------------------------------------------------------
# Reachability: every workflow on the release path must carry a failure alert.
# --------------------------------------------------------------------------


def _load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _needs_own_alert(workflow_dir: Path, *, module_root: Path | None = None) -> set[str]:
    """Return the workflows that must carry their OWN failure alert.

    Derived, never hand-listed, but narrower than "everything the release path
    touches" - and the narrowing is the substance of this gate.

    A workflow whose dispatcher WAITS for its conclusion is already covered: an
    acquisition lane that fails makes the orchestrator's acquire stage fail,
    which fails the orchestrator, which alerts. Adding an alert to the lane too
    would deliver two alerts for one event, which is the same
    train-the-operator-to-filter failure that alerting-plus-webhook was
    rejected for.

    A workflow dispatched FIRE-AND-FORGET has no such parent. The promoter
    dispatches the publication authority and exits without waiting, so a failed
    publication is observed by nobody unless that workflow alerts for itself.
    Likewise a workflow triggered by an event rather than by a dispatcher - the
    documentation publisher runs on `release: published` and has no parent run
    at all.

    So: the roots, plus anything a root reaches without waiting, plus anything
    event-triggered off the release. Waiting is detected by the presence of
    `dev.release.run_resolution` - the module whose entire purpose is to
    dispatch and then wait - in the same step that reaches the workflow.
    """
    roots = [
        name for name in ("release-orchestrator.yml", "release-soak-promoter.yml") if (workflow_dir / name).is_file()
    ]
    needs: set[str] = set(roots)
    candidates = [candidate.name for candidate in scan_directory(workflow_dir, pattern="*.yml")]

    for name in roots:
        document = yaml.safe_load((workflow_dir / name).read_text(encoding="utf-8"))
        for job in document.get("jobs", {}).values():
            for step in job.get("steps", []) or []:
                # Comments AND printed prose are dropped: the orchestrator
                # deliberately names workflows it must never dispatch, in
                # comments and in operator-facing log lines alike. The seal
                # stage's dry-run branch echoes why it is NOT dispatching, and
                # names packaging-smoke.yml while doing so - a line that writes
                # to the run log cannot start a workflow, so counting it as a
                # dispatch demanded an alert on a lane the campaign stage waits
                # for. This is the same NAMING-is-not-DISPATCHING distinction
                # the module scan below already makes, applied to the step body.
                #
                # Only pure output lines are dropped, not every line without a
                # dispatch verb: the campaign stage assigns its workflow to a
                # variable and dispatches through it, so a mention must still
                # count when it is nowhere near the dispatch itself.
                body = "\n".join(
                    line
                    for line in str(step.get("run", "")).splitlines()
                    if not line.lstrip().startswith(("#", "echo ", "printf "))
                )
                if not body:
                    continue
                waits = "dev.release.run_resolution" in body
                reached = {candidate for candidate in candidates if candidate in body}
                if module_root is not None:
                    for module in re.findall(r"dev\.[a-z_]+\.[a-z_]+", body):
                        module_path = module_root / Path(*module.split(".")).with_suffix(".py")
                        if not module_path.is_file():
                            continue
                        module_text = module_path.read_text(encoding="utf-8")
                        # NAMING a workflow is not DISPATCHING it. The
                        # host-extension precondition reads the same lane
                        # mapping the acquisition stage uses, and dispatches
                        # nothing; counting its mapping as a dispatch would
                        # demand alerts on lanes this step never starts.
                        if '"workflow",' not in module_text and "dispatch_and_resolve" not in module_text:
                            continue
                        reached.update(c for c in candidates if c in module_text)
                if not waits:
                    needs.update(reached)

    # Event-triggered off a release: no dispatcher exists to observe a failure.
    for candidate in candidates:
        triggers = yaml.safe_load((workflow_dir / candidate).read_text(encoding="utf-8")) or {}
        on = triggers.get(True, {}) if isinstance(triggers, dict) else {}
        if isinstance(on, dict) and "release" in on:
            needs.add(candidate)

    return needs


def _has_failure_alert(document: Any) -> bool:
    """Whether the workflow alerts on failure, by step-level OR job-level guard.

    Both shapes are legitimate and each is correct in its place: a single-job
    workflow guards the step, a multi-job workflow needs a dedicated job (a
    step in the last job never runs when an earlier job fails). A detector that
    saw only one shape would report the other as unalerted.
    """
    for job in document.get("jobs", {}).values():
        job_guarded = "failure()" in str(job.get("if", ""))
        for step in job.get("steps", []) or []:
            guarded = job_guarded or "failure()" in str(step.get("if", ""))
            if guarded and "dev.release.alerting" in str(step.get("run", "")):
                return True
    return False


def test_reachability_every_release_path_workflow_carries_a_failure_alert() -> None:
    """The declared release path is computed, and every member alerts."""
    release_path = _needs_own_alert(_WORKFLOW_DIR, module_root=_REPO_ROOT)

    # The four the plan names must all be discovered, so the derivation is
    # proven to actually reach them rather than returning a convenient subset.
    for expected in (
        "release-orchestrator.yml",
        "release-soak-promoter.yml",
        "publish-release.yml",
        "docs-publish.yml",
    ):
        assert expected in release_path, f"{expected} is not reachable from the orchestrator/promoter dispatch set"

    unalerted = [name for name in sorted(release_path) if not _has_failure_alert(_load(_WORKFLOW_DIR / name))]
    assert unalerted == [], f"release-path workflows with no failure alert: {unalerted}"


def test_reachability_gate_reds_on_a_planted_unalerted_workflow(tmp_path: Path) -> None:
    """Positive control against an injectable root.

    Without it, a derivation that returned an empty set and a tree that is
    fully alerted are indistinguishable - both make the assertion above pass.
    """
    planted = tmp_path / "workflows"
    planted.mkdir()
    (planted / "release-orchestrator.yml").write_text(
        "name: o\non:\n  workflow_dispatch:\njobs:\n"
        "  go:\n    runs-on: [self-hosted]\n    steps:\n      - run: gh workflow run new-lane.yml\n",
        encoding="utf-8",
    )
    (planted / "new-lane.yml").write_text(
        "name: n\non:\n  workflow_dispatch:\njobs:\n"
        "  go:\n    runs-on: [self-hosted]\n    steps:\n      - run: echo hi\n",
        encoding="utf-8",
    )

    release_path = _needs_own_alert(planted)
    assert "new-lane.yml" in release_path, "the derivation must discover a newly dispatched lane"

    unalerted = [name for name in sorted(release_path) if not _has_failure_alert(_load(planted / name))]
    assert "new-lane.yml" in unalerted, "the gate must red on a release-path workflow with no alert"


def _plant(workflow_dir: Path, name: str, run_body: str) -> None:
    indented = "\n".join(f"          {line}" for line in run_body.splitlines())
    workflow_dir.joinpath(name).write_text(
        f"name: {name}\non:\n  workflow_dispatch:\njobs:\n"
        f"  go:\n    runs-on: [self-hosted]\n    steps:\n      - run: |\n{indented}\n",
        encoding="utf-8",
    )


def test_a_workflow_named_only_in_printed_prose_is_not_counted_as_dispatched(tmp_path: Path) -> None:
    """Explaining why a lane is NOT being started is not starting it.

    The seal stage's dry-run branch echoes the reason it is withholding the
    publication dispatch, and names packaging-smoke.yml in that sentence. Read
    as a dispatch, it demanded an alert on a lane the campaign stage waits for
    - which the exclusion assertion below simultaneously forbids. Both tests
    encode the same model; only the derivation was wrong.
    """
    planted = tmp_path / "workflows"
    planted.mkdir()
    _plant(
        planted,
        "release-orchestrator.yml",
        'echo "not dispatching quiet-lane.yml on a rehearsal"\ngh workflow run loud-lane.yml\n',
    )
    _plant(planted, "quiet-lane.yml", "echo hi\n")
    _plant(planted, "loud-lane.yml", "echo hi\n")

    needs = _needs_own_alert(planted)

    assert "loud-lane.yml" in needs, "a real fire-and-forget dispatch must still be discovered"
    assert "quiet-lane.yml" not in needs, "a workflow named only in an echo was never dispatched"


def test_a_lane_dispatched_through_a_variable_is_still_discovered(tmp_path: Path) -> None:
    """Control for the narrowing above: it must not collapse to dispatch-line-only.

    The campaign stage assigns its workflow to a shell variable and dispatches
    through it, so a mention that sits nowhere near the dispatch verb is still
    a real dispatch. A derivation that only believed names appearing ON the
    dispatch line would go quiet on exactly that shape - and would look
    identical to a correctly narrowed one in the test above.
    """
    planted = tmp_path / "workflows"
    planted.mkdir()
    _plant(
        planted,
        "release-orchestrator.yml",
        'target=".github/workflows/indirect-lane.yml"\ngh workflow run "$target"\n',
    )
    _plant(planted, "indirect-lane.yml", "echo hi\n")

    assert "indirect-lane.yml" in _needs_own_alert(planted)


def test_multi_job_workflows_alert_from_a_dedicated_job_not_a_trailing_step() -> None:
    """The subtle way alerting silently covers almost nothing.

    `if: failure()` inside a job fires only when a step in THAT job failed, and
    a job whose dependency failed never runs at all. So an alert step appended
    to the last job of a chain would stay silent for every failure except one
    in the final stage - which looks correct in review and in a green suite.

    A dedicated job needing every other job, gated on `failure()`, is what
    makes the coverage real.
    """
    for name in ("release-orchestrator.yml", "publish-release.yml"):
        document = _load(_WORKFLOW_DIR / name)
        jobs = document["jobs"]
        assert "alert" in jobs, f"{name} has no dedicated alert job"

        alert = jobs["alert"]
        assert "failure()" in str(alert["if"])
        covered = set(alert["needs"])
        expected = set(jobs) - {"alert"}
        assert covered == expected, f"{name} alert job does not need every stage: missing {expected - covered}"


def test_the_single_job_promoter_alerts_from_a_step() -> None:
    """One job has no earlier job to be skipped by, so a step is correct there."""
    document = _load(_WORKFLOW_DIR / "release-soak-promoter.yml")

    assert set(document["jobs"]) == {"promote"}
    assert _has_failure_alert(document)


def test_the_docs_publisher_alert_reaches_a_human_not_only_the_run_log() -> None:
    """An `::error::` annotation notifies nobody who is not already looking.

    The docs publisher carried a failure step that only echoed a workflow
    annotation. That is prose asserting a property the code did not have: it
    reads as alerting while reaching exactly the person the removed approval
    click used to summon, and no longer does.
    """
    document = _load(_WORKFLOW_DIR / "docs-publish.yml")
    steps = [step for job in document["jobs"].values() for step in job.get("steps", [])]
    failure_steps = [step for step in steps if "failure()" in str(step.get("if", ""))]

    assert failure_steps, "the docs publisher must still alert on failure"
    assert any("dev.release.alerting" in str(step.get("run", "")) for step in failure_steps), (
        "the docs failure step only annotates the run log; it must also reach the operator"
    )


def test_a_waited_on_acquisition_lane_is_deliberately_excluded() -> None:
    """The narrowing is the substance of this gate, so it is pinned explicitly.

    The acquisition lanes are on the release path and are NOT in the
    must-alert set, because the orchestrator waits for each one: a failed lane
    fails the acquire stage, which fails the orchestrator, which alerts. Giving
    the lane its own alert would deliver two alerts for one event - the same
    train-the-operator-to-filter failure that ruled out sending both an issue
    and a webhook.

    Without this assertion, a derivation that quietly stopped discovering
    anything would still satisfy the coverage test above.
    """
    needs = _needs_own_alert(_WORKFLOW_DIR, module_root=_REPO_ROOT)

    for waited in ("packaging-scoop.yml", "packaging-homebrew.yml", "packaging-smoke.yml"):
        present = {path.name for path in iter_directory(_WORKFLOW_DIR, pattern="*.yml")}
        assert waited in present, f"{waited} should exist to be excluded"
        assert waited not in needs, f"{waited} is waited on by its dispatcher and must not alert separately"

    # ...and the set is exactly the four with no watching parent.
    assert needs == {
        "release-orchestrator.yml",
        "release-soak-promoter.yml",
        "publish-release.yml",
        "docs-publish.yml",
    }


def test_every_alert_invocation_supplies_the_refusal_detail() -> None:
    """An alert must say WHY, not only that something failed.

    Without a detail argument the emitter rendered its `(no detail captured)`
    placeholder on every alert, so the operator got a link and nothing else -
    spending their attention on navigation, which is the cost this channel
    exists to avoid.
    """
    for name in ("release-orchestrator.yml", "release-soak-promoter.yml", "publish-release.yml", "docs-publish.yml"):
        document = _load(_WORKFLOW_DIR / name)
        invocations = [
            str(step.get("run", ""))
            for job in document["jobs"].values()
            for step in job.get("steps", []) or []
            if "dev.release.alerting" in str(step.get("run", ""))
        ]
        assert invocations, f"{name} carries no alert invocation"
        for invocation in invocations:
            assert "--detail" in invocation, f"{name} alerts without supplying the refusal detail"


def test_the_rendered_payload_carries_the_supplied_detail() -> None:
    """The emitter must actually surface what the workflow captured.

    Paired with the assertion above deliberately: passing `--detail` and
    dropping it in the payload would satisfy the workflow-side check while
    delivering the same empty alert.
    """
    body = alert_payload(_alert())

    assert "REFUSED: version 1.2.3 is burned" in body
    assert "(no detail captured)" not in body

    # ...and the placeholder still appears when there genuinely is no detail,
    # so an empty alert is visibly empty rather than silently blank.
    empty = alert_payload(ReleaseAlert(workflow="w", run_id="1", run_url="u", stage="s", detail="  "))
    assert "(no detail captured)" in empty


def test_every_release_path_alert_guard_admits_a_cancelled_run() -> None:
    """A cancelled run is the same silence as a failed one.

    A runner eviction or a concurrency interaction cancels rather than fails,
    and `failure()` alone does not fire for a cancellation - so the release
    would end with no result and no alert, which is exactly the state this
    campaign exists to remove.
    """
    for name in ("release-orchestrator.yml", "release-soak-promoter.yml", "publish-release.yml", "docs-publish.yml"):
        document = _load(_WORKFLOW_DIR / name)
        guards = [
            str(job.get("if", "")) + str(step.get("if", ""))
            for job in document["jobs"].values()
            for step in job.get("steps", []) or []
            if "dev.release.alerting" in str(step.get("run", ""))
        ]
        assert guards, f"{name} carries no alert invocation"
        for guard in guards:
            assert "cancelled()" in guard, f"{name} alert guard does not admit a cancelled run: {guard!r}"


def test_a_failure_only_guard_is_caught_by_the_cancellation_assertion() -> None:
    """Positive control for the guard scan above.

    Without it, a scan that looked at the wrong field would pass on a tree
    where every guard was still `failure()` alone.
    """
    failure_only = {"jobs": {"j": {"if": "${{ failure() }}", "steps": [{"run": "dev.release.alerting"}]}}}

    guards = [
        str(job.get("if", "")) + str(step.get("if", ""))
        for job in failure_only["jobs"].values()
        for step in job.get("steps", [])
        if "dev.release.alerting" in str(step.get("run", ""))
    ]
    assert guards and all("cancelled()" not in guard for guard in guards)


def _write_label_refusing_gh(bin_dir: Path, log: Path) -> Path:
    """Write a real `gh` stub that refuses anything naming the alert label.

    Deliberately STRICTER than the live forge: it refuses every call naming
    the label, where the forge refuses only the labelled issue creation. If
    the emitter delivers under this stub it delivers under the real thing, and
    the strictness also covers the lookup path, which passes the same label
    and would otherwise abort the alert before it ever reached creation.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "gh.bat"
        script.write_text(
            "@echo off\r\n"
            f'echo %1 %2 %3 %4 %5 >> "{log}"\r\n'
            'echo %* | findstr /C:"release-alert" >nul\r\n'
            "if %errorlevel%==0 (echo could not add label >&2 & exit /b 1)\r\n"
            "echo []\r\n",
            encoding="utf-8",
        )
    else:
        script = bin_dir / "gh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            f'echo "$1 $2 $3 $4 $5" >> "{log}"\n'
            'if [[ "$*" == *release-alert* ]]; then echo "could not add label" >&2; exit 1; fi\n'
            "echo '[]'\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_the_alert_is_still_delivered_when_the_repository_has_no_alert_label(tmp_path: Path) -> None:
    """Delivery outranks filing.

    Measured on the live forge: the repository carries no `release-alert`
    label, so the labelled issue creation was refused, the emitter raised, the
    entry point caught it, and the alert degraded to a run-log warning nobody
    reads. The deliverable that pays for the removed approval click was
    delivering nothing.

    The label is how an operator subscribes to one stream rather than the whole
    tracker - a convenience. The alert is the deliverable. So a repository
    without the label must still receive the alert.
    """
    log = tmp_path / "argv.log"
    script = _write_label_refusing_gh(tmp_path / "bin", log)

    result = emit_alert(_alert(), repository="nevenincs/cadrumo", gh_executable=str(script))

    recorded = log.read_text(encoding="utf-8")
    assert "issue create" in recorded, "the alert must still be filed"
    assert "unlabelled" in result
    # It tried to label first, and only fell back after the forge refused - so
    # a repository that DOES carry the label still gets a labelled alert.
    assert "label create" in recorded


def test_a_repository_with_the_label_still_gets_a_labelled_alert(tmp_path: Path) -> None:
    """Control: the fallback must not become the only path.

    Without this, an emitter that had quietly stopped passing the label at all
    would satisfy the test above perfectly.
    """
    log = tmp_path / "argv.log"
    script = _write_recording_gh(tmp_path / "bin", stdout="[]", log=log)

    result = emit_alert(_alert(), repository="nevenincs/cadrumo", gh_executable=str(script))

    assert "unlabelled" not in result
    assert "opened alert" in result
