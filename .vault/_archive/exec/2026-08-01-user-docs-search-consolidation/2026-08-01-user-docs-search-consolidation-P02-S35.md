---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:764bae547a9a03432eafbb3e1170b6937ef0ffa7a7938e06d6a3abf8350f26e5'
step_id: 'S35'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Correct the two prose sites asserting a Rung-2 mechanism the tree no longer has

## Scope

- `dev/docs/terminology/_miss_rate.py`
- `dev/docs/pagefind_inject.py`

## Description

- Confirm both sites against HEAD rather than against the record that reported them, because a peer fix can land between investigation and remediation.
- Rewrite the miss-rate evaluator's module docstring so it states what the evaluator measures today instead of implying a partly-built semantic tier is pending.
- Rewrite the injector's record-identity comment so it stops naming a bridge module that does not exist, while keeping the deduplication contract and the no-URL-derivation rule it correctly documents.
- Change no behaviour: both edits are prose, and no symbol, signature, constant or control path was touched.

## Outcome

Both dead references are gone and neither file's behaviour changed.

The evaluator's docstring opened by calling itself "the deferral gate for a possible rung-2 static term-embedding matrix". The word possible carried the whole falsehood: it reads as a tier awaiting a decision, when the matrix, its compiler and the browser's cosine pass were all removed from this tree. The replacement keeps the ratified materiality line, which is still real and still governs, and then states plainly that no such tier exists and that the measured figure is the honest recall statement for the shipped lexical ladder rather than a baseline waiting for a semantic half to arrive. That distinction matters to the next reader who has to decide whether the number is a gap or a result.

The injector's comment asserted that a bridge hydrates the opaque record identity from its authoritative manifest. No such module is in the tree. The rewrite keeps both facts the comment got right, that results deduplicate on the same identity whichever pass surfaced them and that neither the browser nor this seam derives a URL from the id, and moves the bridge into the conditional it now belongs in.

This row was gated on nothing. The finding it acts on was measured while preparing both branches of a separate ruling, and the correction is right under either branch, so holding it behind that ruling would have been deferring work that nothing was waiting on.

## Notes

The two sibling findings from the same sweep are deliberately NOT actioned here. The three orphaned build-time modules and the zero-entry authority shipping inside the wheel are unconditional findings with conditional remedies, because under a recovery branch both regain the consumers they lost. Acting on them now would compound the loss a recovery exists to reverse, so each carries its own row stating both remedies and the coupling.

No tests, gates or linters were run. This fleet has a single test-run authority and the verification was queued to it rather than executed here. Both files were confirmed free of peer working changes before the edit and were claimed in the fleet ownership ledger.
