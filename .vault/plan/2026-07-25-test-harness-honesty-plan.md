---
tags:
  - '#plan'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
tier: L1
related:
  - '[[2026-07-25-test-harness-honesty-false-green-gates-audit]]'
  - '[[2026-07-25-test-harness-honesty-adr]]'
---
# `test-harness-honesty` plan

- [x] `S01` - CLOSED at commit ad2d2e3eda, the bare-.xls scan pattern carried a doubled backslash so it could never match a real literal and passed over four live sites, now corrected with three routed through the canonical constants, one documented Literal-alias escape guarded by a justification test, a positive control asserting every survivor pattern matches its target and rejects near-misses, and a non-empty-corpus assertion, verified by reintroducing a bare literal and observing the gate name the exact file and line; `src/cadrumo/tests/test_enum_constant_extraction_inventory.py`.
- [ ] `S02` - Signal a degraded state on the semantic discovery service so a truncated index either refuses to answer or marks its answers untrustworthy, because the governing rule makes an agent refuse coding work when the service is DOWN while a service that ANSWERS from a partial index never trips that refusal and returns a confident empty result for a concept that does have a canonical owner, measured at 1027 code sections against roughly 4546 files with an empty degraded-reasons list; `external, vaultspec-rag repository not this tree`.
- [ ] `S03` - Assess whether the code index can converge at all while a committing fleet re-triggers its rebuild through the file watcher, since the degraded window is not self-limiting and chunk counts were observed climbing while the job identifier changed; `external, vaultspec-rag repository not this tree`.
- [ ] `S04` - Make the packaging preflight recipe state its marker selection explicitly, because it inherits the default marker expression over a mixed-marker directory and silently drops 106 of 330 tests while exiting zero, and the dropped modules are those named for the packaging smoke, Scoop, Homebrew, and Docker workflows the recipe gates; `justfile, dev/packaging/tests/`.
- [ ] `S05` - Refresh the module size-budget pins that are documented as having no headroom while sitting far above actual, since a stale ceiling permits silent regrowth up to the gap and the gate reports green throughout; `src/cadrumo/tests/test_data_size_budget.py`.
- [ ] `S06` - VERIFIED-SOUND RECORD, the held-serial escalation mechanism is unwired by design rather than dead code, recorded so a later reader does not fix a mechanism that is deliberately inert; `src/cadrumo/tests/_marker_hook.py`.
- [ ] `S07` - VERIFIED-SOUND RECORD, the majority of the audited gate surface carries genuine positive controls, recorded so a later audit does not re-derive the same negative result; `.vault/audit/2026-07-25-test-harness-honesty-false-green-gates-audit.md`.
- [ ] `S08` - Sweep the remaining survivor and conformance gates for the vacuous-pattern shape this audit found twice in one day, in the bare-literal scan and in the documentation claims gate, asserting each pattern against a known-match and a known-reject rather than trusting that a green gate is measuring anything; `src/cadrumo/tests/, dev/`.

## Description

## Steps

## Parallelization

## Verification

## Context

Tracks the six findings of the false-green gate audit. One (the vacuous bare-.xls scan pattern) is closed at commit ad2d2e3eda; the remainder are open. Two findings are informational records of verified-sound surfaces and are carried so a later reader does not re-derive them.
