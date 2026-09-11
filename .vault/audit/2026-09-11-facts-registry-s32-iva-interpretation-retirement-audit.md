---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:712e82818962948c288eadee45579a49b78dc18efda7ab21e592597b47a48d65'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S32 IVA interpretation retirement`

## Scope

Reviewed S32 against the retirement ledger: remove enum-text numeric interpretation while retaining the persisted `IvaRate` taxonomy and resolve numeric slots through the dated IVA authority. The review covered the current enum source and the regression census in `test_rate_parity.py`.

## Findings

### numeric-constant-detector-teeth | medium | Initial regression census omitted the historical assignment form

The first census mutation proof covered the retired function form but not the assigned `_NUMERIC_RATE_PREFIX` constant.

### numeric-constant-detector-teeth | resolved | The census detects both retired declaration forms

The completed correction proves both assignment and function reintroduction. The five named legacy bindings remain absent; `IvaRate` retains stable tokens and nonnumeric members, while `iva_rate_percentage` projects a dated result through IVA authority resolution rather than parsing an enum token.

## Recommendations

No remediation remains. Run the full rate-parity suite after the signed authority artifact is published to this worktree.
