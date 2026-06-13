---
tags:
  - "#adr"
  - "#submission-safety-sweep"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-submission-safety-sweep-research]]"
  - "[[2026-04-16-submission-safety-sweep-reference]]"
  - "[[2026-04-16-live-write-static-audit]]"
  - "[[2026-04-12-submission-engine-adr]]"
---

# `submission-safety-sweep` adr: `issues-142-146-live-write-hardening` | (**status:** `accepted`)

## Problem Statement

The current AEAT submission boundary still violates charter rules `R2` through `R6`. Live-capable APIs still allow omitted `dry_run`, the submission engine lacks the distinct live-submit env gate and pytest refusal, the exact-phrase confirmation hook and append-only audit log do not exist, and the CLI still exposes a stub-backed "LIVE submission OK" path that is not a real AEAT transport.

## Considerations

- The write leaf remains `Modelo130Submitter.submit`; the missing safety rules belong above it in the engine, workflow, and CLI contract.
- The production workflow helper is intentionally not fully wired on this branch, so the sweep should harden the workflow API contract without pretending the workflow CLI can perform a real live filing today.
- The current submission CLI helper still builds the engine around `_NullSession`, so rewiring to a real browser/certificate stack would widen scope into unfinished browser/auth integration.
- The existing static audit already split the gap into focused issues `#142` through `#146`, so the implementation can stay tight if the new contract maps directly to those issue scopes.

## Constraints

- No live AEAT write may occur during tests or verification.
- The confirmation hook must remain private to `aeat.adapters.outbound.aeat.export`; it must not be re-exported or made part of the normal test seam.
- The log must be durable and append-only in practice, but the implementation should stay within the current branch’s file-based persistence model rather than introducing a new storage backend.
- The sweep should not attempt to complete the unfinished real-transport wiring in `aeat.adapters.outbound.aeat.browser.session` or the sibling-branch workflow composition.

## Implementation

- Require `dry_run` as an explicit keyword-only argument on all live-capable submission/workflow APIs and update every call site to spell out `dry_run=True` or `dry_run=False`.
- Replace the legacy `aeat_submission_require_human_confirmation` safety model with a distinct `aeat_live_submit_enabled` setting sourced from `AEAT_LIVE_SUBMIT_ENABLED`.
- Move the live-submit hardening into `SubmissionEngine._submit_with_transport`:
  - refuse live mode when `aeat_live_submit_enabled` is false
  - refuse live mode when `PYTEST_CURRENT_TEST` is present
  - compute a stable filing checksum and assemble the operator-facing confirmation payload
  - call a private exact-phrase confirmation function immediately before dispatch
  - append a structured live-submit audit record to `.aeat/live-submit-audit.log` after the live attempt resolves
- Add private modules `aeat.adapters.outbound.aeat.export._confirm` and `aeat.adapters.outbound.aeat.export._audit`; keep both outside the `aeat.adapters.outbound.aeat.export` public export surface.
- Fail closed on CLI live surfaces that still depend on `aeat.entrypoints.cli.submission._helpers.build_engine()` and `_NullSession`; dry-run and read-only helper paths remain supported.
- Retire the separate amendment/complementaria live gate: `aeat filing complementaria submit --live` must stop consulting `AEAT_LIVE_TESTS_ENABLED` and stop using `typer.confirm`; it must either flow into the same engine-owned live-submit barrier or fail closed when the transport remains stubbed.
- Remove the legacy `override_confirmation` contract from the submission/workflow public APIs and let the engine-owned confirmation hook be the final live-write barrier.

## Rationale

The charter’s load-bearing invariant is that a live AEAT write must be impossible by omission, test leakage, or an overly-friendly CLI surface. Requiring explicit `dry_run=` closes the omission hole; the distinct env gate separates live reads from live writes; the pytest refusal makes leaked env impossible to exploit from the suite; and the private confirmation hook plus append-only audit log add the last operator-visible control and the durable forensic record. Failing closed on the stubbed CLI path is the only truthful option on this branch because the browser/auth transport is not yet real.

The live-submit audit log is intentionally separate from `aeat_submissions_dir`: per-submission JSON records are business-domain persistence, while `.aeat/live-submit-audit.log` is the forensic trail required by `R6`. Each appended record must carry the charter payload exactly: UTC timestamp, modelo, period, taxpayer NIF, draft checksum, submission URL, AEAT response status, justificante CSV when present, the exact confirmation phrase typed by the operator, the env-var state at call time, and the caller process PID plus argv.

## Consequences

- Submission, workflow, and CLI tests will need broad signature updates because they currently rely on omitted `dry_run` defaults and the legacy `override_confirmation` shape.
- The submission CLI will stop advertising a stubbed live success path until real transport wiring lands in a later branch.
- The amendment and workflow CLI surfaces become thinner wrappers around the engine’s live-write contract instead of maintaining separate confirmation logic.
- The new private confirmation/audit modules create a clearer safety boundary inside `aeat.adapters.outbound.aeat.export`, but future work will still be needed to finish real Playwright + certificate composition for genuine live filing.
