---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:99db065ce458bd22d1ec696a2bc3e46f1ac9ed8db51d2420b92bb6ef57eebfdc'
step_id: 'S38'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Record the three codification candidates from the ADR as post-cycle rule-promotion notes in the feature close audit

## Scope

- `.vault/audit`

## Description

- Author the feature close audit recording the three ADR codification candidates as post-cycle rule-promotion notes, each with proposed rule slug, one-sentence obligation, origin (ADR ruling plus the landed commit/gate), and its concrete promotion-ready condition.
- Reconcile the candidates against what actually landed across W01 through W05 (exec records and commits as ground truth), and record three secondary emergent cross-wave patterns not in the ADR list, held for a second occurrence before promotion.
- Record the accumulated follow-up register: the deferred `_TREE_DOC_DIRS` tutorial-scope expansion (operator decision), the orphan-golden-dir sweep, the accepted-latent multiline-inline-span extraction gap, the latent negative-number token-classification edge, and the approximately 26 exec records awaiting an annotation-hygiene pass.

## Outcome

- The feature close audit is authored under `.vault/audit` with the three primary candidates, three secondary candidates, and the five-item follow-up register; recommendations route the tutorial-scope expansion to the operator and defer promotion to the close honesty review.
- No rule authored in `.vaultspec/rules/`: per the vaultspec-codify discipline, candidates are recorded for post-cycle promotion only, held one full cycle behind the close honesty review.
- Grounded the `_TREE_DOC_DIRS` follow-up against the live gate: `_flat_docs()` scans flat `docs/*.md`, `docs/explanation`, `docs/how-to`, and `README.md` but not `docs/tutorials`, where the first enrolled pages ship — a real coverage gap flagged for operator decision.

## Notes

- This record is the S38 candidate register, not the campaign close honesty review; that review is a separate fresh-context pass gated behind S37 and the landed content wave.
- `S37` (full docs gate suite green) is intentionally left unchecked: owned by a separate baseline sweep, completing after the content wave lands.
