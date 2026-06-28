---
step_id: S105
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P31.S105 step record

## Step

Land the PROMOTE-001 protect-list as a typed constant `PROMOTE001_PROTECT_LIST` in
`src/aeat/diagnostics/_identity_placement.py`, documenting the constraint-shape
mismatch rationale for each of the 52 blocked sites, and update `find_bare_str_typed_id_fields`
to skip protect-list entries so the W11 Clause 4 detector becomes a zero-violation gate.

## Protect-list size

52 sites in `PROMOTE001_PROTECT_LIST`. Grouped by rationale code:

- `HEX64` — 26 sites where TransactionId, InvoiceId, EvidenceId, SnapshotId aliases
  require 64-char hex digests but field values are arbitrary strings.
- `MINLEN` — 5 sites where BucketId alias has `min_length=1` but fields have
  empty-string defaults or accept empty values.
- `PATTERN` — 1 site where ProfileId has character-class pattern constraint.
- `NODOC` — SnapshotId sites documented as non-hex-64 shape in module docstrings.
- `TRANSIT` — 7 sites where ModeloId (`^\d{3}$`), BindingId, CasillaId, ConstructId
  aliases have shapes incompatible with existing transit-format values.

## Verification

```
Clause 4 violations after protect-list: 0
21 diagnostics tests passed in 11.92s
```

## Files touched

- `src/aeat/diagnostics/_identity_placement.py` — added `PROMOTE001_PROTECT_LIST` constant
  and updated `find_bare_str_typed_id_fields` to accept and honour the protect list.
