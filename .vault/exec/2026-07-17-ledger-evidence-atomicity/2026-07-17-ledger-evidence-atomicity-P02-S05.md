---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged and ## Scope

- `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged

## Scope

- `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py`

## Description

- Add `test_split_children_retain_lineage_and_evidence_provenance`: after an evidence-driven split, prove the parent is SPLIT with a PARENT `split_lineage`, and every child is BUSINESS-classified, carries a CHILD `split_lineage` bound to the same split group and citing the parent as a sibling, inherits the parent's `purchase_invoice_evidence_id`, and carries an `evidence_provenance` entry for it.
- Add `test_split_child_evidence_failure_leaves_everything_unchanged`: seed a parent citing a nonexistent evidence record so the atomic writer's per-child evidence validation fails; prove `apply_evidence_split` raises, the parent stays ACTIVE with no `split_lineage`, only the parent row exists, and the event history equals its pre-call snapshot.

## Outcome

- Consistent inheritance and atomicity proven with real secure storage, real repositories, real bucket-event history, and a real subprocess LLM proposer — no mocks/stubs. The forced failure is genuine (missing evidence record), not injected.
- The lineage-retention assertion pins the P02.S04 fix for the previously-dropped child `split_lineage`.
- `test_llm_evidence_split_apply.py`: 5 passed. Full ledger application suite 384 passed. Ruff clean. Commit `6d6c33f5ba`.

## Notes

- None.
