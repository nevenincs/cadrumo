"""Read which workflow jobs untrusted pull request code can reach, and what they may hold.

The repository is public, so anyone can open a pull request, and a pull
request's run executes the workflow file and the code of that pull request.
Three facts keep that safe, and each is read here from the workflow documents:

- a job on a self-hosted runner admits a pull request only from this
  repository and from an owner, a collaborator or the release App
  (:data:`ADMISSION`), because a self-hosted machine keeps state between jobs;
- every other job a pull request can start runs on a GitHub-hosted runner and
  holds no secret, no repository variable and no write permission;
- nothing runs on ``pull_request_target``, which would hand a fork's code the
  base repository's token and secrets.

A workflow that declares ``workflow_call`` is read as reachable by a pull
request, because a called workflow runs under its caller's event. Each
function returns the violations it finds as plain sentences, so a caller
asserts an empty list and a failure names the job.

Concurrency is read here too, in both directions: a pull request's newer event
cancels the run it supersedes, and a push to a development branch never ends
the run of an earlier landed head.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

__all__ = [
    "ADMISSION",
    "HOSTED_RUNNERS",
    "admission_violations",
    "checkout_credential_violations",
    "is_hosted",
    "landed_head_violations",
    "pull_request_reachable",
    "pull_request_target_violations",
    "superseded_run_violations",
    "triggers",
    "untrusted_job_violations",
]

_SAME_REPOSITORY: Final = "github.event.pull_request.head.repo.full_name == github.repository"
#: An owner, a collaborator, or the App that writes the release pull request.
#: Dependabot, other bots and outside contributors are none of these.
_TRUSTED_AUTHOR: Final = (
    "(github.event.pull_request.author_association == 'OWNER' || "
    "github.event.pull_request.author_association == 'COLLABORATOR' || "
    "github.event.pull_request.user.login == 'nevenincs-release[bot]')"
)
#: What admits a job to a self-hosted runner: any event but a pull request, or
#: a pull request from this repository by a trusted author.
ADMISSION: Final = f"(github.event_name != 'pull_request' || ({_SAME_REPOSITORY} && {_TRUSTED_AUTHOR}))"

#: The GitHub-hosted runner labels the workflows may name. Any other
#: ``runs-on`` is read as self-hosted: a label list, a matrix expression and a
#: misspelt label all reach a machine this file cannot prove is disposable.
HOSTED_RUNNERS: Final = frozenset({"ubuntu-24.04"})

_PULL_REQUEST_EVENTS: Final = frozenset({"pull_request", "pull_request_target", "workflow_call"})
_SECRET: Final = re.compile(r"\bsecrets\s*(?:\.\s*([A-Za-z_][A-Za-z0-9_-]*)|\[\s*'([^']*)'\s*\])")
_ANY_SECRETS_OBJECT: Final = re.compile(r"\bsecrets\b(?!\s*[.\[])")
_VARIABLE: Final = re.compile(r"\bvars\b\s*[.\[]")
_ALLOWED_SECRETS: Final = frozenset({"GITHUB_TOKEN"})
_READ_LEVELS: Final = frozenset({"read", "none"})
#: A workflow that is also dispatched or called cancels only its pull request runs.
_CANCEL_PULL_REQUESTS_ONLY: Final = "${{ github.event_name == 'pull_request' }}"
#: A push run's group ends in its own commit and no other event's does. A
#: group holds one running and one pending run, so two landed heads sharing
#: one lose the pending run to a third landing even when nothing is cancelled
#: in progress; a pull request's runs must still share theirs to be cancelled.
_PUSH_GROUP_SUFFIX: Final = "${{ github.event_name == 'push' && format('-{0}', github.sha) || '' }}"
_RELEASE_BRANCH: Final = "main"

type Documents = Sequence[tuple[str, Mapping[str, Any]]]


def triggers(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a workflow's ``on:`` block as a map, whichever YAML shape it took."""
    # PyYAML reads the bare key `on` as the boolean True.
    trigger = document.get("on", document.get(True))
    if isinstance(trigger, str):
        return {trigger: None}
    if isinstance(trigger, list):
        return dict.fromkeys(trigger)
    return dict(trigger or {})


def pull_request_reachable(document: Mapping[str, Any]) -> bool:
    """Return whether a pull request event can start, or be passed to, this workflow."""
    return bool(_PULL_REQUEST_EVENTS & set(triggers(document)))


def is_hosted(job: Mapping[str, Any]) -> bool:
    """Return whether a job provably runs on a GitHub-hosted runner."""
    runs_on = job.get("runs-on")
    return isinstance(runs_on, str) and runs_on in HOSTED_RUNNERS


def _jobs(document: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    return document.get("jobs") or {}


def _expression(condition: object) -> str:
    text = str(condition or "").strip()
    if text.startswith("${{") and text.endswith("}}"):
        return text[3:-2].strip()
    return text


def _is_admitted(job: Mapping[str, Any]) -> str | None:
    """Return why a job's ``if:`` does not require the admission clause, or ``None``."""
    condition = _expression(job.get("if"))
    position = condition.find(ADMISSION)
    if position < 0 or condition[:position].rstrip().endswith("!"):
        return "without the admission clause"
    # The clause must be a required conjunct, not one side of an `||` that
    # another disjunct could satisfy on an untrusted pull request.
    if "||" in condition.replace(ADMISSION, ""):
        return "behind a widened admission clause"
    return None


def pull_request_target_violations(documents: Documents) -> list[str]:
    """Report every workflow that runs on ``pull_request_target``."""
    return [
        f"{name} runs on pull_request_target"
        for name, document in documents
        if "pull_request_target" in triggers(document)
    ]


def admission_violations(documents: Documents) -> list[str]:
    """Report every way an untrusted pull request might reach a self-hosted runner.

    A job that calls a reusable workflow is followed into this repository's
    own workflows, whose jobs are then judged like any other; a call that
    leaves the repository cannot be followed, so it needs the clause itself.
    """
    violations: list[str] = []
    for name, document in documents:
        if not pull_request_reachable(document):
            continue
        types = (triggers(document).get("pull_request") or {}).get("types") or []
        if "labeled" in types:
            violations.append(f"{name} admits label events, which a bot can raise")
        for job_name, job in _jobs(document).items():
            if "uses" in job:
                if str(job["uses"]).startswith("./.github/workflows/"):
                    continue
                reason = _is_admitted(job)
                if reason is not None:
                    violations.append(f"{name}: {job_name} calls a workflow outside the repository {reason}")
                continue
            if is_hosted(job):
                continue
            reason = _is_admitted(job)
            if reason is not None:
                violations.append(f"{name}: {job_name} reaches a self-hosted runner {reason}")
    return violations


def _text(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _secret_names(text: str) -> set[str]:
    names: set[str] = {match.group(1) or match.group(2) for match in _SECRET.finditer(text)}
    if _ANY_SECRETS_OBJECT.search(text):
        names.add("the whole secrets object")
    return names - _ALLOWED_SECRETS


def _write_scopes(permissions: object) -> list[str]:
    if permissions is None:
        return ["an undeclared permission set"]
    if isinstance(permissions, str):
        return [] if permissions == "read-all" else [permissions]
    if not isinstance(permissions, Mapping):
        return [f"an unreadable permission set {permissions!r}"]
    return sorted(f"{scope}: {level}" for scope, level in permissions.items() if level not in _READ_LEVELS)


def untrusted_job_violations(documents: Documents) -> list[str]:
    """Report what a pull request's code could take from the jobs it can start.

    No job a pull request can reach may name a secret other than the run's own
    token or inherit its caller's secrets. A job without the admission clause
    runs any pull request's code, so it may also read no repository variable
    and hold no write permission.
    """
    violations: list[str] = []
    for name, document in documents:
        if not pull_request_reachable(document):
            continue
        shared = {key: value for key, value in document.items() if key not in {"jobs", "on", True}}
        shared_text = _text(shared)
        for job_name, job in _jobs(document).items():
            # The `secrets:` key of a call is judged on its own below; as text
            # it would read as a use of the whole secrets object.
            job_text = _text({key: value for key, value in job.items() if key != "secrets"}) + shared_text
            job_text += _text(job["secrets"]) if isinstance(job.get("secrets"), Mapping) else ""
            violations.extend(f"{name}: {job_name} references {secret}" for secret in sorted(_secret_names(job_text)))
            if job.get("secrets") == "inherit":
                violations.append(f"{name}: {job_name} inherits its caller's secrets")
            if _is_admitted(job) is None:
                continue
            if _VARIABLE.search(job_text):
                violations.append(f"{name}: {job_name} reads a repository variable on an untrusted pull request")
            permissions = job.get("permissions", document.get("permissions"))
            violations.extend(
                f"{name}: {job_name} holds {scope} on an untrusted pull request" for scope in _write_scopes(permissions)
            )
    return violations


def _steps(document: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for job_name, job in _jobs(document).items():
        for step in job.get("steps") or []:
            yield job_name, step


def checkout_credential_violations(documents: Documents) -> list[str]:
    """Report every checkout that leaves the run's token in the working tree."""
    return [
        f"{name}: {job_name} checks out with persisted credentials"
        for name, document in documents
        for job_name, step in _steps(document)
        if str(step.get("uses", "")).startswith("actions/checkout@")
        and (step.get("with") or {}).get("persist-credentials") is not False
    ]


def superseded_run_violations(documents: Documents) -> list[str]:
    """Report every pull request workflow that lets a superseded run keep going."""
    violations: list[str] = []
    for name, document in documents:
        if "pull_request" not in triggers(document):
            continue
        concurrency = document.get("concurrency")
        if not isinstance(concurrency, Mapping):
            violations.append(f"{name} declares no concurrency group")
            continue
        if "github.event.pull_request.number" not in str(concurrency.get("group", "")):
            violations.append(f"{name} does not group runs by pull request")
        if concurrency.get("cancel-in-progress") not in (True, _CANCEL_PULL_REQUESTS_ONLY):
            violations.append(f"{name} does not cancel a superseded run")
    return violations


def _pushed_branches(document: Mapping[str, Any]) -> list[str]:
    """Return the branches a workflow's push trigger names; empty when it names none."""
    push = triggers(document).get("push")
    branches = push.get("branches") if isinstance(push, Mapping) else None
    return [str(branch) for branch in branches or []]


def landed_head_violations(documents: Documents) -> list[str]:
    """Report every development-branch push workflow in which one landed head's run can end another's.

    A push trigger that names no branch, or names the release branch, isolates
    that branch's runs by its own expression and is judged by the check-set
    contract; this rule covers every push trigger that names other branches
    only.
    """
    violations: list[str] = []
    for name, document in documents:
        branches = _pushed_branches(document)
        if not branches or _RELEASE_BRANCH in branches:
            continue
        concurrency = document.get("concurrency")
        # No group at all lets every run complete, which is the property.
        if isinstance(concurrency, Mapping):
            if not str(concurrency.get("group", "")).endswith(_PUSH_GROUP_SUFFIX):
                violations.append(f"{name} lets the runs of two landed heads share a concurrency group")
            if concurrency.get("cancel-in-progress", False) not in (False, _CANCEL_PULL_REQUESTS_ONLY):
                violations.append(f"{name} lets a push cancel the run of an earlier landed head")
        violations.extend(
            f"{name}: {job_name} holds a concurrency group a later landed head's run would contend for"
            for job_name, job in _jobs(document).items()
            if "concurrency" in job
        )
    return violations
