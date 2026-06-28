---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m720-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m720-standardization-inventory-audit]]'
---

# `schema-hardening-m720-standardization` Code Review

M720STD-001 | INFO | M720 split remained mechanical and generic

The M720 standardization commit changed only vault tracking artifacts and the
M720 registry layout. It did not touch `_loader.py`, `_schema.py`, or
`_validate.py`, and it introduced no per-modelo loader, schema, validation, or
application branch. Reconstructing the fragments in source order is
line-identical to the pre-split `720.toml` source.

M720STD-002 | INFO | Verification covers registry, deadline, and detail-record behavior

The verification slice covers generic directory-mode loading,
committed-registry loading, referential integrity, M720 registry behavior,
M720 filing schedule and deadline windows, M720 detail-record model coverage,
M720 row builders, and M720 application row-set round-trip behavior.

M720STD-003 | LOW | First broad pytest command used a stale test node name

The first S03 broad verification command referenced a non-existent row-set test
node and failed before running the intended surface. The failure was not
ignored: the correct test names were collected and the corrected gate passed.

M720STD-004 | INFO | External reviewer did not return before closeout

The review was dispatched to the existing `vaultspec-code-reviewer` thread
because the session was at the active-agent limit. The reviewer did not return
within 30 seconds. The closeout therefore records the local review checks and
focused regression gate rather than claiming an independent reviewer pass.

M720STD-005 | INFO | Next standardization edge

After M720, M390 is the largest remaining single-file modelo at 808 lines,
followed by M322 and M353. M390 should be the next normalization slice unless
the planned file-size/row-size creep gate identifies a more urgent regression.
