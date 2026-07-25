---
tags:
  - '#exec'
  - '#delivery-pipeline-audit'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S03'
related:
  - "[[2026-07-25-delivery-pipeline-audit-plan]]"
---

# D2, relocate sync_aeat_record_design_corpus to dev/corpus in one atomic explicit-path commit tagged relocation:sync_aeat_record_design_corpus covering the module move, the new package init, the consumer import, and any self-naming strings, with collect-only observed clean immediately before the commit

## Scope

- `dev/packaging/sync_aeat_record_design_corpus.py`
- `dev/corpus/`

## Description

Verify the corpus-sync relocation, which landed at HEAD ahead of this execution pass.

- Confirm the module is tracked at `dev/corpus/sync_aeat_record_design_corpus.py` with the new package `dev/corpus/__init__.py`.
- Enumerate the consumer set by `rg` across the tree: the sole consumer is `src/cadrumo/_data/corpus/tests/test_record_design_support.py`, whose import reads `from dev.corpus.sync_aeat_record_design_corpus import check`.
- Confirm zero residual references to the old packaging path outside `.vault/`, where historical exec and audit records legitimately retain it.
- Run the consumer gate; it collects and passes.

## Outcome

Structurally complete at HEAD. The canonical site is `dev/corpus/`, the sole consumer import is repointed, no re-export bridge was left behind, and the old packaging path has no live referent.

The move landed across two commits rather than one: `bdbb16276a` (subject `relocation:sync_aeat_record_design_corpus move corpus sync tooling to dev/corpus`) added the new package, the 545-line module, and the consumer import, and `56df2b0f04` (subject `relocation:sync_aeat_record_design_corpus remove the duplicate left in dev/packaging`) deleted the original.

## Notes

The atomic-relocation discipline was not met, and this is recorded rather than smoothed over. The first commit copied the module instead of moving it, so for the window between the two commits HEAD carried two byte-identical copies of the same module, with the consumer bound to one of them. The discipline requires the canonical-site move and the consumer sweep to share one git index and one commit. The end state at HEAD is correct and no bridge survives, so the step is closed on its outcome, but the intermediate HEAD was a duplicate-authority state of exactly the kind the discipline exists to prevent.

Semantic discovery was degraded throughout this pass. The code index answers confidently while truncated, and a probe for corpus-acquisition tooling returned unrelated modules. Every consumer claim in this record therefore rests on `rg` sweeps against the working tree, never on a semantic miss.
