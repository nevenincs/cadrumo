---
generated: true
tags:
  - '#index'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - '[[2026-07-25-test-harness-honesty-S01]]'
  - '[[2026-07-25-test-harness-honesty-S06]]'
  - '[[2026-07-25-test-harness-honesty-S07]]'
  - '[[2026-07-25-test-harness-honesty-adr]]'
  - '[[2026-07-25-test-harness-honesty-false-green-gates-audit]]'
  - '[[2026-07-25-test-harness-honesty-plan]]'
---

# `test-harness-honesty` feature index

Auto-generated index of all documents tagged with `#test-harness-honesty`.

## Documents

### adr

- `2026-07-25-test-harness-honesty-adr` - `test-harness-honesty` adr: `A gate must prove it discriminates: positive controls on every scanning gate` | (**status:** `accepted`)

### audit

- `2026-07-25-test-harness-honesty-false-green-gates-audit` - `test-harness-honesty` audit: `false-green gate audit`

### exec

- `2026-07-25-test-harness-honesty-S01` - CLOSED at commit ad2d2e3eda, the bare-.xls scan pattern carried a doubled backslash so it could never match a real literal and passed over four live sites, now corrected with three routed through the canonical constants, one documented Literal-alias escape guarded by a justification test, a positive control asserting every survivor pattern matches its target and rejects near-misses, and a non-empty-corpus assertion, verified by reintroducing a bare literal and observing the gate name the exact file and line
- `2026-07-25-test-harness-honesty-S06` - VERIFIED-SOUND RECORD, the held-serial escalation mechanism is unwired by design rather than dead code, recorded so a later reader does not fix a mechanism that is deliberately inert
- `2026-07-25-test-harness-honesty-S07` - VERIFIED-SOUND RECORD, the majority of the audited gate surface carries genuine positive controls, recorded so a later audit does not re-derive the same negative result

### plan

- `2026-07-25-test-harness-honesty-plan` - `test-harness-honesty` plan
