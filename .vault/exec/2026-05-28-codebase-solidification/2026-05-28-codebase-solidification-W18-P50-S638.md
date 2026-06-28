---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S638
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W18.P50.S638

Canonicalized the `cast()` rationale token in `_streams.py`.

- Modified: `src/aeat/adapters/inbound/sanitizer/_streams.py`

## Description

The existing token `CAST-RATIONALE-SANITIZER-PIKEPDF-OPERANDS` was renamed to `CAST-RATIONALE-SANITIZER-PIKEPDF-OPERAND-LIST` to match the canonical slug required by the inventory ratchet. The prose rationale (pikepdf's `_ObjectList` is the private QPDF type, not statically typed as `Sequence[...]`, cast required for type-checker satisfaction without runtime risk) was preserved verbatim.

## Tests

Grep-post confirmed token present on the line immediately preceding the `cast(` call. `test_cast_rationale_inventory.py` passes with 0 violations. `test_w18_p50_closure.py::test_s638_sanitizer_pikepdf_operand_list_token_present` passes.
