"""Build the private agent wheel and resolve its dependencies against both projects' locks.

The agent owns its dependency set and its own ``uv.lock``; Cadrumo keeps no copy of
it. The application ships one interpreter and one ``site-packages``, so every
distribution both locks name can ship at one version only. At bundle time the agent
wheel's declared requirements are resolved with two constraint sets, both read fresh
from their repositories: Cadrumo's ``uv.lock`` for the shipped groups, and the agent's
``uv.lock``. For a distribution both locks hold, the newer of the two locked versions
that satisfies both projects' requirements, transitive ones included, is selected.
When neither does, the build refuses and names the distribution, both versions and
the requirement each violates.

Every installed file must be one its owning lock recorded: the resolver's output is
narrowed to the hashes of the lock that holds the selected version, so an index or
mirror serving different bytes fails the build instead of passing ``--require-hashes``.
A shared distribution that would ship at a version only one lock holds is refused,
because no release step proves both projects against such a mixed set.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..runtime_wheel_selection import active_requirements, marker_environment
from ..runtime_wheelhouse_contract import target_platform
from ..uv_constraints import local_product_packages
from ..wheel_metadata import read_wheel_metadata
from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .hashing import digest
from .product import BUNDLED_EXTRAS, _wheel_input_digest
from .target import uv_environment, uv_platform

AGENT_DEPENDENCIES = "agent-dependencies.txt"
"""Hash-pinned requirements the agent adds to, or replaces in, Cadrumo's base closure."""
AGENT_DEPENDENCY_RECORD = "agent-dependencies.json"
"""The resolution's inputs, selected versions and the replaced Cadrumo versions."""
_HASHES = re.compile(r"sha256:[0-9a-f]{64}(?:\s+--hash=sha256:[0-9a-f]{64})*")
_AGENT_EXPORT = (
    "export",
    "--frozen",
    "--no-config",
    "--no-dev",
    "--no-emit-project",
    "--no-header",
    "--no-annotate",
)
_OVERRIDE_PREFIXES = ("UV_", "PIP_")


@dataclass(frozen=True)
class ResolvedDistribution:
    """One distribution of the resolved set with the hashes the installer requires."""

    version: str
    hashes: tuple[str, ...]


class DependencyGateError(ValueError):
    """The two projects' locks admit no common version of a shared distribution."""


def _requirement_rows(text: str, origin: str) -> list[tuple[Requirement, tuple[str, ...]]]:
    """Parse exact, optionally hashed requirement rows as uv writes them."""
    rows: list[tuple[Requirement, tuple[str, ...]]] = []
    for row in text.replace("\\\n", " ").splitlines():
        row = row.strip()
        if not row or row.startswith("#"):
            continue
        specification, separator, hashes = row.partition(" --hash=")
        requirement = Requirement(specification.strip())
        pins = tuple(requirement.specifier)
        if (
            (separator and not _HASHES.fullmatch(hashes.strip()))
            or requirement.url is not None
            or len(pins) != 1
            or pins[0].operator != "=="
            or "*" in pins[0].version
        ):
            raise ValueError(f"{origin} row must name one exact version: {specification}")
        found = tuple(item.removeprefix("sha256:") for item in re.findall(r"sha256:[0-9a-f]{64}", hashes))
        rows.append((requirement, found))
    return rows


def locked_distributions(text: str, environment: Mapping[str, str], origin: str) -> dict[str, ResolvedDistribution]:
    """Return the exact versions and recorded hashes a lock export activates for one target environment."""
    distributions: dict[str, ResolvedDistribution] = {}
    for requirement, hashes in _requirement_rows(text, origin):
        if requirement.marker is not None and not requirement.marker.evaluate(dict(environment)):
            continue
        if not hashes:
            raise ValueError(f"{origin} row carries no recorded hashes: {requirement}")
        name = canonicalize_name(requirement.name)
        version = next(iter(requirement.specifier)).version
        previous = distributions.get(name)
        if previous is not None and previous.version != version:
            raise ValueError(f"{origin} activates two versions of {name}")
        distributions[name] = ResolvedDistribution(version, hashes)
    return distributions


def cadrumo_lock_hashes(repo_root: Path = REPO_ROOT) -> dict[tuple[str, str], tuple[str, ...]]:
    """Return every wheel and sdist hash Cadrumo's ``uv.lock`` records, by distribution and version."""
    lock = parse_toml((repo_root / "uv.lock").read_text(encoding="utf-8"))
    recorded: dict[tuple[str, str], tuple[str, ...]] = {}
    for package in lock.get("package", ()):
        if not isinstance(package, dict) or "registry" not in (package.get("source") or {}):
            continue
        files = [*package.get("wheels", ()), *([package["sdist"]] if "sdist" in package else [])]
        hashes = tuple(
            str(item["hash"]).removeprefix("sha256:")
            for item in files
            if isinstance(item, dict) and str(item.get("hash", "")).startswith("sha256:")
        )
        recorded[(canonicalize_name(str(package["name"])), str(package["version"]))] = hashes
    return recorded


def gate_environment(base: Mapping[str, str]) -> dict[str, str]:
    """Drop every uv and pip override so no index, mirror or setting outside the locks reaches the resolver."""
    return {name: value for name, value in base.items() if not name.upper().startswith(_OVERRIDE_PREFIXES)}


def _active(requirement: Requirement, environment: Mapping[str, str]) -> bool:
    return requirement.marker is None or requirement.marker.evaluate(dict(environment))


def _unmarked(requirement: Requirement) -> Requirement:
    """Drop a marker already evaluated for the target so the resolver sees the bare requirement."""
    copy = Requirement(str(requirement))
    copy.marker = None
    return copy


def cadrumo_requirements(environment: Mapping[str, str], *, repo_root: Path = REPO_ROOT) -> list[Requirement]:
    """Return Cadrumo's declared third-party requirements for the shipped extras on one target."""
    project = parse_toml((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = list(project.get("dependencies", ()))
    for extra in BUNDLED_EXTRAS:
        declared.extend(project.get("optional-dependencies", {}).get(extra, ()))
    local = {canonicalize_name(name) for name in local_product_packages(repo_root=repo_root)}
    requirements = []
    for value in declared:
        requirement = Requirement(value)
        if canonicalize_name(requirement.name) not in local and _active(requirement, environment):
            requirements.append(_unmarked(requirement))
    return requirements


def wheel_requirements(wheel: Path, environment: Mapping[str, str]) -> list[Requirement]:
    """Return the wheel's declared requirements active on one target, without optional extras."""
    requirements = []
    for value in read_wheel_metadata(wheel).get_all("Requires-Dist", []):
        requirement = Requirement(value)
        if _active(requirement, environment):
            requirements.append(_unmarked(requirement))
    return requirements


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
    for requirement, hashes in _requirement_rows(output.read_text(encoding="utf-8"), "Resolved agent dependency"):
        if not hashes:
            raise ValueError(f"Resolved agent dependency has no hashes: {requirement}")
        resolved[canonicalize_name(requirement.name)] = ResolvedDistribution(
            next(iter(requirement.specifier)).version, hashes
        )
    return resolved, ""


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
    versions = {"Cadrumo": {name: item.version for name, item in cadrumo_locked.items()}}
    versions["cadrumo-agent"] = {name: item.version for name, item in agent_locked.items()}
    declared = {"Cadrumo": cadrumo_declared, "cadrumo-agent": agent_declared}
    differing = sorted(
        name
        for name in cadrumo_locked.keys() & agent_locked.keys()
        if Version(cadrumo_locked[name].version) != Version(agent_locked[name].version)
    )
    remedy = (
        "Change the refusing requirement or upgrade the lagging lock in its repository, then run "
        "`uv lock --upgrade` there: " + "; ".join(f"{owner} at {path}" for owner, path in repositories.items())
    )
    candidates: dict[str, list[str]] = {}
    for name in differing:
        ordered = sorted({cadrumo_locked[name].version, agent_locked[name].version}, key=Version, reverse=True)
        admitted = []
        reasons = []
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
    base = {**versions["Cadrumo"], **versions["cadrumo-agent"]}
    requirements = [*cadrumo_declared, *agent_declared]
    # Index 0 is each distribution's newest admitted version: fewest older picks first.
    choices = sorted(
        itertools.product(*(range(len(candidates[name])) for name in differing)),
        key=lambda indices: (sum(indices), indices),
    )
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
    names = ", ".join(
        f"{name} (Cadrumo's lock {cadrumo_locked[name].version}, cadrumo-agent's lock {agent_locked[name].version})"
        for name in differing
    )
    raise DependencyGateError(
        f"No common version satisfies both projects for {names or 'the shared distributions'}. "
        + " ".join(attempts)
        + f" {remedy}"
    )


def _lock_owned(
    name: str,
    resolved: ResolvedDistribution,
    pinned: str,
    locks: Mapping[str, Mapping[str, ResolvedDistribution]],
) -> ResolvedDistribution:
    """Keep only the resolver's hashes that a lock holding the selected version recorded."""
    if Version(resolved.version) != Version(pinned):
        raise DependencyGateError(f"Resolution moved {name} off its locked version {pinned}")
    owners = {
        owner: locked[name].hashes
        for owner, locked in locks.items()
        if name in locked and Version(locked[name].version) == Version(pinned)
    }
    recorded = {value for hashes in owners.values() for value in hashes}
    hashes = tuple(value for value in resolved.hashes if value in recorded)
    if not hashes:
        raise DependencyGateError(
            f"The index serves no file of {name} {pinned} whose hash {' or '.join(owners) or 'a lock'} recorded; "
            "refusing bytes neither lock tested. Re-lock the owning repository against the current index."
        )
    return ResolvedDistribution(resolved.version, hashes)


def require_single_lock_provenance(
    replaced: Mapping[str, Mapping[str, str | None]], repositories: Mapping[str, Path]
) -> None:
    """Refuse a shared distribution that would ship at a version only one project's lock holds.

    Such a set has been proven by neither project as a whole: shipping it needs both the
    agent's package proofs and Cadrumo's packaged runtime probes against the bundle, and
    no release step runs the agent's.
    """
    if not replaced:
        return
    rows = "; ".join(
        f"{name} {row['selected']} (Cadrumo's lock {row['cadrumo']}, cadrumo-agent's lock {row['agent']})"
        for name, row in sorted(replaced.items())
    )
    raise DependencyGateError(
        f"The bundle would ship shared distributions at a version only one lock holds: {rows}. Upgrade the lagging "
        "repository so both locks hold the shipped version, then run `uv lock --upgrade` there: "
        + "; ".join(f"{owner} at {path}" for owner, path in repositories.items())
        + ". A mixed set needs both projects' proofs against the bundle (the agent's package proofs and Cadrumo's "
        "packaged runtime probes) before it can be delivered, and no release step runs the agent's."
    )


def require_python_step_lock(requires_python: str | None, python: str, source: Path) -> None:
    """Refuse an agent whose declared Python does not admit the release Python Cadrumo ships."""
    if requires_python is None:
        raise DependencyGateError(
            f"cadrumo-agent declares no Requires-Python; step-lock it to Cadrumo's release Python {python} in {source}"
        )
    specifiers = SpecifierSet(requires_python)
    if specifiers.contains(python, prereleases=True):
        return
    floors = [
        Version(item.version)
        for item in specifiers
        if item.operator in {">", ">=", "==", "~="} and "*" not in item.version
    ]
    behind = (
        f"Cadrumo, whose release Python is {python} (dev/packaging/release-python-version in {REPO_ROOT})"
        if floors and Version(python) < min(floors)
        else f"cadrumo-agent, whose pyproject.toml requires-python is {requires_python} (in {source})"
    )
    raise DependencyGateError(
        f"cadrumo-agent requires Python {requires_python}, which excludes Cadrumo's release Python {python}. "
        f"Move the side behind: {behind}."
    )


def _gate_inputs(source: Path, wheel: Path, target: str, python: str, uv_version: str) -> str:
    identity = dict(
        uv=uv_version,
        wheel=digest(wheel),
        cadrumo_lock=digest(REPO_ROOT / "uv.lock"),
        cadrumo_project=digest(REPO_ROOT / "pyproject.toml"),
        agent_lock=digest(source / "uv.lock"),
        target=target,
        python=python,
    )
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def gate_agent_dependencies(output: Path, source: Path, target: str, uv: str) -> None:
    """Resolve the built wheel against both locks and record the requirements the agent adds."""
    source = source.resolve(strict=True)
    if not (source / "uv.lock").is_file():
        raise ValueError(f"The configured agent project has no uv.lock: {source}; run `uv lock` there")
    python = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    wheel = agent_wheel(output)
    require_python_step_lock(read_wheel_metadata(wheel).get("Requires-Python"), python, source)
    subprocess_environment = gate_environment(uv_environment(target))
    reported = run_command([uv, "--version"], cwd=REPO_ROOT, environment=subprocess_environment)
    if reported.returncode:
        raise RuntimeError(f"The configured uv cannot report its version: {reported.stderr.strip()}")
    inputs = _gate_inputs(source, wheel, target, python, reported.stdout.strip())
    try:
        if _gate_record(output)["inputs"] == inputs:
            resolved_requirements(output, target, python)
            return
    except (OSError, ValueError, KeyError):
        pass
    environment = marker_environment(target_platform(target), python)
    exported = run_command([uv, *_AGENT_EXPORT], cwd=source, environment=subprocess_environment)
    if exported.returncode:
        raise RuntimeError(f"Exporting the agent lock failed in {source}: {exported.stderr.strip()}")
    agent_locked = locked_distributions(exported.stdout, environment, "Agent lock export")
    recorded = cadrumo_lock_hashes()
    cadrumo_locked: dict[str, ResolvedDistribution] = {}
    for name, requirement in active_requirements(
        REPO_ROOT, target_platform(target), python, extras=BUNDLED_EXTRAS
    ).items():
        version = next(iter(requirement.specifier)).version
        hashes = recorded.get((name, version), ())
        if len(hashes) == 0:
            raise ValueError(f"Cadrumo's uv.lock records no hashes for {name} {version}")
        cadrumo_locked[name] = ResolvedDistribution(version, hashes)
    repositories = {"Cadrumo": REPO_ROOT, "cadrumo-agent": source}
    resolved = resolve_shared_dependencies(
        cadrumo_declared=cadrumo_requirements(environment),
        agent_declared=wheel_requirements(wheel, environment),
        cadrumo_locked=cadrumo_locked,
        agent_locked=agent_locked,
        python=python,
        platform=uv_platform(target),
        uv=uv,
        work=output / "dependency-resolution",
        repositories=repositories,
        environment=subprocess_environment,
    )
    replaced = {
        name: dict(
            selected=resolved[name].version, cadrumo=cadrumo_locked[name].version, agent=agent_locked[name].version
        )
        for name in sorted(cadrumo_locked.keys() & agent_locked.keys() & resolved.keys())
        if Version(cadrumo_locked[name].version) != Version(agent_locked[name].version)
    }
    require_single_lock_provenance(replaced, repositories)
    added = {
        name: distribution
        for name, distribution in sorted(resolved.items())
        if name not in cadrumo_locked or Version(cadrumo_locked[name].version) != Version(distribution.version)
    }
    requirements = "".join(
        f"{name}=={distribution.version} " + " ".join(f"--hash=sha256:{value}" for value in distribution.hashes) + "\n"
        for name, distribution in added.items()
    )
    (output / AGENT_DEPENDENCIES).write_text(requirements, encoding="utf-8", newline="\n")
    record = dict(
        inputs=inputs,
        target=target,
        python=python,
        wheel_sha256=digest(wheel),
        cadrumo_lock_sha256=digest(REPO_ROOT / "uv.lock"),
        agent_lock_sha256=digest(source / "uv.lock"),
        requirements_sha256=digest(output / AGENT_DEPENDENCIES),
        versions={name: distribution.version for name, distribution in added.items()},
        replaced=replaced,
    )
    (output / AGENT_DEPENDENCY_RECORD).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    resolved_requirements(output, target, python)


def _gate_record(output: Path) -> dict[str, object]:
    record: object = json.loads((output / AGENT_DEPENDENCY_RECORD).read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("Agent dependency record must be a mapping")
    return {str(key): value for key, value in record.items()}


def resolved_requirements(output: Path, target: str, python: str) -> dict[str, Requirement]:
    """Return the recorded requirements the agent adds to Cadrumo's base closure."""
    record = _gate_record(output)
    if record.get("target") != target or record.get("python") != python:
        raise ValueError("Agent dependency resolution was made for another target or Python; rebuild agent_project")
    path = output / AGENT_DEPENDENCIES
    if digest(path) != record.get("requirements_sha256"):
        raise ValueError("Agent dependency requirements differ from their resolution record")
    environment = marker_environment(target_platform(target), python)
    requirements: dict[str, Requirement] = {}
    for requirement, hashes in _requirement_rows(path.read_text(encoding="utf-8"), "Agent dependency"):
        if not hashes:
            raise ValueError(f"Agent dependency must carry SHA-256 hashes: {requirement}")
        if requirement.marker is not None and not requirement.marker.evaluate(environment):
            continue
        name = canonicalize_name(requirement.name)
        if name in requirements:
            raise ValueError(f"Duplicate agent dependency: {name}")
        requirements[name] = requirement
    versions = record.get("versions")
    if not isinstance(versions, dict) or versions != {
        name: next(iter(requirement.specifier)).version for name, requirement in requirements.items()
    }:
        raise ValueError("Agent dependency requirements differ from their resolution record")
    return requirements


def build_agent(output: Path, source: Path, uv: str) -> None:
    """Build the configured local project through the native CMake action."""
    source = source.resolve(strict=True)
    project = parse_toml((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if canonicalize_name(project["name"]) != "cadrumo-agent":
        raise ValueError("Configured agent directory must contain cadrumo-agent")
    output.mkdir(parents=True, exist_ok=True)
    wheels = output / "wheels"
    inputs = _wheel_input_digest(source, toolchain={"python": sys.version, "uv": uv})
    input_receipt = output / "agent-inputs.json"
    try:
        prior = json.loads(input_receipt.read_text(encoding="utf-8"))
        if prior == inputs:
            agent_wheel(output)
            return
    except (OSError, ValueError, KeyError):
        pass
    result = run_command(
        [
            uv,
            "build",
            "--python",
            sys.executable,
            "--no-build-isolation",
            "--no-sources",
            "--wheel",
            "--out-dir",
            str(wheels),
            str(source),
        ],
        cwd=REPO_ROOT,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    artifacts = [wheel for wheel in wheels.glob("*.whl") if read_wheel_metadata(wheel)["Version"] == project["version"]]
    if len(artifacts) != 1:
        raise ValueError("Agent build must produce exactly one wheel")
    metadata = read_wheel_metadata(artifacts[0])
    if metadata["Name"] != "cadrumo-agent" or metadata["Version"] != project["version"]:
        raise ValueError("Agent wheel metadata differs from the configured project")
    (output / "agent-wheel.json").write_text(
        json.dumps(
            dict(
                source=str(source),
                version=metadata["Version"],
                wheel=artifacts[0].name,
                wheel_sha256=digest(artifacts[0]),
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for wheel in wheels.glob("*.whl"):
        if wheel != artifacts[0]:
            wheel.unlink()
    input_receipt.write_text(json.dumps(inputs) + "\n", encoding="utf-8")


def agent_wheel(output: Path) -> Path:
    """Verify the built wheel against its recorded artifact checksum."""
    record = json.loads((output / "agent-wheel.json").read_text(encoding="utf-8"))
    name = record["wheel"]
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".whl"):
        raise ValueError("Invalid agent wheel path")
    name = str(name)
    wheel = output / "wheels" / name
    if digest(wheel) != record["wheel_sha256"]:
        raise ValueError("Agent wheel checksum mismatch")
    return wheel


def validate_wheel_dependencies(wheel: Path, target: str, python: str, output: Path) -> dict[str, Requirement]:
    """Check the wheel's active requirements against Cadrumo's base plus the recorded resolution."""
    if _gate_record(output).get("wheel_sha256") != digest(wheel):
        raise ValueError("Agent dependency resolution was made for another wheel; rebuild agent_project")
    added = resolved_requirements(output, target, python)
    expected = {
        name: next(iter(requirement.specifier)).version
        for name, requirement in active_requirements(
            REPO_ROOT, target_platform(target), python, extras=BUNDLED_EXTRAS
        ).items()
    }
    expected.update({name: next(iter(requirement.specifier)).version for name, requirement in added.items()})
    environment = marker_environment(target_platform(target), python)
    for requirement in wheel_requirements(wheel, environment):
        version = expected.get(canonicalize_name(requirement.name))
        if version is None or not requirement.specifier.contains(version, prereleases=True):
            raise ValueError(f"Agent wheel dependency differs from the resolved closure: {requirement}")
    return added


def main() -> None:
    """Run checksum admission from CMake."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("checksum",))
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    arguments = parser.parse_args()
    agent_wheel(build_paths(arguments.build)["agent"])


if __name__ == "__main__":
    main()
