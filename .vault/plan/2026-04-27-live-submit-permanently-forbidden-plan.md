---
tags:
  - '#plan'
  - '#live-submit-permanently-forbidden'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-live-submit-permanently-forbidden-research]]'
  - '[[2026-04-27-live-submit-permanently-forbidden-adr]]'
---

# `live-submit-permanently-forbidden` `phase-1` plan

Permanently align runtime, tests, docs, charter, and vault artifacts with the
 accepted policy that the product never submits to AEAT.

## Proposed Changes

- Remove or hard-refuse every remaining live-submit code path under
  `src/aeat/submission`, `src/aeat/auth`, and the amendment CLI surface while
  preserving dry-run, preflight, and export behavior.
- Add a dedicated regression module that proves the permanent prohibition from
  multiple angles.
- Rewrite public docs, charter text, and vault guidance so no "future
  live-submit" framing survives outside clearly marked historical context.
- Create the missing mandate source file and regenerate provider copies.
- Amend the historical ADRs and write a new policy ADR that supersedes their
  future-facing live-submit assumptions.
- Record execution and code-review evidence for the excision.

## Tasks

- `Phase 1 - code excision`
  1. Remove product live-submit env vars and collapse the write gate to a
     permanent refusal.
  1. Make the submission engine and submitters dry-run-only.
  1. Remove the amendment CLI `--live` path and sweep stale live-submit
     docstrings.
- `Phase 2 - regression coverage`
  1. Replace older gate-preservation tests with permanent-forbid assertions.
  1. Add `test_live_submit_permanently_forbidden.py`.
  1. Re-run focused unit coverage until the new refusal contract is stable.
- `Phase 3 - docs and charter`
  1. Correct the stale same-day research note and write the new policy ADR.
  1. Amend the 2026-04-18 ADRs with explicit 2026-04-27 supersession language.
  1. Rewrite roadmap/coverage/mandate/charter surfaces into present-tense
     permanent-forbid wording.
- `Phase 4 - audit and verification`
  1. Regenerate provider rule copies from the new mandate source.
  1. Run the mandated grep audits, lint, typecheck, tests, hooks, and
     coverage.
  1. Run a mandatory code review and capture the outcome in `.vault/audit/`.

## Parallelization

The code and documentation streams can overlap, but the permanent-forbid
regression tests must land before the final verification pass. Documentation
rewrites follow the explicit researcher -> author -> editor workflow. Code
review runs after implementation stabilizes.

## Verification

- `rg -n "live_transport_supported|AEAT_ALLOW_LIVE_SUBMIT|AEAT_LIVE_SUBMIT_ENABLED|i-understand-this-is-real" src/aeat`
  returns only the dedicated regression assertions and historical workflow-flag
  refusal tests.
- `ROADMAP.md`, `docs/coverage/kent-capabilities.md`, and the mandate source
  state that live AEAT submission is permanently forbidden.
- Issue `#116` body is rewritten to match the new policy and includes a rule
  that the codebase must contain no executable AEAT write path.
- `just lint`, `just typecheck`, `just test`, `just hooks`, and
  `just test-cov` pass.

## Plan Review

Self-review against the issue scope, project mandates, sibling-branch
boundaries, the security audit, and the no-mocks discipline: pass.

- Zero live-submit code path remains reachable from product execution.
- The remaining grep matches are limited to intentional regression assertions or
  clearly historical context.
- The soft-collision surfaces with branch `#216` remain confined to
  `src/aeat/config.py` and `env/.env.example`.
- No changes cross into the declared `#321`, `#239`, or `#395` ownership
  boundaries.
