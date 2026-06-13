---
tags:
  - "#plan"
  - "#live-write-test-audit"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-live-write-test-audit-research]]"
  - "[[2026-04-16-live-write-test-audit-reference]]"
  - "[[2026-04-16-live-write-test-audit-adr]]"
---

# `live-write-test-audit` `phase-1` plan

Deliver issue `#119` as an autonomous vaultspec audit workstream: inventory every test module, prove that no live-marked test can reach a live AEAT write, remediate any narrow test-side drift, publish the audit trail, and raise follow-up issues for deeper submission-boundary testing debt.

## Proposed Changes

- Enumerate every collected test module under `src/aeat/` and `tests/`.
- Verify marker integrity across all test functions.
- Audit every live-marked test body for AEAT live-write tokens and submission-engine misuse.
- Inspect `conftest.py`, live env surfaces, and submission-engine imports for alternate write-enable paths.
- Apply only narrow test-side fixes discovered during the audit.
- Persist the audit, execution record, and local code review.
- Create GitHub follow-up issues for nontrivial test-quality drift that cannot be responsibly fixed inside this issue.

## Tasks

- `Phase 1: execute the static audit`
  - Run repo-wide marker, env, fixture, and submission-boundary searches.
  - Validate the live test bodies with an AST-backed pass.
- `Phase 2: execute the runtime audit`
  - Run `uv run pytest --collect-only` under the current clean env.
  - Confirm `AEAT_LIVE_SUBMIT_ENABLED` is absent and document the expected pytest env surface.
- `Phase 3: remediate narrow drift`
  - Fix any missing or incorrect `unit`/`live` markers.
  - Re-run targeted tests and the marker audit until clean.
- `Phase 4: publish and escalate`
  - Write the vault artifacts and mandated audit report.
  - Open follow-up issues for nontrivial submission-boundary double usage.
  - Open a PR with the marker fix and audit documents.

## Verification

- Every collected test function carries exactly one of `unit` or `live`.
- No `live` test body contains `dry_run=False`, `submit(`, `live=True`, `--live`, `CONFIRMO`, or `AEAT_LIVE_SUBMIT_ENABLED`.
- No `conftest.py` or global fixture writes `AEAT_LIVE_SUBMIT_ENABLED` or patches a human-confirmation hook.
- `uv run pytest --collect-only` succeeds with `AEAT_LIVE_SUBMIT_ENABLED` absent from the shell environment.
- The local code review on the applied fix reports no remaining defects in the changed file.

## Explicit Plan Review

- **Scope check:** limited to test-suite audit work, `.vault/` artifacts, narrow test-side fixes, and GitHub follow-up/PR publication.
- **Production-code check:** no changes will be made under `src/aeat/` except issue creation for deeper drift if it is discovered there.
- **Approval check:** the user explicitly instructed an autonomous execution without pausing for human approval, so execution proceeded immediately after plan formation.
