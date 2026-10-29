"""Resolve one lock-owned dependency set for the agent and application."""

from __future__ import annotations

import itertools
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from dev._paths import REPO_ROOT

from ..command_execution import run_command

_HASHES = re.compile(r"sha256:[0-9a-f]{64}(?:\s+--hash=sha256:[0-9a-f]{64})*")


@dataclass(frozen=True)
class ResolvedDistribution:
    """One distribution of the resolved set with the hashes the installer requires."""

    version: str
    hashes: tuple[str, ...]


class DependencyGateError(ValueError):
    """The two projects' locks admit no common version of a shared distribution."""


def _validate_requirement(
    requirement: Requirement, separator: str, hashes: str, origin: str, specification: str
) -> None:
    pins = tuple(requirement.specifier)
    if (
        (separator and not _HASHES.fullmatch(hashes.strip()))
        or requirement.url is not None
        or len(pins) != 1
        or pins[0].operator != "=="
        or "*" in pins[0].version
    ):
        raise ValueError(f"{origin} row must name one exact version: {specification}")


def requirement_rows(text: str, origin: str) -> list[tuple[Requirement, tuple[str, ...]]]:
    """Parse exact, optionally hashed requirement rows as uv writes them."""
    rows: list[tuple[Requirement, tuple[str, ...]]] = []
    for row in text.replace("\\\n", " ").splitlines():
        row = row.strip()
        if not row or row.startswith("#"):
            continue
        specification, separator, hashes = row.partition(" --hash=")
        requirement = Requirement(specification.strip())
        _validate_requirement(requirement, separator, hashes, origin, specification)
        found = tuple(item.removeprefix("sha256:") for item in re.findall(r"sha256:[0-9a-f]{64}", hashes))
        rows.append((requirement, found))
    return rows


def _declared_refusals(
    name: str, version: str, declared: Mapping[str, Sequence[Requirement]]
) -> list[tuple[str, Requirement]]:
    return [
        (owner, requirement)
        for owner, requirements in declared.items()
        for requirement in requirements
        if canonicalize_name(requirement.name) == name and not requirement.specifier.contains(version, prereleases=True)
    ]


def _compile(
    requirements: Sequence[Requirement],
    pins: Mapping[str, str],
    *,
    python: str,
    platform: str,
    uv: str,
    work: Path,
    environment: Mapping[str, str] | None,
    index_arguments: Sequence[str],
) -> tuple[dict[str, ResolvedDistribution] | None, str]:
    """Resolve the declared requirements with every version fixed; report an unsatisfiable set."""
    work.mkdir(parents=True, exist_ok=True)
    inputs = work / "requirements.in"
    constraints = work / "constraints.txt"
    output = work / "requirements.txt"
    output.unlink(missing_ok=True)
    inputs.write_text("".join(f"{requirement}\n" for requirement in requirements), encoding="utf-8")
    constraints.write_text("".join(f"{name}=={version}\n" for name, version in sorted(pins.items())), encoding="utf-8")
    result = run_command(
        [
            uv,
            "pip",
            "compile",
            "--no-config",
            str(inputs),
            "--constraint",
            str(constraints),
            "--python-version",
            python,
            "--python-platform",
            platform,
            "--only-binary",
            ":all:",
            "--generate-hashes",
            "--no-header",
            "--no-annotate",
            "--output-file",
            str(output),
            *index_arguments,
        ],
        cwd=REPO_ROOT,
        environment=environment,
    )
    if result.returncode:
        if "No solution found" not in result.stderr:
            raise RuntimeError(f"Resolving the agent dependencies failed: {result.stderr.strip()}")
        return None, result.stderr.strip()
    resolved: dict[str, ResolvedDistribution] = {}
    for requirement, hashes in requirement_rows(output.read_text(encoding="utf-8"), "Resolved agent dependency"):
        if not hashes:
            raise ValueError(f"Resolved agent dependency has no hashes: {requirement}")
        resolved[canonicalize_name(requirement.name)] = ResolvedDistribution(
            next(iter(requirement.specifier)).version, hashes
        )
    return resolved, ""


def _candidate_versions(
    differing: Sequence[str],
    cadrumo_locked: Mapping[str, ResolvedDistribution],
    agent_locked: Mapping[str, ResolvedDistribution],
    versions: Mapping[str, Mapping[str, str]],
    declared: Mapping[str, Sequence[Requirement]],
    remedy: str,
) -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = {}
    for name in differing:
        ordered = sorted({cadrumo_locked[name].version, agent_locked[name].version}, key=Version, reverse=True)
        admitted: list[str] = []
        reasons: list[str] = []
        for version in ordered:
            holders = " and ".join(f"{owner}'s lock" for owner, locked in versions.items() if locked[name] == version)
            refusals = _declared_refusals(name, version, declared)
            if refusals:
                refused = "; ".join(f"{owner} requires {requirement}" for owner, requirement in refusals)
                reasons.append(f"{holders} holds {name} {version}, refused because {refused}")
            else:
                admitted.append(version)
        if not admitted:
            raise DependencyGateError(f"No version of {name} satisfies both projects: {'. '.join(reasons)}. {remedy}")
        candidates[name] = admitted
    return candidates


def _resolution_inputs(
    cadrumo_locked: Mapping[str, ResolvedDistribution],
    agent_locked: Mapping[str, ResolvedDistribution],
    repositories: Mapping[str, Path],
) -> tuple[dict[str, dict[str, str]], list[str], str]:
    versions = {"Cadrumo": {name: item.version for name, item in cadrumo_locked.items()}}
    versions["cadrumo-agent"] = {name: item.version for name, item in agent_locked.items()}
    differing = sorted(
        name
        for name in cadrumo_locked.keys() & agent_locked.keys()
        if Version(cadrumo_locked[name].version) != Version(agent_locked[name].version)
    )
    remedy = (
        "Change the refusing requirement or upgrade the lagging lock in its repository, then run "
        "`uv lock --upgrade` there: " + "; ".join(f"{owner} at {path}" for owner, path in repositories.items())
    )
    return versions, differing, remedy


def _resolution_choices(candidates: Mapping[str, list[str]], differing: Sequence[str]) -> list[tuple[int, ...]]:
    # Index 0 is each distribution's newest admitted version: fewest older picks first.
    choices = sorted(
        itertools.product(*(range(len(candidates[name])) for name in differing)),
        key=lambda indices: (sum(indices), indices),
    )
    return choices


def _raise_resolution_failure(
    differing: Sequence[str],
    cadrumo_locked: Mapping[str, ResolvedDistribution],
    agent_locked: Mapping[str, ResolvedDistribution],
    attempts: list[str],
    remedy: str,
) -> NoReturn:
    names = ", ".join(
        f"{name} (Cadrumo's lock {cadrumo_locked[name].version}, cadrumo-agent's lock {agent_locked[name].version})"
        for name in differing
    )
    raise DependencyGateError(
        f"No common version satisfies both projects for {names or 'the shared distributions'}. "
        + " ".join(attempts)
        + f" {remedy}"
    )


def resolve_shared_dependencies(
    *,
    cadrumo_declared: Sequence[Requirement],
    agent_declared: Sequence[Requirement],
    cadrumo_locked: Mapping[str, ResolvedDistribution],
    agent_locked: Mapping[str, ResolvedDistribution],
    python: str,
    platform: str,
    uv: str,
    work: Path,
    repositories: Mapping[str, Path],
    environment: Mapping[str, str] | None = None,
    index_arguments: Sequence[str] = (),
) -> dict[str, ResolvedDistribution]:
    """Select one version of every distribution both projects need and return the hashed set.

    Each distribution only one lock names keeps that lock's version. A distribution both
    name at one version keeps it. For one they name at different versions, the newer is
    tried first, then the older; a version either project's declared requirements refuse
    is dropped before resolving. Every combination is resolved with all other versions
    fixed, so a transitive requirement of any locked distribution is enforced by the
    resolver. Combinations taking the newer version for more distributions are tried
    first. Each returned hash is one the lock holding the selected version recorded.
    """
    versions, differing, remedy = _resolution_inputs(cadrumo_locked, agent_locked, repositories)
    declared = {"Cadrumo": cadrumo_declared, "cadrumo-agent": agent_declared}
    candidates = _candidate_versions(differing, cadrumo_locked, agent_locked, versions, declared, remedy)
    base = {**versions["Cadrumo"], **versions["cadrumo-agent"]}
    requirements = [*cadrumo_declared, *agent_declared]
    choices = _resolution_choices(candidates, differing)
    attempts: list[str] = []
    for indices in choices:
        selected = {name: candidates[name][index] for name, index in zip(differing, indices, strict=True)}
        pins = {**base, **selected}
        resolved, explanation = _compile(
            requirements,
            pins,
            python=python,
            platform=platform,
            uv=uv,
            work=work,
            environment=environment,
            index_arguments=index_arguments,
        )
        if resolved is None:
            chosen = ", ".join(f"{name} {version}" for name, version in selected.items()) or "the locked versions"
            attempts.append(f"with {chosen}: {explanation}")
            continue
        outside = sorted(resolved.keys() - pins.keys())
        if outside:
            raise DependencyGateError(f"Resolution reached distributions neither lock holds: {', '.join(outside)}")
        return {
            name: _lock_owned(
                name, distribution, pins[name], {"Cadrumo": cadrumo_locked, "cadrumo-agent": agent_locked}
            )
            for name, distribution in resolved.items()
        }
    _raise_resolution_failure(differing, cadrumo_locked, agent_locked, attempts, remedy)


def _recorded_hashes(
    name: str,
    resolved: ResolvedDistribution,
    pinned: str,
    locks: Mapping[str, Mapping[str, ResolvedDistribution]],
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    owners = {
        owner: locked[name].hashes
        for owner, locked in locks.items()
        if name in locked and Version(locked[name].version) == Version(pinned)
    }
    recorded = {value for hashes in owners.values() for value in hashes}
    hashes = tuple(value for value in resolved.hashes if value in recorded)
    return owners, hashes


def _lock_owned(
    name: str,
    resolved: ResolvedDistribution,
    pinned: str,
    locks: Mapping[str, Mapping[str, ResolvedDistribution]],
) -> ResolvedDistribution:
    """Keep only the resolver's hashes that a lock holding the selected version recorded."""
    if Version(resolved.version) != Version(pinned):
        raise DependencyGateError(f"Resolution moved {name} off its locked version {pinned}")
    owners, hashes = _recorded_hashes(name, resolved, pinned, locks)
    if not hashes:
        raise DependencyGateError(
            f"The index serves no file of {name} {pinned} whose hash {' or '.join(owners) or 'a lock'} recorded; "
            "refusing bytes neither lock tested. Re-lock the owning repository against the current index."
        )
    return ResolvedDistribution(resolved.version, hashes)
