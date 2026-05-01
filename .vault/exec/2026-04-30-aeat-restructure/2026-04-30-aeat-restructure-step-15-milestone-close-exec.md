---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-summary]]"
---

# 2026-04-30-aeat-restructure step-15 milestone close

## status

Pipeline complete. EPIC #475 closed; milestone 0.1.5 closed; issue
#476 closed. Step-13 follow-up issues triaged into the next
milestone via labels.

## acceptance re-verification (Step 8 -> Step 15 invariance)

The 15 ADR acceptance criteria were verified at Step 8 (keystone
merge). The Step-15 trigger re-runs the same set against the
post-pipeline state to confirm no regression has been introduced
by Steps 9-14.

| criterion | verified Step 8 | re-verified Step 15 |
|-----------|-----------------|---------------------|
| Hexagonal layout in place | ✓ | ✓ |
| Import-linter contract clean | ✓ | ✓ |
| Public-surface shims working | ✓ (verify_shims exit 0) | ✓ |
| End-to-end behavioural smoke test | ✓ | ✓ |
| Type-checker clean run | ✓ | ✓ |
| Migration-script correctness fixture | ✓ | ✓ |
| Packaging verification (wheel-install + post-install layer-import smoke) | ✓ | ✓ |
| Tier-1 supersession landed | ✓ | ✓ |
| Tier-2 validation landed | ✓ | ✓ |
| Tier-3 inline-updates landed | (deferred) | ✓ (Step 12) |
| Dead-code Phase-1 complete | ✓ | ✓ |
| Dead-code Phase-2 candidates dispositioned | ✓ | ✓ |
| Carve-out registry stable | ✓ (9 entries) | ✓ (9 entries) |
| Step-13 missing-impl audit complete | (deferred) | ✓ (Step 13) |
| Phase summary written | (deferred) | ✓ (Step 14) |

15 / 15 ✓ — re-verification clean.

## next-milestone enqueue

Step-13 follow-up issues are labelled and triaged:

- #498 Modelo 202 ruleset gap → labelled `gap`, queued for backlog
- #499 Modelo 303/2024 casilla closure → labelled `gap`, queued for backlog

## shim-removal schedule

Per ADR Shim deprecation contract: shim removal is eligible at the
second minor release after introduction. With this milestone landing
0.1.0 -> 0.1.1, shim removal eligibility opens at 0.1.3. An auto-
generated removal PR is scheduled for the corresponding release
window.

## report to owner

Pipeline closed autonomously per the ADR + plan's autonomous-execution
mandate. No human-in-the-loop gates were invoked. The milestone-close
announcement is posted on issue #476 alongside the Step-8 acceptance
comment + Step-9 lift-freeze comment.
