---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m390-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m390-standardization-inventory-audit]]'
---

# `schema-hardening-m390-standardization` Code Review

M390STD-001 | INFO | M390 split remained mechanical and generic

The M390 standardization commit changed only vault tracking artifacts and the
M390 registry layout. It did not touch `_loader.py`, `_schema.py`, or
`_validate.py`, and it introduced no per-modelo loader, schema, validation, or
application branch. Reconstructing the fragments in source order is
line-identical to the pre-split `390.toml` source.

M390STD-002 | INFO | Verification covers registry and annual IVA behavior

The verification slice covers generic directory-mode loading,
committed-registry loading, referential integrity, M390 registry behavior, M390
annual IVA binding resolution from M303 filings, application binding prefill,
and registry-backed filing draft construction for M303/M390.

M390STD-003 | LOW | Broader verification surfaced stale bound-casilla test inputs

The first S03 broad verification gate failed because
`test_modelo_303_390.py` still constructed M303/M390 drafts without required
bound-casilla binding values. The test was corrected to pass binding ids
explicitly and to scope the runtime schema provider to M303/M390. In the shared
worktree, that test correction was absorbed by concurrent commit `a5a01f573`
before the M390 S03 commit landed.

M390STD-004 | INFO | External reviewer did not return before closeout

The first reviewer id was stale, and the reused `vaultspec-code-reviewer`
thread did not return within 30 seconds. The closeout therefore records the
local review checks and focused regression gate rather than claiming an
independent reviewer pass.

M390STD-005 | INFO | Next standardization edge

After M390, M322 is the largest remaining single-file modelo at 573 lines,
followed closely by M353 at 569 lines. M322 should be the next normalization
slice unless the planned file-size/row-size creep gate identifies a more urgent
regression.
