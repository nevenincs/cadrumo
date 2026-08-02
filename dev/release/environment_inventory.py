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

See Also:
    :func:`protection_rule_types`
        The parse layer, over an already-fetched payload.
    :func:`fetch_environments`
        The one subprocess boundary.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

_GH_TIMEOUT_SECONDS: Final[float] = 30.0
_DEFAULT_REPO_SLUG: Final[str] = "nevenincs/cadrumo"

#: The protection rule that gates a deployment on a human approval click. This
#: is the rule OP-9 removes; every other rule type is left alone.
HUMAN_APPROVAL_RULE: Final[str] = "required_reviewers"

#: Environments whose ``required_reviewers`` rule OP-9 removes. Both are OIDC
#: trust anchors and both keep their ``branch_policy``.
OP9_ENVIRONMENTS: Final[tuple[str, ...]] = ("release", "docs")


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


def fetch_environments(
    names: Sequence[str] = OP9_ENVIRONMENTS,
    *,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
) -> tuple[EnvironmentRecord, ...]:
    """Read each named environment from the forge, one GET apiece.

    ``gh_executable`` accepts an explicit resolved path so tests can drive a
    real stub executable without depending on the host's PATH resolution rules,
    matching the injection the readiness gate's blocker check already uses.

    Every failure mode -- ``gh`` absent, a non-zero exit, a timeout, non-JSON
    output -- yields an UNREADABLE record carrying the reason, never a record
    that happens to look rule-free.
    """
    resolved = gh_executable if gh_executable is not None else shutil.which("gh")
    if resolved is None:
        return tuple(EnvironmentRecord(name, None, "gh unavailable: not found on PATH") for name in names)

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
        records.append(EnvironmentRecord(name, protection_rule_types(payload)))
    return tuple(records)


def render_report(records: Sequence[EnvironmentRecord]) -> str:
    """Render the inventory as operator-facing lines naming the outstanding work."""
    lines: list[str] = []
    for record in records:
        if not record.readable:
            lines.append(f"{record.name}: UNKNOWN - {record.detail}")
            continue
        rules = ", ".join(record.rule_types or ()) or "none"
        if record.carries_human_approval_gate:
            lines.append(
                f"{record.name}: OP-9 OUTSTANDING - carries {HUMAN_APPROVAL_RULE} (rules: {rules}). "
                f"Remove that rule only. Keep the environment and its branch_policy."
            )
        else:
            lines.append(f"{record.name}: OP-9 satisfied - no {HUMAN_APPROVAL_RULE} rule (rules: {rules}).")
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
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    names = tuple(args.environments) if args.environments else OP9_ENVIRONMENTS
    records = fetch_environments(names, repo_slug=args.repository)

    if args.as_json:
        print(
            json.dumps(
                [
                    {
                        "name": r.name,
                        "rule_types": list(r.rule_types) if r.rule_types is not None else None,
                        "readable": r.readable,
                        "detail": r.detail,
                    }
                    for r in records
                ],
                indent=2,
            )
        )
    else:
        print(render_report(records))

    return 0 if all(record.readable for record in records) else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
