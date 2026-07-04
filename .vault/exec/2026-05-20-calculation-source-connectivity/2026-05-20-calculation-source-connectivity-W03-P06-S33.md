---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S33'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S33 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Add region field to Renta deductibility context when category profiles require it and ## Scope

- `src/aeat/domain/renta/_ledger_expenses.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add region field to Renta deductibility context when category profiles require it

## Scope

- `src/aeat/domain/renta/_ledger_expenses.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Add an optional `residence_ccaa: CCAA | None = None` field to `RentaDeductibilityContext` (strict-frozen, default `None`), importing `CCAA` through the domain contribuyente facade. The field reuses the one residence-comunidad axis the autonomic-scale bindings already consume.

## Outcome

The region axis now exists on the deductibility context, optional and inert for the general expense path. Landed in commit `1ca532e93a`. A domain test pins the field defaults to `None` and accepts a member. ruff / ruff format / ty clean; pyright clean on the added code.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Implements decision D1-A of the proposed ADR `2026-07-04-renta-region-deductibility`. No behaviour change: LIRPF arts. 28-30 base-imponible deductibility is state law and does not vary by comunidad, so the field is inert until a territorial-regime override is declared.
