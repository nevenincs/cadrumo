---
generated: true
tags:
  - '#index'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:451a591ad9142cf33bad40477554cd86efa2a9b32f38a8784fb54042ccce5ace'
related:
  - '[[2026-08-08-synced-history-consumption-P01-S01]]'
  - '[[2026-08-08-synced-history-consumption-P01-S02]]'
  - '[[2026-08-08-synced-history-consumption-P01-S03]]'
  - '[[2026-08-08-synced-history-consumption-P01-S04]]'
  - '[[2026-08-08-synced-history-consumption-P01-S05]]'
  - '[[2026-08-08-synced-history-consumption-P01-S06]]'
  - '[[2026-08-08-synced-history-consumption-P01-S08]]'
  - '[[2026-08-08-synced-history-consumption-P01-S09]]'
  - '[[2026-08-08-synced-history-consumption-P01-S10]]'
  - '[[2026-08-08-synced-history-consumption-P02-S07]]'
  - '[[2026-08-08-synced-history-consumption-adr]]'
  - '[[2026-08-08-synced-history-consumption-plan]]'
  - '[[2026-08-08-synced-history-consumption-pulled-fact-classification-reference]]'
  - '[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]'
  - '[[2026-08-08-synced-history-consumption-research]]'
---

# `synced-history-consumption` feature index

Auto-generated index of all documents tagged with `#synced-history-consumption`.

## Documents

### adr

- `2026-08-08-synced-history-consumption-adr` - `synced-history-consumption` adr: `Which pulled AEAT facts are calculation inputs` | (**status:** `accepted`)

### exec

- `2026-08-08-synced-history-consumption-P01-S01` - Census every calculation input channel that could have consumed a pulled AEAT filing fact
- `2026-08-08-synced-history-consumption-P01-S02` - Prove the consumption rather than assuming it, in the direction S01 measured
- `2026-08-08-synced-history-consumption-P01-S03` - Classify each census row as calculation input, reconciliation target only, or display only
- `2026-08-08-synced-history-consumption-P01-S04` - Investigate whether previous renta values are consumed
- `2026-08-08-synced-history-consumption-P01-S05` - Investigate whether a ledger-derived casilla on a pulled work unit should be back-derived, left empty with an advisory, or refused
- `2026-08-08-synced-history-consumption-P01-S06` - Probe the over-payment direction deliberately
- `2026-08-08-synced-history-consumption-P01-S08` - Establish what a Sociedades filer's unpullable carries do on the consumption side
- `2026-08-08-synced-history-consumption-P01-S09` - Establish whether Modelo 200 and Modelo 202 can declare the authenticated filed-declarations read surface at all, keeping this separate from the consumption question S08 asks. The nine structurally excluded carry slots are a coverage gap in what the pull can FETCH, not a wiring gap in what the engine CONSUMES, and the two must not be ruled on as one. Determine from AEAT published material whether filed Sociedades declarations are exposed at the consulta view the reader is pinned to. If they are, the registry revisions are missing a live cross-reference and the nine become reachable. If AEAT does not expose them there, the nine are correctly unreachable and the honest output is a documented refusal naming the reason rather than a fix. Gate: the verdict cites AEAT published material rather than an inference from the registry silence, no live submission or remote mutation is performed, and either outcome lands as a change to the tree - a declared read surface or a recorded refusal - never as an open question
- `2026-08-08-synced-history-consumption-P01-S10` - Give the previous-filing channel a diagnostic
- `2026-08-08-synced-history-consumption-P02-S07` - Author the decision record ruling which pulled facts are calculation inputs, which are reconciliation targets and which stay display only, plus the mechanism each wired channel uses from the existing one-mechanism-per-calculation-type taxonomy, amending that taxonomy in the same change if no row covers a needed channel. Open every implementing row in the SAME action as the ruling, because a decision record ruling on code is not self-executing and the debt it creates otherwise has no owner while every later reader sees the ruling as in force. Gate: the record cites the census denominator and every ruling maps to an opened row id

### plan

- `2026-08-08-synced-history-consumption-plan` - `synced-history-consumption` plan

### reference

- `2026-08-08-synced-history-consumption-pulled-fact-classification-reference` - `synced-history-consumption` reference: `calculation input, reconciliation target, or display only`
- `2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference` - `synced-history-consumption` reference: `which pulled AEAT facts reach the calculation engine`

### research

- `2026-08-08-synced-history-consumption-research` - `synced-history-consumption` research: who consumes pulled AEAT filing history
