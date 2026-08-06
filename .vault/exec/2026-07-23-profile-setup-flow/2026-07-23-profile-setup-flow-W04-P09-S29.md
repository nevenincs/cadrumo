---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:91e1465e36a4dd7757d9edb2a311fc3947dd68002aa2a4f8364271433681578a'
step_id: 'S29'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Add roundtrip plus anti-tautology coverage for divergence facts, the setup-incomplete state, and resume projection

## Scope

- `src/cadrumo/application/user_profile/tests/`

## Description

- Prove the divergence boundary through a genuine fresh encrypted-store reload: two `censo.divergencia.{0,1}.*` rows with all three subfields non-default (manual-CLI source, the non-default against the artefact default) reconstruct with strict frozen-model tuple equality; clearing one persisted subfield through the canonical `value=None` seam yields strict, index-specific inequality.
- Prove the setup-incomplete lifecycle on both persistence surfaces: create-then-reload reports the status on the encrypted record AND the manifest mirror; `complete_setup` flips both to active with facts surviving; corrupting the persisted manifest status line (asserted-applied) makes `load` raise the integrity refusal.
- Prove the resume projection with a maximal fixture — every optional descendant field populated non-default, including the disabled grade-65 and convivencia-false branches — through save, encrypted reload, checkpoint re-projection, and `resume_flow`; a resume followed by an immediate save-exit leaves the on-record path-value map identical in full.

## Outcome

Landed as `ac5b23e369` on `chore/s29-s30-roundtrip-hardening` off the merged main. Review verdict: clean pass — every anti-tautology guard verified non-vacuous, real encrypted adapters throughout, strict equality on every boundary, no mocks or skips, and each addition extends rather than duplicates its neighbouring coverage. Suites 48 passed, zero failed; full-tree collection clean at 13732 (the report's 13730 figure corrected by review — peer churn on the shared base, no collection errors either way).

## Notes

- Executed in a purpose-provisioned worktree off origin's merged main after the shared main worktree was independently confirmed diverged with live peer work; only read-only git ever ran in the shared tree.
- The burn-down's date-typing change was re-grounded before authoring: it is internal to the persistence seams, the answer maps stay ISO strings, so the assertions compare projection-to-projection and are type-agnostic.
- A stale three-line import hunk from the pre-merge attempt remains untouched in the retired feature worktree per the no-discard discipline; its intent is realised properly here.
