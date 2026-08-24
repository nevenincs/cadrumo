---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:9399d67e44f3c4ae61e555dc3c449737d164051efd62b98113e2365adb307135'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `Modelo 187 Article 42 filer-limb review`

## Scope

Independent post-review of `f8abe74abb`, limited to Modelo 187's Article 2
filer population, the Article 42 RGAT limb, legal citation anchoring,
applicability refusal, owner routing, anti-redeclaration boundary, and the
regression evidence added by `W02.P04.S78`.

The review used Vaultspec-RAG to locate the canonical applicability path and
governing campaign record, then read the production and registry epicentres in
full. Exact repository searches found one Modelo 187 applicability declaration
(`m187-seed`), no Modelo 187 `FilingProducerKey` namespace, and no second
Modelo 187 export or legal-filer authority.

## Findings

No findings. `f8abe74abb` is safe to close.

The official BOE text for Orden HAC/1417/2018, artículo primero, replaces
Modelo 187 Article 2 and expressly adds the persons or entities in RGAT Article
42 as a second filer limb. The live BOE text and its bundled official corpus
agree. RGAT Article 42 identifies the relevant IIC managers, distributors,
financial entities, intermediaries, public notaries, SICAV cases, and its
priority rules. The retained direct Article-2 legal record therefore grounds
both limbs without creating a redundant standalone Article-42 catalogue record.

The one-fact `m187-seed` selector still decides only the withholding/payment on
account limb. It explicitly leaves the Article 42 population unresolved, does
not infer it from a missing withholding fact, and preserves applicability grade
with no export layout. The reference preserves the non-fileable disposition and
routes its live closure condition to S29; it neither adds a producer nor opens a
parallel filing path.

The focused committed-registry suite passed (`10 passed`), and it invokes the
strict catalogue validator, including bundled-corpus required-text validation.
An additional direct legal-catalogue verification of
`orden-hac-1417-2018:art-primero` passed. The added test fails if the retained
Article-2 legal reference, Article-42 disclosure, or unresolved state is
removed. `git show --check f8abe74abb` was clean.

## Recommendations

None. Future multi-limb support must extend the existing canonical
`ModeloApplicabilityRule` path and remain subject to the existing S29 closure
condition.
