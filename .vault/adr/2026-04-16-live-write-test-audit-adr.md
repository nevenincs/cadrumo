---
tags:
  - "#adr"
  - "#live-write-test-audit"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-live-write-test-audit-research]]"
  - "[[2026-04-16-live-write-test-audit-reference]]"
  - "[[2026-04-12-submission-engine-adr]]"
---

# `live-write-test-audit` adr: `treat-marker-integrity-as-the-test-boundary-tripwire` | (**status:** `accepted`)

## Problem Statement

Issue `#119` must verify that the AEAT test suite cannot cross into a live write under pytest, while staying inside a strict scope: no production edits, only narrow test-side remediation, and follow-up issue creation for deeper charter drift.

## Considerations

- The default pytest invocation already excludes `live` tests.
- The live AEAT-facing tests that do exist are dry-run or read-only.
- Marker integrity is therefore the first and most brittle boundary: an unmarked test can bypass the intended suite partitioning.
- The submission and workflow unit suites still depend on test doubles around `aeat.adapters.outbound.aeat.export`, which is a quality problem but not evidence of a reachable live AEAT write path.

## Decision

- Treat exact `unit`/`live` classification on every collected test function as a required suite invariant and fix any narrow marker drift immediately.
- Use the actual body of each `live` test function, not just file-level grep noise, to determine whether the test can reach an AEAT write token.
- Treat absence of `AEAT_LIVE_SUBMIT_ENABLED` from both config and runtime env as part of the audit evidence, because that variable would represent an alternate write-enable surface.
- Record the submission-boundary double usage as follow-up debt instead of expanding this issue into a broad test refactor.

## Rationale

- Marker integrity is the cheapest high-signal safeguard for keeping live tests out of default pytest runs.
- Function-body inspection avoids false positives from helper classes or explanatory docstrings while still proving the actual marked test path is safe.
- Narrow remediation keeps this issue aligned with the user’s explicit instruction not to widen scope or touch `src/aeat/`.
- Follow-up issues preserve momentum on the suite-hardening objective without burying the audit under speculative rewrites.

## Consequences

- This issue can close with a `GO` verdict for live-write safety even if follow-up quality issues remain open.
- Future work must retire the submission/workflow doubles if the repo wants the no-fakes testing charter to apply consistently at the AEAT boundary.
