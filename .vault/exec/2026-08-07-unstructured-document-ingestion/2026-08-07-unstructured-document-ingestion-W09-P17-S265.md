---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:079b1792db0a27fdbfad3cf647d0ca30cb3f9c80d097eae4e30799e3d69a6614'
step_id: 'S265'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S265

## Scope

- `dev/locales`

## Description

- Read both verbs before fixing either, rather than trusting the diagnosis carried in the row.
- Probe whether the defect reaches further than the row describes, with a control that does not share it.
- Converge the single-key verbs onto the structural path the batch verb already uses, rather than teaching the text scanner about quoting.
- Delete the text-scanning machinery once nothing calls it.
- Pin the behaviour with controls, and mutation-prove the gate in both directions.

## Outcome

**The defect was broader than the row states, and the correction came from a probe rather than from reading.** The row describes `remove` refusing a key that `set` resolves. That is true, and it is half of it. Measured against a throwaway catalogue: the same refusal hits `set` as well, whenever the leaf is NEW. The setter reached the parsed mapping only for a leaf that already existed and fell back to a line-oriented writer otherwise, so appending a key under a quoted ancestor failed for exactly the same reason removing one did.

**And it is triggered by any quoted ancestor, not by the leaf's own parent.** The first probe reported all four cases refusing, including the two meant as controls, because the fixture nested everything under `'100'` — a quoted segment — so the control shared the defect and proved nothing. A control that fails alongside the case it is controlling for is not a control. Rebuilt with a genuinely unquoted branch, the four cases separated cleanly: unquoted remove and append both worked, both quoted paths refused.

**The fix is convergence, not repair.** The batch verb was already fully structural — parse, write into the mapping, rewrite through the guard — and handles quoted keys correctly because the parser normalises them. Both single-key verbs now take that same path. Teaching the line scanner about quoting was available and rejected: it would have left two implementations that agree only for as long as someone maintains both, which is the shape that produced this defect.

The line-oriented machinery had no callers afterwards and is deleted rather than left dormant: the key pattern, the line iterator, the leaf-end scanner, the append writer, the leaf remover, its namespace pruner, the newline chooser and the one-line scalar renderer. The namespace pruning it provided is reimplemented against the parsed mapping, where a quoted namespace prunes like any other.

**The leaf this row existed to unblock was closed by someone else while the fix was being built.** At HEAD it now carries an authored Hungarian string rather than a placeholder, so the specific blockage is gone. The verb was genuinely broken and the fix stands on its own, but the row's motivating instance is no longer the evidence for it — the gate is.

## Verification

    pytest dev/locales/tests/test_quoted_key_segments_are_addressable.py -n0 -q
    7 passed

Behaviour confirmed directly before the gate was written: a leaf under two quoted ancestors removes while its sibling survives; a fully unquoted leaf still removes; a NEW leaf appends under quoted ancestors; removing an only child prunes its quoted namespace while a populated neighbour is untouched; and both refusals hold — addressing a namespace refuses rather than deleting everything beneath it, and an absent key refuses as a key rather than as a fact about YAML text.

Mutation proof, restoring the pre-fix line scan from a plugin outside the repository:

    LOCMUT_MODE=remove   2 failed, 5 passed   (both quoted-remove cases; controls and refusals green)
    LOCMUT_MODE=append   1 failed, 6 passed   (the quoted-append case; unquoted control green)

**The first append run was a false reading and the instrument was mine.** It reddened the unquoted control as well, which would have suggested the gate could not discriminate. The cause was in the plugin: its replacement opened the catalogue write guard and then delegated to the real setter, which re-entered the same guard and blocked on the lock — the run took sixty seconds against half a second. Reading the text on a plain read and delegating outside the guard produced the clean result above. A mutation that fails for its own reasons looks exactly like a gate that does not work.

## Notes

The larger locale suite reports three failures, none from this change. Two are catalogue-audit findings naming keys this Step never touched — a TUI status screen's deadline keys and the docs legal-page chrome from another lane's commit — where code requests a key the catalogues do not carry. The third is the key-echo ratchet. This change alters only write paths; the audit reads.

**The ratchet reading has moved by two orders of magnitude for reasons outside this row.** It stood at one key-echo when the previous Step closed. It now stands at 176 in the working tree and 182 at HEAD, from keys another lane introduced while this fix was being built. That is the same inflow reported at the end of S243, at a scale that makes the point better than the earlier eleven did: this gate cannot be closed by whoever happens to be working it, because the tail refills faster than a lane drains it.

A `remove` attempted during this Step failed with `PermissionError` on the atomic replace and landed nothing — the contention hazard, observed directly rather than inherited from another lane's report.

The fix landed at HEAD in a sweeper commit **without its test**, which was still untracked at that point. The gate was committed immediately afterwards; both are present at HEAD and green. A behaviour that lands without the gate that proves it is the ordering this campaign explicitly warns against, and it happened here through a sweep rather than through a choice.
