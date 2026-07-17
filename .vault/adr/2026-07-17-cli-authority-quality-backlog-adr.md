---
tags:
  - '#adr'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---
# `cli-authority-quality-backlog` adr: `cli-authority-quality-backlog rescope grounding` | (**status:** `accepted`)

## Problem Statement

This feature is a rescoped slice carved out of the cli-authority-verb-conformance campaign. That campaign was split into six smaller, individually-closeable successor plans, each carrying its own feature tag so it can be tracked and closed independently. The vaultspec lifecycle (research -> ADR -> plan -> exec) requires an ADR under the plan's own feature tag before any execution record can be scaffolded: `vault add exec` refuses a feature that has a plan but no same-tag ADR, and `--related` pointing at another feature's ADR does not satisfy the check. Without a same-feature ADR this plan cannot record execution records and therefore cannot close honestly under the plan-closure-requires-exec-records discipline. This ADR exists to supply that grounding.

## Considerations

The governing architectural decision for every successor remains the shared 2026-07-15 cli-authority-verb-conformance ADR; this record does not re-decide the architecture. The constraint is purely the lifecycle-tooling requirement that execution records be grounded in a same-feature decision. The six successors must remain independently closeable, so any resolution must preserve their distinct feature tags rather than re-merging them.

This successor's scope: Absorb the residue of the CLI-authority campaign that is real work carrying no operator-safety defect and no false-green risk: registry as-of honesty, the hashing recurrence gate, secure-object namespace adoption, the filed-capture finalizer, the typed LLM review workflow, and the enrolled MCP composition, CLI-MCP parity, profile-create question-count, acceptance-wall isolation, and coverage-gap follow-ups.

## Considered options

- Share the single cli-authority-verb-conformance feature tag across all six successors so they reuse the existing ADR. Rejected: it re-merges the six plans into one feature in status reporting and defeats the independent closeability the rescope was performed to obtain.
- Point `vault add exec --related` at the shared ADR. Rejected: the tool checks for an ADR under the plan's own feature tag; `--related` does not satisfy it (verified against the live CLI).
- Author one thin grounding ADR per successor feature, referencing the shared governing decision. Chosen: it satisfies the lifecycle without duplicating the architectural decision and preserves independent closeability.

## Constraints

None beyond the lifecycle-tooling requirement above. This record depends on the shared 2026-07-15 cli-authority-verb-conformance ADR remaining the authoritative decision; it adds no new technical dependency.

## Implementation

Scaffold this ADR under the successor's own feature tag with `vault add adr`, relate it to the shared governing ADR and to this successor's plan, and mark it accepted. Execution records for this plan then scaffold normally with `vault add exec --feature cli-authority-quality-backlog --step S##`. No source code changes accompany this ADR; it is a vault-lifecycle grounding record only.

## Rationale

The shared 2026-07-15 cli-authority-verb-conformance ADR is the single source of the architectural decision. This ADR records the rescope carve for this successor and gives its plan the same-feature decision record the lifecycle requires, so its execution and closure are honest rather than blocked. It is a grounding record, not a competing decision.

## Consequences

This successor plan can now record execution records and close honestly against real evidence. The six successors stay independently trackable and closeable. The shared ADR remains the one place the architectural decision lives. The cost is six thin grounding records whose only content is the rescope provenance and the successor's scope boundary.
