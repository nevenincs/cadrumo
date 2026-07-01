---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S19'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Run the focused gates clean: pytest collect-only, the ledger and modelo-verify suites, JSON schema and notice conformance, documented-command and harness-surface conformance, plus lint and type checks

## Scope

- `src/aeat/`

## Description

- Run collect-only over `src/aeat` sequentially (no parallel workers) to avoid the loader-cache/parallel-collection race documented in `aeat-local-execution`.
- Run the focused feature suites sequentially: ledger, modelo verify + filing, domain/modelos, and the JSON-schema + notice conformance suite.
- Dispatch an independent code review over the 16 feature commits (satisfies the campaign-close honesty-review gate).
- Remediate the two in-scope review findings and re-run the affected suites.

## Outcome

- Collect-only: clean, exit 0 (14119-line manifest; the transient collect errors seen under parallel `-n` do not reproduce sequentially).
- Focused suites: 1329 passed, 1 failed, 184 deselected. The single failure — `test_work_unit.py::test_no_parallel_work_unit_storage_namespace` — is OWNER-ATTRIBUTED to a peer campaign: it trips on `application/user_profile/_bundle.py` and `_custody_carry.py` (the custody campaign) referencing the `aeat.domain.modelos.work_units` namespace. It is not this feature's surface (no idempotency file appears in the offender list) and is recorded as out-of-scope inventory per `full-tree-gate-must-distinguish-owner`.
- Independent review verdict: PASS / GO, no CRITICAL/HIGH. Core safety and correctness hold (clock-free keyed guard, true no-op, keyless append preserved, verify-report collapse, re-file no-op never touches a submit path).
- In-scope review findings remediated: MEDIUM-2 (`bdd141a59`) — the idempotency/re-affirmation match now includes `recargo_amount` and `source_jurisdiction` (previously omitted, a silent surcharge under-declaration on a same-key retry), with two regression tests; MEDIUM-1 (`ce1f79e38`) — the filing-record anti-tautology proof now uses a valid hex seed so the outcome-pinned id model_validator (not field validation) is what raises, making the proof load-bearing. Post-fix: idempotency suite 13 passed, filing roundtrip suite 15 passed.

## Notes

- MEDIUM-3 (deferred to follow-up, not reverted): commit `f5bd349a5` (the P01.S01 provider-id lookup fix) also bundled unrelated Modelo 390 registry TOML + a 253-line M390 fold-in test — a scope-bleed / peer-WIP capture into an atomic ledger commit. The work is preserved in history; reverting would destroy the M390 work and is entangled with the ledger fix, so it is documented here and surfaced for the M390 campaign to confirm rather than unwound.
- LOW follow-ups (non-blocking): (1) the S22 modelo-file no-op Notice uses an inline message string rather than a `tr()` locale key (a deliberate choice to avoid concurrent locale-catalogue contention; it remains a properly typed Notice and mirrors the adjacent hardcoded `filing_disambiguation` line) — promote to a `tr` key once the locale surface settles, for parity with the localized ledger-add no-op; (2) P05.S16's Transaction roundtrip is a survives-reload check rather than a strict equality + on-disk-mutation anti-tautology proof — strengthen in a follow-up.
- Shared-worktree discipline: both MEDIUM fixes landed as explicit-pathspec commits; the two peer-staged files in the shared index (`test_modelo_200_bin_carry_forward_continuity.py`, `test_tax_id.py`) were confirmed untouched before and after each commit.
