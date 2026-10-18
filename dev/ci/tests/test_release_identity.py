"""Which identity writes each part of a release.

The release pull request must be written by the release App. A pull request or
a push written with the default token raises no workflow events, so the merge
gate never runs on it and the required check stays expected until someone
works around it. Tags and GitHub releases stay on the default token, because
GitHub raises no workflow events for refs and releases that token creates, and
nothing keyed on a tag or a release should start twice.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Final

import pytest
import yaml

from dev._paths import REPO_ROOT

from ..workflow_run_text import executed_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RELEASE_PLEASE: Final = REPO_ROOT / ".github" / "workflows" / "release-please.yml"
_RELEASE_ACTION: Final = "googleapis/release-please-action@"
_APP_MINTER_ACTION: Final = "actions/create-github-app-token@"
_FULL_SHA: Final = re.compile(r"@[0-9a-f]{40}$")
_APP_INPUTS: Final = {
    "client-id": "${{ vars.RELEASE_APP_CLIENT_ID }}",
    "private-key": "${{ secrets.RELEASE_APP_PRIVATE_KEY }}",
    "permission-contents": "write",
    "permission-pull-requests": "write",
}
#: A token chosen with `a || b` silently falls back to the default token when
#: the App is unavailable, which is the identity this file exists to keep off
#: the release pull request.
_TOKEN_FALLBACK: Final = re.compile(r"\|\|\s*(?:secrets\.GITHUB_TOKEN|github\.token)")
#: Commands that write a branch or a pull request with whatever token the step holds.
_BRANCH_WRITES: Final = ("git push", "--method PUT", "--method PATCH", "gh pr create", "gh pr merge", "gh pr edit")


def _steps(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in (document.get("jobs") or {}).values() for step in job.get("steps") or []]


def _identity_violations(document: dict[str, Any], text: str) -> list[str]:
    """Why the release pull request might be written by anything but the release App."""
    violations: list[str] = []
    steps = _steps(document)
    minters = [step for step in steps if str(step.get("uses", "")).startswith(_APP_MINTER_ACTION)]
    if len(minters) != 1:
        return [f"{len(minters)} steps mint the release App token, not one"]
    minter = minters[0]
    if not _FULL_SHA.search(str(minter["uses"])):
        violations.append("the App token action is not pinned to a full commit SHA")
    if (minter.get("with") or {}) != _APP_INPUTS:
        violations.append(f"the App token is minted with {minter.get('with')}, not {_APP_INPUTS}")
    app_token = f"${{{{ steps.{minter.get('id')}.outputs.token }}}}"

    releases = [step for step in steps if str(step.get("uses", "")).startswith(_RELEASE_ACTION)]
    proposers = [step for step in releases if (step.get("with") or {}).get("skip-github-release") is True]
    cutters = [step for step in releases if (step.get("with") or {}).get("skip-github-pull-request") is True]
    if len(proposers) != 1 or [(step.get("with") or {}).get("token") for step in proposers] != [app_token]:
        violations.append("the release pull request is not written by exactly one release-please step on the App token")
    if len(cutters) != 1 or any("token" in (step.get("with") or {}) for step in cutters):
        violations.append("tags and releases are not cut by exactly one release-please step on the default token")
    if len(releases) != len(proposers) + len(cutters):
        violations.append("a release-please step both proposes and cuts, so one identity writes both")

    if _TOKEN_FALLBACK.search(text):
        violations.append("a token falls back to the default token")
    writes = sorted(
        {command for step in steps for command in _BRANCH_WRITES if command in executed_text(step.get("run"))}
    )
    if writes:
        violations.append(f"a step writes a branch or pull request outside release-please: {writes}")
    return violations


def test_the_release_app_writes_the_release_pull_request() -> None:
    """The App token proposes, the default token cuts, and nothing falls back or writes around them.

    Proved able to fail: replacing the proposing step's `token:` in
    `release-please.yml` with `${{ steps.app-token.outputs.token ||
    secrets.GITHUB_TOKEN }}` and running this test alone failed on its
    assertion, the helper reporting both the proposer and the fallback;
    restoring the App token made it pass.
    """
    text = _RELEASE_PLEASE.read_text(encoding="utf-8")
    assert _identity_violations(yaml.safe_load(text), text) == []


def test_the_identity_check_detects_each_regression() -> None:
    """Teeth: each way back to the default token is reported on its own."""
    text = _RELEASE_PLEASE.read_text(encoding="utf-8")
    live = yaml.safe_load(text)

    def releases(document: dict[str, Any]) -> list[dict[str, Any]]:
        return [step for step in _steps(document) if str(step.get("uses", "")).startswith(_RELEASE_ACTION)]

    default_token = deepcopy(live)
    for step in releases(default_token):
        step["with"].pop("token", None)
    assert _identity_violations(default_token, text) == [
        "the release pull request is not written by exactly one release-please step on the App token"
    ]

    fallback = deepcopy(live)
    fallback_text = text.replace(
        "token: ${{ steps.app-token.outputs.token }}",
        "token: ${{ steps.app-token.outputs.token || secrets.GITHUB_TOKEN }}",
    )
    assert fallback_text != text
    assert _identity_violations(fallback, fallback_text) == ["a token falls back to the default token"]

    merged = deepcopy(live)
    for step in releases(merged):
        step["with"].pop("skip-github-release", None)
        step["with"].pop("skip-github-pull-request", None)
    assert _identity_violations(merged, text) == [
        "the release pull request is not written by exactly one release-please step on the App token",
        "tags and releases are not cut by exactly one release-please step on the default token",
        "a release-please step both proposes and cuts, so one identity writes both",
    ]

    widened = deepcopy(live)
    minter = next(step for step in _steps(widened) if str(step.get("uses", "")).startswith(_APP_MINTER_ACTION))
    minter["with"]["permission-administration"] = "write"
    minter["uses"] = _APP_MINTER_ACTION + "v3"
    assert _identity_violations(widened, text) == [
        "the App token action is not pinned to a full commit SHA",
        f"the App token is minted with {minter['with']}, not {_APP_INPUTS}",
    ]

    pushed = deepcopy(live)
    next(iter(pushed["jobs"].values()))["steps"].append(
        {"run": 'gh api --method PUT "repos/${GITHUB_REPOSITORY}/contents/uv.lock" --input body.json'}
    )
    assert _identity_violations(pushed, text) == [
        "a step writes a branch or pull request outside release-please: ['--method PUT']"
    ]
