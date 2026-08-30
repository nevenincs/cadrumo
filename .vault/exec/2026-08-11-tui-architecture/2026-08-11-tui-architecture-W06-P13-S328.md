---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:ff17b46d8bab62656ba4d51db26e9354f40f7fb91f886cac3c9d65a77cf48716'
step_id: 'S328'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make dependency-receipt drift adjudicable by recording WHAT the fingerprint covers, not merely that it moved. OBSOLETE AS OF 2026-08-28 -- DISCHARGED BY DELETION, NOT BY REPAIR, same disposition as S334 and from the same commit. The subject was the C0 dependency receipt, and the deleted blob confirms the shape this row describes: `src/cadrumo/entrypoints/tests/test_public_operation_dependency_receipt.py` at 00de767e9a^ carried `source_digest`, `source_tree_digest`, `result_digest` and `definition_contract_digest`, all opaque, with no field-level schema snapshot -- which is why adjudicating a drift once took hand archaeology across eight commits. Commit 00de767e9a deleted that file. VERIFIED NOT INHERITED rather than assumed: the three surviving receipt tests were checked individually. `test_workspace_dependency_receipt.py` carries no digest at all; the digests in `test_edit_dependency_receipt.py` are a `_DIGEST = "a" * 64` fixture constant passed to the LIVE registry contract set, not a persisted drift fingerprint; and the only hits in `test_financial_operand_dependency_receipt.py` are inside a forbidden-token list. No `TuiOperation*ReceiptV1` model survives in `src/`. So nothing in the tree now stores a digest that a later reader would need to adjudicate. DECISION REQUIRED: close as discharged-by-deletion with this record as its evidence, or reopen against a successor if a fingerprinted receipt is reintroduced -- in which case the row's original demand stands, that the schema or a field-level manifest ride beside the digest and be proven by a mint, a known additive change to a transitive input, a re-mint, and an assertion that the two receipts differ in exactly the field that changed and nowhere else

## Scope

- `the dependency receipt schema`
- `its minting path`
- `and a drift-diff proof over a known additive change`

## Changes

- `verify:` `ls src/cadrumo/entrypoints/tests/` -> `pass`

## Notes

No code change. Same disposition and same commit as `S334`: `00de767e9a`
deleted `src/cadrumo/entrypoints/tests/test_public_operation_dependency_receipt.py`,
the C0 dependency receipt that carried the opaque `source_digest`,
`source_tree_digest`, `result_digest` and `definition_contract_digest` fields
this row existed to make adjudicable.

Verified NOT inherited at `c9e5cd7cc4` rather than assumed, by reading each
surviving receipt test: `test_workspace_dependency_receipt.py` carries no
digest; the digests in `test_edit_dependency_receipt.py` are a fixture
constant passed to the live registry contract set, not a persisted drift
fingerprint; and the only hits in `test_financial_operand_dependency_receipt.py`
are inside a forbidden-token list. No `TuiOperation*ReceiptV1` model survives
in `src/`. Nothing in the tree now stores a digest a later reader would need
to adjudicate.

Recorded as discharged-by-deletion. If a fingerprinted receipt is ever
reintroduced, the row's original demand stands: the schema or a field-level
manifest must ride beside the digest, proven by a mint, a known additive
change to a transitive input, a re-mint, and an assertion that the two
receipts differ in exactly the field that changed and nowhere else.
