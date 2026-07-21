---
tags:
  - '#research'
  - '#release-readiness-gate'
date: '2026-07-06'
modified: '2026-07-17'
related: []
---

# `release-readiness-gate` research: `audit-state gate and permanent blocker grounding`

## Findings

### Decision input

GitHub issue `#415` asked for release confidence before tagging: an
audit-state gate, a release-candidate soak, and a rollback path. The accepted
release-readiness ADR chose a local, read-only gate rather than hosted beta
infrastructure because the product had not yet shipped a first stable PyPI
release and the repository release process is explicitly human-gated.

The implemented plan records that `just release-readiness` is expected to read
local version and changelog surfaces, inspect the most recent packaging-smoke
evidence, and query GitHub for open issues carrying `priority:P0-blocker`.
The gate is wired into `just release-apply` as a pre-check and must not tag,
push, publish, or yank anything.

### Current implementation evidence

The live implementation keeps the gate read-only. `dev/release/readiness.py`
defines the blocker label as `priority:P0-blocker`, builds a typed
`ReadinessReport`, exposes `--json` and `--skip-network`, and hard-blocks only
when the GitHub query returns genuine open blocker issues. `justfile` exposes
`release-readiness` and `release-readiness-json`, then invokes the gate before
the human release-apply checklist. `RELEASING.md` documents that the check is
read-only and that a real open P0 blocker stops the release path.

The step record confirms the landed behavior with real-behavior tests under
`dev/release/tests` and `src/aeat/tests/test_release_config.py`, plus a live
gate run that reported BLOCKED on issue `#116`.

### Permanent safety charter interaction

Issue `#116` is open and labelled `priority:P0-blocker`. Its body says it is a
permanent safety charter and "stays open permanently as the reference pointer"
for the rule that the product never submits to AEAT on Kent's behalf.

That creates an intentional policy tension rather than a release-readiness code
defect: the release gate treats every genuinely open `priority:P0-blocker` as a
hard release blocker, while the safety charter says this particular issue is
permanent. Local source edits to the release gate would weaken the accepted ADR
unless a coordinator-owned policy decision changes how permanent charter issues
are labelled or exempted.

### Recommendation

Keep the release-readiness gate behavior unchanged. The current
`just release-readiness` failure is honest: a real open issue with the blocker
label is present. Clearing the release gate requires an external policy action,
such as relabelling or superseding the permanent charter handling, not a local
code bypass.

This research bridge closes the missing same-feature research provenance for the
accepted release-readiness ADR. It does not authorize a new exception for issue
`#116`, and it should not be used to claim release readiness while
`just release-readiness` remains blocked.

### Sources

- `2026-07-04-release-readiness-gate-adr`: accepted ADR for the read-only
  audit-state gate, local RC soak, and rollback procedure.
- `2026-07-04-release-readiness-gate-plan`: single-step plan and verification
  contract for issue `#415`.
- `2026-07-04-release-readiness-gate-S01`: execution record for the landed gate
  and live BLOCKED evidence against issue `#116`.
- `dev/release/readiness.py:38`, `dev/release/readiness.py:150`,
  `dev/release/readiness.py:275`: blocker-label constant, GitHub blocker check,
  and CLI entry point.
- `justfile:459`, `justfile:463`, `justfile:585`: read-only recipe contract,
  release-readiness recipe, and release-apply pre-check refusal.
- `RELEASING.md:75`: operator-facing audit-state gate instructions.
- `gh issue view 116 --json number,title,state,labels,url,body`: current
  external-state evidence that issue `#116` is open, permanently intended to
  stay open, and labelled `priority:P0-blocker`.
