---
tags:
  - '#plan'
  - '#cli-persona-testimonials'
date: '2026-05-21'
modified: '2026-05-21'
tier: L2
related:
  - '[[2026-05-20-cli-persona-testimonials-audit]]'
  - '[[2026-05-20-cli-persona-testimonials-research]]'
  - '[[2026-05-20-test-fidelity-sweep-audit]]'
  - '[[2026-05-21-cli-persona-testimonials-audit]]'
  - '[[2026-05-21-cli-persona-testimonials-audit]]'
  - '[[2026-06-04-cli-persona-testimonials-adr]]'
---







# `cli-persona-testimonials` `cli-persona-testimonial-remediation-plan` plan

Brief description of the proposed feature, change, or refactor.

## Proposed Changes

Describe what work needs to be done at a high level. Reference `{adr}`s,
`{research}`, `{reference}`, and other plan or reference files where
appropriate so implementation remains grounded in architectural decisions.

## Steps

The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks.

Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates.





## Parallelization

State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency.

## Verification

State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter.


## Context

## Intent

Remediation campaign driven by the operator-persona testimonial swarm
and the test-fidelity sweep. Each phase is a remediation wave; granular
execution state is maintained in the coordinator task list (task ids
cross-referenced per step). Complexity tier: L2 (Phases > Steps).

Source artefacts: ``2026-05-20-cli-persona-testimonials-audit``,
``2026-05-20-cli-persona-testimonials-research``,
``2026-05-20-test-fidelity-sweep-audit``.

## P01 — i18n naked-string remediation — COMPLETE

Wave delivered: 8 commits, ~55 operator-facing naked strings eliminated,
~45 locale keys translated es/en/ca/hu via the `aeat.locales` CLI.

- [x] S01 Cluster C — ledger import (9ec797b5f) — task #519
- [x] S02 Cluster D — CLI boundary errors + locale-scanner extension (46889d841)
- [x] S03 Cluster E — censo sync (6903944a9)
- [x] S04 Cluster A — IdentityError NIF/NIE/CIF (5e30ffd18)
- [x] S05 Cluster F — app-live verify/portals/borrador (7502b3ec1)
- [x] S06 Cluster B — modelo-work BadParameter (70715be3a)
- [x] S07 singletons — startup / bucket-history / auth-diagnostic (7afd19aed)

## P02 — bucket isolation & workflow correctness

- [x] S01 modelo work create binds to active profile bucket (d870a936c) — task #513
- [x] S02 work verify NO_PENDING_OBLIGATION raw-repr leak — task #516 — DELEGATED to `cli-workflow-redesign`; RESOLVED by their commit 0775cfb63 (bug-inventory B2).

## P03 — profile-lifecycle & session

- [x] S01 delete/logout active profile → switch lockout — task #515 — DELEGATED to `cli-workflow-redesign`; RESOLVED by their commit 623795a8d (BLOCKER B1, cluster A).

## P04 — calculation-engine binding gaps

- [ ] S01 engine populates decl.ejercicio/decl.periodo from work-unit metadata — task #517
- [ ] S02 profile-sourced bindings auto-resolve; estimacion-directa enum/Decimal — task #521

## P05 — CLI UX & display

- [~] S01 profile display name instead of UUID across surfaces — task #518 — DELEGATED to `cli-workflow-redesign` (profile-uuid-identity ADR, plan Wave W01). Tracking only.
- [ ] S02 CLI UX polish cluster (revision discoverability, classify echo, etc.) — task #520 (cross-check against `cli-workflow-redesign` bug-inventory clusters D/E before executing)

## P06 — tooling & follow-ups

- [x] S01 aeat.locales ErrorCode message_key scope decision — task #522 — investigated; decision persisted in `2026-05-21-cli-persona-testimonials-audit`. Remediation split to S05.
- [x] S02 i18n aeat config google error wrappers — task #523 (6491aeceb + 8e0f15b7b) — _google_refusal helper + 14 cli.config.google.errors.* keys × 4 locales.
- [x] S03 audit help-text vocabulary drift (aede996da) — task #524
- [ ] S04 registry drift: modelo-200 casilla 00592 — task #514 (concurrent #476 campaign)
- [x] S05 errors.* registry-fallback translation wave (+ scanner extension) — task #525 — RESOLVED: scanner generalisation landed in _ast_scanner.py; ~375 errors.* + wizard.setup.verifier.* keys translated across all 4 locales by a concurrent campaign; parity + locale-honesty gates green.

## Maintenance

This plan is the durable wave tracker; the coordinator task list is the
live granular tracker. Update both as steps complete: check the step
here, mark the task completed, and record the commit SHA.
