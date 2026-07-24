---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S29'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S29 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add roundtrip plus anti-tautology coverage for divergence facts, the setup-incomplete state, and resume projection and ## Scope

- `src/cadrumo/application/user_profile/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add roundtrip plus anti-tautology coverage for divergence facts, the setup-incomplete state, and resume projection

## Scope

- `src/cadrumo/application/user_profile/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Prove the divergence boundary through a genuine fresh encrypted-store reload: two `censo.divergencia.{0,1}.*` rows with all three subfields non-default (manual-CLI source, the non-default against the artefact default) reconstruct with strict frozen-model tuple equality; clearing one persisted subfield through the canonical `value=None` seam yields strict, index-specific inequality.
- Prove the setup-incomplete lifecycle on both persistence surfaces: create-then-reload reports the status on the encrypted record AND the manifest mirror; `complete_setup` flips both to active with facts surviving; corrupting the persisted manifest status line (asserted-applied) makes `load` raise the integrity refusal.
- Prove the resume projection with a maximal fixture — every optional descendant field populated non-default, including the disabled grade-65 and convivencia-false branches — through save, encrypted reload, checkpoint re-projection, and `resume_flow`; a resume followed by an immediate save-exit leaves the on-record path-value map identical in full.

## Outcome

Landed as `ac5b23e369` on `chore/s29-s30-roundtrip-hardening` off the merged main. Review verdict: clean pass — every anti-tautology guard verified non-vacuous, real encrypted adapters throughout, strict equality on every boundary, no mocks or skips, and each addition extends rather than duplicates its neighbouring coverage. Suites 48 passed, zero failed; full-tree collection clean at 13732 (the report's 13730 figure corrected by review — peer churn on the shared base, no collection errors either way).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- Executed in a purpose-provisioned worktree off origin's merged main after the shared main worktree was independently confirmed diverged with live peer work; only read-only git ever ran in the shared tree.
- The burn-down's date-typing change was re-grounded before authoring: it is internal to the persistence seams, the answer maps stay ISO strings, so the assertions compare projection-to-projection and are type-agnostic.
- A stale three-line import hunk from the pre-merge attempt remains untouched in the retired feature worktree per the no-discard discipline; its intent is realised properly here.
