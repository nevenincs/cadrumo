"""Report a failed or refused release-path run to somewhere a human will see it.

This module exists to pay for a specific removal. The publication used to stop
at an approval click, and that click was the only moment a human was
STRUCTURALLY guaranteed to look at a release. With it gone, a silently failed
orchestration is indistinguishable from a release nobody started -- both look
like nothing happening -- and that is the one new failure mode the automation
creates.

A workflow-log annotation does not close this. ``echo "::error::"`` is visible
only to someone already reading the run, which is exactly the person the click
used to summon and no longer does. An alert has to arrive somewhere the
operator looks WITHOUT being told to look.

The default target is therefore a labelled repository issue: it needs no
configuration, no secret, and no nominated channel, so alerting works from the
moment this lands rather than from the moment someone provisions a webhook.
Once the operator nominates a channel (OP-10) the webhook variable overrides
it.

Re-alerting is idempotent per run. A workflow re-run, or several failing jobs
in one run, must not mint a fresh issue apiece -- an alerting channel that
floods is one the operator learns to filter, which returns us to nobody
looking by a slower route.

See Also:
    :func:`alert_payload`
        The pure projection, testable without a process.
    :func:`emit_alert`
        The one side-effecting entry point.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8
_GH_TIMEOUT_SECONDS: Final[float] = 60.0
_WEBHOOK_TIMEOUT_SECONDS: Final[float] = 30.0

#: The label every release alert carries, so the operator can subscribe to one
#: label rather than to the whole issue tracker.
ALERT_LABEL: Final[str] = "release-alert"

#: Repository variable naming an operator-chosen webhook. Empty until OP-10 is
#: decided; the issue path is the default precisely so alerting does not wait.
WEBHOOK_VARIABLE: Final[str] = "CADRUMO_ALERT_WEBHOOK"


class AlertError(RuntimeError):
    """Emitting an alert failed; the message names the transport that refused."""


@dataclass(frozen=True, slots=True)
class ReleaseAlert:
    """One failed or refused release-path run, as the operator will read it."""

    workflow: str
    run_id: str
    run_url: str
    stage: str
    detail: str

    @property
    def fingerprint(self) -> str:
        """Stable per-RUN identity, so re-runs update one alert instead of adding one.

        Keyed on the run rather than the workflow: two genuinely different
        failed releases deserve two alerts, while one release failing twice
        deserves one thread.
        """
        return f"{self.workflow}#{self.run_id}"

    @property
    def title(self) -> str:
        """Return the issue title, carrying the fingerprint so it can be found again."""
        return f"Release alert: {self.workflow} failed ({self.fingerprint})"


def alert_payload(alert: ReleaseAlert) -> str:
    """Render the operator-facing alert body.

    Carries the run URL first. The operator's next action is always to open the
    run, and an alert that makes them search for it has spent their attention
    on navigation rather than on the failure.
    """
    return "\n".join(
        (
            f"**{alert.workflow}** failed at stage `{alert.stage}`.",
            "",
            f"Run: {alert.run_url}",
            "",
            "```",
            alert.detail.strip() or "(no detail captured)",
            "```",
            "",
            "This alert exists because the release pipeline no longer stops at a human approval click.",
            "A failed release that alerts nobody is indistinguishable from a release nobody started.",
        ),
    )


def _resolve_gh(explicit: str | None) -> str:
    resolved = explicit if explicit is not None else shutil.which("gh")
    if resolved is None:
        raise AlertError("gh is not on PATH; cannot open a release alert issue")
    return resolved


def _run_gh(gh: str, arguments: Sequence[str]) -> str:
    """Run one gh invocation, converting every failure mode into AlertError.

    An absent or unrunnable executable raises OSError from subprocess, which
    would escape this module as a foreign exception type and defeat the
    caller's `except AlertError` - so the alert path would crash the failure
    handler it lives in rather than degrading to a warning.
    """
    try:
        completed = subprocess.run(
            [gh, *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AlertError(f"gh could not be run: {error}") from error
    if completed.returncode != 0:
        raise AlertError(
            f"gh {' '.join(arguments)} failed (rc={completed.returncode}): {completed.stderr.strip()[:300]}",
        )
    return completed.stdout


def find_open_alert(alert: ReleaseAlert, *, repository: str, gh_executable: str | None = None) -> str | None:
    """Return the number of an open alert for this run, or ``None``.

    Searched by the fingerprint in the title rather than by label alone: the
    label collects every release alert, but only the fingerprint identifies
    THIS run's.
    """
    gh = _resolve_gh(gh_executable)
    base = ["issue", "list", "--repo", repository, "--state", "open", "--json", "number,title"]
    try:
        raw = _run_gh(gh, [*base, "--label", ALERT_LABEL])
    except AlertError:
        # The label may not exist on this repository. Falling back to an
        # unlabelled query keeps DEDUPLICATION working there; failing here
        # instead would abort the whole alert over a filing convenience.
        try:
            raw = _run_gh(gh, base)
        except AlertError:
            # Cannot determine whether an alert already exists. Returning None
            # means the caller opens a new one: a duplicate alert is a far
            # better outcome than no alert, which is the silence this module
            # exists to remove.
            return None
    try:
        issues = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return None
    for issue in issues:
        if alert.fingerprint in str(issue.get("title", "")):
            return str(issue.get("number"))
    return None


def ensure_alert_label(*, repository: str, gh_executable: str | None = None) -> bool:
    """Create the alert label when the repository lacks it; report whether it exists.

    Measured, not assumed: the live repository carried no ``release-alert``
    label, so every default-path alert was refused by the forge and degraded to
    a run-log warning. The alerting deliverable that pays for the removed
    approval click was therefore delivering nothing at all.

    Never raises. A repository that already has the label, and a token that
    cannot create one, both return without disturbing the caller -- the
    subsequent issue creation is what actually has to succeed.
    """
    gh = _resolve_gh(gh_executable)
    try:
        _run_gh(
            gh,
            [
                "label",
                "create",
                ALERT_LABEL,
                "--repo",
                repository,
                "--description",
                "Automated release-pipeline failure alert",
                "--color",
                "B60205",
            ],
        )
    except AlertError:
        # Already present, or not creatable with this token. Both are fine here.
        return False
    return True


def post_webhook(url: str, alert: ReleaseAlert) -> None:
    """POST the alert to an operator-nominated webhook."""
    body = json.dumps({"text": alert_payload(alert), "workflow": alert.workflow, "run_url": alert.run_url})
    request = urllib.request.Request(  # noqa: S310 - operator-nominated https endpoint
        url,
        data=body.encode(_UTF_8),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_WEBHOOK_TIMEOUT_SECONDS):  # noqa: S310
            return
    except (urllib.error.URLError, OSError) as error:
        raise AlertError(f"alert webhook refused the delivery: {error}") from error


def emit_alert(
    alert: ReleaseAlert,
    *,
    repository: str,
    webhook_url: str = "",
    gh_executable: str | None = None,
    webhook_sender: Callable[[str, ReleaseAlert], None] = post_webhook,
) -> str:
    """Deliver one alert and return a one-line description of what was delivered.

    The webhook, when configured, REPLACES the issue rather than supplementing
    it: two channels for one event trains the operator to read whichever is
    quieter, and the nominated channel is the one they chose.
    """
    if webhook_url.strip():
        webhook_sender(webhook_url.strip(), alert)
        return f"alerted via webhook: {alert.fingerprint}"

    gh = _resolve_gh(gh_executable)
    if (existing := find_open_alert(alert, repository=repository, gh_executable=gh)) is not None:
        with tempfile.TemporaryDirectory() as scratch:
            body_path = Path(scratch) / "alert-body.md"
            body_path.write_text(alert_payload(alert), encoding=_UTF_8, newline="\n")
            _run_gh(gh, ["issue", "comment", existing, "--repo", repository, "--body-file", str(body_path)])
        return f"updated open alert #{existing}: {alert.fingerprint}"

    ensure_alert_label(repository=repository, gh_executable=gh)

    # The body rides a FILE rather than an argv element. It is multi-line and
    # unbounded, and a command line is neither: Windows caps one at ~8k
    # characters, and embedded newlines are quoted differently by every shell
    # in the chain. `--body-file` sidesteps both.
    with tempfile.TemporaryDirectory() as scratch:
        body_path = Path(scratch) / "alert-body.md"
        body_path.write_text(alert_payload(alert), encoding=_UTF_8, newline="\n")
        base = ["issue", "create", "--repo", repository, "--title", alert.title, "--body-file", str(body_path)]
        return _create_alert_issue(gh, base, alert)


def _create_alert_issue(gh: str, base: list[str], alert: ReleaseAlert) -> str:
    """Create the alert issue, dropping the label rather than the alert."""
    try:
        _run_gh(gh, [*base, "--label", ALERT_LABEL])
    except AlertError:
        # DELIVERY OUTRANKS FILING. The label is how an operator subscribes to
        # one stream instead of the whole tracker, which is a convenience; the
        # alert itself is the deliverable that pays for the removed approval
        # click. A repository whose label is absent or whose token cannot
        # create one must still receive the alert, so this falls back to an
        # unlabelled issue rather than raising and degrading to a run-log
        # warning nobody reads.
        _run_gh(gh, base)
        return f"opened alert (unlabelled - {ALERT_LABEL} unavailable): {alert.fingerprint}"
    return f"opened alert: {alert.fingerprint}"


def main(argv: Sequence[str] | None = None) -> int:
    """Emit one release alert from the failing workflow's own environment.

    Never raises out of a failure handler. An alerting transport that itself
    fails must not replace the original failure with its own: the run is
    already red, and the operator needs the first error, not the second.
    """
    parser = argparse.ArgumentParser(description="Report a failed release-path run to the operator.")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--workflow", default=os.environ.get("GITHUB_WORKFLOW", "unknown workflow"))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "0"))
    parser.add_argument("--stage", default="unknown")
    parser.add_argument("--detail", default="")
    parser.add_argument("--webhook", default=os.environ.get(WEBHOOK_VARIABLE, ""))
    parser.add_argument("--gh", default=None)
    args = parser.parse_args(argv)

    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    alert = ReleaseAlert(
        workflow=args.workflow,
        run_id=args.run_id,
        run_url=f"{server}/{args.repository}/actions/runs/{args.run_id}",
        stage=args.stage,
        detail=args.detail,
    )
    try:
        print(emit_alert(alert, repository=args.repository, webhook_url=args.webhook, gh_executable=args.gh))
    except AlertError as error:
        # Loud on the run log, but never fatal. See the docstring: the run is
        # already failing and its original error is the one that matters.
        print(f"::warning::release alert could not be delivered: {error}")
    return 0


__all__ = [
    "ALERT_LABEL",
    "WEBHOOK_VARIABLE",
    "AlertError",
    "ReleaseAlert",
    "alert_payload",
    "emit_alert",
    "ensure_alert_label",
    "find_open_alert",
    "main",
    "post_webhook",
]


if __name__ == "__main__":
    raise SystemExit(main())
