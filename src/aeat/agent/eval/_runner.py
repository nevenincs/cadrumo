"""Runner for the operator golden-task eval.

Pure with respect to the CLI: the set of resolvable command keys is injected by
the caller (the test wires it from the live CLI schema registry), so this module
never imports the entrypoints layer. The registry snapshot it reads for the
provenance dimension is a pure registry read through ``aeat.core.resources`` and
needs no profile or secret storage.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from itertools import pairwise
from pathlib import Path

from ...core.resources import resources
from .. import iter_skill_documents
from ._models import GoldenResult, GoldenScenario

# Lifecycle stage ordering the trajectory must respect when the stages are present:
# create the work unit, then calculate, then verify, then export. Keyed by the
# registry command key for each stage.
_LIFECYCLE_ORDER: tuple[str, ...] = (
    "modelo.work.create",
    "modelo.work.calculate",
    "modelo.work.verify",
    "modelo.export",
)


def load_scenario(path: Path) -> GoldenScenario:
    """Load and validate a :class:`GoldenScenario` from a scenario TOML file.

    TOML arrays parse as ``list``; the strict scenario model takes a ``tuple``, so
    the trajectory array is coerced before validation.
    """
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    trajectory = payload.get("expected_trajectory")
    if isinstance(trajectory, list):
        payload["expected_trajectory"] = tuple(trajectory)
    return GoldenScenario.model_validate(payload)


def _cli_form(command_key: str) -> str:
    """Render a registry command key as its ``aeat app ...`` CLI form."""
    return "aeat app " + command_key.replace(".", " ")


def _skill_text(skill_name: str) -> str | None:
    for skill in iter_skill_documents():
        # Each skill's SKILL.md lives under skills/<skill_name>/SKILL.md.
        if skill_name in _skill_path_parts(skill):
            return skill.read_text(encoding="utf-8")
    return None


def _skill_path_parts(skill: object) -> set[str]:
    # ``Traversable`` does not expose a parent reliably across backends; recover the
    # owning skill directory name from the joined path string.
    text = str(skill)
    return set(text.replace("\\", "/").split("/"))


def _check_provenance(scenario: GoldenScenario, failures: list[str]) -> bool:
    snapshot = resources().modelos.authority.snapshot(
        scenario.modelo,
        filing_year=scenario.filing_year,
        period=scenario.period,
    )
    casillas: Iterable[object] = _iter_casillas(snapshot.revision.casillas)
    ungrounded = 0
    for casilla in casillas:
        legal_refs = getattr(casilla, "legal_refs", ())
        source_refs = getattr(casilla, "source_refs", ())
        if not legal_refs or not source_refs:
            ungrounded += 1
    if ungrounded:
        failures.append(
            f"{ungrounded} casilla(s) on {scenario.modelo} {scenario.period} lack legal_refs/source_refs",
        )
        return False
    return True


def _iter_casillas(casillas: object) -> Iterable[object]:
    if isinstance(casillas, dict):
        return tuple(casillas.values())
    return tuple(casillas)  # type: ignore[arg-type]


def run_golden_scenario(scenario: GoldenScenario, *, valid_commands: frozenset[str]) -> GoldenResult:
    """Run one golden scenario and return its per-dimension verdict.

    Args:
        scenario: The declared workflow expectation.
        valid_commands: The set of resolvable registry command keys, injected by
            the caller from the live CLI schema registry.

    Returns:
        A :class:`GoldenResult` whose ``passed`` is true only when the trajectory
        resolves, follows the lifecycle order, is consistent with the shipped
        skill, and (when required) the revision's casillas carry provenance.
    """
    failures: list[str] = []

    unresolved = [verb for verb in scenario.expected_trajectory if verb not in valid_commands]
    trajectory_resolves = not unresolved
    if unresolved:
        failures.append(f"trajectory cites unresolved command keys: {', '.join(unresolved)}")

    positions = {verb: index for index, verb in enumerate(scenario.expected_trajectory)}
    present_stages = [stage for stage in _LIFECYCLE_ORDER if stage in positions]
    lifecycle_ordered = all(positions[earlier] < positions[later] for earlier, later in pairwise(present_stages))
    if not lifecycle_ordered:
        failures.append("trajectory violates the create -> calculate -> verify -> export lifecycle order")

    skill_text = _skill_text(scenario.skill_name)
    if skill_text is None:
        skill_consistent = False
        failures.append(f"skill '{scenario.skill_name}' not found among shipped skills")
    else:
        missing = [verb for verb in scenario.expected_trajectory if _cli_form(verb) not in skill_text]
        skill_consistent = not missing
        if missing:
            failures.append(
                "skill playbook does not cite trajectory verbs: " + ", ".join(_cli_form(v) for v in missing),
            )

    provenance_present = True
    if scenario.provenance_required:
        provenance_present = _check_provenance(scenario, failures)

    return GoldenResult(
        scenario=scenario.name,
        trajectory_resolves=trajectory_resolves,
        lifecycle_ordered=lifecycle_ordered,
        skill_consistent=skill_consistent,
        provenance_present=provenance_present,
        failures=tuple(failures),
    )
