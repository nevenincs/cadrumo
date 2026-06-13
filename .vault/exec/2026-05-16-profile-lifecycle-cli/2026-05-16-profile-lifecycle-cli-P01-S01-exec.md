---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S01
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P01.S01`

Introduced the `ProfileName` typed alias in the operator profile domain
package.

- Created: `src/aeat/domain/profile/_constants.py`

## Description

`ProfileName` is the operator-typed identifier for one profile.
Constraint shape preserves the historical secure-object index
contract (`strip_whitespace=True, min_length=1, max_length=128`) so
existing bucket-id values stored in encrypted indices remain valid
after the alias rolls out. Tightening to kebab-case is deferred to a
future commit because historical data uses looser characters.

## Tests

Covered by `P01.S10` test contract in
`src/aeat/domain/profile/test_constants.py`.
