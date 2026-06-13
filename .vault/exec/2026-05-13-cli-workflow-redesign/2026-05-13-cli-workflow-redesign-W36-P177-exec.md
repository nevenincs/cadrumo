---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W36.P177'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W36.P177`

Completed the shadow-duplicate removal phase for the legal IVA prorrata
substrate.

- Modified: `src/aeat/domain/vat/test_prorrata.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

W36 is greenfield: no prior prorrata implementation existed in the
codebase. The audit confirmed the canonical owner is
`aeat.domain.vat._prorrata` and that no competing module declares
`compute_prorrata_general`, `classify_input_deduction`,
`is_especial_mandatory`, `requires_sectoral_separation`, or
`compute_sectoral_prorrata`. `domain.usage_ratios` was inspected and
confirmed distinct (proportional-expense allocation, not legal
prorrata).

Two regression guards were persisted as boundary tests in
`src/aeat/domain/vat/test_prorrata.py`:

- `test_no_parallel_prorrata_implementation_exists` walks
  `src/aeat/` and asserts that the canonical prorrata symbols appear
  only in the canonical module. A future drift that re-introduces a
  parallel implementation under a different module will fail this
  test before merge.

- `test_no_usage_ratios_to_prorrata_shim_exists` asserts that no
  production module imports both `aeat.domain.usage_ratios` and a
  prorrata type together. Test files are exempt (they may legitimately
  reference both while encoding the boundary).

The boundary contract from the ADR's Constraints (`do not reuse
usage_ratios`, `do not translate usage ratios into prorrata through a
shim`, `do not reuse the ledger ratios persistence shape`) is now
machine-checked.

Closed plan rows: `W36.P177.S1057`, `W36.P177.S1058`,
`W36.P177.S1059`, `W36.P177.S1060`, `W36.P177.S1061`,
`W36.P177.S1062`.

## Tests

`uv run --no-sync pytest src/aeat/domain/vat/test_prorrata.py -q`

The two new boundary tests both pass; full prorrata test slice runs at
35 cases.
