---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:80cf373ed613f39f5f1845ec97f8be029a8d6ea00a447d0b22b298068a92f606'
step_id: 'S148'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Decision taken: do NOT widen the printed country vocabulary with fourth-language exonyms, reversing the coordinator pre-ruling on measured evidence. French, German and Italian are already present as ENDONYMS because the three-language rule covers every country in each of its own official languages, so Belgique, Schweiz, Svizzera and Letzebuerg all resolve today. What remains uncovered is only the cross-exonym, which requires a three-party document naming a country that is neither party address, a shape that appears in shipping lines rather than in the address blocks the ladder reads. And the most frequent uncovered case is behaviourally empty: adding Espagne, Spanien and Spagna resolves them to ES, for which the country resolver returns nothing by design because the code names the State while the territory stays undetermined, so coverage and absence give the identical answer. Cost side rejected on top of that: a four-language widening reaches 401 names from 169 and multiplies collision and containment risk across a loader that refuses wholesale

## Scope

- `src/cadrumo/_data/registry`

## Description

## Outcome

Executed. This row's own account is written into the plan row text, which opens with its verdict (Decision taken: do NOT widen the printed country vocabulary, reversing the coordinator pre-ruling on measured evidence) and gives the reasoning a record would have carried.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account.** The real account exists verbatim in the plan; it was filed as a work item rather than as evidence, which is why no record accompanied it.

## Notes
