---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S30'
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
     The S30 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
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
     The Verify the portable-export shape against the compatibility lifecycle for every schema addition and ## Scope

- `src/cadrumo/domain/user_profile/_portable_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the portable-export shape against the compatibility lifecycle for every schema addition

## Scope

- `src/cadrumo/domain/user_profile/_portable_export.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Prove, rather than assert, that the portable export carries every schema surface this campaign added: a populated record with divergence rows, descendant extensions, and the setup-incomplete status round-trips through the version-3 bundle with strict profile equality and the status surviving (a drop would re-default to active and fail).
- Confirm the no-version-bump conclusion under the pre-release compatibility regime: the export composes the whole record generically, its shape did not change, and the commit adds no fabricated old-version fixture, no upgrader, and touches no floor constant — exactly what the regime requires.
- Add the export-boundary anti-tautology: mangling a unique fact value inside the serialized bundle (asserted-applied) makes the reloaded profile strictly differ.

## Outcome

Landed as `807a51aae2` on `chore/s29-s30-roundtrip-hardening`. Review verdict: clean pass; the compatibility-lifecycle rules were verified respected in both directions — the shape is carried, not versioned against bytes nothing released ever wrote.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The bundle version stays three; any future post-checkpoint bump follows the frozen-floor rules, not this campaign's surfaces.
