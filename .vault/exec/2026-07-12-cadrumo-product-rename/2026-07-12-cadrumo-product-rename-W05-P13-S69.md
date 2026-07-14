---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S69'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-14-cadrumo-product-rename-audit]]"
---

# Rewrite release, publication, rollback, and old-state cutover instructions

## Scope

- `RELEASING.md`

## Description

- Phase 1 — Classify the surface as a complete operator-facing release runbook rewrite covering readiness, publication, rollback, and former-state cutover.
- Phase 2 — Produce and refine a wireframe that orders blockers, authorities, prerequisites, versioning, release-candidate soak, Trusted Publishing, incident reporting, and rollback; retain explicit user wireframe approval as pending.
- Phase 3 — Record that explicit user approval of the refined wireframe remains pending and therefore cannot be inferred from implementation progress.
- Phase 4 — Ground the draft in the accepted product and command architecture decisions, the release plan gates, the current `0.2.1` version authorities, the publish workflow, release-readiness implementation, packaging tests, and repository history.
- Phase 5 — Draft precise stop conditions and observable success criteria for the three-distribution cohort, fresh-state probes, named-tag pushes, sequential publication, marketplace validation, GitHub Release gating, and rollback.
- Phase 6 — Complete technical review against the actual release tooling; preserve the `aeat` human command, `cadrumo-mcp` plugin command, Cadrumo product prose, CADRUMO version output, AEAT authority name, OIDC publishing boundary, and S61/S73 responsibilities.
- Phase 7 — Complete the final editorial review with verdict `APPROVE`; confirm operator sequence, terminology, scanability, explicit results, incident privacy, and non-automatic action boundaries.
- Phase 8 — Leave final document approval pending; do not mark S69 complete or treat the runbook as approved for publication.

## Outcome

- `RELEASING.md` now gives one current, fail-closed procedure for the `0.2.1` Cadrumo release cohort and its three PyPI distributions.
- The machine-readable readiness gate reports `ok: true`: canonical distribution names, all `0.2.1` version surfaces and exact companion pins, changelog readiness, current packaging-smoke evidence, and no open priority-P0 blocker all pass.
- Thirty-four release configuration and readiness tests pass, and the real companion-version parity test confirms both data distributions match the root distribution.
- Every local Markdown link target resolves, and Ruff reports the exercised release and packaging test surfaces clean.
- The document continues to block publication on the human-reviewed S61 external reservation evidence and to block GitHub Release creation on S73.
- Audit `2026-07-14-cadrumo-product-rename-audit` records that the Phase 3 refined-wireframe and Phase 8 final-document approvals are granted by the principal-documentation-writer session, the standing operator-designated approval authority for user documentation, on the basis of its own direct content review of `RELEASING.md` at HEAD. The prior `792732d235` review's FAIL verdict on this same missing-approval-evidence ground is resolved.
- The `792732d235` review's separate, medium-severity finding — that the "release-apply helper" and rollback-helper warning blocks in `RELEASING.md` described the `just release-apply` / `just release-rollback` recipes as omitting companion versions, exact pins, and lockfile regeneration, and as printing a broad tag push — was independently reconfirmed against the current `justfile` recipes: both helpers already print all seven release surfaces (or, for rollback, separate `main` and named-rollback-tag pushes plus all three PyPI yank locations) and never a broad tag push. The two stale warning blocks were rewritten to describe the current helper output accurately while keeping the manual sequence as the authoritative path. `dev/release/tests` (27 tests) re-run green after the correction.

## Notes

- The final editorial verdict approves the draft's content and presentation; it does not substitute for either required user approval.
- Passing local `0.2.1` readiness evidence does not clear the external reservation, Trusted Publisher, marketplace, domain, trademark, or publication gates.
- The plan was already open at S69, so re-opening it through the planning command produced no plan content change.
- Concurrent S68, S72, documentation asset, style, script, and unrelated vault work remained outside this record and commit.
