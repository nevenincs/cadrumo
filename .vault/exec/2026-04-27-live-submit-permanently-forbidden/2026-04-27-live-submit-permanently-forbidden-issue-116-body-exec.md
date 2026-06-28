---
tags:
  - "#exec"
  - "#live-submit-permanently-forbidden"
date: "2026-04-27"
modified: '2026-04-27'
related:
  - "[[2026-04-27-live-submit-permanently-forbidden-adr]]"
  - "[[2026-04-27-live-submit-permanently-forbidden-phase-1-summary-exec]]"
---

**Type:** permanent safety charter. This issue stays open as the canonical
pointer for the rule that the product never submits to AEAT on Kent's behalf.
It is not a staging area for a future live-submit feature. It defines the
non-negotiable invariants that every implementation, ADR, workflow, and audit
must honor.

**Cadence:** permanent umbrella. Reference it from every issue or PR that
touches submission, workflow, auth gate, settings, or any surface adjacent to a
potential AEAT write.

## Product contract

The Kent-facing product loop is `produce -> verify -> export`. Kent uploads the
exported fichero himself in the AEAT portal. Live AEAT submission is
permanently forbidden and permanently out of scope.

## The non-negotiable rules

### R1 — Product policy

The product never submits to AEAT. No CLI command, hidden command, workflow
branch, background job, provider mode, agent delegation, or helper composition
may file on Kent's behalf.

### R2 — Runtime refusal

Any product-path attempt to request a live AEAT write must fail immediately with
`LiveSubmitForbiddenError`. No environment variable, typed confirmation phrase,
provider selection, or legacy compatibility shim may enable live submission.

### R3 — No executable live-write path

The codebase must contain no executable path that invokes an AEAT write
endpoint. This includes browser actions, HTTP requests, transport branches,
submitter implementations, or workflow paths that can sign, send, confirm, or
otherwise finalize a return against AEAT from normal product behavior.

### R4 — Regression defense

The repository must contain regression tests that defend the permanent
prohibition. At minimum the tests must prove that:

- live-submit CLI surfaces are absent
- live-submit product env vars are absent from `Settings`
- the live-write gate always refuses
- no executable submission path can reach an AEAT write transport

### R5 — Live-read boundary

`AEAT_LIVE_TESTS_ENABLED=1` remains a live-read opt-in only. Live reads are a
separate category from live writes. Live-read support must never be described,
implemented, or tested as a write-side capability.

### R6 — Documentation and ADR alignment

User-facing docs, roadmap surfaces, mandate files, ADRs, and plans must
describe live AEAT submission in present tense as permanently forbidden.
Historical artifacts may remain only when explicitly labeled `historical`,
`legacy`, `pre-#432`, or `stale`.

### R7 — Charter enforcement in code review and audit

Every issue, PR, and rolling audit that touches submission, workflow, auth
gate, settings, or CLI surfaces must verify that the repository still contains
no executable AEAT write path and that the regression guard still defends that
condition.

## Non-goals

- This charter does not prevent live AEAT reads that are explicitly gated by
  `AEAT_LIVE_TESTS_ENABLED=1`.
- This charter does not prevent dry-run portal walks, preflight checks, export,
  or verification.
- This charter does not stop Kent from filing manually through the official AEAT
  portal after he exports the fichero.

## Relationship to older safety work

Earlier repository history used a four-factor live-submit gate model involving
environment variables, typed confirmation, and workflow flags. That history is
superseded. The controlling policy is now simpler and stricter: live AEAT
submission is permanently forbidden.

## Why this exists

AEAT has no sandbox for autónomo filings. A successful write is a real legal
act by the taxpayer. The only acceptable accidental-live-write rate is zero.
This charter defines what zero means for the repository, the CLI, and the audit
process.

## Acceptance

- The charter stays open permanently as the reference pointer.
- Any new work that touches submission-adjacent surfaces cites this charter.
- The repository contains a regression test proving no executable live-submit
  path remains.
- Rolling audits continue to verify this charter as a standing invariant.
