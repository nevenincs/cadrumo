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

from ._models import (
    ConfirmationGateCheck,
    ConfirmationTier,
    ContradictionScenario,
    ContradictionVerdict,
    ElicitationAction,
    ExitCodeScenario,
    ExitCodeVerdict,
    GoldenResult,
    GoldenScenario,
    LiveElicitationRecord,
    LiveInvariantVerdict,
    LiveNarrationRecord,
    LiveToolCallRecord,
    LiveTrajectory,
    NarrationFaithfulness,
    ProfileConfirmationScenario,
    ProfileConfirmationVerdict,
    UnderDeclarationScenario,
    UnderDeclarationVerdict,
)
from ._replay import (
    GoldenToolCall,
    ToolCallResolver,
    divergent_replays,
    record_tool_call,
    replay_tool_call,
)
from ._runner import (
    check_contradiction_scenario,
    check_exit_code_scenario,
    check_profile_confirmation_scenario,
    check_under_declaration_scenario,
    load_scenario,
    run_golden_scenario,
)

__all__ = [
    "ConfirmationGateCheck",
    "ConfirmationTier",
    "ContradictionScenario",
    "ContradictionVerdict",
    "ElicitationAction",
    "ExitCodeScenario",
    "ExitCodeVerdict",
    "GoldenResult",
    "GoldenScenario",
    "GoldenToolCall",
    "LiveElicitationRecord",
    "LiveInvariantVerdict",
    "LiveNarrationRecord",
    "LiveToolCallRecord",
    "LiveTrajectory",
    "NarrationFaithfulness",
    "ProfileConfirmationScenario",
    "ProfileConfirmationVerdict",
    "ToolCallResolver",
    "UnderDeclarationScenario",
    "UnderDeclarationVerdict",
    "check_contradiction_scenario",
    "check_exit_code_scenario",
    "check_profile_confirmation_scenario",
    "check_under_declaration_scenario",
    "divergent_replays",
    "load_scenario",
    "record_tool_call",
    "replay_tool_call",
    "run_golden_scenario",
]
