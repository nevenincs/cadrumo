---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S157'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert MCP mutability distinguishes read-only status from destructive operations

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_write_policy_mutability_parity.py`

## Description

- Check the record's own worked example against the classification rather than restating it.
- Find the example false, and find the reason it is false is the property the row is about.
- Establish which axis actually separates a status verb from its destructive siblings.
- Assert that axis directly, including the negative half that the read-only flag does not separate them.
- Confirm each verb carries a declared row so the flags are declared facts rather than the unclassified default.

## Outcome

The row is now satisfied, and closing it required correcting this record rather than only adding a test.

Corrected claim: an earlier version of this record stated the distinction is "the same one the reset lifecycle relies on, where status is a read while start and resume are destructive". Measured, `config.reset.status` reports `read_only=False`. It is not a read. Mutability is declared per FAMILY, so every verb inside the mutating reset family is non-read-only, `status` included.

That correction is not a detail, because it is the row's subject. Reading the read-only flag as the separator gets this family exactly wrong, and an agent deciding whether to ask a human before running a reset verb would find all three verbs indistinguishable on that axis.

The separator that does exist is the destructive axis, measured across the family: `status` is non-destructive while `start` and `resume` are destructive. Nothing asserted it. The new case pins both directions — that the read-only flag does NOT separate the three, and that the destructive flag does — so the case fails if the family collapses either way, whether status became destructive or start and resume stopped being. It also asserts each of the three carries a declared risk row, so the flags are declared facts rather than the all-false default an unclassified key reports.

The pre-existing content of the module is sound and was left alone: the live-write leaf tripwire, and the write-policy parity holding every profile-bound write verb to a mutating family.

`uv run --no-sync pytest` over the module reported `3 passed in 17.23s`, and the full MCP suite under an explicit marker expression reported `285 passed, 6 warnings in 83.02s`. `ruff check`, `ruff format --check` and `ty check` all reported clean.

## Notes

The failure mode this row surfaced is worth separating from the fix. The record asserted a worked example that read as evidence the gate was understood, and the example was wrong in the direction that mattered. A later reader trusting it would have concluded the read-only flag separates a status verb from a destructive one and built on that.

The write-policy catalogue's prefix matching with custody verbs bootstrap-exempt was examined and deliberately left alone. It reads like a fail-open gap and is documented at its own site as not being one.

Not verified: whether every other family containing a status-shaped verb separates on the destructive axis as the reset family does. Only the reset family was measured, because it is the one this record named.
