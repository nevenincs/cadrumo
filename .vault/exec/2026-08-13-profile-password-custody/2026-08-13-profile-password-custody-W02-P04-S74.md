---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:e96781d020a4ca5c5d0f2a59fd13a19e3e288d98c497313901be22d345e422a0'
step_id: 'S74'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S74 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh remove the latent hazard in the persisted profile record whose setup-state field defaults to the completed value, so a record constructed without stating it silently claims completion, noting that all three production construction sites state it explicitly today which makes this latent rather than live, and that changing a persisted-model default is a shape change wanting its own deliberate commit and ## Scope

- `src/cadrumo/application/user_profile/_capsule_record.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh remove the latent hazard in the persisted profile record whose setup-state field defaults to the completed value, so a record constructed without stating it silently claims completion, noting that all three production construction sites state it explicitly today which makes this latent rather than live, and that changing a persisted-model default is a shape change wanting its own deliberate commit

## Scope

- `src/cadrumo/application/user_profile/_capsule_record.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

The hazard is removed at the shape itself (commit `8af8766858`): `UserProfileRecord.setup_state` no longer carries the COMPLETE default — it is a required field on the strict-frozen model, so a record constructed without stating it fails at construction instead of silently claiming completion. The write-path guard `_assert_setup_state_was_stated` became unreachable and was deleted with its call site. Every in-tree construction now states the field explicitly (125 files swept; the batch stated the previous default COMPLETE, so observable behaviour is unchanged), and the anti-tautology roundtrip now proves the missing-field refusal at the model boundary.

## Notes

The sweep was executed while peer campaigns were editing test files in the same tree; several files were briefly held open by peers (Windows sharing locks), and two import-repair passes were needed to converge the sweep to compile-clean. Ruff clean on the swept set; collect-only on the touched packages clean; the record-boundary and roundtrip suites green. The tree-wide AttributeError red seen during the sweep belongs to a peer's in-flight registry refactor, not this row.
