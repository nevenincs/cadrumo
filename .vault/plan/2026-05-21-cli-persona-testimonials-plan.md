---
tags:
  - '#plan'
  - '#cli-persona-testimonials'
date: '2026-05-21'
modified: '2026-07-17'
body_hash: 'sha256:ae8c17f0555fece046fa4d0f03e8ebb72e913d383327199fa0afb76d35d40305'
tier: L2
related:
  - '[[2026-05-20-cli-persona-testimonials-audit]]'
  - '[[2026-05-20-cli-persona-testimonials-research]]'
  - '[[2026-05-20-test-fidelity-sweep-audit]]'
  - '[[2026-05-21-cli-persona-testimonials-audit]]'
  - '[[2026-06-04-cli-persona-testimonials-adr]]'
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# `cli-persona-testimonials` initial remediation plan

## Description

Initial remediation campaign driven by the operator-persona testimonial swarm
and the test-fidelity sweep. Each phase records a bounded remediation cluster
from the May campaign. Later open-ended testimonial intake continues in
`2026-06-30-cli-persona-testimonials-plan`; this document is retained as the
historical L2 closure tracker for the original wave.

Source artifacts: `2026-05-20-cli-persona-testimonials-audit`,
`2026-05-20-cli-persona-testimonials-research`, and
`2026-05-20-test-fidelity-sweep-audit`.

## Steps

### Phase `P01` - i18n naked-string remediation

Eliminate operator-facing naked strings from the CLI surfaces identified by the
initial testimonial and locale-fidelity sweeps.

- [x] `P01.S01` - Close ledger import naked-string cluster C, task 519, commit 9ec797b5f; `src/aeat/entrypoints/cli`.
- [x] `P01.S02` - Close CLI boundary errors and locale-scanner cluster D, commit 46889d841; `src/aeat/entrypoints/cli`.
- [x] `P01.S03` - Close censo sync naked-string cluster E, commit 6903944a9; `src/aeat/entrypoints/cli`.
- [x] `P01.S04` - Close IdentityError NIF NIE CIF naked-string cluster A, commit 5e30ffd18; `src/aeat`.
- [x] `P01.S05` - Close app-live verify portals borrador naked-string cluster F, commit 7502b3ec1; `src/aeat/entrypoints/cli`.
- [x] `P01.S06` - Close modelo-work BadParameter naked-string cluster B, commit 70715be3a; `src/aeat/entrypoints/cli`.
- [x] `P01.S07` - Close startup bucket-history and auth-diagnostic singleton strings, commit 7afd19aed; `src/aeat/entrypoints/cli`.

### Phase `P02` - bucket isolation and workflow correctness

Close bucket binding and workflow diagnostics that could confuse taxpayer
context or leak internal representations.

- [x] `P02.S08` - Bind modelo work create to the active profile bucket, task 513, commit d870a936c; `src/aeat/application/modelo`.
- [x] `P02.S09` - Replace work verify NO_PENDING_OBLIGATION raw repr leak, task 516, delegated to cli-workflow-redesign and resolved by commit 0775cfb63; `src/aeat/entrypoints/cli`.

### Phase `P03` - profile lifecycle and session

Close active-profile lifecycle behavior after profile deletion and logout.

- [x] `P03.S10` - Enforce switch lockout after delete or logout of the active profile, task 515, delegated to cli-workflow-redesign and resolved by commit 623795a8d; `src/aeat/application/user_profile`.

### Phase `P04` - calculation-engine binding gaps

Ensure registry calculations receive declaration metadata and profile-sourced
bindings without caller-side duplication.

- [x] `P04.S11` - Populate declaration year and period from work-unit metadata, task 517, closed by `2026-05-22-cli-persona-testimonials-P04-S01`; `src/aeat/application/modelo`.
- [x] `P04.S12` - Auto-resolve profile-sourced bindings and keep estimacion-directa enum Decimal behavior, task 521, closed by `2026-05-22-cli-persona-testimonials-P04-S02`; `src/aeat/application/modelo`.

### Phase `P05` - CLI UX and display

Align operator-facing profile names, workflow discovery, and ledger/modelo
diagnostics with the UX clusters reproduced by the persona campaign.

- [x] `P05.S13` - Display profile names instead of UUIDs across operator surfaces, task 518, delegated and closed by `2026-05-22-cli-persona-testimonials-P05-S01`; `src/aeat/entrypoints/cli`.
- [x] `P05.S14` - Close CLI UX polish cluster for revision discovery, classify echo, ledger guidance, and state-aware overview wording, task 520, closed by `2026-05-22-cli-persona-testimonials-P05-S02`; `src/aeat/entrypoints/cli`.

### Phase `P06` - tooling and follow-ups

Close locale tooling decisions, registry drift follow-up, and translated error
fallbacks found during the testimonial campaign.

- [x] `P06.S15` - Decide aeat.locales ErrorCode message_key scope, task 522, recorded in `2026-05-21-cli-persona-testimonials-audit`; `.vault/audit`.
- [x] `P06.S16` - Translate aeat config google error wrappers, task 523, commits 6491aeceb and 8e0f15b7b; `src/aeat/locales`.
- [x] `P06.S17` - Audit help-text vocabulary drift, task 524, commit aede996da; `src/aeat/entrypoints/cli`.
- [x] `P06.S18` - Reconcile Modelo 200 casilla 00592 registry drift, task 514, closed by `2026-05-22-cli-persona-testimonials-P06-S04`; `src/aeat/_data/registry/aeat/modelos/200`.
- [x] `P06.S19` - Translate errors registry fallback wave and extend scanner coverage, task 525, closed by concurrent parity and locale-honesty gates; `src/aeat/locales`.

### Phase `P07` - revision-year temporal validation

Close the fresh persona repair that caught incompatible `--revision` and
`--year` combinations during work-unit creation.

- [x] `P07.S20` - Reject work create when the supplied revision does not cover the filing year, closed by `2026-05-27-fresh-cli-persona-repair-S171`, commit a0d7daa27; `src/aeat/entrypoints/cli`.

## Parallelization

The original May work ran as a swarm campaign. P01 through P06 were
independent remediation clusters once shared locale and profile-identity
decisions were established. P07 was a later fresh-persona repair linked back to
this plan for continuity.

New persona waves are no longer scheduled here. Use
`2026-06-30-cli-persona-testimonials-plan` for continuation work.

## Verification

This plan is complete when all Step rows are checked and the cited exec records
or commits remain discoverable in the vault and git history.

Required checks for this archival repair:

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-21-cli-persona-testimonials-plan.md`
- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-05-21-cli-persona-testimonials-plan.md`
