"""The data flywheel: promote a live failure into a golden regression scenario.

A live subagent-persona failure is not just a red
run — it becomes a NEW golden scenario so the same failure cannot recur
unnoticed. Promotion is deliberately conservative: the promoted scenario pins
the ORIGINAL scenario's declared expectations (the correct path), while the
observed failing behaviour is preserved verbatim in the scenario's comment
header as the annotation-queue evidence a tax-professional reviews. Names are
content-addressed (a hash of scenario + failure signature) so re-promoting
the same failure is idempotent — the flywheel dedups by construction, never
by clock.
"""

from __future__ import annotations

import json
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING as _UTF_8
from cadrumo.core.hashing import sha256_hex

from ._live_scoring import LiveScenarioScore
from ._models import GoldenScenario, LiveTrajectory


def failure_signature(score: LiveScenarioScore) -> str:
    """Return a stable content address for all evidence in one failed score."""
    evidence = {
        "scenario": score.scenario,
        "keys_resolve": score.keys_resolve,
        "lifecycle_ordered": score.lifecycle_ordered,
        "expected_covered": score.expected_covered,
        "invariants": score.invariants.model_dump(mode="json"),
        "tool_errors": score.tool_errors,
        "narration_checks": [check.model_dump(mode="json") for check in score.narration_checks],
        "failures": score.failures,
    }
    basis = json.dumps(
        evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_hex(basis.encode(_UTF_8))[:12]


def promote_failure(
    *,
    score: LiveScenarioScore,
    trajectory: LiveTrajectory,
    scenario: GoldenScenario,
) -> str:
    """Render the promoted golden-scenario TOML for one live failure.

    The promoted scenario re-declares the ORIGINAL correct expectations; the
    observed failing trajectory and the failure reasons ride in the comment
    header as evidence, never as expectations (a failure must not become the
    new normal).

    Raises:
        ValueError: When the score did not actually fail — a passing run has
            nothing to promote.
    """
    if score.passed:
        raise ValueError(f"live run for scenario '{score.scenario}' passed; nothing to promote")
    observed = ", ".join(trajectory.observed_command_keys) or "(none)"
    reasons = "\n".join(f"#   - {reason}" for reason in score.failures) or "#   - (no reason recorded)"
    trajectory_lines = ",\n".join(f'  "{key}"' for key in scenario.expected_trajectory)
    casillas = ", ".join(f'"{c}"' for c in scenario.expected_computed_casillas)
    return (
        f"# Golden regression scenario promoted from live failure {failure_signature(score)}.\n"
        f"# Origin: scenario '{score.scenario}', persona '{score.persona}', session '{score.session_id}'.\n"
        f"# Observed (failing) trajectory: {observed}\n"
        f"# Failure reasons:\n{reasons}\n"
        f"# The expectations below re-declare the ORIGINAL correct path; the observed\n"
        f"# behaviour above is evidence for the annotation queue, not an expectation.\n"
        f"\n"
        f'name = "{scenario.name}-regression-{failure_signature(score)}"\n'
        f'modelo = "{scenario.modelo}"\n'
        f"filing_year = {scenario.filing_year}\n"
        f'period = "{scenario.period}"\n'
        f'skill_name = "{scenario.skill_name}"\n'
        f"provenance_required = {str(scenario.provenance_required).lower()}\n"
        f"expected_computed_casillas = [{casillas}]\n"
        f"\n"
        f"expected_trajectory = [\n{trajectory_lines},\n]\n"
    )


def write_promoted_scenario(
    *,
    score: LiveScenarioScore,
    trajectory: LiveTrajectory,
    scenario: GoldenScenario,
    scenarios_dir: Path,
) -> Path:
    """Write the promoted scenario into ``scenarios_dir``, idempotently.

    Returns:
        The path written (or the existing identical file on re-promotion).

    Raises:
        ValueError: When an existing promotion at the content-addressed path
            has different contents. A hash collision or incomplete identity
            must never overwrite a prior failure's evidence.
    """
    text = promote_failure(score=score, trajectory=trajectory, scenario=scenario)
    stem = f"{scenario.name.replace('-', '_')}_regression_{failure_signature(score)}"
    path = scenarios_dir / f"{stem}.toml"
    if path.exists():
        existing = path.read_text(encoding=_UTF_8)
        if existing == text:
            return path
        raise ValueError(f"promotion identity collision at {path.name}; refusing to overwrite existing evidence")
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=_UTF_8, newline="\n")
    return path


__all__ = [
    "failure_signature",
    "promote_failure",
    "write_promoted_scenario",
]
