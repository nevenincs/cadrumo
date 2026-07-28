---
generated: true
tags:
  - '#index'
  - '#test-harness-honesty'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - '[[2026-07-25-test-harness-honesty-S01]]'
  - '[[2026-07-25-test-harness-honesty-S04]]'
  - '[[2026-07-25-test-harness-honesty-S05]]'
  - '[[2026-07-25-test-harness-honesty-S06]]'
  - '[[2026-07-25-test-harness-honesty-S07]]'
  - '[[2026-07-25-test-harness-honesty-S08]]'
  - '[[2026-07-25-test-harness-honesty-S09]]'
  - '[[2026-07-25-test-harness-honesty-S10]]'
  - '[[2026-07-25-test-harness-honesty-S11]]'
  - '[[2026-07-25-test-harness-honesty-S12]]'
  - '[[2026-07-25-test-harness-honesty-S13]]'
  - '[[2026-07-25-test-harness-honesty-adr]]'
  - '[[2026-07-25-test-harness-honesty-false-green-gates-audit]]'
  - '[[2026-07-25-test-harness-honesty-plan]]'
  - '[[2026-07-28-test-harness-honesty-rag-service-start-refused-by-witness-timeout-audit]]'
---

# `test-harness-honesty` feature index

Auto-generated index of all documents tagged with `#test-harness-honesty`.

## Documents

### adr

- `2026-07-25-test-harness-honesty-adr` - `test-harness-honesty` adr: `A gate must prove it discriminates: positive controls on every scanning gate` | (**status:** `accepted`)

### audit

- `2026-07-25-test-harness-honesty-false-green-gates-audit` - `test-harness-honesty` audit: `false-green gate audit`
- `2026-07-28-test-harness-honesty-rag-service-start-refused-by-witness-timeout-audit` - `test-harness-honesty` audit: `The discovery service cannot start under fleet load, and reports the timeout as an identity failure`

### exec

- `2026-07-25-test-harness-honesty-S01` - CLOSED at commit ad2d2e3eda, the bare-.xls scan pattern carried a doubled backslash so it could never match a real literal and passed over four live sites, now corrected with three routed through the canonical constants, one documented Literal-alias escape guarded by a justification test, a positive control asserting every survivor pattern matches its target and rejects near-misses, and a non-empty-corpus assertion, verified by reintroducing a bare literal and observing the gate name the exact file and line
- `2026-07-25-test-harness-honesty-S04` - Make the packaging preflight recipe state its marker selection explicitly, because it inherits the default marker expression over a mixed-marker directory and silently drops 106 of 330 tests while exiting zero, and the dropped modules are those named for the packaging smoke, Scoop, Homebrew, and Docker workflows the recipe gates
- `2026-07-25-test-harness-honesty-S05` - Refresh the module size-budget pins that are documented as having no headroom while sitting far above actual, since a stale ceiling permits silent regrowth up to the gap and the gate reports green throughout
- `2026-07-25-test-harness-honesty-S06` - VERIFIED-SOUND RECORD, the held-serial escalation mechanism is unwired by design rather than dead code, recorded so a later reader does not fix a mechanism that is deliberately inert
- `2026-07-25-test-harness-honesty-S07` - VERIFIED-SOUND RECORD, the majority of the audited gate surface carries genuine positive controls, recorded so a later audit does not re-derive the same negative result
- `2026-07-25-test-harness-honesty-S08` - Sweep the remaining survivor and conformance gates for the vacuous-pattern shape this audit found twice in one day, in the bare-literal scan and in the documentation claims gate, asserting each pattern against a known-match and a known-reject rather than trusting that a green gate is measuring anything
- `2026-07-25-test-harness-honesty-S11` - Reconcile the duplication disposition record against a fresh live scan
- `2026-07-25-test-harness-honesty-S12` - Audit the gate surface for checks reachable only through a marker-scoped or narrowed selection
- `2026-07-25-test-harness-honesty-S09` - Triage the empty-assert functions the screen flags
- `2026-07-25-test-harness-honesty-S10` - Extend the vacuity screen, and search for escapes that outlived their reasons
- `2026-07-25-test-harness-honesty-S13` - Close the stale-fixture family by requiring a test to bind a persisted record's version constant rather than restate its value, since two bucket-manifest fixtures kept writing schema_version=1 after the durability floor moved to 2 and neither failed loudly because both read paths treat the resulting raise as an ordinary degraded state, and the gate found five further stale sites on its first run

### plan

- `2026-07-25-test-harness-honesty-plan` - `test-harness-honesty` plan
