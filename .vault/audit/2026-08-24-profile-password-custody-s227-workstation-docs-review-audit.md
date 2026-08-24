---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:20a8218628a0491809f9c5d0e090b90ac6928208e8af5cff7e295117bb358536'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S227 workstation docs review`

## Scope

Reviewed accepted custody authority, S227's plan and execution record, corrected S223 findings, concurrent commit `1beef77048`, the current workstation guide, live CLI command tree, and the root and `cadrumo-harness` packaging declarations. The documented-command conformance result (349 passed) and sequence contract/build focus (10 passed) support the Markdown and contract inventory. The target live workstation check and user-scope nitpicky build remain honestly recorded as not reaching page evaluation because unrelated registry validation refuses pending `deadline_windows` for Modelo 303 revision 2023 and Modelo 322 revisions 2008-2022.

## Findings

### stale-agent-materialization-golden | medium | The unsupported materialization sequence remains as a committed success artifact

The public workstation directive and private `install-agent-harness` contract were removed, and the live CLI has no `aeat app agent` verb. However, `docs/_sequences/workstation-setup/install-agent-harness.json` remains committed and still records `aeat --format json app agent --output ./operator-workspace` as a successful command with a materialized workspace result. The focused contract inventory does not detect orphan golden JSON, and its passing result therefore does not prove the sequence fully retired. S227's outcome says the sequence and command claim are absent, so evidence-only closure is not honest while this active generated evidence remains.

### harness-agent-extra-language | low | Separate harness production text still names the retired base-package extra

The root package correctly declares that no `agent` extra exists, and the workstation guide correctly routes source users through the separate `cadrumo-harness` workspace package and `cadrumo-mcp`. That legitimate guidance is preserved. Separately, production docstrings and refusal constants under `src/cadrumo-harness` still instruct users to install `cadrumo[agent]` and describe the MCP SDK as that extra. Those files sit outside S227's declared documentation paths, so this review does not make them an S227 implementation edit; they remain a real follow-on packaging/documentation inconsistency rather than grounds to remove the valid harness/MCP workflow.

### stale-agent-materialization-golden-resolved | resolved | The unsupported generated success artifact is retired

Re-review confirms the tracked `install-agent-harness.json` golden is deleted. A targeted search across the workstation guide and the complete sequence tree finds no `install-agent-harness`, `app agent`, or `--output ./operator-workspace` claim. The repeated documented-command conformance suite passes 349 tests, and the sequence contract, build, and golden-crash focus passes 10 tests. The target live page and nitpicky build remain accurately classified as external registry blockers because they stop before page evaluation; they do not conceal a remaining S227 defect.

### final-disposition | resolved | S227 documentation closure passes review

S227 now fully retires the unsupported workstation materialization directive, private contract, and generated evidence while preserving the legitimate separate `cadrumo-harness` package and `cadrumo-mcp` workflow. The remaining production harness references to `cadrumo[agent]` retain the separate LOW follow-on recorded above and do not block this documentation-scoped Step. Final disposition: PASS with no unresolved S227 CRITICAL, HIGH, or MEDIUM finding; evidence-only closure is honest after including the tracked golden deletion.

## Recommendations

- Block S227 closure until the orphan `install-agent-harness` golden is retired through the sequence owner's supported workflow and the focused sequence gates are repeated.
- Amend S227 evidence to distinguish removal of the Markdown directive/private contract from retirement of every committed sequence artifact.
- Track the `src/cadrumo-harness` stale `cadrumo[agent]` docstrings and install hints in a separately scoped implementation step that replaces them with the actual `cadrumo-harness` installation authority.
