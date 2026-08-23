"""Operator golden-task eval: trajectory + provenance assertions over the harness.

The operator-side counterpart of the persona testimonial gate. A golden scenario
declares the expected tool trajectory for a workflow and the provenance the result
must carry; the runner asserts the trajectory resolves against the live CLI
surface, follows the modelo lifecycle order, is consistent with the shipped skill
playbook, and that the modelo's casillas carry their legal grounding in the
registry. It reuses the scenario methodology of the persona testimonials without
inheriting their knowledge-withholding brief, and it never hand-computes a tax
value (that would be a tautological calculation test).

Boundary posture: this is dev tooling built ON TOP of the shipped surfaces, not
beside them. Harness-owned material — skills, personas, operator rules, workspace
materialisation — comes from the ``cadrumo_harness`` distribution's public facade;
taxpayer and application state comes from the real ``aeat`` CLI / ``cadrumo-mcp``
dispatch the caller performs and hands in as decoded envelope data; and the only
``cadrumo`` imports here are its public ``cadrumo.core`` primitives (the envelope
status enum, the encoding constant, the hashing helper, and the registry authority
facade for the two registry-shaped dimensions no CLI verb projects). Nothing in
this package imports ``cadrumo``'s adapters, application, domain or entrypoints
layers, and nothing imports the MCP server layer.
"""

from __future__ import annotations

from ._live_harness import (
    AnthropicPersonaDriver,
    LiveCallTool,
    LiveFinish,
    LiveHarnessError,
    LiveNarrate,
    LiveToolSpec,
    PersonaAction,
    PersonaDriver,
    ScriptedPersonaDriver,
    accept_all_confirmations,
    decline_all_elicitations,
    run_live_session,
    run_live_session_async,
)
from ._live_scoring import (
    FaithfulnessCheckFn,
    LiveScenarioScore,
    score_live_trajectory,
)
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
    "AnthropicPersonaDriver",
    "ConfirmationGateCheck",
    "ConfirmationTier",
    "ContradictionScenario",
    "ContradictionVerdict",
    "ElicitationAction",
    "ExitCodeScenario",
    "ExitCodeVerdict",
    "FaithfulnessCheckFn",
    "GoldenResult",
    "GoldenScenario",
    "GoldenToolCall",
    "LiveCallTool",
    "LiveElicitationRecord",
    "LiveFinish",
    "LiveHarnessError",
    "LiveInvariantVerdict",
    "LiveNarrate",
    "LiveNarrationRecord",
    "LiveScenarioScore",
    "LiveToolCallRecord",
    "LiveToolSpec",
    "LiveTrajectory",
    "NarrationFaithfulness",
    "PersonaAction",
    "PersonaDriver",
    "ProfileConfirmationScenario",
    "ProfileConfirmationVerdict",
    "ScriptedPersonaDriver",
    "ToolCallResolver",
    "UnderDeclarationScenario",
    "UnderDeclarationVerdict",
    "accept_all_confirmations",
    "check_contradiction_scenario",
    "check_exit_code_scenario",
    "check_profile_confirmation_scenario",
    "check_under_declaration_scenario",
    "decline_all_elicitations",
    "divergent_replays",
    "load_scenario",
    "record_tool_call",
    "replay_tool_call",
    "run_golden_scenario",
    "run_live_session",
    "run_live_session_async",
    "score_live_trajectory",
]
