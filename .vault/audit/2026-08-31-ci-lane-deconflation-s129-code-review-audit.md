---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c782738f8eb8861baf83a62928a3fa5fc7109d9caacbda21be387ae757eb75a5'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S129 code review`

## Scope

Independent review of source predecessor `28f4780f9a` and record/checkbox closure `4697d9be7c`, the approved CI-lane/evidence ADRs, exact SQL source/test changes, public imports, MRO ownership, size baseline, and current `HEAD`.

## Findings

### P05 S129 code review | high | ownership proof is asserted without an executable instrument

The S129 execution record says a direct ownership proof exited zero and confirmed that public writes resolve from `_secure_object_writes.py` while `load` remains in `secure_objects.py`, but gives neither the command nor its output. Its Changes pytest entry is also merely `-> pass`, although a literal summary appears later in Notes. This does not meet the accepted execution-evidence ADR's requirement to quote the instrument and result: a reviewer cannot replay the source-owner/MRO claim, nor tell what was actually asserted. Add the exact Python or pytest command that imports the public owner, proves `SecureObjectRepository` is the sole public repository surface, confirms its `SecureObjectWriteOperations` MRO, and quotes the literal output/exit. Replace the bare pytest claim with its full recorded summary as well.

### P05 S129 code review | low | record-only repair resolves the ownership evidence finding

Commit `bdd2e85488afb1256f60b04f67a810331b74abcc` changes only the S129 execution record. It now names the complete executable public-owner/MRO assertion command, each of the five asserted output lines, and `EXIT=0`; it also replaces the SQL suite's bare pass claim with the exact command, `169 passed, 2 warnings`, and `EXIT=0`. No source, plan, size baseline, or S130 surface changed. The prior high finding is resolved.

## Recommendations

- Add a complete executable ownership/MRO proof and literal output to the S129 record, then re-review the evidence-only correction.

No additional P05.S129 corrective work is required.

Source disposition is otherwise sound: `SecureObjectRepository` remains the public repository owner and inherits the private `SecureObjectWriteOperations` mixin; write and revision-lineage implementation carries no incidental public facade. `sql.__init__` keeps public API ownership while records move to their canonical records module. The SQL suite record cites 169 passed, the stale `1617` pin remains at `1191` for P05.S227 to regenerate, and no baseline entry changes.
