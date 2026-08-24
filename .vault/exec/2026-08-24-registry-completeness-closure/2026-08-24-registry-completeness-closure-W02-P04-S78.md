---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:dc7fcc51d5057183b2c91db21a0c710a1f602f5569dbc6b4fc9a55e5b03fd60f'
step_id: 'S78'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

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
