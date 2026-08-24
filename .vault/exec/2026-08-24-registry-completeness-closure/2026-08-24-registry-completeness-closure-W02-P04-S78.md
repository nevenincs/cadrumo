---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6a157cd14c66d896d18e833aa24b87fc7fe80c86349b9c275f00e8ae361284d8'
step_id: 'S78'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S78 and 2026-08-24-registry-completeness-closure-plan placeholders are machine-filled by
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
     The Correct Modelo 187 Article-2 filer-population wording to include the separate Article 42 RGAT obligated-person/entity limb, update its prerequisite, reconsideration, and existing owner routes, and re-attest the reference and execution record. and ## Scope

- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-187-design-era-coverage-reference.md`
- `.vault/exec/2026-08-24-registry-completeness-closure/2026-08-24-registry-completeness-closure-W02-P03-S17.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Correct Modelo 187 Article-2 filer-population wording to include the separate Article 42 RGAT obligated-person/entity limb, update its prerequisite, reconsideration, and existing owner routes, and re-attest the reference and execution record.

## Scope

- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-187-design-era-coverage-reference.md`
- `.vault/exec/2026-08-24-registry-completeness-closure/2026-08-24-registry-completeness-closure-W02-P03-S17.md`

## Description

- Ground the 2019-and-later Article 2 wording in the official Orden HAC/1417/2018 text and the bundled official corpus.
- Record that Article 2 has two independent filer limbs: withholding or payment on account, and the persons or entities described by Article 42 RGAT.
- Bind the retained Modelo 187 applicability rule to that direct legal authority without adding a parallel selector or a duplicate legal-filer authority.
- Keep the Article 42 limb explicitly unresolved because the current canonical applicability rule accepts one payer fact only; do not infer it from the absence or presence of withholding.
- Re-attest the S17 reference and record, and add a regression assertion for the retained legal authority and explicit incomplete state.

## Outcome

Modelo 187 remains applicability-grade and non-fileable. The retained `m187-seed` rule decides only Article 2's withholding or payment-on-account limb. The independent Article 42 RGAT population is now stated and legally linked, but remains explicitly incomplete until an accepted profile fact can represent it.

Any later multi-limb applicability work must extend the existing canonical `ModeloApplicabilityRule` resolution path. It must not add a second Modelo 187 selector, producer, or legal-filer authority. S29 remains the existing closure owner for the resulting live filing gap and its reconsideration condition.

## Notes

- Vaultspec-RAG semantic discovery and whole-epicentre reads found one production Modelo 187 applicability authority. Exact repository searches found no competing selector, producer, export route, or legal-filer definition.
- The direct Article 2 legal record is sufficient to ground both limbs. A proposed standalone RGAT Article 42 catalogue record was not retained because the bundled source has a pre-existing canonical-anchor collision; shipping an ambiguous corpus reference would be invalid.
- The regression test was mutation-tested by temporarily removing the 2018 Article 2 legal reference. It failed as expected, then passed after exact restoration.
