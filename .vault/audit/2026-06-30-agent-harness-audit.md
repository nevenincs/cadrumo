---
tags:
  - '#audit'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` audit: `campaign close honesty review`

## Scope

A fresh-context campaign-close honesty review of the agent-harness feature (the
five-wave buildout: capability manifest, operator rules, personas, skills, golden
eval, MCP server, workspace materialiser), dispatched per the
`aeat-campaign-close-honesty-review` rule before declaring the campaign
structurally complete. The reviewer inspected the implementation under
`src/aeat/agent/`, `src/aeat/entrypoints/mcp/`, the `_app_contract` and
`_app_agent_workspace` CLI modules, `operator_surface/_manifest.py`, and
`src/aeat/_data/agent/`, ran the suites, and verified every finding against HEAD.
Verdict: GO-WITH-FIXES.

## Findings

### contract-drift-red | critical | the `agent` family was mounted but absent from the contract, reddening the drift gate

`aeat app agent` (W05) was mounted on the CLI but never added to
`OperatorSurfaceContract`, so `test_operator_surface_contract_drift` was RED at
HEAD and `aeat app contract --format json` (the agent's capability catalogue)
omitted `agent` - the exact hole that gate exists to catch. Resolved: added
`MountedCommandDomain.AGENT`, the `agent` family, and `agent` to the app
`required_children`; the drift gate is green and the manifest lists 20 families.

### ci-gate-omits-drift | high | the standing CI eval gate did not run the drift or conformance gates

`agent-harness-eval.yml` ran the agent/MCP/contract/workspace tests but not
`test_operator_surface_contract_drift` (the test that catches the above) nor
`test_json_schema_conformance`, so the drift was invisible to the campaign's own
CI. Resolved: both gates were added to the workflow.

### value-oracle-misjustified | medium | the golden value-oracle deferral inverted the no-tautological-tests rule

The golden runner asserts trajectory, lifecycle, skill-consistency, and
provenance but not a computed casilla value; the scenario comments justified this
as avoiding a "tautological" test. That inverts `no-tautological-calculation-tests`,
which sanctions AEAT-worked-example oracles (only hand-computing from the registry
formula under test is tautological). Resolved: corrected the scenario comments and
tracked the work as an open follow-up step `W03.P07.S56`.

### faithfulness-not-server-enforced | medium | faithfulness and CONFIRM are tested primitives awaiting an Agent-SDK host

`faithfulness_check` and `confirmation_for_tool` are unit-tested pure functions
for the Agent-SDK `PostToolUse`/`PreToolUse` hook layer; the MCP server itself
sees no agent narration and enforces only the forbidden-live-write `BLOCK` rail
(plus the CLI `LiveSubmitForbiddenError` backstop). This is architecturally
correct for MCP and is stated plainly in the W04.P09 execution record; no code
change required.

### workspace-drops-reference | low | the materialiser dropped each skill's reference subtree

`materialise_workspace` wrote only `SKILL.md`, so a materialised
`preparar-modelo-130` lost the `reference/casillas.md` its SKILL cites. Resolved:
the materialiser now copies the whole skill subtree; a test asserts the reference
lands.

### faithfulness-digit-heuristic | low | the hard-block rests on a loose digit-membership heuristic

The faithfulness check grounds against bare digit sequences of every number in the
tool JSON, so a fabricated amount whose digits coincide with an unrelated number
can pass even on the blocking path. Acceptable for the advisory default; a tighter
match for the hard-block path is a future improvement (not yet tracked as a step).

### drift-gate-checks-verbs-not-flags | low | the rule-surface drift gate validates verbs but not flag names

`test_rule_surface_conformance` validates cited command paths across rules,
personas, and skills, but not flag names, and the envelope-field check hardcodes
the spine list rather than scanning the documents. A future enhancement.

## Recommendations

The two blocking and the workspace findings are resolved in commit `e98e5e877`;
the value-oracle deferral is corrected and tracked as open step `W03.P07.S56`. The
faithfulness/CONFIRM framing is already honest in the execution records. The two
remaining low findings (tighter faithfulness hard-block matching, flag-name drift
checking) are improvements that do not block structural completion; capture them
as follow-ups if they recur. The campaign is structurally complete once the open
value-oracle step is either implemented or carried forward as a tracked deferral.
