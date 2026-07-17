---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S17'
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
     The S17 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Add an explicit id-stability assertion to split_transaction_with_classified_children that raises when a classified replacement child transaction_id diverges from the bare child it derives from, so a divergence cannot silently misattribute evidence and provenance, gated on a test proving the split raises on a mismatched replacement transaction_id rather than proceeding and ## Scope

- `src/cadrumo/application/ledger/_actions_split_merge.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add an explicit id-stability assertion to split_transaction_with_classified_children that raises when a classified replacement child transaction_id diverges from the bare child it derives from, so a divergence cannot silently misattribute evidence and provenance, gated on a test proving the split raises on a mismatched replacement transaction_id rather than proceeding

## Scope

- `src/cadrumo/application/ledger/_actions_split_merge.py`

## Description

- Add the id-stability assertion inside `split_transaction_with_classified_children`: after building each classified replacement child, raise `TransactionValidationError` if `replacement.transaction_id != bare_child.transaction_id` (landed in commit `b3d8ab6b76`).
- Add `test_split_child_classification_that_changes_raw_id_is_refused`: call the atomic writer directly with a per-child classification patch that alters a raw movement field (amount), and prove it raises before any persistence — the parent stays ACTIVE and only the parent row exists (commit `58497dc90a`).

## Outcome

- A classification patch that would re-address a child under a new content id can no longer silently misattribute evidence/provenance to a stale sibling id; the atomic writer refuses and persists nothing. `test_llm_evidence_split_apply.py`: 6 passed.

## Notes

- The raise is unreachable through the live `apply_evidence_split` path (its patches never carry raw fields), so the test drives the writer directly with a raw-field patch to exercise the guard — the reviewer's requested proof that the guard bites.
