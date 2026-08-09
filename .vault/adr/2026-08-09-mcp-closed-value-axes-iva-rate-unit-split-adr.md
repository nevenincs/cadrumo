---
tags:
  - '#adr'
  - '#mcp-closed-value-axes'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:ca21614d247affb85c949fdc1318ff2f34859bc0858f90b299dad55fdb7c9382'
related:
  - "[[2026-08-08-mcp-closed-value-axes-audit]]"
---

# `mcp-closed-value-axes` adr: `The --iva-rate unit split stays, bounded on both sides` | (**status:** `accepted`)

## Problem Statement

Two command families take the same tax concept under the same option name in different units.

`ledger inventory movement add` and the asset ledger take `--iva-rate` as a **percentage**: the field is bounded `0..100`, the default is `21.00`, and the value object computes `taxable_base * iva_rate / 100`.

`ledger add|classify|update`, the evidence verbs and the invoice verbs take `--iva-rate` as a **fraction**: `0.21`, used as-is.

Both are internally correct and each help string accurately describes its own side. The hazard is the seam: an operator or agent carrying one convention across the seam produces a value that is off by a factor of a hundred and arithmetically valid.

## Considerations

The asymmetry that mattered was not the naming but the **enforcement**. The percentage side was bounded `0..100` from the start; a fraction supplied there yields `0.21%`, a cuota so small it is visible in the very next output line. The fraction side was **unbounded**, so a percentage supplied there yielded a 2100% rate that nothing refused, persisted on the transaction, and inherited by every downstream aggregation reading the row.

The two directions are also not equally dangerous. Over-statement produces a valid-looking return the taxpayer overpays, with no counterparty and no later filing to contradict it; this codebase's gates are built almost entirely against under-declaration.

A rename is the obvious remedy and it is not free. `--iva-rate` is an operator-facing token on nine verbs across two families, cited in shipped help, in the agent harness surface, and in the documented command sequences. Renaming one side splits a vocabulary operators transfer between verbs, and the CLI contract rules treat that transferability as load-bearing.

## Considered options

**A. Rename the percentage side** to `--iva-rate-pct`, leaving `--iva-rate` to mean a fraction everywhere.

**B. Converge on one unit**, changing one side's arithmetic and its stored values.

**C. Keep both, and make the dangerous direction refuse.** Bound the fraction side so a percentage cannot be mistaken for one, and record the split as deliberate.

## Constraints

The percentage side's unit is not arbitrary. Its default is the registry-grounded `DEFAULT_IVA_GENERAL_RATE_PCT`, and the inventory and asset value objects are written against a percentage throughout -- docstrings, bounds and the `/100` in the computation. Option B therefore changes persisted values and a computation path, on a surface this campaign does not own.

Option A's cost lands on the side that is *already safe*. The percentage side has never been able to silently accept a fraction; renaming it addresses the confusion by relabelling the surface that was not producing the defect.

No Spanish IVA rate approaches 100% (LIVA arts. 90-91 put the general rate at 21%), so a fraction field can be bounded at 1 without any risk of refusing a real filing, and the bound never moves when a rate does.

## Implementation

Option C. `Transaction.iva_rate` carries a validator refusing a value above 1, and the refusal names the **unit** rather than the bound:

> `iva_rate is a decimal fraction, not a percentage: got 21. Express 21% IVA as 0.21.`

"Must be <= 1" is a true statement that leaves the operator to rediscover the convention that caused the mistake, which is the whole failure being caught.

The split itself stays. Each side keeps its own unit, its own bound, and a help string that states which unit it takes -- and both help strings were verified against the code rather than assumed.

## Rationale

The defect was never the shared name; it was that one side of the seam had no bound. With the bound in place both directions of the confusion now fail loudly and immediately: a percentage on the fraction side is refused with a message naming the unit, and a fraction on the percentage side yields a visibly absurd cuota against a `0..100` field.

That leaves the rename as a readability improvement rather than a safety one, and its cost is a split operator vocabulary across nine verbs plus a sweep of the harness and documented sequences. Recording the split as deliberate, with the dangerous direction closed, buys the safety without paying that.

This is a decision to *not* change something, which is exactly the kind that goes unrecorded and then gets rediscovered as an open question. The reasoning is written down so the next reader can disagree with the trade rather than re-derive it.

## Consequences


One option name continues to mean two units. An operator reading only the option name across the two families still learns nothing about which applies; they must read the help, which now reliably states it.

If the inventory or asset surface later grows an unbounded path, or a third surface adopts `--iva-rate` in a third unit, this decision should be reopened -- the bound is what makes the split safe, not the naming.

Revisiting is cheap and should not require this ADR to be wrong: if the ledger surface is being reworked for other reasons, folding a rename in at that point costs far less than a standalone sweep, and this record explains why it was deferred rather than rejected.

