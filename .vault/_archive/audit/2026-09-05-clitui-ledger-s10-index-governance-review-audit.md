---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:a472fd69ad1e2ac1fc919b52a08c27e236b51289324d8b102d0746db33354b93'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[clitui-ledger.index]]"
  - "[[2026-09-04-clitui-ledger-W01-P03-S10]]"
---

# `clitui-ledger` audit: `S10 index governance review`

## Scope

Reviewed S10's generated feature index, execution record, campaign plan and
reference, generator provenance, and commit `ca3d739957`. The review challenged
whether the generated body exposes the promised ownership, hold, and gate
dependency facts, and regenerated the index to test stability. Vaultspec-RAG
was attempted first; its local vault index returned no results, so whole-file
and exact-text inspection supplied the evidence.

## Findings

**Ruling: NOT ACCEPTED.** One HIGH finding remains.

The index is generator-owned and stable: regeneration produced the identical
Git object. It correctly links the accepted ADR, plan, reference, S09 and S10
records, and preceding review audits without copying matrix evidence. S10 is
checked, S11 is next, and the reference still keeps G0 OPEN. Commit
`ca3d739957` changes only Vault documents; it introduces no product or TUI
implementation.

### claimed-governance-facts-are-not-published | high | The index lists generic documents but does not expose the gate chain

The generated body is only the standard document-type catalogue. It contains
no `G0`, `G1`, `G2`, `G3`, or `G4` token, no OPEN state, and no dependency edge.
The S09 title incidentally exposes sole ownership and the TUI hold, while S10's
title says a chain was published, but neither the S10 record nor its indexed
entry states the chain. The plan and reference appear under generic titles.
Consequently an index reader cannot determine the current gate, why the TUI is
held, or the ordered G0 -> G1 -> G2 -> G3 -> G4 dependency without leaving the
index and searching generic linked documents. That is navigation, not the
publication S10 claims.

## Recommendations

- Preserve CLI ownership of the generated index. Change canonical generator
  inputs so their indexed titles or typed records explicitly expose the active
  sole plan owner, current G0 OPEN state, TUI hold until G3, and ordered G0 ->
  G1 -> G2 -> G3 -> G4 dependency chain without copying row evidence into the
  index.
- Add a focused generator-output detector for the exact indexed facts and
  canonical links, then regenerate through `vault feature index`.

## Verification

`vault feature index -f clitui-ledger` reproduced the exact existing index
object. The feature-scoped full Vault check passes. Those checks verify
generator consistency and Vault structure, but do not require the missing
governance facts.

## Remediation review

**Ruling: ACCEPT.** No HIGH or CRITICAL findings remain. The canonical S10
record title now visibly states `clitui-ledger` as the sole active Ledger parity
owner, G0 OPEN, the ordered G0 -> G1 -> G2 -> G3 -> G4 chain, and the Ledger
TUI hold until G3 closes. The generator projects that exact title into the S10
index entry and retains canonical links to the ADR, plan, reference, and S09
record. It publishes governance facts only; it does not duplicate matrix or
behavioral evidence.

The detector binds the live record title to the exact generated S10 entry,
requires all four facts and canonical links, rejects missing/wrong owner,
current gate, reordered or incomplete chain, wrong hold gate, missing link, and
manual-only body prose, and requires a dry-run regeneration to report no
change. The exact-entry check prevents satisfying the contract by scattering
facts through unrelated titles, while the generator dry-run rejects hand-only
index edits.

Independent regeneration reproduced the identical index Git object
`1e6612914863a230917c49c8af9759329338bf9f`. All eight focused tests pass.
Ruff format/check, scoped `ty`, and feature Vault checks pass. S10 remains
checked, S11 is next, G0 remains OPEN, and the remediation introduces no
product or TUI implementation.
