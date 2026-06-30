"""Operator golden-task eval: trajectory + provenance assertions over the harness.

The operator-side counterpart of the persona testimonial gate. A golden scenario
declares the expected tool trajectory for a workflow and the provenance the result
must carry; the runner asserts the trajectory resolves against the live CLI
surface, follows the modelo lifecycle order, is consistent with the shipped skill
playbook, and that the modelo's casillas carry their legal grounding in the
registry. It reuses the scenario methodology of the persona testimonials without
inheriting their knowledge-withholding brief, and it never hand-computes a tax
value (that would be a tautological calculation test).
"""

from __future__ import annotations

from ._models import GoldenResult, GoldenScenario
from ._runner import load_scenario, run_golden_scenario

__all__ = [
    "GoldenResult",
    "GoldenScenario",
    "load_scenario",
    "run_golden_scenario",
]
