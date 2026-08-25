"""Read-only inventory of the forge deployment environments and their rules.

An obligation split across the repository and the forge is half-invisible by
construction: a settings change leaves no commit, so nothing in the tree records
whether it happened. That is not hypothetical here. Two accepted operator
obligations were found PARTIALLY executed on the forge with no trail, and their
tracking artefacts went on describing a state that had stopped being true.

This module is the repository's half of the answer. It cannot perform an
operator settings action -- removing a protection rule and deleting an
environment are forge acts, and no agent can do either -- but it can make the
current state READABLE, so an operator obligation is verified rather than
assumed, and so the next reader is told what is rather than what was intended.

It is strictly read-only. It issues one GET per environment and holds no token
of its own, and there is deliberately no write path in this module: an inventory
that could also mutate would be a standing authority over exactly the settings
it exists to audit.

Operator obligations this reports on:

OP-9
    The ``required_reviewers`` protection rule comes OFF both the ``release``
    and ``docs`` environments. Both environments STAY, and so does each
    ``branch_policy`` rule: the environment name is the Trusted Publishing trust
    anchor and the shared-runner product boundary, and ``branch_policy`` pins
    which refs may deploy and is not a human gate. Removing the environments
    along with the rule breaks OIDC publication outright.

OP-12
    The orphaned ``pypi-data-official`` environment is deleted. It is a live
    Trusted Publishing trust anchor left behind by the retired ``pypi-upload.yml``
    workflow, which no longer exists in this tree — standing authority with no
    owner. This module detects the orphan class generically
    (:attr:`EnvironmentRecord.is_orphaned`): an environment that still exists on the
    forge but that NO live workflow in ``.github/workflows/`` declares
    ``environment:`` for. That is the repository-verifiable half of "orphaned".
    Whether a matching index-side PyPI Trusted Publisher registration still
    exists is outside this repository and this forge — no agent can check or
    clear it from here, and this module never claims to.

Alongside OP-10 (nominating the alerting channel)
    The ``release-alert`` label the default failure-alert path
    (:mod:`dev.release.alerting`) collects every alert issue under must exist
    on the forge, or every default-path alert silently degrades to a run-log
    warning nobody reads — measured live on 2026-08-02: the label does not
    exist on ``nevenincs/cadrumo``. This module reports that state
    (:func:`fetch_label`) so it is verified rather than assumed, the same
    discipline OP-9/OP-12 already get.

See Also:
    :func:`protection_rule_types`
        The parse layer, over an already-fetched payload.
    :func:`environments_referenced_by_workflows`
        The repo-tree scan behind orphan detection.
    :func:`fetch_environments`
        The environment subprocess boundary.
    :func:`fetch_label`
        The label subprocess boundary.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from cadrumo.core import scan_directory

from .._paths import REPO_ROOT, UTF_8

_GH_TIMEOUT_SECONDS: Final[float] = 30.0
_DEFAULT_REPO_SLUG: Final[str] = "nevenincs/cadrumo"
_UTF_8: Final[str] = UTF_8

#: The protection rule that gates a deployment on a human approval click. This
#: is the rule OP-9 removes; every other rule type is left alone.
HUMAN_APPROVAL_RULE: Final[str] = "required_reviewers"

#: Environments whose ``required_reviewers`` rule OP-9 removes. Both are OIDC
#: trust anchors and both keep their ``branch_policy``.
OP9_ENVIRONMENTS: Final[tuple[str, ...]] = ("release", "docs")

#: Environments whose live-but-unreferenced status this module checks for the
#: orphan class OP-12 names. ``pypi-data-official`` is the one measured orphan
#: (its owning workflow, ``pypi-upload.yml``, was deleted 2026-07-27); a future
#: retirement adds its environment name here rather than growing a bespoke check.
ORPHAN_CANDIDATE_ENVIRONMENTS: Final[tuple[str, ...]] = ("pypi-data-official",)

#: The full default inventory: OP-9's two environments plus every named orphan
#: candidate. This is what a plain ``python -m dev.release.environment_inventory``
#: reports on, matching the RELEASING.md verification instruction.
DEFAULT_INVENTORIED_ENVIRONMENTS: Final[tuple[str, ...]] = (*OP9_ENVIRONMENTS, *ORPHAN_CANDIDATE_ENVIRONMENTS)

#: The label the failure-alert emitter's default path
#: (``dev.release.alerting.ALERT_LABEL``) collects every release alert issue
#: under, so an operator can subscribe to one label rather than the whole
#: tracker. Declared here as a local literal rather than imported from
#: ``dev.release.alerting`` — the two modules land on independent schedules in
#: this shared worktree, and importing would make this module's commit order
#: depend on that one's. It MUST stay byte-identical to
#: ``dev.release.alerting.ALERT_LABEL``.
ALERT_LABEL: Final[str] = "release-alert"


def _repo_root() -> Path:
    """Return the repository root two levels above this module."""
    return REPO_ROOT


@dataclass(frozen=True, slots=True)
class EnvironmentRecord:
    """One forge environment as currently configured, or the reason it is unknown.

    ``rule_types`` is ``None`` -- not the empty tuple -- when the environment
    could not be read. The distinction is the whole point of this type: an
    environment with no protection rules and an environment whose rules could
    not be determined look identical in any representation that collapses both
    to "empty", and they mean opposite things. An unreadable environment is
    never reported as clean.
    """

    name: str
    rule_types: tuple[str, ...] | None
    detail: str = ""
    #: Live workflow paths that declare ``environment: <name>``, or ``None``
    #: when the repo-tree scan was not run for this record (the three-way
    #: distinction matters the same way ``rule_types`` does: "no workflow
    #: references this" and "we never checked" are opposite facts).
    referenced_by: tuple[str, ...] | None = None

    @property
    def readable(self) -> bool:
        """Whether the environment's rule set was actually determined."""
        return self.rule_types is not None

    @property
    def carries_human_approval_gate(self) -> bool | None:
        """Whether a human approval rule is present, or ``None`` when unknown."""
        if self.rule_types is None:
            return None
        return HUMAN_APPROVAL_RULE in self.rule_types

    @property
    def is_orphaned(self) -> bool | None:
        """Whether this is a live forge environment no workflow in the tree claims.

        ``None`` when unknown: either the environment could not be read from
        the forge, or the repo-tree reference scan was not performed for this
        record. Never ``True`` for an unreadable environment — an orphan claim
        requires confirming the environment still exists.
        """
        if not self.readable or self.referenced_by is None:
            return None
        return len(self.referenced_by) == 0


@dataclass(frozen=True, slots=True)
class LabelRecord:
    """Whether one repository label exists on the forge, or the reason it is unknown.

    ``exists`` is a three-state fact, matching :class:`EnvironmentRecord`'s own
    readable/unreadable discipline: ``True`` (confirmed present), ``False`` (a
    genuine 404 — confirmed absent, real actionable state: create the label),
    or ``None`` (could not be determined — ``gh`` missing, a timeout, or any
    other failure). A confirmed-absent label and an undetermined one must
    never collapse to the same report line: an operator who has not yet
    created the label needs to see that plainly, distinct from a transient
    forge-reachability failure that tells them nothing.
    """

    name: str
    exists: bool | None
    detail: str = ""

    @property
    def readable(self) -> bool:
        """Whether existence was actually determined (True or False), not merely guessed."""
        return self.exists is not None


def protection_rule_types(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the rule type names declared on one environment payload.

    Tolerant of a malformed entry rather than raising: a rule with no ``type``
    is skipped, because the caller's question is "is a human gate present", and
    an unparseable neighbour rule does not change the answer for the rules that
    did parse. A wholly unreadable environment is a different case and is
    represented by ``EnvironmentRecord.rule_types is None``.
    """
    rules = payload.get("protection_rules")
    if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
        return ()
    types: list[str] = []
    for rule in rules:
        if isinstance(rule, Mapping) and isinstance(name := rule.get("type"), str):
            types.append(name)
    return tuple(types)


def _workflow_files(repo_root: Path) -> tuple[Path, ...]:
    """Return every ``.github/workflows/*.yml`` file under ``repo_root``, sorted."""
    workflows_dir = repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return ()
    return scan_directory(workflows_dir, pattern="*.yml")


def environments_referenced_by_workflows(repo_root: Path) -> Mapping[str, tuple[str, ...]]:
    """Return environment name -> the live workflow paths that deploy to it.

    Scans every ``.github/workflows/*.yml`` file for a job-level ``environment:``
    key: the bare scalar-name form this repo uses (``environment: release``) and,
    defensively, the ``{name, url}`` mapping form. An environment name absent
    from this mapping's keys has no live workflow claiming it as a deployment
    target — that absence is the repository-verifiable half of "orphaned"
    (:attr:`EnvironmentRecord.is_orphaned`). The external half — whether a
    matching index-side Trusted Publisher registration still names a workflow —
    lives outside this repository and this forge, and is never claimed here.

    A malformed workflow file is skipped rather than raised: a neighbour's YAML
    error must not blind this scan to every other workflow's declarations.
    """
    references: dict[str, list[str]] = {}
    for workflow_path in _workflow_files(repo_root):
        try:
            document = yaml.safe_load(workflow_path.read_text(encoding=_UTF_8))
        except (yaml.YAMLError, UnicodeDecodeError):
            continue
        if not isinstance(document, Mapping):
            continue
        jobs = document.get("jobs")
        if not isinstance(jobs, Mapping):
            continue
        relative = workflow_path.relative_to(repo_root).as_posix()
        for job in jobs.values():
            if not isinstance(job, Mapping):
                continue
            environment = job.get("environment")
            if isinstance(environment, str):
                name = environment
            elif isinstance(environment, Mapping) and isinstance(environment.get("name"), str):
                name = environment["name"]
            else:
                continue
            references.setdefault(name, []).append(relative)
    return {name: tuple(sorted(set(paths))) for name, paths in references.items()}


def fetch_environments(
    names: Sequence[str] = OP9_ENVIRONMENTS,
    *,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
    repo_root: Path | None = None,
) -> tuple[EnvironmentRecord, ...]:
    """Read each named environment from the forge, one GET apiece.

    ``gh_executable`` accepts an explicit resolved path so tests can drive a
    real stub executable without depending on the host's PATH resolution rules,
    matching the injection the readiness gate's blocker check already uses.

    Every failure mode -- ``gh`` absent, a non-zero exit, a timeout, non-JSON
    output -- yields an UNREADABLE record carrying the reason, never a record
    that happens to look rule-free.

    ``repo_root`` opts a caller into orphan detection: when supplied, every
    successfully-read record's ``referenced_by`` is populated from
    :func:`environments_referenced_by_workflows` scanned at that root. Omitted
    (the default), every record's ``referenced_by`` stays ``None`` and
    :attr:`EnvironmentRecord.is_orphaned` reports unknown rather than guessing
    from an unscanned tree.
    """
    resolved = gh_executable if gh_executable is not None else shutil.which("gh")
    if resolved is None:
        return tuple(EnvironmentRecord(name, None, "gh unavailable: not found on PATH") for name in names)

    references = environments_referenced_by_workflows(repo_root) if repo_root is not None else None

    records: list[EnvironmentRecord] = []
    for name in names:
        try:
            result = subprocess.run(
                [resolved, "api", f"repos/{repo_slug}/environments/{name}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=_GH_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            records.append(EnvironmentRecord(name, None, f"gh unavailable: {exc}"))
            continue
        if result.returncode != 0:
            detail = result.stderr.strip()[:200] or f"exit {result.returncode}"
            records.append(EnvironmentRecord(name, None, f"could not be read: {detail}"))
            continue
        try:
            payload = json.loads(result.stdout or "null")
        except json.JSONDecodeError:
            records.append(EnvironmentRecord(name, None, "could not be read: gh returned non-JSON output"))
            continue
        if not isinstance(payload, Mapping):
            records.append(EnvironmentRecord(name, None, "could not be read: unexpected payload shape"))
            continue
        referenced_by = references.get(name, ()) if references is not None else None
        records.append(EnvironmentRecord(name, protection_rule_types(payload), referenced_by=referenced_by))
    return tuple(records)


def fetch_label(
    name: str = ALERT_LABEL,
    *,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
) -> LabelRecord:
    """Read whether one repository label exists on the forge, one GET.

    Distinguishes a genuine 404 (the label does not exist — real, actionable
    state) from every other failure (gh absent, a timeout, a non-404 error),
    which stays unreadable rather than being guessed as absent. The 404 is
    read from the API's own JSON error body (``{"status": "404", ...}``)
    rather than from ``gh``'s CLI wrapper text, which is not a contract this
    module should depend on across ``gh`` versions; the stderr text is only a
    fallback when the body did not parse.
    """
    resolved = gh_executable if gh_executable is not None else shutil.which("gh")
    if resolved is None:
        return LabelRecord(name, None, "gh unavailable: not found on PATH")
    try:
        result = subprocess.run(
            [resolved, "api", f"repos/{repo_slug}/labels/{name}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return LabelRecord(name, None, f"gh unavailable: {exc}")
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout or "null")
        except json.JSONDecodeError:
            return LabelRecord(name, None, "could not be read: gh returned non-JSON output")
        if not isinstance(payload, Mapping):
            return LabelRecord(name, None, "could not be read: unexpected payload shape")
        return LabelRecord(name, True)
    try:
        error_payload = json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        error_payload = None
    reported_status = str(error_payload.get("status", "")) if isinstance(error_payload, Mapping) else ""
    if reported_status == "404" or "404" in result.stderr:
        return LabelRecord(name, False)
    detail = result.stderr.strip()[:200] or f"exit {result.returncode}"
    return LabelRecord(name, None, f"could not be read: {detail}")


def render_label_line(record: LabelRecord) -> str:
    """Render one label record as an operator-facing line naming the create command."""
    if not record.readable:
        return f"{record.name}: UNKNOWN - {record.detail}"
    if record.exists:
        return f"{record.name}: label exists."
    return (
        f"{record.name}: MISSING - the failure-alert emitter's default path degrades to a "
        f"run-log warning nobody reads without this label. Create it: "
        f'gh label create {record.name} --description "Cadrumo release-chain failure alert" '
        "--color b60205."
    )


def render_report(records: Sequence[EnvironmentRecord]) -> str:
    """Render the inventory as operator-facing lines naming the outstanding work."""
    lines: list[str] = []
    for record in records:
        if not record.readable:
            lines.append(f"{record.name}: UNKNOWN - {record.detail}")
            continue
        rules = ", ".join(record.rule_types or ()) or "none"
        if record.name in OP9_ENVIRONMENTS:
            if record.carries_human_approval_gate:
                lines.append(
                    f"{record.name}: OP-9 OUTSTANDING - carries {HUMAN_APPROVAL_RULE} (rules: {rules}). "
                    f"Remove that rule only. Keep the environment and its branch_policy."
                )
            else:
                lines.append(f"{record.name}: OP-9 satisfied - no {HUMAN_APPROVAL_RULE} rule (rules: {rules}).")
        else:
            lines.append(f"{record.name}: rules: {rules}.")
        if record.is_orphaned:
            lines.append(
                f"{record.name}: OP-12 OUTSTANDING - ORPHANED, no live workflow declares "
                f"environment: {record.name}. Delete this environment (Settings -> Environments -> "
                f"{record.name} -> Delete environment). Then verify separately whether an index-side "
                "PyPI Trusted Publisher registration still names this environment; that check is "
                "outside this repository and this forge."
            )
        elif record.is_orphaned is False and record.name in ORPHAN_CANDIDATE_ENVIRONMENTS:
            # Still readable AND referenced: this environment is not (or no
            # longer) orphaned, which contradicts why it is on the orphan
            # candidate list. Surfaced rather than silenced, because a
            # re-referenced "orphan" is exactly the kind of drift this probe
            # exists to make visible.
            lines.append(
                f"{record.name}: not orphaned - referenced by live workflow(s): "
                f"{', '.join(record.referenced_by or ())}. OP-12 may need re-evaluation.",
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the environment inventory. Reports state, never changes it.

    Exit status is 0 whenever the inventory was PRODUCED, including when it
    reports outstanding operator work, because this is a reporting probe and not
    a gate. It exits non-zero only when some environment could not be read, so
    an unreadable forge is never mistaken for a clean one.
    """
    parser = argparse.ArgumentParser(description="Report forge environment protection rules (read-only).")
    parser.add_argument("--repository", default=_DEFAULT_REPO_SLUG)
    parser.add_argument("--environment", action="append", dest="environments")
    parser.add_argument("--label", action="append", dest="labels")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    names = tuple(args.environments) if args.environments else DEFAULT_INVENTORIED_ENVIRONMENTS
    records = fetch_environments(names, repo_slug=args.repository, repo_root=_repo_root())
    label_names = tuple(args.labels) if args.labels else (ALERT_LABEL,)
    label_records = tuple(fetch_label(name, repo_slug=args.repository) for name in label_names)

    if args.as_json:
        print(
            json.dumps(
                {
                    "environments": [
                        {
                            "name": r.name,
                            "rule_types": list(r.rule_types) if r.rule_types is not None else None,
                            "readable": r.readable,
                            "detail": r.detail,
                            "referenced_by": list(r.referenced_by) if r.referenced_by is not None else None,
                            "is_orphaned": r.is_orphaned,
                        }
                        for r in records
                    ],
                    "labels": [
                        {
                            "name": r.name,
                            "exists": r.exists,
                            "readable": r.readable,
                            "detail": r.detail,
                        }
                        for r in label_records
                    ],
                },
                indent=2,
            )
        )
    else:
        print(render_report(records))
        for label_record in label_records:
            print(render_label_line(label_record))

    return 0 if all(record.readable for record in records) and all(r.readable for r in label_records) else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
