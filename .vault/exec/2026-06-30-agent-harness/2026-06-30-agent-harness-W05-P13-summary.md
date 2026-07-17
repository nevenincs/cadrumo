---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-07-17'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W05.P13` summary

Phase P13 shipped the operator-workspace materialiser, expanded the eval, and
codified the drift rule. All five steps closed; landed in commits `6e46cd93b`
(code) and `531974c74` (rule).

- Created: `src/aeat/agent/_workspace.py`,
  `src/aeat/entrypoints/cli/_app_agent_workspace.py` (+ payloads, tests)
- Created: `src/aeat/agent/eval/scenarios/modelo_303.toml`,
  `src/aeat/_data/agent/skills/preparar-modelo-303/SKILL.md`
- Created: `.github/workflows/agent-harness-eval.yml`
- Created: `.vaultspec/rules/operator-harness-cites-live-cli-surface.md`

## Description

- S50: `aeat app agent --output DIR` materialises the shipped harness (rules,
  personas, skills) into an operator directory for an end-user agent runtime - a
  group-callback (like `app contract`) so it needs no profile or secret store;
  the distinct end-user workspace, never the dev `.claude/` tree.
- S51: the workspace materialiser schema is registered (`agent` envelope key) and
  passes the JSON-schema conformance gate; behaviour tests cover the function and
  the CLI command.
- S52: a modelo-303 golden scenario + `preparar-modelo-303` skill; the golden gate
  now parametrises over every shipped scenario (130 + 303), each passing
  trajectory / lifecycle / skill-consistency / provenance.
- S53: a path-filtered CI workflow runs the agent-harness eval surface (drift,
  golden, replay, MCP, workspace) on every harness change - the standing gate.
- S54: codified `operator-harness-cites-live-cli-surface` as a project rule via the
  vaultspec rules CLI and synced it to the provider surfaces.

## Outcome

42 agent-harness tests pass; the materialiser writes the full harness (4 rules, 7
personas, 6 skills); both golden scenarios pass; the rule is live across providers.

## Notes

The materialiser is a group-callback because all app *leaf* commands require the
bucket session / secret store, which a profile-independent materialiser must not.
The conformance gate registers `agent` as a group-callback emit key alongside
`contract`. The 303 scenario asserts no casilla value (a value-oracle against an
AEAT worked example remains the documented W03 follow-up); it proves the eval
methodology generalises across modelos.
