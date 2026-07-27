---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S17'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace declaracion-real-render-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-07-26-declaracion-real-render-verification-plan placeholders are machine-filled by
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
     The Decide whether Modelo 202 is enrolled in casilla-level reconcile, now that its profile is confirmed to exist and D5 governs enrolment and ## Scope

- `.vault/adr`
- `src/cadrumo/application/modelo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Decide whether Modelo 202 is enrolled in casilla-level reconcile, now that its profile is confirmed to exist and D5 governs enrolment

## Scope

- `.vault/adr`
- `src/cadrumo/application/modelo`

## Description

- Establish whether Modelo 202 satisfies the recorded enrolment criterion.
- Apply D5, which requires a real render in addition to registry readiness.
- Re-read the exclusion rationale in the enrolled-set docstring against what is now known.

## Outcome

Not enrollable, and the reason is D5 rather than any registry gap.

Modelo 202 is fully registry-ready. All four targets resolve cleanly, and the two genuinely engine-computed ones are correctly declared in the revision's computed set while the bound and manual ones are correctly absent, so the apparent asymmetry is not a gap. Its only fixture is synthetic. Under D5 that leaves it blocked on a real render and on nothing else, which is an evidence gap under D3 rather than a backlog item.

The enrolled-set docstring is corrected a second time, and differently. It first claimed Modelo 202 had no declaracion_pdf surface, which was false. The correction then claimed its casilla-id alignment was unconfirmed, which is also false now that alignment is measured complete. Rather than write a third per-modelo reason, the enumeration is removed: a reason recorded there is a copy of a fact that lives in the registry and the fixture corpus, and it goes stale whenever either moves without anything failing. The docstring now states the two real gates generically and points the reader at the sources.

## Notes

Two wrong reasons in the same paragraph, each introduced by someone correcting the previous one, is the argument against the enumeration rather than against either author. The pattern is that prose restating a fact owned elsewhere drifts silently, and the fix is to stop restating it.

The alignment measurement itself came from an independent pass rather than from the docstring, which is how the second drift was caught at all.
